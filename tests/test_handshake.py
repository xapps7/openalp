from __future__ import annotations

import unittest

from alp.handshake import HandshakeError, compatibility, parse_hello


class HandshakeTests(unittest.TestCase):
    def test_compatible_hello(self) -> None:
        hello = parse_hello(
            {
                "protocol": "ALP",
                "version": "0.2",
                "features": ["vm-stack-v1", "deterministic"],
                "targets": ["ref-vm"],
            }
        )
        result = compatibility(hello)
        self.assertTrue(result["compatible"])
        self.assertFalse(result["deprecated"])

    def test_deprecated_hello_version_still_works(self) -> None:
        hello = parse_hello(
            {
                "protocol": "ALP",
                "version": "0.1",
                "features": ["vm-stack-v1"],
                "targets": ["ref-vm"],
            }
        )
        result = compatibility(hello)
        self.assertTrue(result["compatible"])
        self.assertTrue(result["deprecated"])

    def test_invalid_payload(self) -> None:
        with self.assertRaises(HandshakeError):
            parse_hello({"protocol": "ALP"})


if __name__ == "__main__":
    unittest.main()
