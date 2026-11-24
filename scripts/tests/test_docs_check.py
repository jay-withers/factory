"""Tests for scripts/docs-check.py, each against a throwaway git repo."""

import importlib.util
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "docs-check.py"
spec = importlib.util.spec_from_file_location("docs_check", SCRIPT)
docs_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(docs_check)

# Run as a pre-commit hook, these tests inherit GIT_DIR and GIT_INDEX_FILE
# for the repo being committed to: keep git off it.
ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


class RepoTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.git("init", "--quiet", "--initial-branch=main")
        self.git("config", "user.email", "test@example.com")
        self.git("config", "user.name", "test")
        self.git("config", "commit.gpgsign", "false")

    def tearDown(self):
        self._tmp.cleanup()

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True, env=ENV)

    def write(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text))

    def commit(self):
        self.git("add", "-A")
        self.git("commit", "--quiet", "-m", "x")

    def problems(self):
        docs_check.anchors.cache_clear()
        docs_check.make_targets.cache_clear()
        return [str(p) for p in docs_check.Repo(self.root).problems(set(docs_check.KINDS))]

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args, str(self.root)],
            capture_output=True, text=True, env=ENV,
        )


class Links(RepoTest):
    def test_link_to_missing_file(self):
        self.write("README.md", "See [the guide](docs/guide.md).\n")
        self.assertEqual(self.problems(), ["README.md:1: link docs/guide.md: no such file"])

    def test_link_to_existing_file_and_heading(self):
        self.write("docs/guide.md", "# Guide\n\n## Hard rules\n")
        self.write("README.md", "[a](docs/guide.md#hard-rules) [b](#top)\n\n# Top\n")
        self.assertEqual(self.problems(), [])

    def test_link_to_missing_heading(self):
        self.write("docs/guide.md", "# Guide\n")
        self.write("README.md", "[a](docs/guide.md#hard-rules)\n")
        self.assertEqual(self.problems(), ["README.md:1: link docs/guide.md#hard-rules: no heading #hard-rules"])

    def test_heading_slugs_match_github(self):
        self.write("README.md", textwrap.dedent("""\
            [a](#when-to-ask-and-when-to-just-do-it) [b](#make-run--make-test) [c](#faq-1)

            # When to ask, and when to just do it
            ## `make run` / `make test`
            ## FAQ
            ## FAQ
            """))
        self.assertEqual(self.problems(), [])

    def test_terraform_docs_anchors(self):
        self.write("README.md", '| [x](#input\\_name) |\n\n### <a name="input_name"></a> [name](#input\\_name)\n')
        self.assertEqual(self.problems(), [])

    def test_setext_headings(self):
        self.write("README.md", "[a](#usage) [b](#overview)\n\nOverview\n========\n\nUsage\n-----\n\n- item\n---\n")
        self.assertEqual(self.problems(), [])

    def test_fence_closes_only_on_its_own_kind(self):
        self.write("README.md", "~~~markdown\n```\n# Not a heading\n~~~\n\n[a](#not-a-heading) [b](#real)\n\n# Real\n")
        self.assertEqual(self.problems(), ["README.md:6: link #not-a-heading: no heading #not-a-heading"])

    def test_external_links_and_links_in_code_are_ignored(self):
        self.write("README.md", "[a](https://example.com/x) [m](mailto:a@b.c) `[c](nope.md)`\n\n```\n[d](nope.md)\n```\n")
        self.assertEqual(self.problems(), [])

    def test_untracked_but_unignored_file_counts(self):
        self.write("README.md", "[a](new.md)\n")
        self.write("new.md", "x\n")
        self.assertEqual(self.problems(), [])

    def test_gitignored_file_does_not_count(self):
        self.write(".gitignore", ".env\n")
        self.write(".env", "x\n")
        self.write("README.md", "[a](.env)\n")
        self.assertEqual(self.problems(), ["README.md:1: link .env: no such file"])


