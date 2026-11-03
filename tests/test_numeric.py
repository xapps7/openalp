from __future__ import annotations

"""Numeric semantics under decision D1-numeric-model.

These tests exist because the previous behaviour was unspecifiable, not
merely undertested: arithmetic used Python arbitrary-precision integers
(F1), division floored toward negative infinity where C, Rust, Go and
WASM truncate toward zero (F2), and PUSH_CONST sign-extended while
PRINT_CHAR demanded 0..255, making bytes 128-255 unreachable (F3).

Each test below fails if a future change reintroduces one of those.
"""

import unittest

from alp.format import Instruction, Module, VERSION
from alp.profile import ExecutionProfile
from alp.vm import INT64_MAX, INT64_MIN, VMTrap, div_i64, run_module, wrap_i64

PUSH, ADD, SUB, MUL, DIV = 0x01, 0x02, 0x03, 0x04, 0x05
DUP, POP, PRINT, HALT = 0x09, 0x0A, 0x0B, 0x08


def run(instrs, step_budget: int = 10_000):
    module = Module(version=VERSION, flags=0, entry=0, instructions=tuple(instrs))
    return run_module(module, ExecutionProfile(step_budget=step_budget))


class WrappingTests(unittest.TestCase):
    def test_wrap_is_identity_inside_the_range(self) -> None:
        for v in (0, 1, -1, INT64_MAX, INT64_MIN):
            self.assertEqual(wrap_i64(v), v)

    def test_overflow_wraps_to_the_minimum(self) -> None:
        self.assertEqual(wrap_i64(INT64_MAX + 1), INT64_MIN)
        self.assertEqual(wrap_i64(INT64_MIN - 1), INT64_MAX)

    def test_wrap_is_modular(self) -> None:
        self.assertEqual(wrap_i64(INT64_MAX + 2), INT64_MIN + 1)
        self.assertEqual(wrap_i64(2 ** 64), 0)
        self.assertEqual(wrap_i64(2 ** 64 + 5), 5)

    def test_repeated_multiplication_stays_in_range(self) -> None:
        # 127 squared four times previously produced a 112-bit value, which
        # no 64-bit implementation could reproduce.
        prog = [Instruction(PUSH, 127, 0, 0)]
        prog += [Instruction(DUP, 0, 0, 0), Instruction(MUL, 0, 0, 0)] * 4
        prog += [Instruction(HALT, 0, 0, 0)]
        top = run(prog).top
        self.assertGreaterEqual(top, INT64_MIN)
        self.assertLessEqual(top, INT64_MAX)
        self.assertLessEqual(top.bit_length(), 64)

    def test_arithmetic_never_traps(self) -> None:
        for op in (ADD, SUB, MUL):
            with self.subTest(op=op):
                prog = [
                    Instruction(PUSH, 127, 0, 0),
                    Instruction(PUSH, 127, 0, 0),
                    Instruction(op, 0, 0, 0),
                    Instruction(HALT, 0, 0, 0),
                ]
                self.assertTrue(run(prog).halted)


