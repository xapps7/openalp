from __future__ import annotations

"""Canonical encoding: total, injective, and rejecting rather than normalizing.

Finding F7: output was accumulated as code points, so a byte above 127
serialised as a multi-byte character. Worse, the test suite asserted that
behaviour, which made the wrong rule normative. These tests hold the
corrected rule and the serialization that goes with it.
"""

import json
import unittest

from alp.canonical import (
    CanonicalError,
    canonical_json,
    canonical_preimage,
    canonical_result,
    require_canonical_module,
)
from alp.format import HEADER_SIZE, Instruction, Module, VERSION, encode_module
from alp.profile import ExecutionProfile
from alp.vm import TRAP_CODES, VMResult, VMTrap, run_module

PUSH, ADD, DIV, JMP, HALT, PRINT, NOP = 0x01, 0x02, 0x05, 0x06, 0x08, 0x0B, 0x00
PROFILE = ExecutionProfile(step_budget=1_000)


def mod(instrs):
    return Module(version=VERSION, flags=0, entry=0, instructions=tuple(instrs))


class CanonicalJsonTests(unittest.TestCase):
    def test_keys_are_sorted_and_whitespace_is_absent(self) -> None:
        text = canonical_json({"b": 1, "a": 2})
        self.assertEqual(text, '{"a":2,"b":1}')

    def test_is_stable_across_calls_and_insertion_order(self) -> None:
        self.assertEqual(canonical_json({"a": 1, "b": 2}), canonical_json({"b": 2, "a": 1}))

    def test_round_trips(self) -> None:
        payload = {"a": [1, 2, 3], "b": {"c": True}, "d": None}
        self.assertEqual(json.loads(canonical_json(payload)), payload)


class CanonicalModuleTests(unittest.TestCase):
    def _raw(self):
        return encode_module(mod([Instruction(PUSH, 1, 0, 0), Instruction(HALT, 0, 0, 0)]))

    def test_accepts_a_canonically_encoded_module(self) -> None:
        module = require_canonical_module(self._raw())
        self.assertEqual(len(module.instructions), 2)

    def test_rejects_trailing_bytes_rather_than_ignoring_them(self) -> None:
        with self.assertRaises(Exception):
            require_canonical_module(self._raw() + b"\x00")

    def test_rejects_nonzero_flags(self) -> None:
        raw = bytearray(self._raw())
        raw[5] = 1
        with self.assertRaises(Exception):
            require_canonical_module(bytes(raw))

    def test_rejects_nonzero_reserved(self) -> None:
        raw = bytearray(self._raw())
        raw[6] = 1
        with self.assertRaises(Exception):
            require_canonical_module(bytes(raw))

    def test_header_size_is_what_the_format_says(self) -> None:
        self.assertEqual(len(self._raw()), HEADER_SIZE + 2 * 4)


