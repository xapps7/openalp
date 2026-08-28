from __future__ import annotations

from dataclasses import dataclass

from .format import Module


class VMError(RuntimeError):
    pass


class VMTrap(VMError):
    """A deterministic, canonically identified execution trap.

    A trap is a normal outcome of execution, not an absence of one. It
    carries a stable code so two implementations can establish that they
    failed the same way. See decision D1-numeric-model in docs/status.json.
    """

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        super().__init__(f"{code}: {detail}" if detail else code)


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
    output: str
    trace: list[str] | None = None

    @property
    def top(self) -> int | None:
        return self.stack[-1] if self.stack else None


def _as_i8(value: int) -> int:
    """PUSH_CONST reads its operand as signed 8-bit, then widens to i64."""
    return value - 256 if value > 127 else value


def run_module(module: Module, max_steps: int = 100_000, trace: bool = False) -> VMResult:
    ip = module.entry
    steps = 0
    stack: list[int] = []
    halted = False
    output_chars: list[str] = []
    instrs = module.instructions
    trace_lines: list[str] | None = [] if trace else None

    while steps < max_steps:
        if ip >= len(instrs):
            raise VMError(f"instruction pointer out of range: {ip}")

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
            stack.append(wrap_i64(div_i64(lhs, rhs)))
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
            output_chars.append(chr(value & 0xFF))
        else:
            raise VMError(f"unknown opcode during execution: {op:#04x}")

        if trace_lines is not None:
            trace_lines.append(f"step={steps} ip={curr_ip} op={op:#04x} stack={stack}")

        if halted:
            break

    if not halted and steps >= max_steps:
        raise VMError(f"max steps exceeded ({max_steps})")

    return VMResult(
        halted=halted,
        steps=steps,
        stack=stack,
        output="".join(output_chars),
        trace=trace_lines,
    )


def _require_stack(stack: list[int], n: int, op: str) -> None:
    if len(stack) < n:
        raise VMError(f"stack underflow in {op}: need {n}, have {len(stack)}")
