from __future__ import annotations

import unittest

from alp.format import Instruction, Module, VERSION
from alp.vm import VMError, run_module


def make_module(instructions: list[Instruction], entry: int = 0) -> Module:
    return Module(version=VERSION, flags=0, entry=entry, instructions=tuple(instructions))


class VMTests(unittest.TestCase):
    def test_add_program(self) -> None:
        module = make_module(
            [
                Instruction(0x01, 2, 0, 0),
                Instruction(0x01, 5, 0, 0),
                Instruction(0x02, 0, 0, 0),
                Instruction(0x08, 0, 0, 0),
            ]
        )
        result = run_module(module)
        self.assertEqual(result.top, 7)

    def test_div_zero_fails(self) -> None:
        module = make_module(
            [
                Instruction(0x01, 9, 0, 0),
                Instruction(0x01, 0, 0, 0),
                Instruction(0x05, 0, 0, 0),
                Instruction(0x08, 0, 0, 0),
            ]
        )
        with self.assertRaises(VMError):
            run_module(module)

    def test_print_char_output(self) -> None:
        module = make_module(
            [
                Instruction(0x01, ord("H"), 0, 0),
                Instruction(0x0B, 0, 0, 0),
                Instruction(0x01, ord("i"), 0, 0),
                Instruction(0x0B, 0, 0, 0),
                Instruction(0x08, 0, 0, 0),
            ]
        )
        result = run_module(module)
        self.assertEqual(result.output, "Hi")


if __name__ == "__main__":
    unittest.main()
