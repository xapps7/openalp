# OpenALP Worklog

## Logging Rules

1. Log only actual implementation, testing, debugging, or spec-writing time.
2. Group work into focused blocks with concrete outputs.
3. Record total hours at the end of each day.
4. Keep all work local until explicit release approval.

## 2026-03-18

### Block 1

- Duration: `1.4h`
- Focus: Binary bundle path follow-up
- Output:
  - added `.alppb` compact bundle support
  - added bundle auto-detect runtime path
  - added binary bundle tests

### Block 2

- Duration: `1.8h`
- Focus: Protocol governance and runtime validation
- Output:
  - added [alp/protocol.py](/Users/cedcoss/Documents/AgentLang/alp_mvp/alp/protocol.py)
  - added protocol lifecycle enforcement
  - added `alp runtime validate`
  - wired handshake and bundle checks into governance path

### Block 3

- Duration: `1.3h`
- Focus: Specs, manifests, and validation
- Output:
  - added [alp-governance-v0.2.md](/Users/cedcoss/Documents/AgentLang/alp_mvp/spec/alp-governance-v0.2.md)
  - added [runtime-semantics-v0.2.md](/Users/cedcoss/Documents/AgentLang/alp_mvp/spec/runtime-semantics-v0.2.md)
  - added [index.json](/Users/cedcoss/Documents/AgentLang/alp_mvp/spec/index.json)
  - updated launch checks
  - ran full local test suite and launch check

### Block 3

- Duration: `2.5h`
- Focus: `p1-result-hash`, `p1-golden-vectors`, `p1-conformance-tests` — phase 1 closed
- Output:
  - `alp/hashing.py`: the invariant stated formally with its quantification, `H(A,P) = sha256(canonical_preimage_json(...))`, plus `alp hash`
  - a trap hashes like a halt; two runs with identical results but different budgets hash differently, which is the profile earning its place in the preimage
  - `spec/golden/vectors.json`: 19 vectors at the edges languages disagree on — wraparound, INT64_MIN, all four division sign cases, operand order, budget boundary both sides, all 256 output bytes
  - `trap.invalid_opcode` found unreachable by a valid artifact (the parser rejects first); recorded as unreachable with the reason rather than quietly missing
  - `spec/conformance-map.json` + `tests/test_normative_coverage.py`: all 28 normative sections mapped, built as a ratchet so gaps carry reasons and can only fall
  - the ratchet immediately caught my own rewrite of semantics §10 for containing an unmapped normative token
  - suite `156` -> `185`; phase 1 complete

### Total

- `7.0h`

## 2026-08-27

### Block 1

- Duration: `0.4h`
- Focus: Resume and verification
- Output:
  - verified repo state against [HANDOFF_2026-08-27.md](/Users/cedcoss/Documents/AgentLang/alp_mvp/docs/HANDOFF_2026-08-27.md)
  - ran full suite (26 passing) and `launch_check.sh`
  - committed the Phase 2C governance/runtime work locally (`070568a`, `a2284e1`), no push

### Block 2

- Duration: `2.6h`
- Focus: Transport abstraction layer
- Output:
  - added [transport-envelope-v0.2.json](/Users/cedcoss/Documents/AgentLang/alp_mvp/spec/transport-envelope-v0.2.json)
  - added [transport-semantics-v0.2.md](/Users/cedcoss/Documents/AgentLang/alp_mvp/spec/transport-semantics-v0.2.md)
  - added `alp/transport/`: status model, envelope, transport interface, local reference transport
  - content-derived envelope identity, logical clock, deterministic backoff
  - idempotency via receipt store, per-stream contiguous ordering with pending-buffer flush
  - added CLI: `transport envelope create`, `transport envelope validate`, `transport send`
  - registered both specs in `spec/index.json`, extended `launch_check.sh`

### Block 3

- Duration: `1.0h`
- Focus: Tests and docs
- Output:
  - added [test_transport.py](/Users/cedcoss/Documents/AgentLang/alp_mvp/tests/test_transport.py) (34 cases)
  - coverage: identity derivation, tamper and forgery rejection, retry classification, attempt bounds, deadline expiry, idempotent replay, ordering flush, stale rejection, CLI paths
  - suite now `60` tests passing, `launch_check.sh` ok
  - updated `agent-manifest.json` and `PHASE2_PROGRESS.md`

### Block 4

- Duration: `2.0h`
- Focus: Roadmap reconciliation and gap closure
- Output:
  - added [status.json](/Users/cedcoss/Documents/AgentLang/alp_mvp/docs/status.json) as the single machine-readable work queue
  - audited `NEXT_ACTIONS.md`: four of five items already shipped, one partial; retired it to a pointer
  - added Clock Policy section to transport semantics (`step` vs `observed`, quantization rule, determinism downgrade)
  - added `quantize_ms` and `Transport.describe()` conformance statement
  - extended adversarial corpus to bundles, manifests and hello payloads (`test_malformed.py`: 4 -> 21 cases)
  - added [SECURITY_MODEL.md](/Users/cedcoss/Documents/AgentLang/alp_mvp/docs/SECURITY_MODEL.md); flagged 24-bit demo RSA as non-security in `agent-manifest.json`
  - suite now `80` tests passing

### Block 5

