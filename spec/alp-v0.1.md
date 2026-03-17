# ALP v0.1 Draft (MVP)

## Scope

This MVP defines a portable binary module and deterministic execution semantics for a small stack-based VM.

## Goals

1. Machine-first representation
2. No mandatory interpreter dependency in future (MVP uses reference VM)
3. Deterministic behavior across hosts
4. Verifiable module validity before execution
5. Human-inspectable and decompilable structure

## Binary Layout

Header:

- bytes 0-3: ASCII `ALP1`
- byte 4: `version` (must be `1`)
- byte 5: `flags` (must be `0`)
- bytes 6-7: reserved (must be `0`)
- bytes 8-9: entry instruction index (`u16`, little-endian)
- bytes 10-11: instruction count (`u16`, little-endian)

Body:

- `instruction_count` records, each 4 bytes: `[opcode, a, b, c]`

## Opcodes (MVP)

- `0x00 NOP`
- `0x01 PUSH_CONST a` push signed int8 `a`
- `0x02 ADD` pop 2, push sum
- `0x03 SUB` pop 2, push lhs-rhs
- `0x04 MUL` pop 2, push product
- `0x05 DIV` pop 2, push integer floor division (`rhs != 0`)
- `0x06 JMP a` set IP to `a`
- `0x07 JZ a` pop value; if zero set IP to `a`
- `0x08 HALT` stop program
- `0x09 DUP` duplicate stack top
- `0x0A POP` pop stack top
- `0x0B PRINT_CHAR` pop byte and append ASCII char to output stream

## Validation Rules

- Header fields must match constraints.
- `entry < instruction_count`.
- Every instruction opcode must be recognized.
- Every static jump target must be in range.

## Execution Semantics

- Execution starts at `entry`.
- One instruction executes per step.
- Max steps default to 100000 to prevent runaway loops.
- Result is top of stack at halt; empty stack returns `null`.
- `PRINT_CHAR` emits text output as a side stream.

## ALP-Hello (MVP stub)

Out-of-scope for binary runtime, but reserved as JSON capability exchange:

```json
{
  "protocol": "ALP",
  "version": "0.1",
  "features": ["vm-stack-v1", "deterministic"],
  "targets": ["ref-vm"]
}
```

## Forward Compatibility

- Unknown flags/version rejected in MVP.
- Extension sections reserved for v0.2+.

## Raw Authoring Format (`.alpb`, MVP tooling)

For direct low-level authoring, OpenALP tooling accepts `.alpb`:

- Optional header line: `entry=<instruction_index>`
- One instruction per line: `opcode a b c` (4 byte values, decimal or `0x` hex)
- `#` starts a comment

Example:

```text
entry=0
0x01 72 0 0
0x0B 0 0 0
0x08 0 0 0
```

## Integrity and Signature Sidecars (MVP operational profile)

OpenALP MVP supports integrity/signature as sidecar manifests, not embedded module sections:

- `module.alp.sha256.json` (checksum)
- `module.alp.sig.json` (HMAC-SHA256 signature)
- `module.alp.rsa.sig.json` (demo RSA public-key signature)

Signature profile currently supports:

- shared-secret HMAC for low-friction rollout
- demo RSA for public-key workflow validation in the MVP

Production-grade asymmetric cryptography is planned for the next iteration.
