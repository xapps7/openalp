from __future__ import annotations

from .format import Module


def _as_i8(value: int) -> int:
    return value - 256 if value > 127 else value


def to_python_like(module: Module) -> str:
    lines: list[str] = []
    lines.append("# Decompiled from ALP v0.1")
    lines.append("stack = []")
    lines.append(f"ip = {module.entry}")
    lines.append("while True:")

    for idx, inst in enumerate(module.instructions):
        prefix = "if" if idx == 0 else "elif"
        lines.append(f"    {prefix} ip == {idx}:")

        op = inst.opcode
        if op == 0x00:
            lines.append("        ip += 1  # NOP")
        elif op == 0x01:
            lines.append(f"        stack.append({_as_i8(inst.a)})  # PUSH_CONST")
            lines.append("        ip += 1")
        elif op == 0x02:
            lines.append("        rhs = stack.pop(); lhs = stack.pop(); stack.append(lhs + rhs)  # ADD")
            lines.append("        ip += 1")
        elif op == 0x03:
            lines.append("        rhs = stack.pop(); lhs = stack.pop(); stack.append(lhs - rhs)  # SUB")
            lines.append("        ip += 1")
        elif op == 0x04:
            lines.append("        rhs = stack.pop(); lhs = stack.pop(); stack.append(lhs * rhs)  # MUL")
            lines.append("        ip += 1")
        elif op == 0x05:
            lines.append("        rhs = stack.pop(); lhs = stack.pop(); stack.append(lhs // rhs)  # DIV")
            lines.append("        ip += 1")
        elif op == 0x06:
            lines.append(f"        ip = {inst.a}  # JMP")
        elif op == 0x07:
            lines.append("        value = stack.pop()  # JZ")
            lines.append(f"        ip = {inst.a} if value == 0 else ip + 1")
        elif op == 0x08:
            lines.append("        break  # HALT")
        elif op == 0x09:
            lines.append("        stack.append(stack[-1])  # DUP")
            lines.append("        ip += 1")
        elif op == 0x0A:
            lines.append("        stack.pop()  # POP")
            lines.append("        ip += 1")
        elif op == 0x0B:
            lines.append("        print(chr(stack.pop()), end='')  # PRINT_CHAR")
            lines.append("        ip += 1")
        else:
            lines.append(f"        raise RuntimeError('unknown opcode: {op:#04x}')")

    lines.append("    else:")
    lines.append("        raise RuntimeError('ip out of range')")
    lines.append("result = stack[-1] if stack else None")

    return "\n".join(lines)
