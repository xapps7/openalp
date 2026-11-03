from __future__ import annotations

"""Transport interface and receipt shape.

Every transport, in-process or remote, returns the same receipt so that
callers never branch on transport identity.
"""

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from . import status as st
from .envelope import Envelope


@dataclass(frozen=True)
class ExecutionResult:
    output: bytes
    top: int | None
    steps: int

    def to_dict(self) -> dict[str, object]:
        # output is bytes and carries no encoding, so it is hex here, never text.
        return {"output_hex": self.output.hex(), "top": self.top, "steps": self.steps}


@dataclass(frozen=True)
class TransportError(Exception):
    """Classified failure raised by an executor.

    The class field decides retry behavior; see
    spec/transport-semantics-v0.2.md.
    """

    error_class: str
    reason: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.error_class}: {self.reason}"

    def to_dict(self) -> dict[str, object]:
        return {"class": self.error_class, "reason": self.reason}


@dataclass(frozen=True)
class Receipt:
    envelope_id: str
    idempotency_key: str
    stream_id: str
    sequence: int
    status: str
    attempts: int
    elapsed_ms: int
    backoff_schedule_ms: tuple[int, ...] = ()
    result: ExecutionResult | None = None
    error: TransportError | None = None
    pending: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return self.status == st.SUCCEEDED

    @property
    def terminal(self) -> bool:
        return st.is_terminal(self.status)

    def to_dict(self) -> dict[str, object]:
        return {
            "envelope_id": self.envelope_id,
            "idempotency_key": self.idempotency_key,
            "stream_id": self.stream_id,
            "sequence": self.sequence,
            "status": self.status,
            "attempts": self.attempts,
            "elapsed_ms": self.elapsed_ms,
            "backoff_schedule_ms": list(self.backoff_schedule_ms),
            "result": self.result.to_dict() if self.result else None,
            "error": self.error.to_dict() if self.error else None,
            "pending": list(self.pending),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)


class Transport(ABC):
    """Abstract transport.

    Implementations must satisfy the conformance rules in
    spec/transport-semantics-v0.2.md.
    """

    name: str = "abstract"
    clock_policy: str = "step"
    quantum_ms: int = 1
    deterministic_receipts: bool = True

    def describe(self) -> dict[str, object]:
        """Machine-readable conformance statement.

        Required by spec/transport-semantics-v0.2.md so a caller can tell
        whether receipts from this transport are reproducible before it
        depends on them being so.
        """
        return {
            "name": self.name,
            "clock_policy": self.clock_policy,
            "quantum_ms": self.quantum_ms,
            "deterministic_receipts": self.deterministic_receipts,
        }

    @abstractmethod
    def send(self, envelope: Envelope) -> Receipt:
        """Deliver one envelope and return its terminal receipt."""

    @abstractmethod
    def receipt_for(self, idempotency_key: str) -> Receipt | None:
        """Return a retained receipt, or None if not retained."""