class CanonicalResultTests(unittest.TestCase):
    def test_halted_result(self) -> None:
        result = canonical_result(run_module(mod([Instruction(PUSH, 9, 0, 0), Instruction(HALT, 0, 0, 0)]), PROFILE))
        self.assertEqual(result.outcome, "halted")
        self.assertEqual(result.stack, (9,))
        self.assertIsNone(result.trap_code)
        self.assertNotIn("trap_code", result.to_dict())

    def test_output_is_hex_never_text(self) -> None:
        # The byte 200 must encode as "c8", not as a character.
        result = canonical_result(
            run_module(mod([Instruction(PUSH, 200, 0, 0), Instruction(PRINT, 0, 0, 0), Instruction(HALT, 0, 0, 0)]), PROFILE)
        )
        self.assertEqual(result.to_dict()["output_hex"], "c8")
        self.assertNotIn("output", result.to_dict())
        self.assertEqual(result.canonical_json().count("c8"), 1)

    def test_output_hex_is_lowercase_and_round_trips(self) -> None:
        payload = bytes(range(250, 256))
        encoded = canonical_result(
            VMResult(halted=True, steps=1, stack=[], output=payload, profile=PROFILE)
        ).to_dict()["output_hex"]
        self.assertEqual(encoded, encoded.lower())
        self.assertEqual(bytes.fromhex(encoded), payload)

    def test_a_trap_has_a_canonical_result(self) -> None:
        # F5/F6: a trap is an outcome, not the absence of one.
        with self.assertRaises(VMTrap) as ctx:
            run_module(mod([Instruction(ADD, 0, 0, 0), Instruction(HALT, 0, 0, 0)]), PROFILE)
        result = canonical_result(ctx.exception)
        self.assertEqual(result.outcome, "trap")
        self.assertEqual(result.trap_code, "trap.stack_underflow")
        self.assertIn("trap_code", result.to_dict())

    def test_a_trap_keeps_the_output_it_produced_first(self) -> None:
        prog = [Instruction(PUSH, 65, 0, 0), Instruction(PRINT, 0, 0, 0), Instruction(JMP, 0, 0, 0)]
        with self.assertRaises(VMTrap) as ctx:
            run_module(mod(prog), ExecutionProfile(step_budget=9))
        result = canonical_result(ctx.exception)
        self.assertEqual(result.trap_code, "trap.step_budget_exceeded")
        self.assertEqual(bytes.fromhex(result.to_dict()["output_hex"]), b"AAA")

    def test_every_trap_code_is_encodable(self) -> None:
        # Totality: no reachable outcome lacks an encoding.
        for code in TRAP_CODES:
            with self.subTest(code=code):
                encoded = canonical_result(VMTrap(code, "detail", 3, (1, 2), b"\x01")).to_dict()
                self.assertEqual(encoded["trap_code"], code)

    def test_human_detail_never_enters_the_encoding(self) -> None:
        # Section 6.4: the code is the identity; the message is not.
        a = canonical_result(VMTrap("trap.div_by_zero", "divisor is zero", 2, (), b"")).canonical_json()
        b = canonical_result(VMTrap("trap.div_by_zero", "something else entirely", 2, (), b"")).canonical_json()
        self.assertEqual(a, b)

    def test_distinct_results_never_share_an_encoding(self) -> None:
        # Injectivity, across each field that can differ.
        variants = [
            VMResult(halted=True, steps=1, stack=[], output=b"", profile=PROFILE),
            VMResult(halted=True, steps=2, stack=[], output=b"", profile=PROFILE),
            VMResult(halted=True, steps=1, stack=[0], output=b"", profile=PROFILE),
            VMResult(halted=True, steps=1, stack=[1], output=b"", profile=PROFILE),
            VMResult(halted=True, steps=1, stack=[1, 0], output=b"", profile=PROFILE),
            VMResult(halted=True, steps=1, stack=[0, 1], output=b"", profile=PROFILE),
            VMResult(halted=True, steps=1, stack=[], output=b"\x00", profile=PROFILE),
            VMResult(halted=True, steps=1, stack=[], output=b"\x00\x00", profile=PROFILE),
            VMTrap("trap.div_by_zero", "", 1, (), b""),
            VMTrap("trap.stack_underflow", "", 1, (), b""),
        ]
        encodings = [canonical_result(v).canonical_json() for v in variants]
        self.assertEqual(len(encodings), len(set(encodings)))

    def test_a_non_halted_result_has_no_encoding(self) -> None:
        with self.assertRaises(CanonicalError):
            canonical_result(VMResult(halted=False, steps=1, stack=[], output=b"", profile=PROFILE))

    def test_text_output_is_rejected(self) -> None:
        with self.assertRaises(CanonicalError):
            canonical_result(VMResult(halted=True, steps=1, stack=[], output="text", profile=PROFILE))  # type: ignore[arg-type]

    def test_unknown_objects_are_rejected(self) -> None:
        with self.assertRaises(CanonicalError):
            canonical_result(object())  # type: ignore[arg-type]


class PreimageTests(unittest.TestCase):
    def test_preimage_carries_artifact_profile_and_result(self) -> None:
        raw = encode_module(mod([Instruction(PUSH, 3, 0, 0), Instruction(HALT, 0, 0, 0)]))
        result = canonical_result(run_module(require_canonical_module(raw), PROFILE))
        preimage = canonical_preimage(raw, PROFILE, result)
        self.assertEqual(bytes.fromhex(preimage["artifact_hex"]), raw)
        self.assertEqual(preimage["profile"], PROFILE.to_dict())
        self.assertEqual(preimage["result"], result.to_dict())

    def test_profile_is_part_of_the_preimage(self) -> None:
        # The invariant is artifact + profile. Two budgets must not share a
        # preimage even when the result happens to match.
        raw = encode_module(mod([Instruction(HALT, 0, 0, 0)]))
        module = require_canonical_module(raw)
        a = canonical_preimage(raw, ExecutionProfile(step_budget=10), canonical_result(run_module(module, ExecutionProfile(step_budget=10))))
        b = canonical_preimage(raw, ExecutionProfile(step_budget=20), canonical_result(run_module(module, ExecutionProfile(step_budget=20))))
        self.assertNotEqual(canonical_json(a), canonical_json(b))


if __name__ == "__main__":
    unittest.main()
