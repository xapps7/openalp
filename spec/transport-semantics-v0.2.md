# OpenALP Transport Semantics v0.2

## Scope

This document defines how an ALP execution envelope is delivered, ordered, retried, and reported, independent of any concrete transport. It governs `spec/transport-envelope-v0.2.json`.

A transport is any mechanism that moves an envelope from a sender to a runtime. The runtime contract is identical whether the transport is an in-process call, a queue, a socket, or an HTTP endpoint.

## Separation Of Concerns

1. A bundle defines **what** executes.
2. An envelope defines **how it is delivered**.
3. A receipt defines **what happened**.

A transport must not alter payload bytes. A runtime must not depend on transport-specific fields.

## Determinism Constraints

Transport metadata must not introduce nondeterminism into execution identity.

1. `envelope_id` is content-derived, never random.
2. Envelopes carry no wall-clock timestamp.
3. Time budgets are expressed against a **logical clock** owned by the transport, advancing by a fixed increment per attempt.
4. `reply_to` and `trace` are excluded from envelope identity.

Consequence: replaying the same logical send always produces the same `envelope_id`, so deduplication works without coordination.

## Identity And Idempotency

`envelope_id` = first 32 hex characters of `sha256` over the canonical JSON of:

```json
{"payload_hash": "<payload.content_hash>", "sequence": <sequence>, "stream_id": "<stream_id>"}
```

`idempotency_key` defaults to `envelope_id`. A sender may override it to make two structurally different envelopes deduplicate to one execution.

Rules:

1. Delivery is **at-least-once**; execution is **effectively-once**.
2. A transport must retain a receipt per `idempotency_key`.
3. A second envelope with a known `idempotency_key` must not execute. It returns status `duplicate` carrying the original result.
4. Receipt retention is transport policy. A transport that drops receipts degrades to at-least-once execution and must declare that.

## Ordering

Ordering is guaranteed **within** a `stream_id` and undefined **across** `stream_id` values.

1. The first envelope accepted for a stream establishes the baseline sequence.
2. Subsequent envelopes must be contiguous: `sequence == last_delivered + 1`.
3. An envelope arriving ahead of its turn is **held pending**, not rejected, and is delivered when the gap fills.
4. An envelope whose `sequence` is at or below `last_delivered` is stale: it returns `duplicate` if its `idempotency_key` is known, otherwise `rejected` with reason `stale_sequence`.
5. Flushing a filled gap delivers pending envelopes in ascending sequence order before returning.

Head-of-line blocking is explicit and bounded by the sender: a sender that does not need ordering uses distinct `stream_id` values.

## Execution Status Model

| status | terminal | meaning |
| --- | --- | --- |
| `accepted` | no | envelope validated, awaiting its turn in the stream |
| `running` | no | execution in progress |
| `retrying` | no | transient failure, attempts remain |
| `succeeded` | yes | execution completed |
| `failed` | yes | execution failed permanently or exhausted attempts |
| `rejected` | yes | envelope invalid, incompatible, or stale; never executed |
| `expired` | yes | logical deadline exceeded |
| `duplicate` | yes | `idempotency_key` already resolved; prior result returned |

A transport must move every envelope to a terminal status.

## Error Classes

| class | retryable | examples |
| --- | --- | --- |
| `transient` | yes | runtime resource exhaustion, transport interruption |
| `permanent` | no | invalid module, checksum or signature failure, VM error |
| `protocol` | no | unsupported protocol version, incompatible module version, malformed envelope |

`protocol` and `permanent` failures must not be retried. Retrying them is a conformance violation.

## Retry Semantics

1. Only `transient` errors are retried.
2. Total executions must not exceed `max_attempts`.
3. Backoff is deterministic: `backoff_ms(n) = min(base_backoff_ms * 2^(n-1), max_backoff_ms)`.
4. The transport returns the computed backoff schedule in the receipt. It does not require the runtime to sleep; an in-process transport reports the schedule without waiting.
5. Attempts consume the logical clock, so retries can trigger `expired`.
6. Exhausting attempts yields `failed`, not `retrying`. The reason is prefixed `attempts_exhausted:` followed by the last underlying reason, so the cause is not lost.

