# OpenALP Agent Context

## Purpose

Machine-readable execution context for agents integrating OpenALP.

## Artifacts

- `*.alp` executable module
- `*.alpb` raw source (optional authoring form)
- `*.alpp.json` ALP-Bundle (single-file agent exchange package)
- `*.sha256.json` checksum sidecar
- `*.sig.json` HMAC signature sidecar
- `*.rsa.sig.json` demo RSA signature sidecar
- `ALP-Hello` capability payload

## Required Runtime Capabilities

1. Module validation
2. Checksum and signature verification
3. Handshake compatibility checks
4. Deterministic bounded execution
5. Output hash logging
6. Bundle create/run support

## Canonical Execution Order

1. `validate`
2. `checksum verify`
3. `sign verify` or `sign-rsa verify`
4. `handshake validate`
5. `run`
6. log output hash

For bundle execution:

1. `bundle run`
2. internally enforces: validate -> checksum -> signature -> handshake -> run
3. returns deterministic output payload

## Minimal Bootstrap

```bash
cd openalp
./scripts/setup.sh
export PYTHONPATH="$PWD"
python3 -m alp.cli bundle run --bundle samples/add.alpp.json --key samples/dev_hmac.key
./scripts/quality_gate.sh
```

## Key File References

- Runtime CLI: `alp/cli.py`
- Spec: `spec/alp-v0.1.md`
- Browser demo: `web/index.html`
- Hello source: `samples/hello.alpb`
