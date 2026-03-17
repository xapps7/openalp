from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from alp.cli import main
from alp.format import Instruction, Module, VERSION, encode_module


class BundleTests(unittest.TestCase):
    def test_bundle_create_and_run(self) -> None:
        module = Module(
            version=VERSION,
            flags=0,
            entry=0,
            instructions=(
                Instruction(0x01, ord("O"), 0, 0),
                Instruction(0x0B, 0, 0, 0),
                Instruction(0x01, ord("K"), 0, 0),
                Instruction(0x0B, 0, 0, 0),
                Instruction(0x08, 0, 0, 0),
            ),
        )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            m = root / "m.alp"
            h = root / "hello.json"
            k = root / "k.key"
            b = root / "bundle.alpp.json"
            m.write_bytes(encode_module(module))
            h.write_text(json.dumps({"protocol": "ALP", "version": "0.1", "features": ["vm-stack-v1"], "targets": ["ref-vm"]}))
            k.write_text("secret-key")

            self.assertEqual(main(["checksum", "create", str(m)]), 0)
            self.assertEqual(main(["sign", "create", str(m), "--key", str(k)]), 0)

            rc = main([
                "bundle",
                "create",
                "--module",
                str(m),
                "--hello",
                str(h),
                "--checksum",
                str(m.with_suffix(".alp.sha256.json")),
                "--signature",
                str(m.with_suffix(".alp.sig.json")),
                "--key",
                str(k),
                "--out",
                str(b),
            ])
            self.assertEqual(rc, 0)

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = main(["bundle", "run", "--bundle", str(b), "--key", str(k)])
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["output"], "OK")
            self.assertTrue(payload["verified_checksum"])
            self.assertTrue(payload["verified_signature"])
            self.assertTrue(payload["compatible"])


if __name__ == "__main__":
    unittest.main()
