from __future__ import annotations

import unittest

from alp.format import ALPFormatError, Instruction, Module, VERSION, encode_module, parse_module


class FormatTests(unittest.TestCase):
    def test_roundtrip_module(self) -> None:
        module = Module(
            version=VERSION,
            flags=0,
            entry=0,
            instructions=(
                Instruction(0x01, 1, 0, 0),
                Instruction(0x08, 0, 0, 0),
            ),
        )

        payload = encode_module(module)
        parsed = parse_module(payload)
        self.assertEqual(parsed, module)

    def test_reject_invalid_magic(self) -> None:
        bad = b"XXXX" + bytes(20)
        with self.assertRaises(ALPFormatError):
            parse_module(bad)


if __name__ == "__main__":
    unittest.main()
