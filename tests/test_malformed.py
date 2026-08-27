from __future__ import annotations

import base64
import json
import tempfile
import unittest
import zlib
from pathlib import Path

from alp.bundle import BundleError, run_bundle
from alp.format import ALPFormatError, Instruction, Module, VERSION, encode_module, parse_module
from alp.handshake import HandshakeError, parse_hello
from alp.integrity import verify_manifest, verify_signature_manifest


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


def _module_bytes() -> bytes:
    return encode_module(
        Module(
            version=VERSION,
            flags=0,
            entry=0,
            instructions=(
                Instruction(0x01, 5, 0, 0),
                Instruction(0x08, 0, 0, 0),
            ),
        )
    )


def _bundle_payload(module: bytes, **overrides: object) -> dict:
    payload = {
        "bundle_version": "1",
        "protocol": "ALP",
        "protocol_version": "0.2",
        "module_name": "m.alp",
        "module_b64": base64.b64encode(module).decode("ascii"),
        "hello": {
            "protocol": "ALP",
            "version": "0.2",
            "features": ["vm-stack-v1"],
            "targets": ["ref-vm"],
        },
        "checksum_manifest": {"algorithm": "sha256", "file": "m.alp", "checksum": "0" * 64},
        "signature_manifest": {"algorithm": "hmac-sha256", "file": "m.alp", "signature": "0" * 64},
        "signature_key_hint": "k.key",
    }
    payload.update(overrides)
    return payload


class MalformedBundleTests(unittest.TestCase):
    """Every untrusted bundle entry point must reject rather than execute."""

    def _run(self, raw: bytes, suffix: str = ".alpp.json") -> str:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bundle = root / f"b{suffix}"
            key = root / "k.key"
            bundle.write_bytes(raw)
            key.write_text("secret-key")
            with self.assertRaises(BundleError) as ctx:
                run_bundle(bundle, key)
            return str(ctx.exception)

    def test_reject_non_json_bundle(self) -> None:
        self._run(b"this is not json")

    def test_reject_truncated_binary_bundle(self) -> None:
        self.assertIn("binary", self._run(b"ALPPB1\x00\x01\x02\x03", ".alppb"))

    def test_reject_binary_bundle_with_non_json_inner_payload(self) -> None:
        raw = b"ALPPB1\x00" + zlib.compress(b"not json", level=9)
        self.assertIn("binary", self._run(raw, ".alppb"))

    def test_reject_unsupported_protocol_version(self) -> None:
        payload = _bundle_payload(_module_bytes(), protocol_version="9.9")
        self.assertIn("protocol_version", self._run(json.dumps(payload).encode()))

    def test_reject_unsupported_protocol_name(self) -> None:
        payload = _bundle_payload(_module_bytes(), protocol="NOTALP")
        self.assertIn("protocol", self._run(json.dumps(payload).encode()))

    def test_reject_non_base64_module(self) -> None:
        payload = _bundle_payload(_module_bytes(), module_b64="!!!not base64!!!")
        self.assertIn("module_b64", self._run(json.dumps(payload).encode()))

    def test_reject_module_that_is_not_an_alp_module(self) -> None:
        payload = _bundle_payload(b"totally not a module")
        self.assertIn("invalid module", self._run(json.dumps(payload).encode()))

    def test_reject_checksum_mismatch(self) -> None:
        payload = _bundle_payload(_module_bytes())
        self.assertIn("checksum", self._run(json.dumps(payload).encode()))

    def test_reject_incompatible_hello(self) -> None:
        module = _module_bytes()
        from alp.integrity import sha256_bytes

        payload = _bundle_payload(
            module,
            checksum_manifest={
                "algorithm": "sha256",
                "file": "m.alp",
                "checksum": sha256_bytes(module),
            },
            hello={
                "protocol": "ALP",
                "version": "0.2",
                "features": ["vm-stack-v1"],
                "targets": ["some-other-vm"],
            },
        )
        # Signature still fails first; ordering is part of the contract.
        self.assertIn("signature", self._run(json.dumps(payload).encode()))


class MalformedManifestTests(unittest.TestCase):
    def _paths(self, root: Path) -> tuple[Path, Path]:
        module = root / "m.alp"
        module.write_bytes(_module_bytes())
        return module, root / "manifest.json"

    def test_checksum_manifest_with_wrong_algorithm_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            module, manifest = self._paths(Path(td))
            manifest.write_text(json.dumps({"algorithm": "md5", "checksum": "0" * 32}))
            ok, reason = verify_manifest(module, manifest)
            self.assertFalse(ok)
            self.assertEqual(reason, "invalid manifest format")

    def test_checksum_manifest_with_non_string_checksum_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            module, manifest = self._paths(Path(td))
            manifest.write_text(json.dumps({"algorithm": "sha256", "checksum": 12345}))
            ok, reason = verify_manifest(module, manifest)
            self.assertFalse(ok)
            self.assertEqual(reason, "invalid manifest format")

    def test_checksum_mismatch_is_distinguished_from_bad_format(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            module, manifest = self._paths(Path(td))
            manifest.write_text(json.dumps({"algorithm": "sha256", "checksum": "0" * 64}))
            ok, reason = verify_manifest(module, manifest)
            self.assertFalse(ok)
            self.assertEqual(reason, "checksum mismatch")

    def test_signature_manifest_with_wrong_algorithm_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            module, manifest = self._paths(root)
            key = root / "k.key"
            key.write_text("secret-key")
            manifest.write_text(json.dumps({"algorithm": "rsa-demo", "signature": "1"}))
            ok, reason = verify_signature_manifest(module, key, manifest)
            self.assertFalse(ok)
            self.assertEqual(reason, "invalid signature manifest format")

    def test_signature_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            module, manifest = self._paths(root)
            key = root / "k.key"
            key.write_text("secret-key")
            manifest.write_text(json.dumps({"algorithm": "hmac-sha256", "signature": "0" * 64}))
            ok, reason = verify_signature_manifest(module, key, manifest)
            self.assertFalse(ok)
            self.assertEqual(reason, "signature mismatch")


class MalformedHelloTests(unittest.TestCase):
    def test_reject_non_object(self) -> None:
        for payload in ([], "hello", 7, None):
            with self.assertRaises(HandshakeError):
                parse_hello(payload)

    def test_reject_missing_fields(self) -> None:
        with self.assertRaises(HandshakeError):
            parse_hello({"protocol": "ALP"})

    def test_reject_wrong_types(self) -> None:
        base = {
            "protocol": "ALP",
            "version": "0.2",
            "features": ["vm-stack-v1"],
            "targets": ["ref-vm"],
        }
        for field, bad in (
            ("protocol", 1),
            ("protocol", ""),
            ("version", []),
            ("features", "vm-stack-v1"),
            ("features", [1, 2]),
            ("targets", {"a": 1}),
        ):
            payload = dict(base)
            payload[field] = bad
            with self.assertRaises(HandshakeError):
                parse_hello(payload)


if __name__ == "__main__":
    unittest.main()
