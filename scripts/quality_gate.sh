#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$ROOT"

python3 "$ROOT/samples/gen_samples.py"
python3 -m alp.cli build-raw "$ROOT/samples/hello.alpb" "$ROOT/samples/hello_from_raw.alp"
python3 -m unittest discover -s "$ROOT/tests" -v
python3 -m alp.cli validate "$ROOT/samples/add.alp"
python3 -m alp.cli run "$ROOT/samples/branch.alp"
python3 -m alp.cli run "$ROOT/samples/hello_from_raw.alp"
python3 -m alp.cli decompile "$ROOT/samples/add.alp" >/tmp/alp-decompile.out
python3 -m alp.cli checksum create "$ROOT/samples/add.alp" >/tmp/alp-checksum-create.out
python3 -m alp.cli checksum verify "$ROOT/samples/add.alp"
python3 -m alp.cli sign create "$ROOT/samples/add.alp" --key "$ROOT/samples/dev_hmac.key" >/tmp/alp-sign-create.out
python3 -m alp.cli sign verify "$ROOT/samples/add.alp" --key "$ROOT/samples/dev_hmac.key"
python3 -m alp.cli keygen-demo-rsa "$ROOT/samples/demo_rsa" >/tmp/alp-rsa-keygen.out
python3 -m alp.cli sign-rsa create "$ROOT/samples/add.alp" --key "$ROOT/samples/demo_rsa.priv.json" >/tmp/alp-rsa-sign.out
python3 -m alp.cli sign-rsa verify "$ROOT/samples/add.alp" --key "$ROOT/samples/demo_rsa.pub.json"
python3 -m alp.cli determinism report "$ROOT/samples/planner_loop.alp" --runs 5
python3 -m alp.cli handshake validate "$ROOT/samples/hello_ref_vm.json"
python3 "$ROOT/scripts/benchmark.py"
