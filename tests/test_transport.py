from __future__ import annotations

import base64
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from alp.cli import main
from alp.profile import ExecutionProfile
from alp.transport import status as st
from alp.transport import (
    EnvelopeError,
    ExecutionResult,
    LocalTransport,
    TransportError,
    backoff_ms,
    build_envelope,
    content_hash,
    derive_envelope_id,
    parse_envelope,
    quantize_ms,
    validate_envelope,
)

PAYLOAD = b"deterministic-payload"


def ok_executor(result: ExecutionResult | None = None):
    """Executor that always succeeds."""
    value = result or ExecutionResult(output=b"", top=42, steps=3)

    def _execute(raw: bytes, envelope: object) -> ExecutionResult:
        return value

    return _execute


def counting_executor(fail_times: int, error: TransportError):
    """Fails `fail_times` times, then succeeds. Records call count."""
    calls = {"n": 0}

    def _execute(raw: bytes, envelope: object) -> ExecutionResult:
        calls["n"] += 1
        if calls["n"] <= fail_times:
            raise error
        return ExecutionResult(output=b"", top=7, steps=1)

    return _execute, calls


def envelope(sequence: int = 0, stream: str = "s", **kwargs):
    return build_envelope(PAYLOAD, stream, sequence, kind="module", **kwargs)


class EnvelopeTests(unittest.TestCase):
    def test_envelope_id_is_content_derived_and_stable(self) -> None:
        a = envelope()
        b = envelope()
        self.assertEqual(a.envelope_id, b.envelope_id)
        self.assertEqual(
            a.envelope_id,
            derive_envelope_id("s", 0, content_hash(PAYLOAD)),
        )

    def test_envelope_id_changes_with_sequence_and_stream(self) -> None:
        self.assertNotEqual(envelope(0).envelope_id, envelope(1).envelope_id)
        self.assertNotEqual(envelope(0, "a").envelope_id, envelope(0, "b").envelope_id)

    def test_idempotency_key_defaults_to_envelope_id(self) -> None:
        env = envelope()
        self.assertEqual(env.idempotency_key, env.envelope_id)

    def test_explicit_idempotency_key_is_preserved(self) -> None:
        env = envelope(idempotency_key="job-1")
        self.assertEqual(env.idempotency_key, "job-1")
        self.assertNotEqual(env.idempotency_key, env.envelope_id)

    def test_round_trip_through_json(self) -> None:
        env = envelope(max_attempts=3, deadline_ms=100, correlation_id="c1")
        restored = parse_envelope(json.loads(env.to_json()))
        self.assertEqual(restored.envelope_id, env.envelope_id)
        self.assertEqual(restored.max_attempts, 3)
        self.assertEqual(restored.deadline_ms, 100)
        self.assertEqual(restored.trace["correlation_id"], "c1")

    def test_tampered_payload_is_rejected(self) -> None:
        payload = json.loads(envelope().to_json())
        payload["payload"]["bytes_b64"] = base64.b64encode(b"tampered").decode("ascii")
        with self.assertRaises(EnvelopeError) as ctx:
            parse_envelope(payload)
        self.assertIn("content_hash mismatch", str(ctx.exception))

    def test_forged_envelope_id_is_rejected(self) -> None:
        payload = json.loads(envelope().to_json())
        payload["envelope_id"] = "0" * 32
        with self.assertRaises(EnvelopeError) as ctx:
            parse_envelope(payload)
        self.assertIn("derived identity", str(ctx.exception))

    def test_unsupported_protocol_version_is_rejected(self) -> None:
        payload = json.loads(envelope().to_json())
        payload["protocol_version"] = "9.9"
        with self.assertRaises(EnvelopeError):
            parse_envelope(payload)

    def test_deprecated_protocol_version_is_accepted(self) -> None:
        env = envelope(protocol_version="0.1")
        result = validate_envelope(env)
        self.assertTrue(result["deprecated"])
        self.assertEqual(result["phase"], "deprecated")

    def test_max_attempts_bounds_are_enforced(self) -> None:
        with self.assertRaises(EnvelopeError):
            envelope(max_attempts=0)
        with self.assertRaises(EnvelopeError):
            envelope(max_attempts=99)

    def test_empty_payload_is_rejected(self) -> None:
        with self.assertRaises(EnvelopeError):
            build_envelope(b"", "s", 0, kind="module")


