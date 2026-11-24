"""Tests for scripts/architecture-check.py."""

import importlib.util
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "architecture-check.py"
DECK = Path(__file__).resolve().parents[2] / "docs" / "architecture.md"
spec = importlib.util.spec_from_file_location("architecture_check", SCRIPT)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}

CATALOG = textwrap.dedent(
    """\
    # Repository catalogue

    - **alpha** - first [x]
    - **beta-two** (template) - second
    """
)

DOC = textwrap.dedent(
    """\
    # Deck

    ```mermaid
    flowchart LR
      other["not the map"]
    ```

    ```mermaid
    %% estate-map
    flowchart LR
      subgraph g["Group"]
        alpha["alpha"]
        beta-two("beta-two (template)")
        factory["factory"]
      end
      alpha --> beta-two
      alpha -. "feeds" .-> g
      classDef parked stroke-dasharray: 5 5
      class alpha parked
    ```
    """
)


class ParseTest(unittest.TestCase):
    def test_catalog_repos(self):
        self.assertEqual(check.catalog_repos(CATALOG), {"alpha", "beta-two"})

    def test_estate_nodes_reads_only_the_marked_block(self):
        self.assertEqual(check.estate_nodes(DOC), {"alpha", "beta-two", "factory"})

    def test_no_marker(self):
        self.assertIsNone(check.estate_nodes("```mermaid\nflowchart LR\n  a[\"a\"]\n```\n"))

    def test_edges_and_subgraphs_are_not_nodes(self):
        doc = '```mermaid\n%% estate-map\nflowchart LR\n  subgraph s["S"]\n  end\n  a["a"] --> b["b"]\n```\n'
        self.assertEqual(check.estate_nodes(doc), set())


class CompareTest(unittest.TestCase):
    def test_match(self):
        self.assertEqual(check.compare({"alpha"}, {"alpha", "factory"}, "factory"), [])

    def test_self_is_required(self):
        problems = check.compare({"alpha"}, {"alpha"}, "factory")
        self.assertEqual(len(problems), 1)
        self.assertTrue(problems[0].startswith("factory: in CATALOG.md"))

    def test_dashes_in_a_label_are_not_an_edge(self):
        doc = '```mermaid\n%% estate-map\nflowchart LR\n  a["a -- renamed"]\n```\n'
        self.assertEqual(check.estate_nodes(doc), {"a"})

    def test_missing_and_extra(self):
        problems = check.compare({"alpha", "new"}, {"alpha", "gone", "factory"}, "factory")
        self.assertEqual(len(problems), 2)
        self.assertTrue(problems[0].startswith("new: in CATALOG.md"))
        self.assertTrue(problems[1].startswith("gone: on the estate map"))


class CliTest(unittest.TestCase):
    def run_check(self, catalog: str | None, doc: str) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "doc.md").write_text(doc)
            args = [sys.executable, str(SCRIPT), str(tmp / "doc.md"), "--self", "factory",
                    "--catalog", str(tmp / "CATALOG.md")]
            if catalog is not None:
                (tmp / "CATALOG.md").write_text(catalog)
            return subprocess.run(args, capture_output=True, text=True, env=ENV)

    def test_passes(self):
        self.assertEqual(self.run_check(CATALOG, DOC).returncode, 0)

    def test_new_repo_fails(self):
        result = self.run_check(CATALOG + "- **gamma** - third\n", DOC)
        self.assertEqual(result.returncode, 1)
        self.assertIn("gamma: in CATALOG.md but not on the estate map", result.stdout)

    def test_missing_catalog(self):
        self.assertEqual(self.run_check(None, DOC).returncode, 2)


class DeckTest(unittest.TestCase):
    def test_deck_has_an_estate_map(self):
        nodes = check.estate_nodes(DECK.read_text(encoding="utf-8"))
        self.assertIsNotNone(nodes)
        self.assertIn("factory", nodes)
        self.assertIn("github-repos", nodes)


if __name__ == "__main__":
    unittest.main()
