from __future__ import annotations

"""ALP execution envelope: construction, canonicalization, and validation.

Governed by spec/transport-envelope-v0.2.json and
spec/transport-semantics-v0.2.md.

The envelope carries no wall-clock time and no random identifiers, so the
same logical send always yields the same envelope_id. That is what makes
deduplication work without coordination between sender and runtime.
"""

import base64
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from ..protocol import (
    CURRENT_PROTOCOL_VERSION,
    PROTOCOL_NAME,
    ProtocolError,
    validate_protocol_version,
)

ENVELOPE_VERSION = "1"
PAYLOAD_KINDS = frozenset({"bundle", "module"})
MAX_ATTEMPTS_LIMIT = 16
_ID_LEN = 32


class EnvelopeError(ValueError):
    """Raised when an envelope is structurally or semantically invalid."""


@dataclass(frozen=True)
class Payload:
    kind: str
    encoding: str
    bytes_b64: str
    content_hash: str

    def raw(self) -> bytes:
        try:
            return base64.b64decode(self.bytes_b64.encode("ascii"), validate=True)
        except Exception as exc:
            raise EnvelopeError("payload bytes_b64 is not valid base64") from exc

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "encoding": self.encoding,
            "bytes_b64": self.bytes_b64,
            "content_hash": self.content_hash,
        }


@dataclass(frozen=True)
class Envelope:
    protocol: str
    protocol_version: str
    envelope_version: str
    envelope_id: str
    idempotency_key: str
    stream_id: str
    sequence: int
    max_attempts: int
    payload: Payload
    deadline_ms: int | None = None
    reply_to: str | None = None
    trace: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "protocol": self.protocol,
            "protocol_version": self.protocol_version,
            "envelope_version": self.envelope_version,
            "envelope_id": self.envelope_id,
            "idempotency_key": self.idempotency_key,
            "stream_id": self.stream_id,
            "sequence": self.sequence,
            "max_attempts": self.max_attempts,
            "payload": self.payload.to_dict(),
        }
        if self.deadline_ms is not None:
            payload["deadline_ms"] = self.deadline_ms
        if self.reply_to is not None:
            payload["reply_to"] = self.reply_to
        if self.trace:
            payload["trace"] = dict(self.trace)
        return payload

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True) + ("\n" if indent else "")


