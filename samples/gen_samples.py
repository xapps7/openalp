from __future__ import annotations

from pathlib import Path

from alp.format import Instruction, Module, VERSION, encode_module


ROOT = Path(__file__).resolve().parent


def write(name: str, instructions: list[Instruction], entry: int = 0) -> None:
    module = Module(version=VERSION, flags=0, entry=entry, instructions=tuple(instructions))
    (ROOT / name).write_bytes(encode_module(module))


def main() -> None:
    write(
        "add.alp",
        [
            Instruction(0x01, 7, 0, 0),
            Instruction(0x01, 5, 0, 0),
            Instruction(0x02, 0, 0, 0),
            Instruction(0x08, 0, 0, 0),
        ],
    )

    write(
        "countdown.alp",
        [
            Instruction(0x01, 3, 0, 0),
            Instruction(0x09, 0, 0, 0),
            Instruction(0x07, 7, 0, 0),
            Instruction(0x01, 1, 0, 0),
            Instruction(0x03, 0, 0, 0),
            Instruction(0x06, 1, 0, 0),
            Instruction(0x00, 0, 0, 0),
            Instruction(0x08, 0, 0, 0),
        ],
    )

    # if 0 -> push 42 else push 7
    write(
        "branch.alp",
        [
            Instruction(0x01, 0, 0, 0),
            Instruction(0x07, 5, 0, 0),
            Instruction(0x01, 7, 0, 0),
            Instruction(0x06, 6, 0, 0),
            Instruction(0x00, 0, 0, 0),
            Instruction(0x01, 42, 0, 0),
            Instruction(0x08, 0, 0, 0),
        ],
    )

    # planner-like bounded loop: (2+1)*4 => 12
    write(
        "planner_loop.alp",
        [
            Instruction(0x01, 2, 0, 0),
            Instruction(0x01, 1, 0, 0),
            Instruction(0x02, 0, 0, 0),
            Instruction(0x01, 4, 0, 0),
            Instruction(0x04, 0, 0, 0),
            Instruction(0x08, 0, 0, 0),
        ],
    )

    hello = "Hello\n"
    hello_instructions: list[Instruction] = []
    for ch in hello:
        hello_instructions.append(Instruction(0x01, ord(ch), 0, 0))
        hello_instructions.append(Instruction(0x0B, 0, 0, 0))
    hello_instructions.append(Instruction(0x08, 0, 0, 0))
    write("hello.alp", hello_instructions)


if __name__ == "__main__":
    main()
