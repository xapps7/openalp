from __future__ import annotations

from dataclasses import dataclass


class ProtocolError(ValueError):
    pass


PROTOCOL_NAME = "ALP"
CURRENT_PROTOCOL_VERSION = "0.2"
SUPPORTED_PROTOCOL_VERSIONS = ("0.1", "0.2")
DEPRECATED_PROTOCOL_VERSIONS = {
    "0.1": {
        "phase": "deprecated",
        "sunset_after": "0.3",
        "replacement": "0.2",
    }
}
MODULE_PROTOCOL_COMPATIBILITY = {
    1: {"0.1", "0.2"},
}
SUPPORTED_FEATURES = {"vm-stack-v1", "deterministic"}
SUPPORTED_TARGETS = {"ref-vm"}


@dataclass(frozen=True)
class RuntimeProfile:
    protocol: str
    protocol_version: str
    module_version: int
    features: tuple[str, ...]
    targets: tuple[str, ...]


def protocol_lifecycle(version: str) -> dict[str, object]:
    if version not in SUPPORTED_PROTOCOL_VERSIONS:
        raise ProtocolError(f"unsupported protocol_version {version}")
    if version in DEPRECATED_PROTOCOL_VERSIONS:
        return {
            "supported": True,
            "deprecated": True,
            **DEPRECATED_PROTOCOL_VERSIONS[version],
        }
    return {
        "supported": True,
        "deprecated": False,
        "phase": "active",
        "replacement": None,
        "sunset_after": None,
    }


def validate_protocol_version(protocol: str, version: str) -> dict[str, object]:
    if protocol != PROTOCOL_NAME:
        raise ProtocolError(f"unsupported protocol {protocol}")
    return protocol_lifecycle(version)


def validate_runtime_compatibility(profile: RuntimeProfile) -> dict[str, object]:
    lifecycle = validate_protocol_version(profile.protocol, profile.protocol_version)

    allowed_versions = MODULE_PROTOCOL_COMPATIBILITY.get(profile.module_version)
    if allowed_versions is None:
        raise ProtocolError(f"unsupported module_version {profile.module_version}")
    if profile.protocol_version not in allowed_versions:
        raise ProtocolError(
            f"module_version {profile.module_version} is not compatible with protocol_version {profile.protocol_version}"
        )

    shared_features = sorted(set(profile.features) & SUPPORTED_FEATURES)
    shared_targets = sorted(set(profile.targets) & SUPPORTED_TARGETS)
    if not shared_targets:
        raise ProtocolError("no shared targets")

    return {
        "compatible": True,
        "protocol": profile.protocol,
        "protocol_version": profile.protocol_version,
        "module_version": profile.module_version,
        "shared_features": shared_features,
        "shared_targets": shared_targets,
        "deprecated": lifecycle["deprecated"],
        "phase": lifecycle["phase"],
        "replacement": lifecycle["replacement"],
        "sunset_after": lifecycle["sunset_after"],
    }
