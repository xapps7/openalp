from __future__ import annotations

import unittest

from alp.format import ALPFormatError, parse_module


class MalformedModuleTests(unittest.TestCase):
    def test_reject_short_module(self) -> None:
        with self.assertRaises(ALPFormatError):
            parse_module(b"ALP1")

    def test_reject_bad_version(self) -> None:
        payload = bytearray()
        payload.extend(b"ALP1")
        payload.append(2)  # bad version
        payload.append(0)
        payload.extend((0).to_bytes(2, "little"))
        payload.extend((0).to_bytes(2, "little"))
        payload.extend((1).to_bytes(2, "little"))
        payload.extend(bytes((0x08, 0, 0, 0)))
        with self.assertRaises(ALPFormatError):
            parse_module(bytes(payload))

    def test_reject_unknown_opcode(self) -> None:
        payload = bytearray()
        payload.extend(b"ALP1")
        payload.append(1)
        payload.append(0)
        payload.extend((0).to_bytes(2, "little"))
        payload.extend((0).to_bytes(2, "little"))
        payload.extend((1).to_bytes(2, "little"))
        payload.extend(bytes((0xFE, 0, 0, 0)))
        with self.assertRaises(ALPFormatError):
            parse_module(bytes(payload))

    def test_reject_jump_out_of_range(self) -> None:
        payload = bytearray()
        payload.extend(b"ALP1")
        payload.append(1)
        payload.append(0)
        payload.extend((0).to_bytes(2, "little"))
        payload.extend((0).to_bytes(2, "little"))
        payload.extend((1).to_bytes(2, "little"))
        payload.extend(bytes((0x06, 9, 0, 0)))
        with self.assertRaises(ALPFormatError):
            parse_module(bytes(payload))


if __name__ == "__main__":
    unittest.main()
