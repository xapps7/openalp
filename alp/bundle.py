from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path

from .format import ALPFormatError, parse_module
from .handshake import HandshakeError, compatibility, parse_hello
from .integrity import verify_manifest, verify_signature_manifest
from .vm import run_module


class BundleError(ValueError):
    pass


@dataclass(frozen=True)
class BundleResult:
    output: str
    top: int | None
    steps: int
    verified_checksum: bool
    verified_signature: bool
    compatible: bool


def _encode_bytes(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _decode_bytes(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"))


def create_bundle(
    module_path: Path,
    hello_path: Path,
    checksum_path: Path,
    signature_path: Path,
    signature_key_path: Path,
    out_path: Path,
) -> None:
    payload = {
        "bundle_version": "1",
        "module_name": module_path.name,
        "module_b64": _encode_bytes(module_path.read_bytes()),
        "hello": json.loads(hello_path.read_text()),
        "checksum_manifest": json.loads(checksum_path.read_text()),
        "signature_manifest": json.loads(signature_path.read_text()),
        "signature_key_hint": signature_key_path.name,
    }
    out_path.write_text(json.dumps(payload, indent=2) + "\n")


def run_bundle(bundle_path: Path, signature_key_path: Path, max_steps: int = 100_000) -> BundleResult:
    bundle = json.loads(bundle_path.read_text())

    try:
        module_bytes = _decode_bytes(bundle["module_b64"])
    except Exception as exc:  # pragma: no cover
        raise BundleError("invalid module_b64") from exc

    # Write temporary sidecars in-memory via temp files for verifier reuse.
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as td:
        tdir = Path(td)
        module_path = tdir / bundle.get("module_name", "module.alp")
        checksum_path = tdir / "module.alp.sha256.json"
        signature_path = tdir / "module.alp.sig.json"
        hello_path = tdir / "hello.json"

        module_path.write_bytes(module_bytes)
        checksum_path.write_text(json.dumps(bundle["checksum_manifest"]))
        signature_path.write_text(json.dumps(bundle["signature_manifest"]))
        hello_path.write_text(json.dumps(bundle["hello"]))

        # Canonical order: validate -> checksum -> signature -> handshake -> run
        try:
            module = parse_module(module_bytes)
        except ALPFormatError as exc:
            raise BundleError(f"invalid module: {exc}") from exc

        ok_checksum, reason_checksum = verify_manifest(module_path, checksum_path)
        if not ok_checksum:
            raise BundleError(f"checksum verify failed: {reason_checksum}")

        ok_sig, reason_sig = verify_signature_manifest(module_path, signature_key_path, signature_path)
        if not ok_sig:
            raise BundleError(f"signature verify failed: {reason_sig}")

        try:
            hello = parse_hello(json.loads(hello_path.read_text()))
            hs = compatibility(hello)
        except (HandshakeError, json.JSONDecodeError) as exc:
            raise BundleError(f"handshake invalid: {exc}") from exc
        if not hs.get("compatible"):
            raise BundleError(f"handshake incompatible: {hs.get('reason', 'unknown')}" )

        vm = run_module(module, max_steps=max_steps)

    return BundleResult(
        output=vm.output,
        top=vm.top,
        steps=vm.steps,
        verified_checksum=True,
        verified_signature=True,
        compatible=True,
    )
