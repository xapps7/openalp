from __future__ import annotations

"""ALP transport abstraction layer.

A bundle says what executes. An envelope says how it is delivered. A
receipt says what happened. Transports are interchangeable; the runtime
contract is not.

Specs: spec/transport-envelope-v0.2.json, spec/transport-semantics-v0.2.md
"""

from . import status
from .base import ExecutionResult, Receipt, Transport, TransportError
from .envelope import (
    ENVELOPE_VERSION,
    Envelope,
    EnvelopeError,
    Payload,
    build_envelope,
    build_envelope_from_file,
    content_hash,
    derive_envelope_id,
    parse_envelope,
    validate_envelope,
)
from .local import LocalTransport, backoff_ms, make_bundle_executor, send_envelope_file

__all__ = [
    "ENVELOPE_VERSION",
    "Envelope",
    "EnvelopeError",
    "ExecutionResult",
    "LocalTransport",
    "Payload",
    "Receipt",
    "Transport",
    "TransportError",
    "backoff_ms",
    "build_envelope",
    "build_envelope_from_file",
    "content_hash",
    "derive_envelope_id",
    "make_bundle_executor",
    "parse_envelope",
    "send_envelope_file",
    "status",
    "validate_envelope",
]