## Deadlines

1. `deadline_ms` is compared against elapsed logical time for that envelope.
2. The deadline is checked before each attempt and after each failed attempt.
3. Exceeding it yields `expired`, which is terminal and not retryable.
4. `deadline_ms: null` disables the check.
5. How the clock advances is set by the transport clock policy below.

## Clock Policy

The logical clock is normative. Wall-clock time never appears in an envelope or a receipt. A transport declares how its logical clock advances.

| policy | advance per attempt | receipts reproducible |
| --- | --- | --- |
| `step` | fixed `clock_step_ms` | yes |
| `observed` | observed wall-clock elapsed, quantized | no |

### `step`

Used by in-process transports. The clock advances by a constant per attempt regardless of real duration. Two identical sends produce byte-identical receipts. This is the reference behavior and the basis for every conformance test.

### `observed`

Used by network transports, where a fixed step would make deadlines meaningless. Wall-clock elapsed is measured per attempt and mapped onto the logical budget:

```
advance_ms = max(quantum_ms, ceil(observed_ms / quantum_ms) * quantum_ms)
```

Rules:

1. The transport declares `quantum_ms` and must not vary it within a stream.
2. Quantization rounds **up**, so a deadline is never overrun by rounding.
3. Every attempt advances the clock by at least one quantum, so an arbitrarily fast transport cannot retry unboundedly inside a finite deadline.
4. The logical clock is monotonic non-decreasing. Backward wall-clock movement, from clock correction or a change of host, must not decrease it.
5. Measurement covers the attempt only. Time spent waiting in a queue before the first attempt is transport overhead and is out of scope for the envelope deadline; a transport that wishes to charge queue time must say so in its own conformance statement.

### Why quantization is required

Without it, every receipt from a network transport differs in `elapsed_ms`, so receipts cannot be diffed, cached, or compared across runs. Quantization trades deadline precision for comparability, which is the right trade for a protocol whose core claim is determinism.

### Determinism downgrade

A transport using `observed` must declare `deterministic_receipts: false`. This is a documented downgrade, not a violation.

What it does **not** affect:

1. `envelope_id`, which is content-derived and unchanged
2. idempotency, which keys on `idempotency_key`, not timing
3. ordering, which keys on `sequence`, not timing

Only `elapsed_ms`, `attempts` and terminal status under deadline pressure may vary between runs. Callers that require reproducible outcomes set `deadline_ms: null` and bound work with `max_attempts` instead.

## Receipt

A receipt is the machine-readable outcome of a delivery.

```json
{
  "envelope_id": "<32 hex>",
  "idempotency_key": "<string>",
  "stream_id": "<string>",
  "sequence": 0,
  "status": "succeeded",
  "attempts": 1,
  "backoff_schedule_ms": [],
  "elapsed_ms": 1,
  "result": {"output": "", "top": 12, "steps": 6},
  "error": null
}
```

On failure, `result` is `null` and `error` is:

```json
{"class": "permanent", "reason": "checksum verify failed"}
```

## Validation Order

A conforming transport validates in this fixed order and stops at the first failure:

1. envelope structure
2. protocol and protocol version governance
3. payload content hash
4. idempotency lookup
5. stream ordering
6. deadline
7. execution

Steps 1 through 3 failing yields `rejected` with class `protocol`. Step 5 failing stale yields `rejected` with reason `stale_sequence`.

## Conformance

A transport is conforming if it:

1. preserves payload bytes exactly
2. derives `envelope_id` per this document
3. executes at most once per `idempotency_key` while receipts are retained
4. preserves per-stream contiguous ordering
5. retries only `transient` errors, bounded by `max_attempts`
6. terminates every envelope in a terminal status
7. emits a receipt matching the shape above
8. declares its clock policy and, for `observed`, its `quantum_ms` and `deterministic_receipts: false`

## Reference Implementation

`alp/transport/local.py` provides `LocalTransport`, an in-process, deterministic, single-threaded reference transport. It is the conformance baseline for any future transport.