class DeliveryTests(unittest.TestCase):
    def test_successful_delivery_returns_result(self) -> None:
        transport = LocalTransport(executor=ok_executor())
        receipt = transport.send(envelope())
        self.assertEqual(receipt.status, st.SUCCEEDED)
        self.assertTrue(receipt.ok)
        self.assertTrue(receipt.terminal)
        self.assertEqual(receipt.attempts, 1)
        self.assertEqual(receipt.result.top, 42)
        self.assertIsNone(receipt.error)

    def test_permanent_failure_is_not_retried(self) -> None:
        execute, calls = counting_executor(5, TransportError(st.PERMANENT, "bad module"))
        transport = LocalTransport(executor=execute)
        receipt = transport.send(envelope(max_attempts=4))
        self.assertEqual(receipt.status, st.FAILED)
        self.assertEqual(receipt.attempts, 1)
        self.assertEqual(calls["n"], 1)
        self.assertEqual(receipt.error.error_class, st.PERMANENT)

    def test_protocol_failure_is_not_retried(self) -> None:
        execute, calls = counting_executor(5, TransportError(st.PROTOCOL, "incompatible"))
        transport = LocalTransport(executor=execute)
        receipt = transport.send(envelope(max_attempts=4))
        self.assertEqual(receipt.status, st.FAILED)
        self.assertEqual(calls["n"], 1)

    def test_transient_failure_is_retried_then_succeeds(self) -> None:
        execute, calls = counting_executor(2, TransportError(st.TRANSIENT, "blip"))
        transport = LocalTransport(executor=execute)
        receipt = transport.send(envelope(max_attempts=4))
        self.assertEqual(receipt.status, st.SUCCEEDED)
        self.assertEqual(receipt.attempts, 3)
        self.assertEqual(calls["n"], 3)
        self.assertEqual(list(receipt.backoff_schedule_ms), [100, 200])

    def test_attempts_are_bounded(self) -> None:
        execute, calls = counting_executor(99, TransportError(st.TRANSIENT, "blip"))
        transport = LocalTransport(executor=execute)
        receipt = transport.send(envelope(max_attempts=3))
        self.assertEqual(receipt.status, st.FAILED)
        self.assertEqual(receipt.attempts, 3)
        self.assertEqual(calls["n"], 3)
        self.assertTrue(receipt.error.reason.startswith("attempts_exhausted"))
        self.assertIn("blip", receipt.error.reason)

    def test_clock_policy_is_declared(self) -> None:
        transport = LocalTransport(executor=ok_executor(), clock_step_ms=5)
        described = transport.describe()
        self.assertEqual(described["clock_policy"], "step")
        self.assertEqual(described["quantum_ms"], 5)
        self.assertTrue(described["deterministic_receipts"])

    def test_identical_sends_produce_identical_receipts(self) -> None:
        # The determinism claim, asserted rather than assumed.
        a = LocalTransport(executor=ok_executor()).send(envelope()).to_json()
        b = LocalTransport(executor=ok_executor()).send(envelope()).to_json()
        self.assertEqual(a, b)

    def test_quantize_rounds_up_and_floors_at_one_quantum(self) -> None:
        self.assertEqual(quantize_ms(0, 10), 10)
        self.assertEqual(quantize_ms(1, 10), 10)
        self.assertEqual(quantize_ms(10, 10), 10)
        self.assertEqual(quantize_ms(11, 10), 20)
        self.assertEqual(quantize_ms(25, 10), 30)
        with self.assertRaises(ValueError):
            quantize_ms(5, 0)
        with self.assertRaises(ValueError):
            quantize_ms(-1, 10)

    def test_backoff_schedule_is_deterministic_and_capped(self) -> None:
        self.assertEqual([backoff_ms(n) for n in range(1, 5)], [100, 200, 400, 800])
        self.assertEqual(backoff_ms(20), 8_000)

    def test_deadline_expires_before_attempts_exhaust(self) -> None:
        execute, calls = counting_executor(99, TransportError(st.TRANSIENT, "blip"))
        transport = LocalTransport(executor=execute, clock_step_ms=10)
        receipt = transport.send(envelope(max_attempts=8, deadline_ms=25))
        self.assertEqual(receipt.status, st.EXPIRED)
        self.assertEqual(calls["n"], 3)
        self.assertIn("deadline_exceeded", receipt.error.reason)

    def test_zero_deadline_expires_without_executing(self) -> None:
        execute, calls = counting_executor(0, TransportError(st.TRANSIENT, "blip"))
        transport = LocalTransport(executor=execute)
        receipt = transport.send(envelope(deadline_ms=0))
        self.assertEqual(receipt.status, st.EXPIRED)
        self.assertEqual(calls["n"], 0)


