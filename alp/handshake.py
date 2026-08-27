from __future__ import annotations

from dataclasses import dataclass

from .protocol import (
    PROTOCOL_NAME,
    CURRENT_PROTOCOL_VERSION,
    ProtocolError,
    RuntimeProfile,
    validate_runtime_compatibility,
)


class HandshakeError(ValueError):
    pass


@dataclass(frozen=True)
class Hello:
    protocol: str
    version: str
    features: tuple[str, ...]
    targets: tuple[str, ...]


def parse_hello(payload: object) -> Hello:
    if not isinstance(payload, dict):
        raise HandshakeError("hello payload must be a JSON object")

    protocol = payload.get("protocol")
    version = payload.get("version")
    features = payload.get("features")
    targets = payload.get("targets")

    if not isinstance(protocol, str) or not protocol:
        raise HandshakeError("protocol must be a non-empty string")
    if not isinstance(version, str) or not version:
        raise HandshakeError("version must be a non-empty string")
    if not isinstance(features, list) or not all(isinstance(x, str) for x in features):
        raise HandshakeError("features must be a string list")
    if not isinstance(targets, list) or not all(isinstance(x, str) for x in targets):
        raise HandshakeError("targets must be a string list")

    return Hello(
        protocol=protocol,
        version=version,
        features=tuple(features),
        targets=tuple(targets),
    )


def compatibility(hello: Hello) -> dict[str, object]:
    try:
        result = validate_runtime_compatibility(
            RuntimeProfile(
                protocol=hello.protocol,
                protocol_version=hello.version,
                module_version=1,
                features=hello.features,
                targets=hello.targets,
            )
        )
    except ProtocolError as exc:
        return {"compatible": False, "reason": str(exc)}

    return {
        "compatible": True,
        "protocol": PROTOCOL_NAME,
        "version": result["protocol_version"],
        "current_version": CURRENT_PROTOCOL_VERSION,
        "shared_features": result["shared_features"],
        "shared_targets": result["shared_targets"],
        "deprecated": result["deprecated"],
        "phase": result["phase"],
        "replacement": result["replacement"],
        "sunset_after": result["sunset_after"],
    }
