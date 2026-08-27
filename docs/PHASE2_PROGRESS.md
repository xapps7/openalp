# Phase 2 Progress

## Completed in current iteration

1. Added `ALP-Bundle v1` implementation (`alp/bundle.py`).
2. Added CLI commands:
- `alp bundle create`
- `alp bundle run`
3. Added bundle test coverage (`tests/test_bundle.py`).
4. Added sample bundle files (`samples/add.alpp.json`, `samples/add.alppb`).
5. Added compact binary bundle format support (`.alppb`) with auto-detect runtime path.
6. Added governance/runtime validation layer with protocol version lifecycle and compatibility checks.
7. Added machine-readable spec registry (`spec/index.json`).
8. Added transport abstraction layer (`alp/transport/`) with a deterministic local reference transport.
9. Added execution envelope schema (`spec/transport-envelope-v0.2.json`) and transport semantics (`spec/transport-semantics-v0.2.md`).
10. Added CLI commands: `alp transport envelope create`, `alp transport envelope validate`, `alp transport send`.
11. Added transport test coverage (`tests/test_transport.py`, 34 cases).

## Why this matters

`ALP-Bundle` reduces dependency on human-language instructions by letting agents exchange executable payloads with trust sidecars and capability declarations in one machine-native package.

## Transport layer rationale

A bundle says *what* executes. An envelope says *how it is delivered*. A receipt says *what happened*.

Separating the three lets the same executable payload move over an in-process call, a queue, a socket, or an HTTP endpoint without the runtime contract changing. Envelope identity is content-derived rather than random and carries no wall-clock time, so replaying the same logical send always produces the same `envelope_id` and deduplication needs no coordination between sender and runtime.

Delivery is at-least-once; execution is effectively-once.
