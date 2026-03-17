from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from alp.format import parse_module
from alp.rawbuild import build_alpb_file
from alp.vm import run_module


class RawBuildTests(unittest.TestCase):
    def test_build_and_run_hello(self) -> None:
        src_text = """
entry=0
0x01 72 0 0
0x0B 0 0 0
0x01 105 0 0
0x0B 0 0 0
0x08 0 0 0
"""
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "hello.alpb"
            out = Path(td) / "hello.alp"
            src.write_text(src_text)

            build_alpb_file(src, out)
            module = parse_module(out.read_bytes())
            result = run_module(module)
            self.assertEqual(result.output, "Hi")


if __name__ == "__main__":
    unittest.main()
