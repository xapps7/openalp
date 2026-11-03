from __future__ import annotations

"""Cross-implementation agreement, against a real second implementation.

DETERMINISTIC_SEMANTICS.md section 6.6 requires that two conforming
implementations given the same artifact and profile produce the same
result and the same hash. Until now that clause was enforced only by a
fresh Python process and a recorded corpus, which is a weak stand-in: the
runtime and its tests were written together, so they agreed with each
other by construction.

impl/c/alpvm.c is an independent implementation written from the
specification text. It found a real divergence on its first run --
`trap.stack_underflow` was recorded with `steps: 0` where the spec
requires 1 -- and the Python side was wrong. See the `corrections`
section of spec/golden/vectors.json.

These tests build it and run every golden vector through it. They skip
rather than fail where no C compiler exists, because a missing toolchain
is not a conformance failure.
"""

import json
import shutil
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).parent.parent
SOURCE = REPO / "impl" / "c" / "alpvm.c"
BINARY = REPO / "impl" / "c" / "alpvm"
VECTORS = json.loads((REPO / "spec" / "golden" / "vectors.json").read_text())
CC = shutil.which("cc") or shutil.which("gcc")


def build() -> bool:
    if not CC or not SOURCE.exists():
        return False
    out = subprocess.run([CC, "-O2", "-std=c99", "-o", str(BINARY), str(SOURCE)],
                         capture_output=True, text=True)
    return out.returncode == 0


@unittest.skipUnless(CC and SOURCE.exists(), "no C compiler, or the second implementation is absent")
class SecondImplementationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not build():
            raise unittest.SkipTest("the second implementation did not build")

    def _run(self, vector) -> dict:
        out = subprocess.run(
            [str(BINARY),
             "--artifact-hex", vector["artifact_hex"],
             "--step-budget", str(vector["profile"]["step_budget"]),
             "--protocol-version", vector["profile"]["protocol_version"],
             "--module-format-version", str(vector["profile"]["module_format_version"])],
            capture_output=True, text=True,
        )
        self.assertEqual(out.returncode, 0, f"{vector['id']}: {out.stderr.strip()}")
        return json.loads(out.stdout)

    def test_it_builds_without_warnings(self) -> None:
        out = subprocess.run([CC, "-O2", "-std=c99", "-Wall", "-Wextra",
                              "-o", str(BINARY), str(SOURCE)],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)

    def test_both_implementations_agree_on_every_result(self) -> None:
        for vector in VECTORS["vectors"]:
            with self.subTest(vector=vector["id"]):
                self.assertEqual(self._run(vector)["result"], vector["expected_result"], vector["why"])

    def test_both_implementations_agree_on_every_hash(self) -> None:
        # The stronger claim: agreeing on the result is not enough, they
        # must agree on the serialization too.
        for vector in VECTORS["vectors"]:
            with self.subTest(vector=vector["id"]):
                self.assertEqual(self._run(vector)["hash"], vector["expected_hash"], vector["why"])

    def test_the_second_implementation_rejects_non_canonical_artifacts(self) -> None:
        # Section 2 of CANONICAL_ENCODING: reject, never normalize.
        good = VECTORS["vectors"][0]
        for label, mutate in (
            ("trailing byte", lambda h: h + "00"),
            ("nonzero flags", lambda h: h[:10] + "01" + h[12:]),
            ("nonzero reserved", lambda h: h[:12] + "01" + h[14:]),
            ("bad magic", lambda h: "00" + h[2:]),
        ):
            with self.subTest(case=label):
                out = subprocess.run(
                    [str(BINARY), "--artifact-hex", mutate(good["artifact_hex"]),
                     "--step-budget", "1000"],
                    capture_output=True, text=True,
                )
                self.assertNotEqual(out.returncode, 0, f"{label} was accepted")

    def test_it_refuses_to_run_without_a_budget(self) -> None:
        # Section 7.6: no implicit budget, in either implementation.
        out = subprocess.run([str(BINARY), "--artifact-hex", VECTORS["vectors"][0]["artifact_hex"]],
                             capture_output=True, text=True)
        self.assertNotEqual(out.returncode, 0)


class CorrectionRecordTests(unittest.TestCase):
    """The divergence it found must stay documented, not quietly absorbed."""

    def test_the_correction_is_recorded_with_its_evidence(self) -> None:
        corrections = VECTORS.get("corrections")
        self.assertIsNotNone(corrections, "the stack-underflow correction record is missing")
        self.assertTrue(corrections["entries"])
        self.assertIn("impl/c", corrections["found_by"])
        self.assertTrue(corrections["deciding_clauses"])
        for entry in corrections["entries"]:
            with self.subTest(vector=entry["vector"]):
                self.assertNotEqual(entry["was"]["expected_hash"], entry["now"]["expected_hash"])

    def test_the_corrected_vector_now_records_the_trapping_step(self) -> None:
        vector = next(v for v in VECTORS["vectors"] if v["id"] == "trap-stack-underflow")
        self.assertEqual(vector["expected_result"]["steps"], 1)


if __name__ == "__main__":
    unittest.main()
