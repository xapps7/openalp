from __future__ import annotations

"""Golden vectors: the artifact a second implementation is checked against.

These are stored in spec/golden/ rather than samples/ on purpose.
samples/gen_samples.py rewrites samples/ from the code under test, so a
vector living there would be regenerated to match whatever the code did
and could never fail.

Never regenerate these to make a test pass.
"""

import json
import unittest
from pathlib import Path

from alp.hashing import execute_and_hash
from alp.profile import parse_profile
from alp.vm import TRAP_CODES

GOLDEN = Path(__file__).parent.parent / "spec" / "golden" / "vectors.json"
MANIFEST = json.loads(GOLDEN.read_text())
VECTORS = MANIFEST["vectors"]


class GoldenVectorTests(unittest.TestCase):
    def test_every_vector_reproduces_its_recorded_result_and_hash(self) -> None:
        for vector in VECTORS:
            with self.subTest(vector=vector["id"]):
                artifact = bytes.fromhex(vector["artifact_hex"])
                profile = parse_profile(vector["profile"])
                result, digest = execute_and_hash(artifact, profile)
                self.assertEqual(result.to_dict(), vector["expected_result"], vector["why"])
                self.assertEqual(digest, vector["expected_hash"], vector["why"])

    def test_the_corpus_is_not_trivially_small(self) -> None:
        self.assertGreaterEqual(len(VECTORS), 15)

    def test_vector_ids_are_unique(self) -> None:
        ids = [v["id"] for v in VECTORS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_vector_explains_why_it_exists(self) -> None:
        for vector in VECTORS:
            with self.subTest(vector=vector["id"]):
                self.assertTrue(vector["why"].strip())


class CoverageTests(unittest.TestCase):
    """The vectors must cover the edges, not the happy path."""

    def _ids(self) -> set[str]:
        return {v["id"] for v in VECTORS}

    def test_numeric_edges_are_covered(self) -> None:
        for required in ("wrap-mul-overflow", "wrap-add-to-int64-min",
                         "div-negative-truncates-toward-zero", "div-both-negative"):
            self.assertIn(required, self._ids())

    def test_int64_min_is_actually_reached(self) -> None:
        vector = next(v for v in VECTORS if v["id"] == "wrap-add-to-int64-min")
        self.assertEqual(vector["expected_result"]["stack"], [-(2 ** 63)])

    def test_negative_division_truncates_toward_zero(self) -> None:
        vector = next(v for v in VECTORS if v["id"] == "div-negative-truncates-toward-zero")
        self.assertEqual(vector["expected_result"]["stack"], [-3])

    def test_the_whole_byte_range_is_covered(self) -> None:
        vector = next(v for v in VECTORS if v["id"] == "output-all-256-bytes")
        output = bytes.fromhex(vector["expected_result"]["output_hex"])
        self.assertEqual(output, bytes(range(256)))

    def test_budget_boundary_is_covered_on_both_sides(self) -> None:
        fit = next(v for v in VECTORS if v["id"] == "budget-exact-fit")
        short = next(v for v in VECTORS if v["id"] == "budget-one-short")
        self.assertEqual(fit["expected_result"]["outcome"], "halted")
        self.assertEqual(short["expected_result"]["trap_code"], "trap.step_budget_exceeded")
        self.assertEqual(fit["profile"]["step_budget"], short["profile"]["step_budget"] + 1)

    def test_every_reachable_trap_code_has_a_vector(self) -> None:
        covered = set(MANIFEST["trap_codes_covered"])
        unreachable = set(MANIFEST["trap_codes_not_covered"])
        self.assertEqual(covered | unreachable, set(TRAP_CODES))

    def test_the_unreachable_trap_is_documented_not_merely_missing(self) -> None:
        for code, reason in MANIFEST["trap_codes_not_covered"].items():
            with self.subTest(code=code):
                self.assertIn(code, TRAP_CODES)
                self.assertGreater(len(reason), 60)

    def test_vectors_live_outside_samples(self) -> None:
        self.assertNotIn("samples", GOLDEN.parts)


if __name__ == "__main__":
    unittest.main()
