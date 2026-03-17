# Phase 2 Week 1 Execution

## Goal

Implement machine-native agent bundle exchange so agents can execute shared payloads with minimal human-language mediation.

## Tasks

1. Define `ALP-Bundle v1` JSON schema.
2. Add CLI command to build bundle from module + sidecars.
3. Add CLI command to verify and run bundle in canonical order.
4. Add tests and samples.
5. Update docs and manifest pointers.

## Exit Criteria

1. `alp bundle create` works.
2. `alp bundle run` enforces validate->verify->handshake->run order.
3. Tests cover pass/fail trust scenarios.
