from __future__ import annotations

import unittest

from alp.decompile import to_python_like
from alp.format import Instruction, Module, VERSION


class DecompileTests(unittest.TestCase):
    def test_generates_python_like_output(self) -> None:
        module = Module(
            version=VERSION,
            flags=0,
            entry=0,
            instructions=(
                Instruction(0x01, 2, 0, 0),
                Instruction(0x01, 3, 0, 0),
                Instruction(0x02, 0, 0, 0),
                Instruction(0x08, 0, 0, 0),
            ),
        )

        out = to_python_like(module)
        self.assertIn("# Decompiled from ALP v0.1", out)
        self.assertIn("stack.append(2)  # PUSH_CONST", out)
        self.assertIn("stack.append(lhs + rhs)  # ADD", out)
        self.assertIn("break  # HALT", out)


if __name__ == "__main__":
    unittest.main()
