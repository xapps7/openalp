# Next Actions

> **Superseded.** The active work queue lives in [`docs/status.json`](/Users/cedcoss/Documents/AgentLang/alp_mvp/docs/status.json), which is machine-readable and authoritative. This file is kept for history.

## Why this file was retired

It was written before Phase 2. Audited on 2026-08-27, four of its five items were already implemented and one was only partially true. Leaving it in place meant a fresh session could read this file and the handoff and get different marching orders.

| Original item | Verdict | Evidence |
| --- | --- | --- |
| Malformed-binary corpus tests | Partial | `tests/test_malformed.py` covered `parse_module` only; bundles, manifests and hello payloads were uncovered. Carried forward as `harden-malformed-corpus`. |
| Signature verification draft | Done, with caveat | `alp/integrity.py` implements `rsa-demo` sign and verify. The modulus is 24 bits and unpadded — see [SECURITY_MODEL.md](/Users/cedcoss/Documents/AgentLang/alp_mvp/docs/SECURITY_MODEL.md). |
| Instruction-level trace filtering | Done | `alp run --trace-limit` |
| Repeated-run output comparison | Done | `alp determinism report` |
| Ecosystem onboarding docs | Done | `docs/ONBOARDING.md`, `docs/INTEROP_PACK.md` |

## Quality Gate Command

```bash
export PYTHONPATH="$PWD"
python3 -m unittest discover -s tests -p 'test_*.py' -q
./scripts/launch_check.sh
```