class Paths(RepoTest):
    def test_missing_path(self):
        self.write("README.md", "Run `scripts/smoke.sh`.\n")
        self.assertEqual(self.problems(), ["README.md:1: `scripts/smoke.sh`: no such file or directory"])

    def test_path_relative_to_the_doc(self):
        self.write("terraform/main.tf", "")
        self.write("terraform/README.md", "Edit `modules/x/` and `../terraform/main.tf`.\n")
        self.write("terraform/modules/x/main.tf", "")
        self.assertEqual(self.problems(), [])

    def test_path_given_from_a_subdirectory(self):
        self.write("app/api/main.py", "")
        self.write("CLAUDE.md", "`api/main.py` and `app/api/` but not `api/gone.py`\n")
        self.assertEqual(self.problems(), ["CLAUDE.md:1: `api/gone.py`: no such file or directory"])

    def test_things_that_are_not_paths(self):
        self.write("README.md", "`jay-withers/workflows` `ghcr.io/a/b` `Microsoft.App/x/y` "
                   "`repos/x/y.md` `main.tf` `owner/repo@v1` `a b/c` `<name>/x`\n")
        self.assertEqual(self.problems(), [])

    def test_ignore_markers(self):
        self.write("README.md", "`gone/a.sh` <!-- docs-check: ignore -->\n"
                   "<!-- docs-check: ignore-next-line -->\n`gone/b.sh`\n`gone/c.sh`\n")
        self.assertEqual(self.problems(), ["README.md:4: `gone/c.sh`: no such file or directory"])


class Make(RepoTest):
    def test_make_targets(self):
        self.write("Makefile", "include extra.mk\n.PHONY: run\nrun: ## run it\n\techo\n")
        self.write("extra.mk", "test:\n\techo\n")
        self.write("README.md", "`make run` `make test PORT=1` `make -C other x`\n\n```bash\nmake gone\n```\n")
        self.assertEqual(self.problems(), ["README.md:4: `make gone`: no such target in the Makefile"])

    def test_assignments_flag_arguments_and_comments_are_not_targets(self):
        self.write("Makefile", "run:\n\techo\ntest:\n\techo\n")
        self.write("README.md", "`make PORT=8001 run` `make -j 4 test` `make -C ../x y` `make` `make -f a.mk z`\n\n"
                   "```bash\n# make sure Docker is running\nmake run  # then make it stop\nmake gone\n```\n")
        self.assertEqual(self.problems(), ["README.md:6: `make gone`: no such target in the Makefile"])

    def test_no_makefile_no_check(self):
        self.write("README.md", "`make gone`\n")
        self.assertEqual(self.problems(), [])


class Base(RepoTest):
    def test_only_new_problems_fail(self):
        self.write("Makefile", "run:\n\techo\nsmoke:\n\techo\n")
        self.write("README.md", "`make run` `make smoke` `old/gone.sh`\n")
        self.commit()
        # The change drops `smoke` but leaves the doc mentioning it.
        self.write("Makefile", "run:\n\techo\n")
        result = self.run_cli("--base", "main")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("README.md:1: `make smoke`: no such target", result.stdout)
        self.assertIn("warning, broken before this change: README.md:1: `old/gone.sh`", result.stdout)

    def test_older_problems_alone_pass_and_survive_line_moves(self):
        self.write("README.md", "`old/gone.sh`\n")
        self.commit()
        self.write("README.md", "# Title\n\nIntro.\n\n`old/gone.sh`\n")
        result = self.run_cli("--base", "main")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("warning", result.stdout)

    def test_hook_environment_is_ignored(self):
        """Inside a git hook, GIT_DIR points at the repo being committed to."""
        self.write("README.md", "`old/gone.sh`\n")
        self.commit()
        with tempfile.TemporaryDirectory() as other:
            subprocess.run(["git", "init", "--quiet", other], check=True, env=ENV)
            env = {**ENV, "GIT_DIR": f"{other}/.git", "GIT_INDEX_FILE": f"{other}/.git/index"}
            result = subprocess.run([sys.executable, str(SCRIPT), "--base", "main", str(self.root)],
                                    capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("broken before this change", result.stdout)

    def test_not_a_checkout(self):
        with tempfile.TemporaryDirectory() as plain:
            result = subprocess.run([sys.executable, str(SCRIPT), plain], capture_output=True, text=True, env=ENV)
        self.assertEqual(result.returncode, 2)
        self.assertIn("is not a git checkout", result.stderr)

    def test_base_leaves_no_worktree_behind(self):
        self.write("README.md", "x\n")
        self.commit()
        self.run_cli("--base", "main")
        out = subprocess.run(["git", "-C", str(self.root), "worktree", "list"],
                             capture_output=True, text=True).stdout
        self.assertEqual(len(out.splitlines()), 1, out)

    def test_without_base_everything_fails(self):
        self.write("README.md", "`old/gone.sh`\n")
        self.commit()
        self.assertEqual(self.run_cli().returncode, 1)


if __name__ == "__main__":
    unittest.main()
