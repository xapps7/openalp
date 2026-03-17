from __future__ import annotations

from dataclasses import dataclass

from .opcodes import OPCODES

MAGIC = b"ALP1"
VERSION = 1
HEADER_SIZE = 12
INSTR_SIZE = 4


class ALPFormatError(ValueError):
    pass


@dataclass(frozen=True)
class Instruction:
    opcode: int
    a: int
    b: int
    c: int


@dataclass(frozen=True)
class Module:
    version: int
    flags: int
    entry: int
    instructions: tuple[Instruction, ...]


def _read_u16_le(data: bytes, offset: int) -> int:
    return data[offset] | (data[offset + 1] << 8)


def parse_module(data: bytes) -> Module:
    if len(data) < HEADER_SIZE:
        raise ALPFormatError("module too small")
    if data[0:4] != MAGIC:
        raise ALPFormatError("invalid magic")

    version = data[4]
    flags = data[5]
    reserved = _read_u16_le(data, 6)
    entry = _read_u16_le(data, 8)
    count = _read_u16_le(data, 10)

    if version != VERSION:
        raise ALPFormatError(f"unsupported version {version}")
    if flags != 0:
        raise ALPFormatError("flags must be zero in MVP")
    if reserved != 0:
        raise ALPFormatError("reserved bytes must be zero")

    expected_len = HEADER_SIZE + count * INSTR_SIZE
    if len(data) != expected_len:
        raise ALPFormatError(
            f"size mismatch: expected {expected_len} bytes, got {len(data)}"
        )
    if count == 0:
        raise ALPFormatError("instruction count must be > 0")
    if entry >= count:
        raise ALPFormatError("entry out of range")

    instructions: list[Instruction] = []
    offset = HEADER_SIZE
    for _ in range(count):
        op, a, b, c = data[offset : offset + INSTR_SIZE]
        if op not in OPCODES:
            raise ALPFormatError(f"unknown opcode {op:#04x}")
        instructions.append(Instruction(op, a, b, c))
        offset += INSTR_SIZE

    for idx, inst in enumerate(instructions):
        if inst.opcode in (0x06, 0x07):
            target = inst.a
            if target >= count:
                raise ALPFormatError(f"jump target out of range at ip={idx}: {target}")

    return Module(
        version=version,
        flags=flags,
        entry=entry,
        instructions=tuple(instructions),
    )


def encode_module(module: Module) -> bytes:
    count = len(module.instructions)
    if count == 0:
        raise ALPFormatError("cannot encode empty module")
    if module.entry >= count:
        raise ALPFormatError("entry out of range")

    out = bytearray()
    out.extend(MAGIC)
    out.append(module.version)
    out.append(module.flags)
    out.extend((0).to_bytes(2, "little"))
    out.extend(module.entry.to_bytes(2, "little"))
    out.extend(count.to_bytes(2, "little"))

    for inst in module.instructions:
        if inst.opcode not in OPCODES:
            raise ALPFormatError(f"unknown opcode {inst.opcode:#04x}")
        out.extend(bytes((inst.opcode, inst.a, inst.b, inst.c)))

    return bytes(out)
