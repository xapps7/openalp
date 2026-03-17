from __future__ import annotations

from pathlib import Path

from .format import ALPFormatError, Instruction, Module, VERSION, encode_module


class RawBuildError(ValueError):
    pass


def _parse_u8(token: str) -> int:
    token = token.strip()
    if token.lower().startswith("0x"):
        value = int(token, 16)
    else:
        value = int(token, 10)
    if value < 0 or value > 255:
        raise RawBuildError(f"byte out of range 0..255: {token}")
    return value


def parse_alpb_text(text: str) -> Module:
    entry = 0
    instructions: list[Instruction] = []

    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue

        if line.lower().startswith("entry="):
            if instructions:
                raise RawBuildError(f"entry must be declared before instructions (line {lineno})")
            value = line.split("=", 1)[1].strip()
            try:
                entry = int(value, 10)
            except ValueError as exc:
                raise RawBuildError(f"invalid entry value at line {lineno}: {value}") from exc
            if entry < 0:
                raise RawBuildError(f"entry must be >= 0 (line {lineno})")
            continue

        parts = line.split()
        if len(parts) != 4:
            raise RawBuildError(f"line {lineno}: expected 4 byte values, got {len(parts)}")

        try:
            op, a, b, c = (_parse_u8(parts[0]), _parse_u8(parts[1]), _parse_u8(parts[2]), _parse_u8(parts[3]))
        except ValueError as exc:
            raise RawBuildError(f"line {lineno}: invalid number") from exc

        instructions.append(Instruction(opcode=op, a=a, b=b, c=c))

    if not instructions:
        raise RawBuildError("no instructions found")

    if entry >= len(instructions):
        raise RawBuildError(f"entry out of range: {entry} >= {len(instructions)}")

    return Module(version=VERSION, flags=0, entry=entry, instructions=tuple(instructions))


def build_alpb_file(src: Path, out: Path) -> None:
    module = parse_alpb_text(src.read_text())
    try:
        payload = encode_module(module)
    except ALPFormatError as exc:
        raise RawBuildError(str(exc)) from exc
    out.write_bytes(payload)
