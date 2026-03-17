#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "setup_status=error"
  echo "reason=python3_not_found"
  exit 1
fi

python3 - <<'PY'
import sys
if sys.version_info < (3, 10):
    print('setup_status=error')
    print('reason=python_version_too_old')
    raise SystemExit(1)
print('setup_status=ok')
print(f'python_version={sys.version.split()[0]}')
PY

export PYTHONPATH="$ROOT"
echo "export_command=export PYTHONPATH=$ROOT"
python3 -m alp.cli validate "$ROOT/samples/add.alp"
echo "next=python3 -m alp.cli run $ROOT/samples/hello.alp"
