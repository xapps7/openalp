# OpenALP MVP Launch Plan

Target launch date: 2026-03-05
Today baseline: 2026-02-25

## Launch Definition

Launch means:
1. Public GitHub repo is ready and pushed.
2. `v0.1.0-mvp` tag and release artifact are available.
3. README + onboarding + browser demo are complete and reproducible.
4. Test suite + quality gate pass on clean environment.

## Remaining Scope (from current state)

1. Add public-key signature profile (in addition to HMAC MVP).
2. Add interop examples and protocol walkthrough.
3. Final release docs, changelog, and launch notes.
4. Freeze branch and perform final release build.

## Date-Wise Execution

### 2026-02-25 to 2026-02-27
- Implement public-key signature profile.
- Add CLI commands/tests for keypair sign/verify flow.
- Update spec security section.

Exit criteria:
- New signature tests green.
- Backward compatibility with current HMAC path preserved.

### 2026-02-28 to 2026-03-01
- Build interop example pack:
  - `ALP-Hello` exchange examples
  - producer/consumer validation order
  - signed module handoff examples
- Add runnable scripts for interop smoke checks.

Exit criteria:
- Interop walkthrough executable from docs.

### 2026-03-02 to 2026-03-03
- Final docs polish:
  - README tightening
  - onboarding simplification
  - architecture overview diagram/text
- Draft release notes + changelog.

Exit criteria:
- New user can run first demo in <10 minutes.

### 2026-03-04
- Release candidate freeze (`rc1`).
- Full quality gate + benchmark + packaging.
- Fix only blockers.

Exit criteria:
- All tests pass.
- `openalp-v0.1.0-mvp.tar.gz` generated cleanly.

### 2026-03-05 (Launch)
- Tag `v0.1.0-mvp`.
- Publish GitHub release + release notes.
- Publish quickstart post and browser demo link/path.

## Release Gates

1. Tests: all pass.
2. Quality gate: pass.
3. Determinism report: `consistent=true` on sample suite.
4. Integrity/signature checks: pass for release artifacts.
5. Docs: quickstart verified on clean run.
