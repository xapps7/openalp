from __future__ import annotations

"""Canonical encodings for artifact, profile and result.

`DETERMINISTIC_SEMANTICS.md` defines behaviour. This module defines bytes.
Two implementations can agree on every rule in that document and still
disagree on a hash if they serialise the answer differently, so exactly
one encoding is canonical and everything else is rejected.

Three rules hold throughout:

1. **Total** — every reachable result has an encoding, traps included.
2. **Injective** — distinct results never share an encoding.
3. **Rejecting, not normalizing** — a non-canonical input is an error. An
   implementation that quietly repairs it lets two artifacts that should
   be distinguishable produce the same hash.
"""

import json
from dataclasses import dataclass

from .format import HEADER_SIZE, INSTR_SIZE, Module, encode_module, parse_module
from .profile import ExecutionProfile
from .vm import VMResult, VMTrap

RESULT_VERSION = "1"
PREIMAGE_VERSION = "1"


class CanonicalError(ValueError):
    pass


def canonical_json(payload: object) -> str:
    """The one JSON form: sorted keys, no insignificant whitespace, UTF-8.

    Used for every JSON structure that enters a hash.
    """
    return json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


# -- artifact ---------------------------------------------------------------


def canonical_module_bytes(module: Module) -> bytes:
    return encode_module(module)


def require_canonical_module(raw: bytes) -> Module:
    """Parse module bytes, rejecting any non-canonical encoding.

    The module format is fixed-width with no optional fields, so exactly
    one byte string encodes a given module. Re-encoding what we parsed
    must reproduce the input exactly; if it does not, the input carried
    something the format does not define and must not be normalized away.
    """
    module = parse_module(raw)
    if encode_module(module) != raw:
        raise CanonicalError("module bytes are not canonical")
    expected = HEADER_SIZE + len(module.instructions) * INSTR_SIZE
    if len(raw) != expected:
        raise CanonicalError(f"module length {len(raw)} is not the canonical {expected}")
    return module


# -- result -----------------------------------------------------------------


@dataclass(frozen=True)
class CanonicalResult:
    outcome: str  # "halted" | "trap"
    steps: int
    stack: tuple[int, ...]
    output: bytes
    trap_code: str | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "result_version": RESULT_VERSION,
            "outcome": self.outcome,
            "steps": self.steps,
            "stack": list(self.stack),
            # hex, not text: output is bytes and carries no encoding, so a
            # text field would invent one. Lowercase, no separators.
            "output_hex": self.output.hex(),
        }
        if self.outcome == "trap":
            payload["trap_code"] = self.trap_code
        return payload

    def canonical_json(self) -> str:
        return canonical_json(self.to_dict())


def canonical_result(outcome: VMResult | VMTrap) -> CanonicalResult:
    """Encode either kind of outcome. A trap is a result, not a failure to produce one."""
    if isinstance(outcome, VMTrap):
        if outcome.code is None:
            raise CanonicalError("trap has no code")
        return CanonicalResult(
            outcome="trap",
            steps=outcome.steps,
            stack=tuple(outcome.stack),
            output=outcome.output,
            trap_code=outcome.code,
        )

    if isinstance(outcome, VMResult):
        if not outcome.halted:
            raise CanonicalError("a VMResult that did not halt has no canonical encoding")
        if not isinstance(outcome.output, bytes):
            raise CanonicalError("output must be bytes; see DETERMINISTIC_SEMANTICS.md section 5")
        return CanonicalResult(
            outcome="halted",
            steps=outcome.steps,
            stack=tuple(outcome.stack),
            output=outcome.output,
        )

    raise CanonicalError(f"cannot encode {type(outcome).__name__}")


# -- preimage ---------------------------------------------------------------


def canonical_preimage(
    artifact: bytes,
    profile: ExecutionProfile,
    result: CanonicalResult,
) -> dict[str, object]:
    """The full canonical form of one execution.

    This is what `p1-result-hash` will hash. It is defined here, with the
    other encodings, so that the hash is a one-line operation over a form
    specified independently of it.
    """
    return {
        "preimage_version": PREIMAGE_VERSION,
        "artifact_hex": artifact.hex(),
        "profile": profile.to_dict(),
        "result": result.to_dict(),
    }


def canonical_preimage_json(
    artifact: bytes,
    profile: ExecutionProfile,
    result: CanonicalResult,
) -> str:
    return canonical_json(canonical_preimage(artifact, profile, result))
