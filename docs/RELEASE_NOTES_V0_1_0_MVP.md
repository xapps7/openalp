# OpenALP v0.1.0-mvp Release Notes

OpenALP v0.1.0-mvp is the first public machine-first release of the Open Agent Language Protocol.

## What Ships

1. Portable `.alp` execution format
2. Raw `.alpb` authoring format
3. Reference runtime and CLI
4. Browser demo
5. Integrity and signature sidecars
6. Agent onboarding and interop documentation

## What This Release Proves

1. Agents can exchange machine-first executable payloads.
2. Modules can be validated, signed, and executed deterministically.
3. A browser can run raw OpenALP source without a backend.

## Security Note

- HMAC signatures are supported for practical MVP deployment.
- Demo RSA signatures are included to validate a public-key-style workflow.
- Production-grade asymmetric cryptography should replace demo RSA in the next release.
