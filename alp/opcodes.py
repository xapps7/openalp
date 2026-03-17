from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Op:
    code: int
    name: str


OPCODES: dict[int, Op] = {
    0x00: Op(0x00, "NOP"),
    0x01: Op(0x01, "PUSH_CONST"),
    0x02: Op(0x02, "ADD"),
    0x03: Op(0x03, "SUB"),
    0x04: Op(0x04, "MUL"),
    0x05: Op(0x05, "DIV"),
    0x06: Op(0x06, "JMP"),
    0x07: Op(0x07, "JZ"),
    0x08: Op(0x08, "HALT"),
    0x09: Op(0x09, "DUP"),
    0x0A: Op(0x0A, "POP"),
    0x0B: Op(0x0B, "PRINT_CHAR"),
}


def opname(code: int) -> str:
    op = OPCODES.get(code)
    return op.name if op else f"UNKNOWN_{code:#04x}"
