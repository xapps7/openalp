from __future__ import annotations

"""Execution profile: everything outside the artifact that affects the result.

Decision D2 requires that the step budget be part of the execution profile
rather than a host parameter, because finding F4 showed the same module
halting under one budget and trapping under another. If the budget is not
recorded, two runs can disagree and both look correct.

So the budget lives here, in a declared profile, and never as an implicit
default inside the runtime. `run_module` has no budget argument at all --
it takes a profile.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from .protocol import CURRENT_PROTOCOL_VERSION, ProtocolError, validate_protocol_version

PROFILE_VERSION = "1"
DEFAULT_STEP_BUDGET = 100_000
MAX_STEP_BUDGET = 1 << 32


class ProfileError(ValueError):
    pass


@dataclass(frozen=True)
class ExecutionProfile:
    """The non-artifact half of the determinism invariant.

    same artifact + same execution profile = same canonical result hash
    """

    step_budget: int
    protocol_version: str = CURRENT_PROTOCOL_VERSION
    module_format_version: int = 1
    profile_version: str = PROFILE_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.step_budget, int) or isinstance(self.step_budget, bool):
            raise ProfileError("step_budget must be an integer")
        if not 1 <= self.step_budget <= MAX_STEP_BUDGET:
            raise ProfileError(f"step_budget must be between 1 and {MAX_STEP_BUDGET}")
        if self.profile_version != PROFILE_VERSION:
            raise ProfileError(f"unsupported profile_version {self.profile_version!r}")
        try:
            validate_protocol_version("ALP", self.protocol_version)
        except ProtocolError as exc:
            raise ProfileError(str(exc)) from exc

    @classmethod
    def default(cls) -> "ExecutionProfile":
        """The canonical profile a host selects when none is given.

        This is a *named* profile, not a hidden default: whichever profile
        is used is recorded in the result and enters the hash preimage.
        """
        return cls(step_budget=DEFAULT_STEP_BUDGET)

    def to_dict(self) -> dict[str, object]:
        return {
            "profile_version": self.profile_version,
            "protocol_version": self.protocol_version,
            "module_format_version": self.module_format_version,
            "step_budget": self.step_budget,
        }

    def canonical_json(self) -> str:
        """Stable serialization. Enters the hash preimage in p1-result-hash."""
        return json.dumps(self.to_dict(), separators=(",", ":"), sort_keys=True)


def parse_profile(payload: object) -> ExecutionProfile:
    if not isinstance(payload, dict):
        raise ProfileError("profile must be a JSON object")

    unknown = set(payload) - {
        "profile_version",
        "protocol_version",
        "module_format_version",
        "step_budget",
    }
    if unknown:
        raise ProfileError(f"unknown profile fields: {sorted(unknown)}")

    if "step_budget" not in payload:
        raise ProfileError("step_budget is required")

    module_format_version = payload.get("module_format_version", 1)
    if not isinstance(module_format_version, int) or isinstance(module_format_version, bool):
        raise ProfileError("module_format_version must be an integer")

    return ExecutionProfile(
        step_budget=payload["step_budget"],
        protocol_version=payload.get("protocol_version", CURRENT_PROTOCOL_VERSION),
        module_format_version=module_format_version,
        profile_version=payload.get("profile_version", PROFILE_VERSION),
    )


def load_profile(path: Path) -> ExecutionProfile:
    try:
        return parse_profile(json.loads(path.read_text()))
    except json.JSONDecodeError as exc:
        raise ProfileError(f"invalid profile JSON: {exc}") from exc
