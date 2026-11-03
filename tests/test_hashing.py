from __future__ import annotations

"""The determinism invariant, as tests.

    same artifact + same execution profile = same canonical result hash

Each test below is one clause of that sentence. The interesting ones are
the negatives: changing something that MUST affect the hash, and changing
something that MUST NOT.
"""

import json
import subprocess
import sys
import unittest
from pathlib import Path

from alp.canonical import canonical_result
from alp.format import Instruction, Module, VERSION, encode_module
from alp.hashing import HASH_ALGORITHM, execute_and_hash, execution_hash
from alp.profile import ExecutionProfile
from alp.vm import VMTrap

PUSH, ADD, DIV, JMP, HALT, PRINT = 0x01, 0x02, 0x05, 0x06, 0x08, 0x0B
REPO = Path(__file__).parent.parent


def art(instrs):
    return encode_module(Module(version=VERSION, flags=0, entry=0, instructions=tuple(instrs)))


ADD_ART = art([Instruction(PUSH, 7, 0, 0), Instruction(PUSH, 5, 0, 0),
               Instruction(ADD, 0, 0, 0), Instruction(HALT, 0, 0, 0)])


class InvariantTests(unittest.TestCase):
    def test_same_artifact_same_profile_same_hash(self) -> None:
        profile = ExecutionProfile.default()
        a = execute_and_hash(ADD_ART, profile)[1]
        b = execute_and_hash(ADD_ART, profile)[1]
        self.assertEqual(a, b)

    def test_hash_is_prefixed_with_its_algorithm(self) -> None:
        _, digest = execute_and_hash(ADD_ART, ExecutionProfile.default())
        self.assertTrue(digest.startswith(f"{HASH_ALGORITHM}:"))
        self.assertEqual(len(digest.split(":")[1]), 64)

    def test_a_different_artifact_hashes_differently(self) -> None:
        other = art([Instruction(PUSH, 7, 0, 0), Instruction(PUSH, 6, 0, 0),
                     Instruction(ADD, 0, 0, 0), Instruction(HALT, 0, 0, 0)])
        profile = ExecutionProfile.default()
        self.assertNotEqual(execute_and_hash(ADD_ART, profile)[1], execute_and_hash(other, profile)[1])

    def test_a_different_profile_hashes_differently_even_when_the_result_matches(self) -> None:
        # The sharp case. Both runs produce an identical result; only the
        # budget differs. If the profile were not in the preimage these
        # would collide and the invariant would be unprovable.
        a_result, a_hash = execute_and_hash(ADD_ART, ExecutionProfile(step_budget=100))
        b_result, b_hash = execute_and_hash(ADD_ART, ExecutionProfile(step_budget=200))
        self.assertEqual(a_result.to_dict(), b_result.to_dict())
        self.assertNotEqual(a_hash, b_hash)

    def test_an_artifact_that_traps_still_has_a_hash(self) -> None:
        trapping = art([Instruction(PUSH, 4, 0, 0), Instruction(PUSH, 0, 0, 0),
                        Instruction(DIV, 0, 0, 0), Instruction(HALT, 0, 0, 0)])
        result, digest = execute_and_hash(trapping, ExecutionProfile.default())
        self.assertEqual(result.outcome, "trap")
        self.assertEqual(result.trap_code, "trap.div_by_zero")
        self.assertTrue(digest.startswith("sha256:"))

    def test_different_traps_hash_differently(self) -> None:
        profile = ExecutionProfile.default()
        underflow = art([Instruction(ADD, 0, 0, 0), Instruction(HALT, 0, 0, 0)])
        div_zero = art([Instruction(PUSH, 4, 0, 0), Instruction(PUSH, 0, 0, 0),
                        Instruction(DIV, 0, 0, 0), Instruction(HALT, 0, 0, 0)])
        self.assertNotEqual(execute_and_hash(underflow, profile)[1],
                            execute_and_hash(div_zero, profile)[1])

    def test_trap_detail_does_not_affect_the_hash(self) -> None:
        # Section 6.4: the code is the identity, the message is not. If
        # wording entered the hash, improving an error message would break
        # every recorded hash.
        profile = ExecutionProfile.default()
        a = execution_hash(ADD_ART, profile, canonical_result(VMTrap("trap.div_by_zero", "divisor is zero", 2, (), b"")))
        b = execution_hash(ADD_ART, profile, canonical_result(VMTrap("trap.div_by_zero", "reworded later", 2, (), b"")))
        self.assertEqual(a, b)

    def test_output_bytes_affect_the_hash(self) -> None:
        profile = ExecutionProfile.default()
        quiet = art([Instruction(PUSH, 65, 0, 0), Instruction(HALT, 0, 0, 0)])
        loud = art([Instruction(PUSH, 65, 0, 0), Instruction(PRINT, 0, 0, 0), Instruction(HALT, 0, 0, 0)])
        self.assertNotEqual(execute_and_hash(quiet, profile)[1], execute_and_hash(loud, profile)[1])


class CrossProcessTests(unittest.TestCase):
    """A hash computed in a fresh interpreter must match one computed here.

    This is the closest a single-implementation suite can get to the
    cross-implementation claim: no process-local state may leak in.
    """

    def test_hash_is_stable_across_processes(self) -> None:
        here = execute_and_hash(ADD_ART, ExecutionProfile.default())[1]
        out = subprocess.run(
            [sys.executable, "-m", "alp.cli", "hash", str(REPO / "samples" / "add.alp")],
            cwd=REPO, capture_output=True, text=True,
            env={"PYTHONPATH": str(REPO), "PATH": "/usr/bin:/bin", "PYTHONPYCACHEPREFIX": "/tmp/alp-pycache-test"},
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout)["hash"], here)

    def test_hash_does_not_depend_on_the_file_path(self) -> None:
        # Section 6 of CANONICAL_ENCODING: paths are not encoded.
        import shutil, tempfile

        with tempfile.TemporaryDirectory() as td:
            copied = Path(td) / "renamed-entirely.alp"
            shutil.copy(REPO / "samples" / "add.alp", copied)
            from alp.hashing import hash_module_file

            a = hash_module_file(REPO / "samples" / "add.alp", ExecutionProfile.default())[1]
            b = hash_module_file(copied, ExecutionProfile.default())[1]
            self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
