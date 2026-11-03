from __future__ import annotations

"""The canonical result hash, and the determinism invariant made computable.

## The invariant, stated formally

For every module artifact `A` (a canonically encoded byte string, §2 of
CANONICAL_ENCODING.md) and every execution profile `P` (§3), there exists
exactly one result `R` such that executing `A` under `P` yields `R`, and:

    H(A, P) = sha256( canonical_preimage_json(A, P, R) )

Quantified over:

- **all conforming implementations** — two implementations of
  DETERMINISTIC_SEMANTICS.md must produce the same `H(A, P)`;
- **all hosts, machines and languages** — nothing about the environment
  enters the preimage;
- **all repetitions** — `H` is a pure function of `(A, P)`;
- **both outcomes** — a trap is a result, so `H` is defined for artifacts
  that trap exactly as for artifacts that halt.

Not quantified over, and deliberately so: wall-clock time, host identity,
implementation version, file paths, or trap detail strings. Any of those
in the preimage would make an identical computation hash differently
somewhere else, which is the failure the invariant exists to exclude.

A definition nobody can compute is a slogan, so this module computes it
and `alp hash` exposes it.
"""

import hashlib
from pathlib import Path

from .canonical import (
    CanonicalResult,
    canonical_preimage_json,
    canonical_result,
    require_canonical_module,
)
from .profile import ExecutionProfile
from .vm import VMTrap, run_module

HASH_ALGORITHM = "sha256"


def hash_preimage(preimage_json: str) -> str:
    """Hash a canonical preimage. Prefixed, so the algorithm is never implied."""
    digest = hashlib.sha256(preimage_json.encode("utf-8")).hexdigest()
    return f"{HASH_ALGORITHM}:{digest}"


def execution_hash(artifact: bytes, profile: ExecutionProfile, result: CanonicalResult) -> str:
    return hash_preimage(canonical_preimage_json(artifact, profile, result))


def execute_and_hash(
    artifact: bytes, profile: ExecutionProfile
) -> tuple[CanonicalResult, str]:
    """Run an artifact under a profile and return its canonical result and hash.

    Traps are not errors here. They are outcomes with hashes.
    """
    module = require_canonical_module(artifact)
    try:
        result = canonical_result(run_module(module, profile))
    except VMTrap as trap:
        result = canonical_result(trap)
    return result, execution_hash(artifact, profile, result)


def hash_module_file(path: Path, profile: ExecutionProfile) -> tuple[CanonicalResult, str]:
    return execute_and_hash(path.read_bytes(), profile)
