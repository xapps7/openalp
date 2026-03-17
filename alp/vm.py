from __future__ import annotations

from dataclasses import dataclass

from .format import Module


class VMError(RuntimeError):
    pass


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
            stack.append(lhs + rhs)
        elif op == 0x03:  # SUB
            _require_stack(stack, 2, "SUB")
            rhs = stack.pop()
            lhs = stack.pop()
            stack.append(lhs - rhs)
        elif op == 0x04:  # MUL
            _require_stack(stack, 2, "MUL")
            rhs = stack.pop()
            lhs = stack.pop()
            stack.append(lhs * rhs)
        elif op == 0x05:  # DIV
            _require_stack(stack, 2, "DIV")
            rhs = stack.pop()
            lhs = stack.pop()
            if rhs == 0:
                raise VMError("division by zero")
            stack.append(lhs // rhs)
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
            if value < 0 or value > 255:
                raise VMError(f"PRINT_CHAR expects byte range 0..255, got {value}")
            output_chars.append(chr(value))
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
