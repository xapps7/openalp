from __future__ import annotations

import unittest

from alp.protocol import (
    ProtocolError,
    RuntimeProfile,
    protocol_lifecycle,
    validate_runtime_compatibility,
)


class ProtocolTests(unittest.TestCase):
    def test_deprecated_version_is_reported(self) -> None:
        result = protocol_lifecycle("0.1")
        self.assertTrue(result["deprecated"])
        self.assertEqual(result["phase"], "deprecated")
        self.assertEqual(result["replacement"], "0.2")

    def test_runtime_compatibility_accepts_current_version(self) -> None:
        result = validate_runtime_compatibility(
            RuntimeProfile(
                protocol="ALP",
                protocol_version="0.2",
                module_version=1,
                features=("vm-stack-v1", "deterministic"),
                targets=("ref-vm",),
            )
        )
        self.assertTrue(result["compatible"])
        self.assertFalse(result["deprecated"])

    def test_runtime_compatibility_rejects_unknown_version(self) -> None:
        with self.assertRaises(ProtocolError):
            validate_runtime_compatibility(
                RuntimeProfile(
                    protocol="ALP",
                    protocol_version="9.9",
                    module_version=1,
                    features=("vm-stack-v1",),
                    targets=("ref-vm",),
                )
            )


if __name__ == "__main__":
    unittest.main()
