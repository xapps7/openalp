# Second implementation (C)

## Why this exists

The Python runtime and its test suite were written together. They agree with each other by construction, so neither can tell you whether `DETERMINISTIC_SEMANTICS.md` and `CANONICAL_ENCODING.md` are implementable from the prose alone — which is the whole claim of the specification phase.

This is an independent implementation written from those two documents. It is the only thing in the repo that can falsify them.

## Why C specifically

Signed integer overflow is undefined behaviour in C. A correct implementation therefore has to take §4.2's wording literally — "compute modulo 2^64 and reinterpret the result as signed" — and do the arithmetic through unsigned types. A language where wrapping is the default would not have tested that sentence at all.

C also truncates integer division toward zero natively, which is the behaviour §4.3 requires and the one Python gets wrong, so the division rules were exercised rather than inherited.

No dependencies. SHA-256 is inline, matching the project's own zero-dependency stance.

## What it found

On its first run against the 19 golden vectors, 18 agreed and one diverged.

`trap-stack-underflow` was recorded with `steps: 0`. The C implementation produced `steps: 1`. The spec decides it: §1.4 increments the step counter before the instruction's effects, and `CANONICAL_ENCODING.md` §4 records the trapping step. The instruction was attempted, so it counts. **The Python implementation was wrong.**

Root cause: `alp/vm.py`'s stack guard raised a trap without the execution frame, so `steps` defaulted to zero. The same bug silently discarded any output produced before a stack-underflow trap — a second defect that no vector exposed and that would have corrupted hashes for any program printing before underflowing.

Both halves are fixed. The vector correction is recorded in the `corrections` section of `spec/golden/vectors.json` with its old value, its new value and the clauses that decided it.

The exercise paid for itself in one run.

## Build and use

```sh
cc -O2 -std=c99 -Wall -Wextra -o alpvm alpvm.c
./alpvm --artifact-hex 414c5031010000000000030001070000020000000800000 --step-budget 1000
```

It prints one line: the canonical result and the hash, in the canonical serialization.

`tests/test_second_implementation.py` builds it and runs every golden vector through it, comparing both the result and the hash. It skips where no C compiler is present, because a missing toolchain is not a conformance failure.

## What it does not prove

1. It shares an author with the Python implementation, so a misreading common to both would go unnoticed. A third implementation by someone else is the real test.
2. It covers the golden vectors, not the whole semantics. §7.1 (no clock or entropy access) and §8.2 (unobservable optimisation) are not testable this way.
3. `trap.invalid_opcode` is unreachable in both: the parser rejects an unknown opcode before execution. Here the two implementations differ in *where* they reject — Python at parse, C at runtime — and the spec does not say which is correct. That ambiguity is recorded as a finding in `docs/status.json`.
