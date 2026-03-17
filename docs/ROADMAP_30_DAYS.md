# ALP MVP 30-Day Roadmap

Start date: 2026-02-17
Target MVP date: 2026-03-18

## Success Criteria

1. External developer can build and run in <= 10 minutes.
2. ALP modules validate and execute deterministically.
3. At least 3 representative agent workflows run on ALP.
4. Published benchmark showing at least one measurable advantage.
5. Public `v0.1.0-mvp` release with tests and docs.

## Week 1 (Days 1-7): Core Foundation

- Deliverables:
  - Binary format spec v0.1 draft
  - Parser/verifier
  - Deterministic VM runtime
  - CLI (`validate`, `run`, `inspect`)
  - Initial conformance tests
- Exit gate:
  - All tests pass in CI-local equivalent
  - Example modules execute correctly

## Week 2 (Days 8-14): Agent Workflow Layer

- Deliverables:
  - ALP-Hello capability handshake JSON schema
  - 3 workflow examples:
    - arithmetic/data transform flow
    - decision loop with branches
    - bounded planning loop
  - CLI enhancement: `handshake` and `trace`
- Exit gate:
  - Handshake compatibility checks pass
  - Workflows produce deterministic outputs on repeated runs

## Week 3 (Days 15-21): Performance + Security

- Deliverables:
  - Bench harness with baseline comparator
  - Fast-path stack/memory optimizations
  - Input fuzz harness for parser/verifier
  - Signature/checksum support for module integrity (MVP-grade)
- Exit gate:
  - Bench report generated
  - Fuzz run completes with no crashes on target corpus

## Week 4 (Days 22-30): Developer Adoption + Release

- Deliverables:
  - Decompiler-lite to Python-like pseudocode
  - Installation guide + quickstart + architecture docs
  - Conformance manifest and compatibility matrix
  - Tagged release package `v0.1.0-mvp`
- Exit gate:
  - Fresh environment setup success <= 10 minutes
  - Full test suite + smoke benchmarks pass

## Risk Controls

1. Scope lock: no new opcodes after day 14 unless critical.
2. Keep single execution backend in MVP.
3. Decompiler remains best-effort (not full round-trip) for v0.1.
4. Every feature ships with a test before merge.
