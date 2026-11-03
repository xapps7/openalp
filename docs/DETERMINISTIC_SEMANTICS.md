# OpenALP Deterministic Execution Semantics v0.3

Status: active. Supersedes the informal notes in `spec/runtime-semantics-v0.2.md`.

## 0. Purpose and the invariant

This document defines what it means for an OpenALP module to execute deterministically, in enough detail that a second implementation in another language can be checked against the first.

The invariant:

> same artifact + same execution profile = same canonical result

An *artifact* is the module bytes. An *execution profile* is everything outside the artifact that can affect the result, defined in §7. There is no third input: modules are closed computations (decision D2).

What this invariant is not: `alp determinism report` runs a module repeatedly in one process and compares outputs. That demonstrates repeatability within one implementation. It says nothing about agreement between two. Only §1–§8 can give that.

Canonical byte encoding of artifact, profile and result is specified separately in `CANONICAL_ENCODING.md`. This document defines *behaviour*; that one defines *bytes*.

## 1. Execution model

A conforming implementation is a stack machine over 64-bit signed integers.

1. Execution state is exactly: an instruction pointer, one operand stack, an append-only output buffer, and a step counter. There MUST be no other observable state.
2. The instruction stream MUST be immutable after parsing. No instruction may modify the program.
3. Execution begins at the `entry` index recorded in the module header.
4. One step executes exactly one instruction. The step counter increments once per instruction executed, before that instruction's effects.
5. The instruction pointer advances by exactly one instruction after each step, except where `JMP` or `JZ` assign it (§2).
6. `HALT` terminates execution normally. The result is the state at that moment.
7. Execution that is neither halted nor trapped when the step counter reaches the profile's `step_budget` MUST trap as `trap.step_budget_exceeded` (§6).
8. An instruction pointer outside the instruction stream MUST trap as `trap.ip_out_of_range`. Running off the end of a module whose last instruction is not `HALT` is this case, not a normal halt.
9. An opcode outside the defined set MUST trap as `trap.invalid_opcode`. Implementations MUST NOT treat unknown opcodes as no-ops.

## 2. Ordering rules

1. Execution is strictly sequential. Instructions take effect one at a time, in instruction-pointer order.
2. Effects within a step are ordered: operands are popped, the operation is applied, the result (if any) is pushed. A trap raised mid-step leaves no partial push.
3. For every binary operation, **the top of the stack is the right-hand operand** and the element beneath it is the left-hand operand. So for a stack `[a, b]` with `b` on top, `SUB` computes `a - b` and `DIV` computes `a / b`. This is observable for `SUB` and `DIV` and MUST NOT be reversed.
4. The output buffer is append-only. Bytes appear in the order their `PRINT_CHAR` instructions executed. Nothing may reorder, buffer or coalesce output in a way that changes that order.
5. `JMP` and `JZ` assign the instruction pointer absolutely, as an index into the instruction stream — not a byte offset and not a relative displacement.
6. `JZ` pops its condition value before testing it, and pops it whether or not the branch is taken.

## 3. Memory model

1. There is one operand stack. There is no heap, no register file, no local variable slots and no addressable memory. A module cannot observe or modify storage outside its own stack.
2. The stack is LIFO and holds i64 values only. There is no other value type — no floats, no pointers, no aggregates, no distinct boolean.
3. Reading or popping beyond the stack's depth MUST trap as `trap.stack_underflow`. An implementation MUST NOT read an undefined value.
4. Stack depth needs no separate bound. Every instruction that grows the stack costs one step, so depth is bounded above by `step_budget`. A conforming implementation MUST NOT impose a lower limit of its own, because doing so would make a module trap on one implementation and succeed on another.
5. The stack's full contents are part of the result, not only its top. Two executions agreeing on the top value but differing in depth are different results.

## 4. Numeric behaviour

Decision D1. The model is 64-bit two's complement, matching WebAssembly.

1. A value is an integer in `[-2^63, 2^63 - 1]`. There is no other numeric width or type.
2. `ADD`, `SUB` and `MUL` compute modulo `2^64` and reinterpret the result as signed. They MUST wrap. They MUST NOT trap, saturate, or widen.
3. `DIV` is signed division truncating toward zero. `-7 / 2` is `-3`, not `-4`. Implementations MUST NOT floor.
4. `DIV` MUST trap as `trap.div_by_zero` when the divisor is zero.
5. `DIV` MUST trap as `trap.div_overflow` when the dividend is `-2^63` and the divisor is `-1`, because the true quotient is not representable.
6. `PUSH_CONST` reads its 8-bit operand as a signed value and sign-extends it to 64 bits. Operand `200` pushes `-56`.
7. `PRINT_CHAR` appends the low 8 bits of its operand, taken as unsigned. It is total over the whole i64 range and MUST NOT trap. Every byte value `0–255` is therefore reachable.

## 5. Output

1. Output is a sequence of bytes. It is not text. It has no encoding, no character set, and no line discipline.
2. Nothing in the execution model interprets output. It is accumulated and returned.

