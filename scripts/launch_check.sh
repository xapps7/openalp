#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPYCACHEPREFIX="${TMPDIR:-/tmp}/alp-pycache"  # keep bytecode off network/fuse mounts; see docs/AGENT_RUNBOOK.md

"$ROOT/scripts/quality_gate.sh"

test -f "$ROOT/docs/LAUNCH_PLAN_MAR5_2026.md"
test -f "$ROOT/docs/ONBOARDING.md"
test -f "$ROOT/docs/AGENT_CONTEXT.md"
test -f "$ROOT/docs/GIT_PUBLICATION.md"
test -f "$ROOT/docs/INTEROP_PACK.md"
test -f "$ROOT/docs/RELEASE_NOTES_V0_1_0_MVP.md"
test -f "$ROOT/INSTALL.md"
test -f "$ROOT/agent-manifest.json"
test -f "$ROOT/web/index.html"
test -f "$ROOT/web/landing.html"
test -f "$ROOT/web/alp_site.html"
test -f "$ROOT/web/agent.html"
test -f "$ROOT/LICENSE"
test -f "$ROOT/CHANGELOG.md"
test -f "$ROOT/spec/transport-envelope-v0.2.json"
test -f "$ROOT/spec/transport-semantics-v0.2.md"
test -f "$ROOT/docs/SECURITY_MODEL.md"
test -f "$ROOT/docs/AGENT_RUNBOOK.md"
test -f "$ROOT/tests/fixtures/v0.2.0/conformance.json"
PYTHONPATH="$ROOT" python3 -m unittest tests.test_conformance -q
test -f "$ROOT/docs/status.json"
PYTHONPATH="$ROOT" python3 -c "import json,sys; d=json.load(open('$ROOT/docs/status.json')); sys.exit(0 if d.get('week',{}).get('tasks') else 1)"
"$ROOT/scripts/setup.sh" >/tmp/openalp-setup.out
PYTHONPATH="$ROOT" python3 -m alp.cli bundle run --bundle "$ROOT/samples/add.alpp.json" --key "$ROOT/samples/dev_hmac.key" >/tmp/openalp-bundle-run.out
PYTHONPATH="$ROOT" python3 -m alp.cli bundle run --bundle "$ROOT/samples/add.alppb" --key "$ROOT/samples/dev_hmac.key" >/tmp/openalp-bundle-run-bin.out
PYTHONPATH="$ROOT" python3 -m alp.cli runtime validate "$ROOT/samples/add.alp" --hello "$ROOT/samples/hello_ref_vm.json" >/tmp/openalp-runtime-validate.out
PYTHONPATH="$ROOT" python3 -m alp.cli transport envelope validate "$ROOT/samples/add.alpe.json" >/tmp/openalp-envelope-validate.out
PYTHONPATH="$ROOT" python3 -m alp.cli transport send --envelope "$ROOT/samples/add.alpe.json" --key "$ROOT/samples/dev_hmac.key" >/tmp/openalp-transport-send.out

echo "launch_check=ok"
