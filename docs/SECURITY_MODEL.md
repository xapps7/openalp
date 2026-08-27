# OpenALP Security Model

## Purpose

OpenALP ships several artifacts that look like trust primitives. This document states exactly what each one proves, what it does not, and which are safe to rely on today. It exists because an agent reading `agent-manifest.json` should not have to infer this from source.

## Summary

| Artifact | Proves | Does not prove | Production ready |
| --- | --- | --- | --- |
| `.sha256.json` checksum manifest | The module bytes match the recorded digest | Who produced the module | Yes, for integrity only |
| `.sig.json` HMAC manifest | The holder of a shared secret vouched for these bytes | Which party, when both sides hold the same key | Yes, within a trusted key-sharing boundary |
| `.rsa.sig.json` demo RSA manifest | Nothing of security value | Anything | **No. Demonstration only** |
| `ALP-Hello` handshake | Declared capability and protocol compatibility | Identity or authorization | Yes, as a compatibility check |
| Execution envelope | Payload integrity and delivery semantics | Sender identity | Yes, for delivery |

## Integrity: checksum manifests

SHA-256 over module bytes. Detects corruption and accidental modification. It is not a signature: anyone who can change the module can recompute the checksum.

## Authenticity: HMAC signature manifests

HMAC-SHA256 with a shared secret. This is real authentication with a real limitation: it is **symmetric**. Every party who can verify a signature can also forge one. It establishes that *someone inside the key boundary* produced the bytes, never *which* someone. It cannot support non-repudiation and must not be used as a public trust root.

## The demo RSA path is not cryptography

`alp/integrity.py` implements `rsa-demo` with:

1. a 24-bit modulus (`3557 x 2579`), factorable instantly by hand
2. no padding scheme — raw `pow(digest mod n, d, n)`
3. a digest reduced modulo a tiny `n`, discarding almost all of SHA-256

It exists to demonstrate the *shape* of an asymmetric signature flow in the CLI without taking a dependency. It provides **zero** security. Treat any `.rsa.sig.json` as unsigned.

Anything relying on asymmetric trust is blocked on the deferred decision in `docs/status.json` (`real-signatures`): whether OpenALP takes a crypto dependency or vendors a verified implementation. That is a human decision, not an implementation detail, because `agent-manifest.json` currently advertises `external_packages: []` and a real signature scheme breaks that promise.

## What the transport layer does and does not add

The execution envelope binds identity to *content*: `envelope_id` is derived from the payload hash, stream and sequence. This gives deduplication and tamper-evidence without coordination.

It gives **no sender authentication**. Any party who can submit an envelope can claim any `stream_id` and any `idempotency_key`. Under the current model a hostile sender can:

1. occupy a stream position and block a legitimate sender behind head-of-line ordering
2. burn an `idempotency_key` so a legitimate send returns `duplicate` with the attacker's result

Both are addressed by the `identity-spec-draft` task in `docs/status.json`, not by the transport layer. Until then, treat the transport as trusted-network only.

## Threat model boundary

Assumed trusted today:

1. the process running the reference VM
2. the filesystem holding modules and keys
3. every party able to submit an envelope

Assumed hostile:

1. module bytes in transit — covered by checksum and HMAC
2. malformed or adversarial module, bundle, manifest, hello and envelope payloads — covered by `tests/test_malformed.py` and `tests/test_transport.py`

## Reporting

This is pre-1.0 software with an explicitly incomplete trust story. Do not use it to execute untrusted code from untrusted senders.
