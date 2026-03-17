# OpenALP Interop Pack

## Goal

Show how two agents exchange an executable OpenALP unit safely.

## Producer Bundle

A producer should send:

1. `module.alp`
2. `module.alp.sha256.json`
3. One of:
- `module.alp.sig.json` (shared-secret HMAC)
- `module.alp.rsa.sig.json` (demo public-key signature)
4. `ALP-Hello` JSON payload

## Consumer Validation Order

```bash
python3 -m alp.cli validate samples/add.alp
python3 -m alp.cli checksum verify samples/add.alp
python3 -m alp.cli sign verify samples/add.alp --key samples/dev_hmac.key
python3 -m alp.cli keygen-demo-rsa samples/demo_rsa
python3 -m alp.cli sign-rsa verify samples/add.alp --key samples/demo_rsa.pub.json
python3 -m alp.cli handshake validate samples/hello_ref_vm.json
python3 -m alp.cli run samples/add.alp
```

## Trust Models

1. HMAC sidecar
- Faster and simpler for tightly coupled agent fleets.

2. Demo RSA sidecar
- Better shape for public-key distribution; current MVP implementation is for protocol demonstration, not production cryptography.

## Recommended Logging

1. module checksum
2. signature verification result
3. handshake result
4. deterministic output hash
5. final output payload
