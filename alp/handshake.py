from __future__ import annotations

from dataclasses import dataclass


class HandshakeError(ValueError):
    pass


@dataclass(frozen=True)
class Hello:
    protocol: str
    version: str
    features: tuple[str, ...]
    targets: tuple[str, ...]


SUPPORTED_PROTOCOL = "ALP"
SUPPORTED_VERSION = "0.1"
SUPPORTED_FEATURES = {"vm-stack-v1", "deterministic"}
SUPPORTED_TARGETS = {"ref-vm"}


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
    if hello.protocol != SUPPORTED_PROTOCOL:
        return {"compatible": False, "reason": f"unsupported protocol {hello.protocol}"}
    if hello.version != SUPPORTED_VERSION:
        return {"compatible": False, "reason": f"unsupported version {hello.version}"}

    shared_features = sorted(set(hello.features) & SUPPORTED_FEATURES)
    shared_targets = sorted(set(hello.targets) & SUPPORTED_TARGETS)

    if not shared_targets:
        return {"compatible": False, "reason": "no shared targets"}

    return {
        "compatible": True,
        "protocol": SUPPORTED_PROTOCOL,
        "version": SUPPORTED_VERSION,
        "shared_features": shared_features,
        "shared_targets": shared_targets,
    }
