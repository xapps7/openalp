from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ChecksumManifest:
    algorithm: str
    file: str
    checksum: str


@dataclass(frozen=True)
class SignatureManifest:
    algorithm: str
    file: str
    signature: str


@dataclass(frozen=True)
class DemoRSAKeyPair:
    public_n: int
    public_e: int
    private_d: int


# Small deterministic RSA demo keypair for MVP docs/tests only.
_DEMO_RSA_P = 3557
_DEMO_RSA_Q = 2579
_DEMO_RSA_N = _DEMO_RSA_P * _DEMO_RSA_Q
_DEMO_RSA_PHI = (_DEMO_RSA_P - 1) * (_DEMO_RSA_Q - 1)
_DEMO_RSA_E = 65537


def _egcd(a: int, b: int) -> tuple[int, int, int]:
    if a == 0:
        return b, 0, 1
    g, y, x = _egcd(b % a, a)
    return g, x - (b // a) * y, y


def _modinv(a: int, m: int) -> int:
    g, x, _ = _egcd(a, m)
    if g != 1:
        raise ValueError("modular inverse does not exist")
    return x % m


_DEMO_RSA_D = _modinv(_DEMO_RSA_E, _DEMO_RSA_PHI)


def demo_rsa_keypair() -> DemoRSAKeyPair:
    return DemoRSAKeyPair(public_n=_DEMO_RSA_N, public_e=_DEMO_RSA_E, private_d=_DEMO_RSA_D)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _digest_int(data: bytes, modulus: int) -> int:
    return int.from_bytes(hashlib.sha256(data).digest(), "big") % modulus


def _load_key(path: Path) -> bytes:
    raw = path.read_text().strip()
    if raw.startswith("hex:"):
        return bytes.fromhex(raw[4:])
    return raw.encode("utf-8")


def _hmac_sha256(data: bytes, key: bytes) -> str:
    return hmac.new(key, data, hashlib.sha256).hexdigest()


def create_manifest(path: Path) -> ChecksumManifest:
    digest = sha256_bytes(path.read_bytes())
    return ChecksumManifest(algorithm="sha256", file=path.name, checksum=digest)


def write_manifest(path: Path, manifest: ChecksumManifest) -> Path:
    out = path.with_suffix(path.suffix + ".sha256.json")
    out.write_text(
        json.dumps(
            {
                "algorithm": manifest.algorithm,
                "file": manifest.file,
                "checksum": manifest.checksum,
            },
            indent=2,
        )
        + "\n"
    )
    return out


def verify_manifest(path: Path, manifest_path: Path) -> tuple[bool, str]:
    payload = json.loads(manifest_path.read_text())
    expected = payload.get("checksum")
    algorithm = payload.get("algorithm")
    if algorithm != "sha256" or not isinstance(expected, str):
        return False, "invalid manifest format"

    actual = sha256_bytes(path.read_bytes())
    if actual != expected:
        return False, "checksum mismatch"

    return True, "ok"


def create_signature_manifest(path: Path, key_path: Path) -> SignatureManifest:
    key = _load_key(key_path)
    sig = _hmac_sha256(path.read_bytes(), key)
    return SignatureManifest(algorithm="hmac-sha256", file=path.name, signature=sig)


def write_signature_manifest(path: Path, manifest: SignatureManifest) -> Path:
    out = path.with_suffix(path.suffix + ".sig.json")
    out.write_text(
        json.dumps(
            {
                "algorithm": manifest.algorithm,
                "file": manifest.file,
                "signature": manifest.signature,
            },
            indent=2,
        )
        + "\n"
    )
    return out


def verify_signature_manifest(path: Path, key_path: Path, manifest_path: Path) -> tuple[bool, str]:
    payload = json.loads(manifest_path.read_text())
    expected = payload.get("signature")
    algorithm = payload.get("algorithm")
    if algorithm != "hmac-sha256" or not isinstance(expected, str):
        return False, "invalid signature manifest format"

    actual = _hmac_sha256(path.read_bytes(), _load_key(key_path))
    if not hmac.compare_digest(actual, expected):
        return False, "signature mismatch"

    return True, "ok"


def write_demo_rsa_keypair(prefix: Path) -> tuple[Path, Path]:
    kp = demo_rsa_keypair()
    pub = prefix.with_suffix(".pub.json")
    priv = prefix.with_suffix(".priv.json")
    pub.write_text(json.dumps({"algorithm": "rsa-demo", "n": kp.public_n, "e": kp.public_e}, indent=2) + "\n")
    priv.write_text(json.dumps({"algorithm": "rsa-demo", "n": kp.public_n, "d": kp.private_d}, indent=2) + "\n")
    return pub, priv


def create_rsa_demo_signature_manifest(path: Path, private_key_path: Path) -> SignatureManifest:
    payload = json.loads(private_key_path.read_text())
    if payload.get("algorithm") != "rsa-demo":
        raise ValueError("unsupported private key algorithm")
    n = int(payload["n"])
    d = int(payload["d"])
    msg = _digest_int(path.read_bytes(), n)
    sig = pow(msg, d, n)
    return SignatureManifest(algorithm="rsa-demo", file=path.name, signature=str(sig))


def verify_rsa_demo_signature_manifest(path: Path, public_key_path: Path, manifest_path: Path) -> tuple[bool, str]:
    key = json.loads(public_key_path.read_text())
    manifest = json.loads(manifest_path.read_text())
    if key.get("algorithm") != "rsa-demo":
        return False, "unsupported public key algorithm"
    if manifest.get("algorithm") != "rsa-demo":
        return False, "invalid signature manifest format"

    n = int(key["n"])
    e = int(key["e"])
    expected = _digest_int(path.read_bytes(), n)
    recovered = pow(int(manifest["signature"]), e, n)
    if recovered != expected:
        return False, "signature mismatch"
    return True, "ok"
