from __future__ import annotations

"""Every MUST statement must have a test, or an explicit reason it does not.

A specification with no executable consequence is documentation. This file
is the bridge: it parses the two specs for normative statements, checks
each one against spec/conformance-map.json, and fails when a rule has no
entry at all.

The design goal is a ratchet, not a gate. Known gaps are listed with
reasons and the suite stays green; what the suite refuses is a *new*
untriaged MUST statement, or a rise in the number of gaps. That way the
coverage can only improve, and nobody has to choose between an honest
spec and a green build.
"""

import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).parent.parent
MAP_PATH = REPO / "spec" / "conformance-map.json"
MAP = json.loads(MAP_PATH.read_text())
DOCS = MAP["documents"]


def normative_sections(doc_path: Path) -> dict[str, int]:
    """Section -> count of MUST statements in it."""
    found: dict[str, int] = {}
    section = None
    for line in doc_path.read_text().splitlines():
        heading = re.match(r"^##\s+(\d+)\.", line)
        if heading:
            section = heading.group(1)
            continue
        if section is None or not re.search(r"\bMUST\b", line):
            continue
        item = re.match(r"^(\d+)\.", line.strip())
        key = f"{section}.{item.group(1)}" if item else section
        found[key] = found.get(key, 0) + 1
    return found


class SpecsAreMappedTests(unittest.TestCase):
    def test_every_normative_statement_has_a_map_entry(self) -> None:
        for doc, mapping in DOCS.items():
            sections = normative_sections(REPO / doc)
            self.assertTrue(sections, f"{doc}: no MUST statements found — did the parser break?")
            missing = sorted(set(sections) - set(mapping))
            self.assertEqual(
                missing, [],
                f"{doc}: normative sections with no entry in spec/conformance-map.json: {missing}. "
                "Add a test, or add the section with an uncovered_reason.",
            )

    def test_no_map_entry_refers_to_a_section_that_no_longer_exists(self) -> None:
        for doc, mapping in DOCS.items():
            sections = normative_sections(REPO / doc)
            stale = sorted(set(mapping) - set(sections))
            self.assertEqual(stale, [], f"{doc}: map entries for sections with no MUST statement: {stale}")

    def test_every_entry_either_names_tests_or_gives_a_reason(self) -> None:
        for doc, mapping in DOCS.items():
            for section, entry in mapping.items():
                with self.subTest(doc=doc, section=section):
                    if entry["tests"]:
                        for name in entry["tests"]:
                            self.assertTrue(name.startswith("tests."), name)
                    else:
                        reason = entry.get("uncovered_reason", "")
                        self.assertGreater(len(reason), 30,
                                           f"{doc} §{section}: an uncovered rule needs a real reason")


class RatchetTests(unittest.TestCase):
    """The number of unenforced rules may fall. It must never rise."""

    def _uncovered(self) -> list[str]:
        out = []
        for doc, mapping in DOCS.items():
            label = "semantics" if "DETERMINISTIC" in doc else "encoding"
            out += [f"{label} §{s}" for s, e in mapping.items() if not e["tests"]]
        return sorted(out)

    def test_recorded_ratchet_matches_reality(self) -> None:
        recorded = sorted(MAP["ratchet"]["uncovered"])
        self.assertEqual(self._uncovered(), recorded,
                         "spec/conformance-map.json ratchet is stale; regenerate it")

    def test_ratchet_count_matches_its_list(self) -> None:
        self.assertEqual(MAP["ratchet"]["uncovered_count"], len(MAP["ratchet"]["uncovered"]))

    def test_coverage_has_not_regressed(self) -> None:
        # The ceiling. Lower it when gaps close; never raise it.
        CEILING = 5
        self.assertLessEqual(
            len(self._uncovered()), CEILING,
            "more normative statements are unenforced than the ratchet allows",
        )

    def test_the_named_tests_actually_exist(self) -> None:
        import importlib

        for doc, mapping in DOCS.items():
            for section, entry in mapping.items():
                for dotted in entry["tests"]:
                    with self.subTest(section=section, test=dotted):
                        parts = dotted.split(".")
                        module = importlib.import_module(".".join(parts[:2]))
                        obj = module
                        for attr in parts[2:]:
                            self.assertTrue(hasattr(obj, attr), f"{dotted} does not exist")
                            obj = getattr(obj, attr)


if __name__ == "__main__":
    unittest.main()
