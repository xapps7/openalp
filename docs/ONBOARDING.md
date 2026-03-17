# OpenALP External Onboarding

## Goal

Get an external team from zero to first verified execution in under 10 minutes.

## Prerequisites

- Python 3.10+

## Quickstart

```bash
cd openalp
./scripts/setup.sh
export PYTHONPATH="$PWD"
python3 -m alp.cli validate samples/add.alp
python3 -m alp.cli run samples/add.alp
python3 -m alp.cli handshake validate samples/hello_ref_vm.json
```

## Integrity + Signature

```bash
python3 -m alp.cli checksum verify samples/add.alp
python3 -m alp.cli sign verify samples/add.alp --key samples/dev_hmac.key
python3 -m alp.cli keygen-demo-rsa samples/demo_rsa
python3 -m alp.cli sign-rsa verify samples/add.alp --key samples/demo_rsa.pub.json
```

## Determinism

```bash
python3 -m alp.cli determinism report samples/planner_loop.alp --runs 5
```

## Consumer Validation Order

1. `validate`
2. checksum/sign verify
3. handshake validate
4. `run` with bounded steps