class IdempotencyTests(unittest.TestCase):
    def test_replay_does_not_execute_twice(self) -> None:
        execute, calls = counting_executor(0, TransportError(st.TRANSIENT, "unused"))
        transport = LocalTransport(executor=execute)
        first = transport.send(envelope())
        second = transport.send(envelope())
        self.assertEqual(first.status, st.SUCCEEDED)
        self.assertEqual(second.status, st.DUPLICATE)
        self.assertEqual(calls["n"], 1)
        self.assertEqual(second.result, first.result)

    def test_shared_idempotency_key_deduplicates_distinct_envelopes(self) -> None:
        execute, calls = counting_executor(0, TransportError(st.TRANSIENT, "unused"))
        transport = LocalTransport(executor=execute)
        transport.send(envelope(0, idempotency_key="job-1"))
        second = transport.send(envelope(1, idempotency_key="job-1"))
        self.assertEqual(second.status, st.DUPLICATE)
        self.assertEqual(calls["n"], 1)

    def test_failed_delivery_is_also_deduplicated(self) -> None:
        execute, calls = counting_executor(99, TransportError(st.PERMANENT, "bad"))
        transport = LocalTransport(executor=execute)
        transport.send(envelope())
        second = transport.send(envelope())
        self.assertEqual(second.status, st.DUPLICATE)
        self.assertEqual(second.error.error_class, st.PERMANENT)
        self.assertEqual(calls["n"], 1)

    def test_receipt_lookup_by_key(self) -> None:
        transport = LocalTransport(executor=ok_executor())
        env = envelope()
        transport.send(env)
        self.assertIsNotNone(transport.receipt_for(env.idempotency_key))
        self.assertIsNone(transport.receipt_for("unknown"))

    def test_dropping_receipts_degrades_to_at_least_once(self) -> None:
        # Without receipt retention the idempotency barrier is gone, so two
        # envelopes sharing a key but occupying different sequences both run.
        execute, calls = counting_executor(0, TransportError(st.TRANSIENT, "unused"))
        transport = LocalTransport(executor=execute, retain_receipts=False)
        first = transport.send(envelope(0, idempotency_key="job-1"))
        second = transport.send(envelope(1, idempotency_key="job-1"))
        self.assertEqual(first.status, st.SUCCEEDED)
        self.assertEqual(second.status, st.SUCCEEDED)
        self.assertEqual(calls["n"], 2)

    def test_ordering_still_blocks_replay_when_receipts_are_dropped(self) -> None:
        # Stream ordering is a second dedup barrier: replaying a delivered
        # sequence is stale even with no receipt to match against.
        execute, calls = counting_executor(0, TransportError(st.TRANSIENT, "unused"))
        transport = LocalTransport(executor=execute, retain_receipts=False)
        transport.send(envelope(0))
        second = transport.send(envelope(0))
        self.assertEqual(second.status, st.REJECTED)
        self.assertEqual(second.error.reason, "stale_sequence")
        self.assertEqual(calls["n"], 1)


class OrderingTests(unittest.TestCase):
    def test_in_order_delivery(self) -> None:
        transport = LocalTransport(executor=ok_executor())
        for seq in range(3):
            self.assertEqual(transport.send(envelope(seq)).status, st.SUCCEEDED)

    def test_out_of_order_envelope_is_held_then_flushed(self) -> None:
        order: list[int] = []

        def execute(raw: bytes, env) -> ExecutionResult:
            order.append(env.sequence)
            return ExecutionResult(output=b"", top=0, steps=1)

        transport = LocalTransport(executor=execute)
        self.assertEqual(transport.send(envelope(0)).status, st.SUCCEEDED)

        held = transport.send(envelope(2))
        self.assertEqual(held.status, st.ACCEPTED)
        self.assertFalse(held.terminal)
        self.assertEqual(order, [0])

        gap = transport.send(envelope(1))
        self.assertEqual(gap.status, st.SUCCEEDED)
        self.assertEqual(order, [0, 1, 2])
        self.assertEqual(len(gap.pending), 1)
        self.assertEqual(gap.pending[0], envelope(2).envelope_id)

    def test_flush_delivers_multiple_pending_in_order(self) -> None:
        order: list[int] = []

        def execute(raw: bytes, env) -> ExecutionResult:
            order.append(env.sequence)
            return ExecutionResult(output=b"", top=0, steps=1)

        transport = LocalTransport(executor=execute)
        transport.send(envelope(0))
        transport.send(envelope(3))
        transport.send(envelope(2))
        self.assertEqual(order, [0])
        transport.send(envelope(1))
        self.assertEqual(order, [0, 1, 2, 3])

    def test_stale_sequence_is_rejected(self) -> None:
        transport = LocalTransport(executor=ok_executor())
        transport.send(envelope(0))
        transport.send(envelope(1))
        stale = transport.send(envelope(0, idempotency_key="fresh-key"))
        self.assertEqual(stale.status, st.REJECTED)
        self.assertEqual(stale.error.reason, "stale_sequence")

    def test_streams_are_independent(self) -> None:
        transport = LocalTransport(executor=ok_executor())
        self.assertEqual(transport.send(envelope(5, "a")).status, st.SUCCEEDED)
        self.assertEqual(transport.send(envelope(9, "b")).status, st.SUCCEEDED)

    def test_first_sequence_establishes_baseline(self) -> None:
        transport = LocalTransport(executor=ok_executor())
        self.assertEqual(transport.send(envelope(100)).status, st.SUCCEEDED)
        self.assertEqual(transport.send(envelope(101)).status, st.SUCCEEDED)


class TransportCliTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, Path]:
        from alp.format import Instruction, Module, VERSION, encode_module

        module = Module(
            version=VERSION,
            flags=0,
            entry=0,
            instructions=(
                Instruction(0x01, 5, 0, 0),
                Instruction(0x01, 6, 0, 0),
                Instruction(0x02, 0, 0, 0),
                Instruction(0x08, 0, 0, 0),
            ),
        )
        m = root / "m.alp"
        h = root / "hello.json"
        k = root / "k.key"
        b = root / "bundle.alpp.json"
        m.write_bytes(encode_module(module))
        h.write_text(
            json.dumps(
                {
                    "protocol": "ALP",
                    "version": "0.2",
                    "features": ["vm-stack-v1"],
                    "targets": ["ref-vm"],
                }
            )
        )
        k.write_text("secret-key")

        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["checksum", "create", str(m)]), 0)
            self.assertEqual(main(["sign", "create", str(m), "--key", str(k)]), 0)
            self.assertEqual(
                main(
                    [
                    "bundle",
                    "create",
                    "--module",
                    str(m),
                    "--hello",
                    str(h),
                    "--checksum",
                    str(m) + ".sha256.json",
                    "--signature",
                    str(m) + ".sig.json",
                    "--key",
                    str(k),
                    "--out",
                    str(b),
                    ]
                ),
                0,
            )
        return b, k

    def test_cli_envelope_create_validate_send(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bundle_path, key_path = self._fixture(root)
            env_path = root / "envelope.json"

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = main(
                    [
                        "transport",
                        "envelope",
                        "create",
                        "--payload",
                        str(bundle_path),
                        "--stream",
                        "cli",
                        "--sequence",
                        "0",
                        "--out",
                        str(env_path),
                    ]
                )
            self.assertEqual(code, 0)
            self.assertIn("envelope_id", buf.getvalue())

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = main(["transport", "envelope", "validate", str(env_path)])
            self.assertEqual(code, 0)
            self.assertTrue(json.loads(buf.getvalue())["valid"])

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = main(
                    ["transport", "send", "--envelope", str(env_path), "--key", str(key_path)]
                )
            self.assertEqual(code, 0)
            receipt = json.loads(buf.getvalue())
            self.assertEqual(receipt["status"], st.SUCCEEDED)
            self.assertEqual(receipt["result"]["top"], 11)

    def test_cli_send_rejects_tampered_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bundle_path, key_path = self._fixture(root)
            env_path = root / "envelope.json"

            with contextlib.redirect_stdout(io.StringIO()):
                main(
                    [
                        "transport",
                        "envelope",
                        "create",
                        "--payload",
                        str(bundle_path),
                        "--stream",
                        "cli",
                        "--sequence",
                        "0",
                        "--out",
                        str(env_path),
                    ]
                )

            payload = json.loads(env_path.read_text())
            payload["payload"]["bytes_b64"] = base64.b64encode(b"not-a-bundle").decode("ascii")
            env_path.write_text(json.dumps(payload))

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = main(
                    ["transport", "send", "--envelope", str(env_path), "--key", str(key_path)]
                )
            self.assertEqual(code, 1)
            self.assertIn("content_hash mismatch", buf.getvalue())


class BundleExecutorTests(unittest.TestCase):
    def test_corrupt_bundle_fails_permanently(self) -> None:
        from alp.transport import make_bundle_executor

        with tempfile.TemporaryDirectory() as td:
            key = Path(td) / "k.key"
            key.write_text("secret-key")
            transport = LocalTransport(executor=make_bundle_executor(key, ExecutionProfile.default()))
            env = build_envelope(b'{"not":"a bundle"}', "s", 0, kind="bundle", max_attempts=3)
            receipt = transport.send(env)
            self.assertEqual(receipt.status, st.FAILED)
            self.assertEqual(receipt.error.error_class, st.PERMANENT)
            self.assertEqual(receipt.attempts, 1)


if __name__ == "__main__":
    unittest.main()
