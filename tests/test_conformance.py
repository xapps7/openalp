from __future__ import annotations

"""Conformance against frozen artifacts.

Why this file exists: samples/gen_samples.py rewrites samples/ from the
code under test, and scripts/quality_gate.sh runs it first. So every
other test validates the binary format against the same code that
produced it. If the encoding changed, the samples would regenerate to
match and the whole suite would stay green while every previously
published .alp file quietly became unreadable.

The artifacts in tests/fixtures/v0.2.0/ were captured at a known-good
commit and are never regenerated. They are the only thing in the repo
that can fail when the format drifts.

If a test here fails, do NOT re-freeze the corpus to make it pass. Either
it is a regression, or it is a deliberate format change that needs a new
corpus directory and a documented migration.
"""

import hashlib
import json
import unittest
from pathlib import Path

from alp.bundle import run_bundle
from alp.format import parse_module
from alp.handshake import compatibility, parse_hello
from alp.transport import LocalTransport, make_bundle_executor, parse_envelope
from alp.transport import status as st
from alp.profile import ExecutionProfile
from alp.canonical import canonical_result, require_canonical_module
from alp.vm import run_module

PROFILE = ExecutionProfile.default()

CORPUS = Path(__file__).parent / "fixtures" / "v0.3.0"
MANIFEST = json.loads((CORPUS / "conformance.json").read_text())
ARTIFACTS = {entry["file"]: entry for entry in MANIFEST["artifacts"]}

# v0.2.0 stays in the tree, byte-identical. Its recorded execution results
# used output-as-text, which section 5 of the semantics says is wrong, so
# they are superseded rather than corrected in place. Its artifact digests
# are still checked: those are file hashes and do not depend on how a
# result is written down.
LEGACY_CORPUS = Path(__file__).parent / "fixtures" / "v0.2.0"
LEGACY_MANIFEST = json.loads((LEGACY_CORPUS / "conformance.json").read_text())
LEGACY_ARTIFACTS = {entry["file"]: entry for entry in LEGACY_MANIFEST["artifacts"]}


class CorpusIntegrityTests(unittest.TestCase):
    """The corpus must not have been quietly regenerated."""

    def test_every_artifact_matches_its_recorded_digest(self) -> None:
        for name, entry in ARTIFACTS.items():
            with self.subTest(artifact=name):
                raw = (CORPUS / name).read_bytes()
                self.assertEqual(
                    hashlib.sha256(raw).hexdigest(),
                    entry["sha256"],
                    f"{name} differs from the frozen corpus. If this was deliberate, "
                    "create a new corpus directory rather than editing this one.",
                )
                self.assertEqual(len(raw), entry["bytes"])

    def test_corpus_is_not_empty(self) -> None:
        self.assertGreaterEqual(len(ARTIFACTS), 8)


class LegacyCorpusTests(unittest.TestCase):
    """v0.2.0 must stay byte-identical even though its result format is superseded."""

    def test_legacy_artifacts_still_match_their_digests(self) -> None:
        for name, entry in LEGACY_ARTIFACTS.items():
            with self.subTest(artifact=name):
                raw = (LEGACY_CORPUS / name).read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(), entry["sha256"])

    def test_both_corpora_hold_the_same_artifact_bytes(self) -> None:
        # The migration changed how results are recorded, not the artifacts.
        shared = set(ARTIFACTS) & set(LEGACY_ARTIFACTS)
        self.assertGreaterEqual(len(shared), 8)
        for name in sorted(shared):
            with self.subTest(artifact=name):
                self.assertEqual(
                    (CORPUS / name).read_bytes(),
                    (LEGACY_CORPUS / name).read_bytes(),
                )

    def test_migration_is_documented(self) -> None:
        self.assertEqual(MANIFEST["supersedes"], "v0.2.0")
        self.assertTrue(MANIFEST["migration_from_v0.2.0"])


