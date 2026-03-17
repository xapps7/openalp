from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from alp.cli import main
from alp.format import Instruction, Module, VERSION, encode_module


class CLITests(unittest.TestCase):
    def test_validate_and_run(self) -> None:
        module = Module(
            version=VERSION,
            flags=0,
            entry=0,
            instructions=(
                Instruction(0x01, 4, 0, 0),
                Instruction(0x01, 5, 0, 0),
                Instruction(0x02, 0, 0, 0),
                Instruction(0x08, 0, 0, 0),
            ),
        )

        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "m.alp"
            p.write_bytes(encode_module(module))

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = main(["validate", str(p)])
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(buf.getvalue())["status"], "valid")

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = main(["run", str(p), "--trace", "--trace-limit", "2"])
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["top"], 9)
            self.assertEqual(len(payload["trace"]), 2)
            self.assertEqual(payload["output"], "")

    def test_handshake_validate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "hello.json"
            p.write_text(
                json.dumps(
                    {
                        "protocol": "ALP",
                        "version": "0.1",
                        "features": ["vm-stack-v1"],
                        "targets": ["ref-vm"],
                    }
                )
            )
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = main(["handshake", "validate", str(p)])
            self.assertEqual(rc, 0)
            self.assertTrue(json.loads(buf.getvalue())["compatible"])

    def test_decompile(self) -> None:
        module = Module(
            version=VERSION,
            flags=0,
            entry=0,
            instructions=(
                Instruction(0x01, 1, 0, 0),
                Instruction(0x08, 0, 0, 0),
            ),
        )
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "d.alp"
            p.write_bytes(encode_module(module))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = main(["decompile", str(p)])
            self.assertEqual(rc, 0)
            self.assertIn("Decompiled from ALP v0.1", buf.getvalue())

    def test_checksum_and_determinism(self) -> None:
        module = Module(
            version=VERSION,
            flags=0,
            entry=0,
            instructions=(
                Instruction(0x01, 2, 0, 0),
                Instruction(0x01, 6, 0, 0),
                Instruction(0x02, 0, 0, 0),
                Instruction(0x08, 0, 0, 0),
            ),
        )
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "z.alp"
            p.write_bytes(encode_module(module))

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = main(["checksum", "create", str(p)])
            self.assertEqual(rc, 0)
            manifest_payload = json.loads(buf.getvalue())
            self.assertEqual(manifest_payload["status"], "created")

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = main(["checksum", "verify", str(p)])
            self.assertEqual(rc, 0)
            self.assertTrue(json.loads(buf.getvalue())["valid"])

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = main(["determinism", "report", str(p), "--runs", "3"])
            self.assertEqual(rc, 0)
            self.assertTrue(json.loads(buf.getvalue())["consistent"])

    def test_sign_create_and_verify(self) -> None:
        module = Module(
            version=VERSION,
            flags=0,
            entry=0,
            instructions=(
                Instruction(0x01, 8, 0, 0),
                Instruction(0x08, 0, 0, 0),
            ),
        )
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "s.alp"
            k = Path(td) / "dev.key"
            p.write_bytes(encode_module(module))
            k.write_text("openalp-test-key")

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = main(["sign", "create", str(p), "--key", str(k)])
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(buf.getvalue())["status"], "created")

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = main(["sign", "verify", str(p), "--key", str(k)])
            self.assertEqual(rc, 0)
            self.assertTrue(json.loads(buf.getvalue())["valid"])

    def test_demo_rsa_keygen_and_sign_verify(self) -> None:
        module = Module(
            version=VERSION,
            flags=0,
            entry=0,
            instructions=(
                Instruction(0x01, 9, 0, 0),
                Instruction(0x08, 0, 0, 0),
            ),
        )
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "r.alp"
            prefix = Path(td) / "demo_rsa"
            p.write_bytes(encode_module(module))

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = main(["keygen-demo-rsa", str(prefix)])
            self.assertEqual(rc, 0)
            keys = json.loads(buf.getvalue())

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = main(["sign-rsa", "create", str(p), "--key", keys["private"]])
            self.assertEqual(rc, 0)

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = main(["sign-rsa", "verify", str(p), "--key", keys["public"]])
            self.assertEqual(rc, 0)
            self.assertTrue(json.loads(buf.getvalue())["valid"])


if __name__ == "__main__":
    unittest.main()