class DivisionTests(unittest.TestCase):
    def test_truncates_toward_zero(self) -> None:
        cases = {(-7, 2): -3, (7, -2): -3, (-7, -2): 3, (7, 2): 3, (-1, 2): 0, (1, -2): 0}
        for (lhs, rhs), expected in cases.items():
            with self.subTest(lhs=lhs, rhs=rhs):
                self.assertEqual(div_i64(lhs, rhs), expected)

    def test_does_not_floor(self) -> None:
        # The specific divergence: Python's // gives -4 here.
        self.assertEqual(div_i64(-7, 2), -3)
        self.assertNotEqual(div_i64(-7, 2), -7 // 2)

    def test_exact_division_is_unaffected(self) -> None:
        self.assertEqual(div_i64(-8, 2), -4)
        self.assertEqual(div_i64(8, -2), -4)

    def test_divide_by_zero_is_a_canonical_trap(self) -> None:
        with self.assertRaises(VMTrap) as ctx:
            div_i64(1, 0)
        self.assertEqual(ctx.exception.code, "trap.div_by_zero")

    def test_min_over_minus_one_is_a_canonical_trap(self) -> None:
        # The one signed division whose true quotient is not representable.
        with self.assertRaises(VMTrap) as ctx:
            div_i64(INT64_MIN, -1)
        self.assertEqual(ctx.exception.code, "trap.div_overflow")

    def test_min_over_other_divisors_is_fine(self) -> None:
        self.assertEqual(div_i64(INT64_MIN, 1), INT64_MIN)
        self.assertEqual(div_i64(INT64_MIN, 2), INT64_MIN // 2)

    def test_div_by_zero_through_the_vm(self) -> None:
        prog = [
            Instruction(PUSH, 4, 0, 0),
            Instruction(PUSH, 0, 0, 0),
            Instruction(DIV, 0, 0, 0),
            Instruction(HALT, 0, 0, 0),
        ]
        with self.assertRaises(VMTrap) as ctx:
            run(prog)
        self.assertEqual(ctx.exception.code, "trap.div_by_zero")


class OperandWidthTests(unittest.TestCase):
    def test_push_const_sign_extends(self) -> None:
        self.assertEqual(run([Instruction(PUSH, 127, 0, 0), Instruction(HALT, 0, 0, 0)]).top, 127)
        self.assertEqual(run([Instruction(PUSH, 128, 0, 0), Instruction(HALT, 0, 0, 0)]).top, -128)
        self.assertEqual(run([Instruction(PUSH, 255, 0, 0), Instruction(HALT, 0, 0, 0)]).top, -1)

    def test_print_char_is_total_over_negatives(self) -> None:
        # Previously a trap: PUSH_CONST 200 sign-extends to -56, and
        # PRINT_CHAR rejected anything outside 0..255.
        result = run([Instruction(PUSH, 200, 0, 0), Instruction(PRINT, 0, 0, 0), Instruction(HALT, 0, 0, 0)])
        self.assertEqual(result.output, chr(200))

    def test_print_char_emits_low_eight_bits(self) -> None:
        prog = [
            Instruction(PUSH, 100, 0, 0),
            Instruction(PUSH, 100, 0, 0),
            Instruction(MUL, 0, 0, 0),  # 10000 -> 0x2710, low byte 0x10
            Instruction(PRINT, 0, 0, 0),
            Instruction(HALT, 0, 0, 0),
        ]
        self.assertEqual(run(prog).output, chr(0x10))

    def test_every_byte_is_reachable(self) -> None:
        for operand in range(256):
            with self.subTest(operand=operand):
                result = run([
                    Instruction(PUSH, operand, 0, 0),
                    Instruction(PRINT, 0, 0, 0),
                    Instruction(HALT, 0, 0, 0),
                ])
                self.assertEqual(ord(result.output), operand)


class DeterminismAcrossImplementationsTests(unittest.TestCase):
    """Properties a second implementation in C, Rust or Go must reproduce."""

    def test_no_result_exceeds_i64(self) -> None:
        prog = [Instruction(PUSH, 127, 0, 0)]
        prog += [Instruction(DUP, 0, 0, 0), Instruction(MUL, 0, 0, 0)] * 8
        prog += [Instruction(HALT, 0, 0, 0)]
        for value in run(prog).stack:
            self.assertGreaterEqual(value, INT64_MIN)
            self.assertLessEqual(value, INT64_MAX)

    def test_division_matches_c_semantics(self) -> None:
        # C99, Rust, Go and WASM all truncate toward zero.
        for lhs in (-9, -1, 0, 1, 9):
            for rhs in (-3, -1, 1, 3):
                with self.subTest(lhs=lhs, rhs=rhs):
                    expected = int(lhs / rhs)  # float division then truncate
                    self.assertEqual(div_i64(lhs, rhs), expected)


if __name__ == "__main__":
    unittest.main()
