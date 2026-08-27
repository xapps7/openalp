# OpenALP Runtime Semantics v0.2

## Deterministic Scheduling

1. Execution order is single-threaded and instruction-index ordered.
2. One instruction is applied per step.
3. `HALT` stops execution immediately after the current instruction.

## Failure Propagation

Runtime must fail hard and stop execution on:

1. stack underflow
2. division by zero
3. out-of-range instruction pointer
4. out-of-range jump target
5. invalid print byte
6. max step exhaustion

## Memory Mutation Rules

1. Only stack state may mutate during execution.
2. Instruction stream is immutable after module parsing.
3. Output is append-only and ordered by `PRINT_CHAR` execution.
4. No hidden external state is allowed in the reference VM.

## Trace Determinism

For a given module, protocol version, and max step budget:

1. step count must be reproducible
2. output must be reproducible
3. final stack state must be reproducible
4. trace event ordering must be reproducible
