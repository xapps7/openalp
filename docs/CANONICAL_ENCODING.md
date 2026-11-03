# OpenALP Canonical Encoding v0.3

Status: active. Companion to `DETERMINISTIC_SEMANTICS.md`, which defines behaviour. This document defines bytes.

## 0. Why this is separate

Two implementations can agree on every behavioural rule and still disagree on a hash, because they wrote the same answer down differently. The invariant

> same artifact + same execution profile = same canonical result hash

is only testable once *artifact*, *profile* and *result* each have exactly one byte form.

Three properties hold throughout:

1. **Total** — every reachable value has an encoding. Traps included.
2. **Injective** — distinct values never share an encoding.
3. **Rejecting, not normalizing** — a non-canonical input is an error. An implementation that silently repairs one lets two inputs that should be distinguishable collapse to the same hash.

Property 3 is the one most often got wrong, and the most damaging. Normalizing is a correctness bug even when it looks like robustness.

## 1. Canonical JSON

Every JSON structure that enters a hash MUST be serialised as:

1. object keys sorted by Unicode code point, ascending;
2. no whitespace between tokens — separators are exactly `,` and `:`;
3. UTF-8, no byte-order mark;
4. no trailing newline;
5. integers written without exponent, decimal point or leading `+`;
6. no floating-point values anywhere — the protocol has no float type.

`{"b":1,"a":2}` is not canonical. `{"a":2,"b":1}` is.

## 2. Artifact: the module

The module format is fixed-width with no optional fields, so exactly one byte string encodes a given module.

### Layout

| Offset | Size | Field |
| --- | --- | --- |
| 0 | 4 | magic `ALP1` |
| 4 | 1 | module format version |
| 5 | 1 | flags — MUST be `0` |
| 6 | 2 | reserved — MUST be `0` |
| 8 | 2 | entry instruction index |
| 10 | 2 | instruction count |
| 12 | 4 × count | instructions, each `opcode, a, b, c` |

All multi-byte integers are little-endian unsigned.

### Rules

1. Total length MUST equal `12 + 4 × count` exactly. Trailing bytes are an error, not padding.
2. `flags` and the reserved field MUST be zero. A non-zero value is an error; an implementation MUST NOT mask or ignore it.
3. Unused instruction operands MUST be zero. Two modules that execute identically but differ in an ignored operand byte are different artifacts and MUST hash differently.
4. The canonicality test is round-trip equality: parse the bytes, re-encode what you parsed, and require the result to equal the input. `require_canonical_module` in `alp/canonical.py` is that check.
5. The artifact enters a preimage as lowercase hex (`artifact_hex`), so the preimage stays valid JSON without a base64 alphabet to argue about.

## 3. Execution profile

Canonical JSON over exactly these fields, no others:

| Field | Type | Notes |
| --- | --- | --- |
| `profile_version` | string | `"1"` |
| `protocol_version` | string | governed by `alp-governance-v0.2.md` |
| `module_format_version` | integer | the format the artifact must declare |
| `step_budget` | integer | required; `1 … 2^32`; no default |

1. An unknown field MUST be rejected, not ignored. Ignoring one means a profile that means something elsewhere silently means less here.
2. `step_budget` MUST be present. There is no implicit budget (`DETERMINISTIC_SEMANTICS.md` §7.6).
3. `ExecutionProfile.canonical_json()` is the reference serialization.

## 4. Result

Canonical JSON. One shape for both outcomes:

| Field | Type | Notes |
| --- | --- | --- |
| `result_version` | string | `"1"` |
| `outcome` | string | `"halted"` or `"trap"` |
| `steps` | integer | steps executed, including the trapping step |
| `stack` | array of integer | full stack, bottom first |
| `output_hex` | string | lowercase hex of the output bytes |
| `trap_code` | string | present only when `outcome` is `"trap"` |

### Rules

1. **Output is hex, never text.** Output is bytes and carries no encoding, so a text field would have to invent one. `output_hex` is lowercase, unseparated, and empty for no output.
2. **The whole stack is recorded**, not just the top. Two executions agreeing on the top value but differing in depth are different results (§3.5 of the semantics).
3. **A trap is a result.** It carries `steps`, `stack` and `output_hex` as at the moment of the trap, plus its code. A failing execution is as hashable as a successful one.
4. **Human-readable trap detail MUST NOT be encoded.** The code is the comparable identity. Including a message would make hashes depend on wording.
5. `trap_code` is absent — not null — when the outcome halted. The field set differs between the two outcomes; this is deliberate and keeps the encoding injective without a sentinel.
6. An execution that neither halted nor trapped has no canonical result. It cannot occur: §1.7 of the semantics requires a trap at budget exhaustion.

## 5. Preimage

One execution, fully described:

| Field | Type |
| --- | --- |
| `preimage_version` | string `"1"` |
| `artifact_hex` | string |
| `profile` | object, §3 |
| `result` | object, §4 |

Serialised as canonical JSON. `p1-result-hash` defines the hash over this form; the form is specified here so the hash is one line over something independently pinned down.

The profile is part of the preimage because the invariant is *artifact + profile*. Two budgets must not share a preimage even when the results coincide.

## 6. What is deliberately not encoded

1. Wall-clock time, anywhere.
2. Host identity, implementation name or version.
3. Trap detail strings.
4. Trace output. `--trace` is a debugging aid, not part of any result.
5. File paths and file names.

Each of these would make an identical computation hash differently on another machine.

## 7. Conformance

An implementation conforms when it:

1. emits canonical JSON per §1;
2. rejects non-canonical module bytes per §2.4 rather than repairing them;
3. rejects unknown profile fields per §3.1;
4. encodes results per §4, including traps;
5. reproduces, byte for byte, the `canonical_result_json` recorded for every artifact in `tests/fixtures/v0.3.0/conformance.json`.

Point 5 is the practical test. The corpus records the exact serialization, not just the values, so a second implementation compares bytes rather than re-deriving the format from this prose.

## 8. Corpus versioning

`tests/fixtures/v0.2.0/` recorded execution results with output as text, which §4.1 now forbids. It stays in the tree byte-identical, its artifact digests still checked, its recorded results superseded rather than corrected in place.

This is the rule for any future change: a deliberate format change gets a **new** corpus directory and a documented migration. Re-freezing an existing corpus to make a test pass destroys the only evidence that the format changed.