class FrozenModuleTests(unittest.TestCase):
    """Frozen modules must still parse and execute identically."""

    def _modules(self):
        return [(n, e) for n, e in ARTIFACTS.items() if n.endswith(".alp")]

    def test_frozen_modules_still_parse(self) -> None:
        for name, entry in self._modules():
            with self.subTest(module=name):
                module = parse_module((CORPUS / name).read_bytes())
                self.assertEqual(module.version, entry["module"]["version"])
                self.assertEqual(module.entry, entry["module"]["entry"])
                self.assertEqual(len(module.instructions), entry["module"]["instructions"])

    def test_frozen_modules_execute_to_recorded_results(self) -> None:
        for name, entry in self._modules():
            with self.subTest(module=name):
                module = parse_module((CORPUS / name).read_bytes())
                result = canonical_result(run_module(module, PROFILE))
                self.assertEqual(result.to_dict(), entry["canonical_result"])

    def test_frozen_modules_serialise_to_recorded_bytes(self) -> None:
        # Compare the canonical JSON string itself, not just the fields. A
        # second implementation has to match the serialization, not only
        # agree about the values.
        for name, entry in self._modules():
            with self.subTest(module=name):
                module = parse_module((CORPUS / name).read_bytes())
                result = canonical_result(run_module(module, PROFILE))
                self.assertEqual(result.canonical_json(), entry["canonical_result_json"])

    def test_recorded_profile_is_the_one_used(self) -> None:
        # A result without its profile is not comparable, so the corpus
        # records the profile and the tests must run under it.
        self.assertEqual(MANIFEST["profile"], PROFILE.to_dict())

    def test_modules_in_the_corpus_are_canonically_encoded(self) -> None:
        for name, _ in self._modules():
            with self.subTest(module=name):
                require_canonical_module((CORPUS / name).read_bytes())

    def test_module_format_version_has_not_moved(self) -> None:
        from alp.format import VERSION

        self.assertEqual(
            VERSION,
            MANIFEST["module_format_version"],
            "Module format version changed. Every artifact ever published at the "
            "old version needs a migration path before this test is updated.",
        )


class FrozenBundleTests(unittest.TestCase):
    """Frozen bundles must still verify and run through the full trust path."""

    KEY = Path(__file__).parent.parent / "samples" / "dev_hmac.key"

    def test_frozen_json_bundle_still_runs(self) -> None:
        result = run_bundle(CORPUS / "add.alpp.json", self.KEY, PROFILE)
        self.assertEqual(result.top, 12)
        self.assertTrue(result.verified_checksum)
        self.assertTrue(result.verified_signature)

    def test_frozen_binary_bundle_still_runs(self) -> None:
        result = run_bundle(CORPUS / "add.alppb", self.KEY, PROFILE)
        self.assertEqual(result.top, 12)

    def test_both_bundle_encodings_agree(self) -> None:
        a = run_bundle(CORPUS / "add.alpp.json", self.KEY, PROFILE)
        b = run_bundle(CORPUS / "add.alppb", self.KEY, PROFILE)
        self.assertEqual((a.top, a.steps, a.output), (b.top, b.steps, b.output))


class FrozenProtocolTests(unittest.TestCase):
    """Governance promises must hold against artifacts that predate them."""

    def test_deprecated_hello_is_still_accepted(self) -> None:
        # add.alpp.json carries a 0.1 hello. The governance layer promises
        # 0.1 is deprecated but accepted; this is that promise under test
        # against a real artifact rather than a constructed one.
        payload = json.loads((CORPUS / "add.alpp.json").read_text())
        hello = parse_hello(payload["hello"])
        self.assertEqual(hello.version, "0.1")
        result = compatibility(hello)
        self.assertTrue(result["compatible"])
        self.assertTrue(result["deprecated"])
        self.assertEqual(result["replacement"], "0.2")

    def test_frozen_envelope_identity_is_stable(self) -> None:
        # envelope_id is content-derived. If this changes, every previously
        # issued receipt stops matching and idempotency silently breaks.
        envelope = parse_envelope(json.loads((CORPUS / "add.alpe.json").read_text()))
        self.assertEqual(envelope.envelope_id, "75e5fdadc3721f8b6792881ec7e13d96")

    def test_frozen_envelope_still_delivers(self) -> None:
        envelope = parse_envelope(json.loads((CORPUS / "add.alpe.json").read_text()))
        transport = LocalTransport(executor=make_bundle_executor(FrozenBundleTests.KEY, PROFILE))
        receipt = transport.send(envelope)
        self.assertEqual(receipt.status, st.SUCCEEDED)
        self.assertEqual(receipt.result.top, 12)


if __name__ == "__main__":
    unittest.main()