**Known deviation.** The reference implementation currently accumulates Python `str` code points rather than bytes, so a value above 127 serialises as a multi-byte character instead of one byte. `tests/test_numeric.py` presently asserts that behaviour, which makes the suite encode the wrong rule. Tracked as finding F7 and fixed in `p1-canonical-encoding`, which must change both the runtime and those assertions. Until then the rule above is normative and the implementation does not meet it.

## 6. Error propagation

1. A trap is a normal, identified outcome of execution — not an absence of one. Execution that traps has a result, and that result is comparable between implementations.
2. Every trap carries a code from this closed set:

| Code | Raised when |
| --- | --- |
| `trap.stack_underflow` | an operation needs more operands than the stack holds |
| `trap.div_by_zero` | `DIV` with a zero divisor |
| `trap.div_overflow` | `DIV` computing `-2^63 / -1` |
| `trap.invalid_opcode` | an opcode outside the defined set |
| `trap.ip_out_of_range` | the instruction pointer leaves the instruction stream |
| `trap.step_budget_exceeded` | the step counter reaches the profile's `step_budget` |

3. Implementations MUST NOT add codes to this set, and MUST NOT report a trap with a code outside it. Extending the set is a protocol version change.
4. A trap code is the comparable identity. Any human-readable detail accompanying it is non-normative and MUST NOT enter any hash or comparison.
5. A trap is terminal. There is no handler, no recovery, no resumption, and no way for a module to observe that a trap occurred.
6. Two conforming implementations given the same artifact and profile MUST trap with the same code at the same step count.

**Known deviation.** The reference implementation raises traps as exceptions and so discards the output buffer and stack produced before the trap. A trap's canonical result is specified in `p1-result-hash`; until then a failing execution is not yet hashable.

## 7. External interaction

1. The deterministic core is closed. A module MUST NOT be able to observe or affect anything outside its own execution state.
2. Specifically forbidden to a conforming implementation: wall-clock or monotonic time, random or entropy sources, environment variables, filesystem access, network access, inter-process communication, host callbacks, and any form of foreign function interface.
3. `PRINT_CHAR` is not external interaction. It appends to a buffer that forms part of the result.
4. The host's entire interface is: supply an artifact, supply a profile, receive a result. Nothing passes in the other direction during execution.
5. The execution profile is the only non-artifact input, and consists of:

| Field | Meaning |
| --- | --- |
| `profile_version` | version of the profile format itself |
| `protocol_version` | ALP protocol version, governed by `alp-governance-v0.2.md` |
| `module_format_version` | module format the artifact must declare |
| `step_budget` | maximum steps; required, with no default |

6. `step_budget` MUST be present. An implementation MUST NOT execute with an implicit or built-in budget, because the same artifact halts under one budget and traps under another (finding F4). A host MAY select a named profile on a caller's behalf, but MUST record the profile it used alongside the result.
7. Any future input mechanism is a new profile field and a new protocol version. It MUST NOT change the result of an artifact executed under an earlier profile version.

## 8. Concurrency

1. Execution is strictly sequential. There are no concurrency primitives, no threads, no coroutines, no asynchrony and no shared state.
2. A conforming implementation MUST NOT introduce observable parallelism. Internal optimisation is permitted only where no execution is distinguishable from the sequential semantics above — including in step counts, trap codes and output order.
3. Concurrent execution of *separate* modules is outside this document. Two executions share nothing, so running many at once cannot affect any one result.
4. This clause exists so that a later implementation cannot add parallelism and still claim conformance. Its absence was finding F8.

## 9. Conformance

An implementation conforms when it:

1. implements §1–§8 exactly, including the ordering details in §2.3 and §2.6;
2. produces identical results to the reference implementation for every golden vector (`p1-golden-vectors`);
3. reports traps only from the §6.2 set, with matching code and step count;
4. refuses to execute without a complete profile;
5. introduces no state, input or effect beyond §1.1 and §7.

Partial conformance is not conformance. An implementation that differs on one ordering rule produces different hashes and is not interchangeable.

## 10. Traceability

Every normative statement must have a test that fails when it is violated. That mapping is **not** maintained here, because a hand-kept table drifts from the tests it claims to describe.

It lives in `spec/conformance-map.json`, section by section, and `tests/test_normative_coverage.py` enforces it:

1. A normative statement with no entry in the map fails the suite. A new rule must be triaged, not silently unenforced.
2. A map entry pointing at a test that does not exist fails the suite.
3. A map entry pointing at a section with no normative statement fails the suite, so the map cannot outlive the prose.
4. An entry with no tests must carry a reason, and the number of such entries is ratcheted: it may fall and must never rise.

As of 2026-11-03: 28 normative sections mapped, 5 unenforced, each with a stated reason. Those five are §1.2 (instruction stream immutability), §3.4 (absence of an implementation stack limit), §7.7 (older profile versions), §8.2 (unobservable optimisation), and `CANONICAL_ENCODING.md` §2.3 (ignored operand bytes affecting the hash).

Two further entries are marked partial rather than complete, and it is worth being explicit about why. §6.6 requires that two conforming implementations agree; a fresh process and a recorded vector corpus stand in for the second implementation, which is the best a single-implementation suite can do. §7.1 forbids all external interaction; the tests prove paths do not leak in, but nothing proves the absence of clock or entropy access. Both close properly only when a second implementation exists.
