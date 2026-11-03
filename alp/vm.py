from __future__ import annotations

from dataclasses import dataclass

from .format import Module
from .profile import ExecutionProfile


class VMError(RuntimeError):
    pass


class VMTrap(VMError):
    """A deterministic, canonically identified execution trap.

    A trap is a normal outcome of execution, not an absence of one. It
    carries a stable code so two implementations can establish that they
    failed the same way. See decision D1-numeric-model in docs/status.json.
    """

    def __init__(
        self,
        code: str,
        detail: str = "",
        steps: int = 0,
        stack: tuple[int, ...] = (),
        output: bytes = b"",
        profile: "ExecutionProfile | None" = None,
    ) -> None:
        self.code = code
        self.detail = detail
        # State at the moment of the trap. A trap is an outcome with a
        # result, so the partial state must survive rather than be
        # discarded with the exception (canonical encoding needs it).
        self.steps = steps
        self.stack = stack
        self.output = output
        self.profile = profile
        super().__init__(f"{code}: {detail}" if detail else code)


# F5: the closed set of canonical trap codes. A trap is an identified,
# comparable outcome of execution, not an absence of one. Two conforming
# implementations must agree on which of these a given execution produces.
TRAP_CODES = (
    "trap.stack_underflow",
    "trap.div_by_zero",
    "trap.div_overflow",
    "trap.invalid_opcode",
    "trap.ip_out_of_range",
    "trap.step_budget_exceeded",
)


# D1-numeric-model: values are 64-bit two's complement integers.
INT64_MIN = -(1 << 63)
INT64_MAX = (1 << 63) - 1
_UINT64_MASK = (1 << 64) - 1


def wrap_i64(value: int) -> int:
    """Reduce an integer into the i64 range, wrapping modulo 2**64.

    ADD, SUB and MUL are defined modulo 2**64 and never trap, so every
    arithmetic result passes through here. Without this the VM computes in
    Python's arbitrary-precision integers and disagrees with any
    implementation in C, Rust, Go or WASM (finding F1).
    """
    value &= _UINT64_MASK
    return value - (1 << 64) if value > INT64_MAX else value


def div_i64(lhs: int, rhs: int) -> int:
    """Signed division truncating toward zero.

    Python's // floors toward negative infinity, so -7 // 2 is -4 where
    every other candidate implementation language gives -3 (finding F2).
    """
    if rhs == 0:
        raise VMTrap("trap.div_by_zero", "divisor is zero")
    if lhs == INT64_MIN and rhs == -1:
        raise VMTrap("trap.div_overflow", "quotient is not representable in i64")
    quotient = abs(lhs) // abs(rhs)
    return -quotient if (lhs < 0) != (rhs < 0) else quotient


@dataclass
class VMResult:
    halted: bool
    steps: int
    stack: list[int]
    output: bytes
    profile: ExecutionProfile | None = None
    trace: list[str] | None = None

    @property
    def top(self) -> int | None:
        return self.stack[-1] if self.stack else None


def _as_i8(value: int) -> int:
    """PUSH_CONST reads its operand as signed 8-bit, then widens to i64."""
    return value - 256 if value > 127 else value


def run_module(module: Module, profile: ExecutionProfile, trace: bool = False) -> VMResult:
    """Execute a module under an explicit profile.

    There is deliberately no budget argument and no default: D2 makes the
    step budget part of the profile, so every execution records the budget
    it ran under. See alp/profile.py.
    """
    max_steps = profile.step_budget
    ip = module.entry
    steps = 0
    stack: list[int] = []
    halted = False
    output_bytes = bytearray()
    instrs = module.instructions
    trace_lines: list[str] | None = [] if trace else None

    while steps < max_steps:
        if ip >= len(instrs):
            raise VMTrap("trap.ip_out_of_range", f"ip={ip}", steps, tuple(stack), bytes(output_bytes), profile)

        curr_ip = ip
        inst = instrs[ip]
        op = inst.opcode
        ip += 1
        steps += 1

        if op == 0x00:  # NOP
            pass
        elif op == 0x01:  # PUSH_CONST
            stack.append(_as_i8(inst.a))
        elif op == 0x02:  # ADD
            _require_stack(stack, 2, "ADD")
            rhs = stack.pop()
            lhs = stack.pop()
            stack.append(wrap_i64(lhs + rhs))
        elif op == 0x03:  # SUB
            _require_stack(stack, 2, "SUB")
            rhs = stack.pop()
            lhs = stack.pop()
            stack.append(wrap_i64(lhs - rhs))
        elif op == 0x04:  # MUL
            _require_stack(stack, 2, "MUL")
            rhs = stack.pop()
            lhs = stack.pop()
            stack.append(wrap_i64(lhs * rhs))
        elif op == 0x05:  # DIV
            _require_stack(stack, 2, "DIV")
            rhs = stack.pop()
            lhs = stack.pop()
            try:
                quotient = div_i64(lhs, rhs)
            except VMTrap as trap:
                raise VMTrap(trap.code, trap.detail, steps, tuple(stack), bytes(output_bytes), profile) from None
            stack.append(wrap_i64(quotient))
        elif op == 0x06:  # JMP
            ip = inst.a
        elif op == 0x07:  # JZ
            _require_stack(stack, 1, "JZ")
            value = stack.pop()
            if value == 0:
                ip = inst.a
        elif op == 0x08:  # HALT
            halted = True
        elif op == 0x09:  # DUP
            _require_stack(stack, 1, "DUP")
            stack.append(stack[-1])
        elif op == 0x0A:  # POP
            _require_stack(stack, 1, "POP")
            stack.pop()
        elif op == 0x0B:  # PRINT_CHAR
            _require_stack(stack, 1, "PRINT_CHAR")
            value = stack.pop()
            # D1: total over the whole i64 range. Emits the low 8 bits, so
            # bytes 128-255 are reachable, which they were not while
            # PUSH_CONST sign-extended and PRINT_CHAR demanded 0..255 (F3).
            output_bytes.append(value & 0xFF)
        else:
            raise VMTrap("trap.invalid_opcode", f"opcode={op:#04x}", steps, tuple(stack), bytes(output_bytes), profile)

        if trace_lines is not None:
            trace_lines.append(f"step={steps} ip={curr_ip} op={op:#04x} stack={stack}")

        if halted:
            break

    if not halted and steps >= max_steps:
        raise VMTrap("trap.step_budget_exceeded", f"step_budget={max_steps}", steps, tuple(stack), bytes(output_bytes), profile)

    return VMResult(
        halted=halted,
        steps=steps,
        stack=stack,
        output=bytes(output_bytes),
        profile=profile,
        trace=trace_lines,
    )


def _require_stack(stack: list[int], n: int, op: str) -> None:
    if len(stack) < n:
        raise VMTrap("trap.stack_underflow", f"{op} needs {n}, have {len(stack)}", stack=tuple(stack))
