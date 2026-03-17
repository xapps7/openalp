#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

"$ROOT/scripts/quality_gate.sh"

test -f "$ROOT/docs/LAUNCH_PLAN_MAR5_2026.md"
test -f "$ROOT/docs/ONBOARDING.md"
test -f "$ROOT/docs/AGENT_CONTEXT.md"
test -f "$ROOT/docs/GIT_PUBLICATION.md"
test -f "$ROOT/docs/INTEROP_PACK.md"
test -f "$ROOT/docs/RELEASE_NOTES_V0_1_0_MVP.md"
test -f "$ROOT/INSTALL.md"
test -f "$ROOT/web/index.html"
test -f "$ROOT/web/landing.html"
test -f "$ROOT/web/alp_site.html"
test -f "$ROOT/LICENSE"
test -f "$ROOT/CHANGELOG.md"
"$ROOT/scripts/setup.sh" >/tmp/openalp-setup.out

echo "launch_check=ok"