def canonical_json(payload: object) -> str:
    """Stable serialization used for every hash in the transport layer."""
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def content_hash(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def derive_envelope_id(stream_id: str, sequence: int, payload_hash: str) -> str:
    """Content-derived identity. See spec/transport-semantics-v0.2.md."""
    material = canonical_json(
        {"payload_hash": payload_hash, "sequence": sequence, "stream_id": stream_id}
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:_ID_LEN]


def build_envelope(
    raw: bytes,
    stream_id: str,
    sequence: int,
    kind: str = "bundle",
    protocol_version: str = CURRENT_PROTOCOL_VERSION,
    idempotency_key: str | None = None,
    max_attempts: int = 1,
    deadline_ms: int | None = None,
    reply_to: str | None = None,
    correlation_id: str | None = None,
    parent_envelope_id: str | None = None,
) -> Envelope:
    if kind not in PAYLOAD_KINDS:
        raise EnvelopeError(f"unsupported payload kind {kind}")
    if not raw:
        raise EnvelopeError("payload is empty")

    digest = content_hash(raw)
    envelope_id = derive_envelope_id(stream_id, sequence, digest)

    trace: dict[str, object] = {}
    if correlation_id is not None:
        trace["correlation_id"] = correlation_id
    if parent_envelope_id is not None:
        trace["parent_envelope_id"] = parent_envelope_id

    envelope = Envelope(
        protocol=PROTOCOL_NAME,
        protocol_version=protocol_version,
        envelope_version=ENVELOPE_VERSION,
        envelope_id=envelope_id,
        idempotency_key=idempotency_key or envelope_id,
        stream_id=stream_id,
        sequence=sequence,
        max_attempts=max_attempts,
        payload=Payload(
            kind=kind,
            encoding="base64",
            bytes_b64=base64.b64encode(raw).decode("ascii"),
            content_hash=digest,
        ),
        deadline_ms=deadline_ms,
        reply_to=reply_to,
        trace=trace,
    )
    validate_envelope(envelope)
    return envelope


def build_envelope_from_file(path: Path, stream_id: str, sequence: int, **kwargs: object) -> Envelope:
    kind = kwargs.pop("kind", None) or ("module" if path.suffix == ".alp" else "bundle")
    return build_envelope(path.read_bytes(), stream_id, sequence, kind=kind, **kwargs)  # type: ignore[arg-type]


def _require_str(value: object, name: str, max_len: int) -> str:
    if not isinstance(value, str) or not value:
        raise EnvelopeError(f"{name} must be a non-empty string")
    if len(value) > max_len:
        raise EnvelopeError(f"{name} exceeds {max_len} characters")
    return value


def parse_envelope(payload: object) -> Envelope:
    """Parse an untrusted JSON object into an Envelope. Does not verify identity."""
    if not isinstance(payload, dict):
        raise EnvelopeError("envelope must be a JSON object")

    if payload.get("envelope_version") != ENVELOPE_VERSION:
        raise EnvelopeError(f"unsupported envelope_version {payload.get('envelope_version')!r}")

    raw_payload = payload.get("payload")
    if not isinstance(raw_payload, dict):
        raise EnvelopeError("payload must be a JSON object")

    kind = raw_payload.get("kind")
    if kind not in PAYLOAD_KINDS:
        raise EnvelopeError(f"unsupported payload kind {kind!r}")
    if raw_payload.get("encoding") != "base64":
        raise EnvelopeError("payload encoding must be base64")

    sequence = payload.get("sequence")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 0:
        raise EnvelopeError("sequence must be a non-negative integer")

    max_attempts = payload.get("max_attempts")
    if not isinstance(max_attempts, int) or isinstance(max_attempts, bool):
        raise EnvelopeError("max_attempts must be an integer")

    deadline_ms = payload.get("deadline_ms")
    if deadline_ms is not None:
        if not isinstance(deadline_ms, int) or isinstance(deadline_ms, bool) or deadline_ms < 0:
            raise EnvelopeError("deadline_ms must be a non-negative integer or null")

    trace = payload.get("trace") or {}
    if not isinstance(trace, dict):
        raise EnvelopeError("trace must be a JSON object")

    envelope = Envelope(
        protocol=_require_str(payload.get("protocol"), "protocol", 32),
        protocol_version=_require_str(payload.get("protocol_version"), "protocol_version", 16),
        envelope_version=ENVELOPE_VERSION,
        envelope_id=_require_str(payload.get("envelope_id"), "envelope_id", _ID_LEN),
        idempotency_key=_require_str(payload.get("idempotency_key"), "idempotency_key", 128),
        stream_id=_require_str(payload.get("stream_id"), "stream_id", 128),
        sequence=sequence,
        max_attempts=max_attempts,
        payload=Payload(
            kind=kind,
            encoding="base64",
            bytes_b64=_require_str(raw_payload.get("bytes_b64"), "payload.bytes_b64", 1 << 24),
            content_hash=_require_str(raw_payload.get("content_hash"), "payload.content_hash", 71),
        ),
        deadline_ms=deadline_ms,
        reply_to=payload.get("reply_to"),
        trace=dict(trace),
    )
    validate_envelope(envelope)
    return envelope


def validate_envelope(envelope: Envelope) -> dict[str, object]:
    """Validation steps 1-3 of spec/transport-semantics-v0.2.md.

    Structure, protocol governance, then payload integrity. Raises
    EnvelopeError on the first failure so callers can classify uniformly.
    """
    if envelope.protocol != PROTOCOL_NAME:
        raise EnvelopeError(f"unsupported protocol {envelope.protocol}")

    try:
        lifecycle = validate_protocol_version(envelope.protocol, envelope.protocol_version)
    except ProtocolError as exc:
        raise EnvelopeError(str(exc)) from exc

    if not 1 <= envelope.max_attempts <= MAX_ATTEMPTS_LIMIT:
        raise EnvelopeError(f"max_attempts must be between 1 and {MAX_ATTEMPTS_LIMIT}")

    if len(envelope.envelope_id) != _ID_LEN or any(
        c not in "0123456789abcdef" for c in envelope.envelope_id
    ):
        raise EnvelopeError("envelope_id must be 32 lowercase hex characters")

    raw = envelope.payload.raw()
    actual = content_hash(raw)
    if actual != envelope.payload.content_hash:
        raise EnvelopeError("payload content_hash mismatch")

    expected_id = derive_envelope_id(envelope.stream_id, envelope.sequence, actual)
    if expected_id != envelope.envelope_id:
        raise EnvelopeError("envelope_id does not match derived identity")

    return {
        "valid": True,
        "envelope_id": envelope.envelope_id,
        "idempotency_key": envelope.idempotency_key,
        "stream_id": envelope.stream_id,
        "sequence": envelope.sequence,
        "payload_kind": envelope.payload.kind,
        "payload_bytes": len(raw),
        "protocol_version": envelope.protocol_version,
        "deprecated": lifecycle["deprecated"],
        "phase": lifecycle["phase"],
    }
