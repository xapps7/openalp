from __future__ import annotations

"""LocalTransport: the in-process reference transport.

Deterministic and single-threaded by construction. It is the conformance
baseline for spec/transport-semantics-v0.2.md: any future transport
(queue, socket, HTTP) must produce the same receipts for the same
envelopes.

Time is logical, not wall clock. The clock advances by a fixed increment
per attempt, so deadline and retry behavior are reproducible in tests and
across machines.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable

from ..bundle import BundleError, run_bundle
from ..format import ALPFormatError, parse_module
from ..protocol import ProtocolError
from ..profile import ExecutionProfile
from ..vm import VMError, run_module
from . import status as st
from .base import ExecutionResult, Receipt, Transport, TransportError
from .envelope import Envelope, EnvelopeError, validate_envelope

Executor = Callable[[bytes, Envelope], ExecutionResult]

DEFAULT_CLOCK_STEP_MS = 1
DEFAULT_BASE_BACKOFF_MS = 100
DEFAULT_MAX_BACKOFF_MS = 8_000


def backoff_ms(attempt: int, base: int = DEFAULT_BASE_BACKOFF_MS, cap: int = DEFAULT_MAX_BACKOFF_MS) -> int:
    """Deterministic exponential backoff: min(base * 2^(n-1), cap)."""
    if attempt < 1:
        raise ValueError("attempt must be >= 1")
    return min(base * (2 ** (attempt - 1)), cap)


def quantize_ms(observed_ms: int, quantum_ms: int) -> int:
    """Map observed wall-clock elapsed onto the logical clock.

    Rounds up, and never returns less than one quantum, so a deadline is
    never overrun by rounding and an arbitrarily fast transport cannot
    retry unboundedly inside a finite deadline. See the Clock Policy
    section of spec/transport-semantics-v0.2.md.

    This function is pure. The reference transport does not call it; it
    exists so a network transport has one canonical implementation to use
    rather than inventing its own rounding.
    """
    if quantum_ms < 1:
        raise ValueError("quantum_ms must be >= 1")
    if observed_ms < 0:
        raise ValueError("observed_ms must be >= 0")
    quanta = -(-observed_ms // quantum_ms)  # ceiling division
    return max(1, quanta) * quantum_ms


@dataclass
class _StreamState:
    last_delivered: int | None = None
    pending: dict[int, Envelope] = field(default_factory=dict)


def _classify(exc: Exception) -> TransportError:
    """Map runtime exceptions onto transport error classes."""
    if isinstance(exc, TransportError):
        return exc
    if isinstance(exc, ProtocolError):
        return TransportError(st.PROTOCOL, str(exc))
    if isinstance(exc, (BundleError, ALPFormatError, VMError)):
        return TransportError(st.PERMANENT, str(exc))
    if isinstance(exc, OSError):
        return TransportError(st.TRANSIENT, str(exc))
    return TransportError(st.PERMANENT, str(exc))


def make_bundle_executor(key_path: Path, profile: ExecutionProfile) -> Executor:
    """Executor that runs a bundle payload through the verified bundle path."""

    def _execute(raw: bytes, envelope: Envelope) -> ExecutionResult:
        if envelope.payload.kind == "module":
            module = parse_module(raw)
            vm = run_module(module, profile)
            return ExecutionResult(output=vm.output, top=vm.top, steps=vm.steps)

        with TemporaryDirectory() as td:
            suffix = ".alppb" if raw.startswith(b"ALPPB1\x00") else ".alpp.json"
            bundle_path = Path(td) / f"envelope{suffix}"
            bundle_path.write_bytes(raw)
            result = run_bundle(bundle_path, key_path, profile)
        return ExecutionResult(output=result.output, top=result.top, steps=result.steps)

    return _execute


class LocalTransport(Transport):
    name = "local"
    clock_policy = "step"
    deterministic_receipts = True

    def __init__(
        self,
        executor: Executor,
        clock_step_ms: int = DEFAULT_CLOCK_STEP_MS,
        base_backoff_ms: int = DEFAULT_BASE_BACKOFF_MS,
        max_backoff_ms: int = DEFAULT_MAX_BACKOFF_MS,
        retain_receipts: bool = True,
    ) -> None:
        self._executor = executor
        self._clock_step_ms = clock_step_ms
        self.quantum_ms = clock_step_ms
        self._base_backoff_ms = base_backoff_ms
        self._max_backoff_ms = max_backoff_ms
        self._retain_receipts = retain_receipts
        self._receipts: dict[str, Receipt] = {}
        self._streams: dict[str, _StreamState] = {}

    # -- Transport interface -------------------------------------------------

    def receipt_for(self, idempotency_key: str) -> Receipt | None:
        return self._receipts.get(idempotency_key)

    def send(self, envelope: Envelope) -> Receipt:
        # Step 1-3: structure, governance, payload integrity.
        try:
            validate_envelope(envelope)
        except EnvelopeError as exc:
            return self._reject(envelope, st.PROTOCOL, str(exc))

        # Step 4: idempotency.
        prior = self._receipts.get(envelope.idempotency_key)
        if prior is not None:
            return Receipt(
                envelope_id=prior.envelope_id,
                idempotency_key=prior.idempotency_key,
                stream_id=prior.stream_id,
                sequence=prior.sequence,
                status=st.DUPLICATE,
                attempts=prior.attempts,
                elapsed_ms=prior.elapsed_ms,
                backoff_schedule_ms=prior.backoff_schedule_ms,
                result=prior.result,
                error=prior.error,
            )

        # Step 5: ordering within the stream.
        stream = self._streams.setdefault(envelope.stream_id, _StreamState())

        if stream.last_delivered is not None:
            if envelope.sequence <= stream.last_delivered:
                return self._reject(envelope, st.PERMANENT, "stale_sequence")
            if envelope.sequence > stream.last_delivered + 1:
                stream.pending[envelope.sequence] = envelope
                return Receipt(
                    envelope_id=envelope.envelope_id,
                    idempotency_key=envelope.idempotency_key,
                    stream_id=envelope.stream_id,
                    sequence=envelope.sequence,
                    status=st.ACCEPTED,
                    attempts=0,
                    elapsed_ms=0,
                )

        receipt = self._deliver(envelope)
        stream.last_delivered = envelope.sequence
        stream.pending.pop(envelope.sequence, None)

        flushed = self._flush(stream)
        if flushed:
            receipt = Receipt(
                envelope_id=receipt.envelope_id,
                idempotency_key=receipt.idempotency_key,
                stream_id=receipt.stream_id,
                sequence=receipt.sequence,
                status=receipt.status,
                attempts=receipt.attempts,
                elapsed_ms=receipt.elapsed_ms,
                backoff_schedule_ms=receipt.backoff_schedule_ms,
                result=receipt.result,
                error=receipt.error,
                pending=tuple(flushed),
            )
        return receipt

    # -- internals -----------------------------------------------------------

    def _flush(self, stream: _StreamState) -> list[str]:
        """Deliver buffered envelopes whose turn has arrived, in order."""
        delivered: list[str] = []
        while stream.last_delivered is not None:
            nxt = stream.pending.pop(stream.last_delivered + 1, None)
            if nxt is None:
                break
            self._deliver(nxt)
            stream.last_delivered = nxt.sequence
            delivered.append(nxt.envelope_id)
        return delivered

    def _reject(self, envelope: Envelope, error_class: str, reason: str) -> Receipt:
        return Receipt(
            envelope_id=envelope.envelope_id,
            idempotency_key=envelope.idempotency_key,
            stream_id=envelope.stream_id,
            sequence=envelope.sequence,
            status=st.REJECTED,
            attempts=0,
            elapsed_ms=0,
            error=TransportError(error_class, reason),
        )

    def _record(self, receipt: Receipt) -> Receipt:
        if self._retain_receipts and receipt.terminal and receipt.status != st.DUPLICATE:
            self._receipts[receipt.idempotency_key] = receipt
        return receipt

    def _deliver(self, envelope: Envelope) -> Receipt:
        """Steps 6-7: deadline enforcement and bounded execution."""
        raw = envelope.payload.raw()
        elapsed = 0
        attempts = 0
        schedule: list[int] = []
        last_error: TransportError | None = None

        def finish(status: str, result: ExecutionResult | None, error: TransportError | None) -> Receipt:
            return self._record(
                Receipt(
                    envelope_id=envelope.envelope_id,
                    idempotency_key=envelope.idempotency_key,
                    stream_id=envelope.stream_id,
                    sequence=envelope.sequence,
                    status=status,
                    attempts=attempts,
                    elapsed_ms=elapsed,
                    backoff_schedule_ms=tuple(schedule),
                    result=result,
                    error=error,
                )
            )

        while True:
            if envelope.deadline_ms is not None and elapsed >= envelope.deadline_ms:
                reason = "deadline_exceeded"
                if last_error is not None:
                    reason = f"deadline_exceeded: {last_error.reason}"
                return finish(st.EXPIRED, None, TransportError(st.TRANSIENT, reason))

            attempts += 1
            try:
                result = self._executor(raw, envelope)
            except Exception as exc:  # classified below
                last_error = _classify(exc)
                elapsed += self._clock_step_ms

                if not st.is_retryable(last_error.error_class):
                    return finish(st.FAILED, None, last_error)
                if attempts >= envelope.max_attempts:
                    return finish(
                        st.FAILED,
                        None,
                        TransportError(st.TRANSIENT, f"attempts_exhausted: {last_error.reason}"),
                    )
                schedule.append(backoff_ms(attempts, self._base_backoff_ms, self._max_backoff_ms))
                continue

            elapsed += self._clock_step_ms
            return finish(st.SUCCEEDED, result, None)


def send_envelope_file(
    envelope_path: Path,
    key_path: Path,
    profile: ExecutionProfile | None = None,
    transport: LocalTransport | None = None,
) -> Receipt:
    """Convenience path used by the CLI: parse an envelope file and send it."""
    from .envelope import parse_envelope

    envelope = parse_envelope(json.loads(envelope_path.read_text()))
    active = transport or LocalTransport(
        executor=make_bundle_executor(key_path, profile or ExecutionProfile.default())
    )
    return active.send(envelope)
