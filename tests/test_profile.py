from __future__ import annotations

"""Execution profile and the closed trap taxonomy.

Finding F4: the same module halted under a 1000-step budget and trapped
under a 5-step budget, and the budget lived in neither the module nor any
declared profile. Decision D2 moves it into the profile. These tests hold
that line: there is no way to execute without recording the budget used.

Finding F5: traps carried free-text messages, so a failing execution had
no comparable identity. Every trap now has a code from a closed set.
"""

import json
import unittest
from pathlib import Path

from alp.format import Instruction, Module, VERSION
from alp.profile import (
    DEFAULT_STEP_BUDGET,
    ExecutionProfile,
    MAX_STEP_BUDGET,
    ProfileError,
    load_profile,
    parse_profile,
)
from alp.vm import TRAP_CODES, VMTrap, run_module

PUSH, ADD, DIV, JMP, HALT = 0x01, 0x02, 0x05, 0x06, 0x08
NOP, PRINT = 0x00, 0x0B
REPO = Path(__file__).parent.parent


def mod(instrs):
    return Module(version=VERSION, flags=0, entry=0, instructions=tuple(instrs))


class ProfileRequiredTests(unittest.TestCase):
    def test_run_module_will_not_execute_without_a_profile(self) -> None:
        # The whole point of D2: no implicit budget anywhere in the runtime.
        with self.assertRaises(TypeError):
            run_module(mod([Instruction(HALT, 0, 0, 0)]))  # type: ignore[call-arg]

    def test_result_records_the_profile_it_ran_under(self) -> None:
        profile = ExecutionProfile(step_budget=50)
        result = run_module(mod([Instruction(HALT, 0, 0, 0)]), profile)
        self.assertEqual(result.profile, profile)
        self.assertEqual(result.profile.step_budget, 50)

    def test_differing_budget_is_a_differing_execution_not_a_differing_answer(self) -> None:
        # F4 restated as a test. Both outcomes are correct; they are
        # outcomes of different executions, and each says which.
        program = mod([Instruction(NOP, 0, 0, 0)] * 10 + [Instruction(HALT, 0, 0, 0)])

        generous = run_module(program, ExecutionProfile(step_budget=1_000))
        self.assertTrue(generous.halted)
        self.assertEqual(generous.profile.step_budget, 1_000)

        with self.assertRaises(VMTrap) as ctx:
            run_module(program, ExecutionProfile(step_budget=5))
        self.assertEqual(ctx.exception.code, "trap.step_budget_exceeded")


class ProfileValidationTests(unittest.TestCase):
    def test_budget_bounds(self) -> None:
        for bad in (0, -1, MAX_STEP_BUDGET + 1):
            with self.subTest(budget=bad), self.assertRaises(ProfileError):
                ExecutionProfile(step_budget=bad)

    def test_budget_must_be_an_integer(self) -> None:
        for bad in (1.5, "100", None, True):
            with self.subTest(budget=bad), self.assertRaises(ProfileError):
                ExecutionProfile(step_budget=bad)  # type: ignore[arg-type]

    def test_step_budget_is_required_when_parsing(self) -> None:
        with self.assertRaises(ProfileError) as ctx:
            parse_profile({"protocol_version": "0.2"})
        self.assertIn("step_budget is required", str(ctx.exception))

    def test_unknown_fields_are_rejected_not_ignored(self) -> None:
        with self.assertRaises(ProfileError) as ctx:
            parse_profile({"step_budget": 10, "turbo": True})
        self.assertIn("turbo", str(ctx.exception))

    def test_non_object_is_rejected(self) -> None:
        for bad in ([], "x", 7, None):
            with self.subTest(payload=bad), self.assertRaises(ProfileError):
                parse_profile(bad)

    def test_unsupported_protocol_version_is_rejected(self) -> None:
        with self.assertRaises(ProfileError):
            ExecutionProfile(step_budget=10, protocol_version="9.9")

    def test_deprecated_protocol_version_is_still_accepted(self) -> None:
        self.assertEqual(ExecutionProfile(step_budget=10, protocol_version="0.1").protocol_version, "0.1")

    def test_round_trip(self) -> None:
        profile = ExecutionProfile(step_budget=321)
        self.assertEqual(parse_profile(json.loads(profile.canonical_json())), profile)

    def test_canonical_json_is_stable_and_sorted(self) -> None:
        a = ExecutionProfile(step_budget=7).canonical_json()
        b = ExecutionProfile(step_budget=7).canonical_json()
        self.assertEqual(a, b)
        self.assertEqual(a, json.dumps(json.loads(a), separators=(",", ":"), sort_keys=True))
        self.assertNotIn(" ", a)

    def test_shipped_default_profile_document_loads(self) -> None:
        profile = load_profile(REPO / "samples" / "profile.default.json")
        self.assertEqual(profile, ExecutionProfile.default())
        self.assertEqual(profile.step_budget, DEFAULT_STEP_BUDGET)


class TrapTaxonomyTests(unittest.TestCase):
    """Every trap code must be reachable, and the set must stay closed."""

    PROFILE = ExecutionProfile(step_budget=1_000)

    def _trap(self, instrs, profile=None) -> str:
        with self.assertRaises(VMTrap) as ctx:
            run_module(mod(instrs), profile or self.PROFILE)
        return ctx.exception.code

    def test_stack_underflow(self) -> None:
        self.assertEqual(self._trap([Instruction(ADD, 0, 0, 0), Instruction(HALT, 0, 0, 0)]),
                         "trap.stack_underflow")

    def test_div_by_zero(self) -> None:
        self.assertEqual(
            self._trap([Instruction(PUSH, 4, 0, 0), Instruction(PUSH, 0, 0, 0),
                        Instruction(DIV, 0, 0, 0), Instruction(HALT, 0, 0, 0)]),
            "trap.div_by_zero",
        )

    def test_ip_out_of_range(self) -> None:
        # A module whose final instruction is not HALT runs off the end.
        self.assertEqual(self._trap([Instruction(NOP, 0, 0, 0)]), "trap.ip_out_of_range")

    def test_step_budget_exceeded(self) -> None:
        # Infinite loop, small budget.
        self.assertEqual(
            self._trap([Instruction(JMP, 0, 0, 0)], ExecutionProfile(step_budget=20)),
            "trap.step_budget_exceeded",
        )

    def test_every_code_is_in_the_closed_set(self) -> None:
        for code in ("trap.stack_underflow", "trap.div_by_zero", "trap.ip_out_of_range",
                     "trap.step_budget_exceeded"):
            self.assertIn(code, TRAP_CODES)

    def test_taxonomy_is_closed_and_unique(self) -> None:
        self.assertEqual(len(TRAP_CODES), len(set(TRAP_CODES)))
        self.assertEqual(len(TRAP_CODES), 6)
        for code in TRAP_CODES:
            self.assertTrue(code.startswith("trap."), code)

    def test_a_trap_carries_its_code_separately_from_its_message(self) -> None:
        # F5: the code is the comparable identity; the detail is for humans.
        with self.assertRaises(VMTrap) as ctx:
            run_module(mod([Instruction(ADD, 0, 0, 0)]), self.PROFILE)
        self.assertEqual(ctx.exception.code, "trap.stack_underflow")
        self.assertIn("trap.stack_underflow", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