- Duration: `1.5h`
- Focus: Conformance corpus and a build hazard
- Output:
  - froze `tests/fixtures/v0.2.0/` with recorded digests and expected execution results
  - added `tests/test_conformance.py` (11 cases); verified by simulating a format-version bump, which fails the corpus as intended
  - found and fixed a stale-bytecode hazard: source and `.pyc` shared mtime `1787817261` on the fuse mount, so the suite ran code no longer on disk
  - gate scripts now export `PYTHONPYCACHEPREFIX`; hazard documented in the runbook
  - suite now `91` tests passing

### Block 6

- Duration: `1.5h`
- Focus: Mandate change — prevent OpenALP from becoming unnecessary
- Output:
  - verified overlap against MCP spec `2026-07-28` and the current A2A specification rather than from memory
  - added four-pillar admission test to [status.json](/Users/cedcoss/Documents/AgentLang/alp_mvp/docs/status.json) and [AGENT_RUNBOOK.md](/Users/cedcoss/Documents/AgentLang/alp_mvp/docs/AGENT_RUNBOOK.md); both agents now reject before they build
  - audited 14 features: 4 keep, 6 remove, 3 reject, 1 add
  - cancelled `identity-spec-draft` — fully duplicated by A2A security schemes and MCP authorization, and it was the task the daily agent would have started on 28 August
  - cancelled `trace-export`, `package registry`, `economic hooks`
  - queued `intent-compilation-spike` and `mcp-a2a-adapters` as the only pillar-strengthening work
  - queued `deprecate-transport-surface` pending approval: 783 lines of transport against a 441-line deterministic core

### Block 7

- Duration: `1.0h`
- Focus: Phase 1 — specification phase opened
- Output:
  - tested the target invariant against the reference VM and found it does not hold across implementations
  - eight findings recorded in `status.json`, each reproduced by running code; three fatal
  - `F1` arbitrary-precision arithmetic: 127^16 yields a 112-bit value, no defined width
  - `F2` floor division: -7/2 = -4 where C, Rust, Go and WASM give -3
  - `F4` step budget changes the outcome of an identical artifact and lives in neither module nor profile
  - queued six ordered phase-1 tasks; phase discipline added to the runbook
  - deferred intent compilation and interop adapters to phase 2

### Block 8

- Duration: `0.5h`
- Focus: Unblock phase 1
- Output:
  - forbade agents from settling permanent decisions (wire formats, numeric semantics, hash preimages, protocol versions)
  - `D1` numeric model decided: i64 two's complement, wrapping add/sub/mul, division truncating toward zero, traps on div-by-zero and `-2^63 / -1`, `PRINT_CHAR` total over the low 8 bits
  - `D2` modules are closed computations; invariant drops "canonical input"; `step_budget` becomes a required profile field, resolving `F4`
  - six of eight findings now resolved by decision rather than deferred
  - all six phase-1 tasks unblocked

### Block 9

- Duration: `1.0h`
- Focus: `p1-numeric-model` implemented; agent execution failure diagnosed
- Output:
  - implemented D1 in `alp/vm.py`: `wrap_i64`, `div_i64`, `VMTrap` with canonical codes
  - ADD/SUB/MUL now compute modulo 2^64 and never trap; DIV truncates toward zero
  - `trap.div_by_zero` and `trap.div_overflow` are the first canonical trap codes
  - `PRINT_CHAR` total over the i64 range, emitting low 8 bits — all 256 byte values now reachable
  - added `tests/test_numeric.py` (18 cases), including a differential check that division matches C semantics
  - suite `91` -> `109`; frozen corpus v0.2.0 verified unchanged, so no migration needed
  - diagnosed why no agent work landed: both scheduled tasks run with `FOLDERS_STATE_NONE`

### Total

- `11.5h`

## 2026-11-03

### Block 1

- Duration: `2.0h`
- Focus: `p1-execution-semantics` — the phase-1 deliverable, plus the code it depends on
- Output:
  - added `alp/profile.py`: `ExecutionProfile` with required `step_budget`, canonical serialization, shipped as `samples/profile.default.json`
  - `run_module(module, profile)` — no budget argument, no default anywhere in the library; `run_bundle` and the transport executor take a profile too
  - every CLI command that executes now echoes the profile it used
  - closed trap taxonomy of six codes; budget exhaustion is a trap, not a bare `VMError`
  - added `tests/test_profile.py` (20 cases); suite `109` -> `129`
  - wrote [DETERMINISTIC_SEMANTICS.md](docs/DETERMINISTIC_SEMANTICS.md) v0.3 — all seven areas, superseding `runtime-semantics-v0.2`
  - split `decided` / `specified` / `implemented` / `enforced` in `status.json`; F4 had been reading as done since August while the code ignored it
  - 66 days of no commits diagnosed: the build agent never had folder access and never worked

### Block 2

- Duration: `2.5h`
- Focus: `p1-canonical-encoding` — the second phase-1 deliverable
- Output:
  - `VMResult.output` is now `bytes`; `PRINT_CHAR` appends one byte (F7)
  - rewrote the assertions in `test_numeric.py` that had made output-as-text normative
  - `VMTrap` carries the steps, stack and output built before it, so a trap has a result
  - added `alp/canonical.py`: canonical JSON, `require_canonical_module`, `canonical_result`, `canonical_preimage`
  - wrote [CANONICAL_ENCODING.md](docs/CANONICAL_ENCODING.md) v0.3
  - new corpus `tests/fixtures/v0.3.0/` recording exact canonical JSON; v0.2.0 kept byte-identical and superseded, not re-frozen
  - added `tests/test_canonical.py` (21 cases) incl. injectivity and totality; suite `129` -> `156`
  - all eight determinism findings now closed

### Total

- `4.5h`
