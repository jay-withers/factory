#!/usr/bin/env python3
"""Find Markdown references that no longer hold.

    scripts/docs-check.py [--base REF] [--only KIND] [DIR ...]

For every tracked (or new, unignored) *.md file in each DIR's repo it checks:

- links: `[text](path)`, `[text](path#heading)` and `[text](#heading)` point
  at a file that exists and, for a Markdown target, a heading it has;
- paths: inline code that looks like a repo path with a directory in it
  (`scripts/verify.sh`, `docs/`) exists: from the repo root, from the doc's
  own directory, or as the tail of some path in the repo (`api/main.py`
  for app/api/main.py);
- make: `make <target>` in inline code or a code block is a target the
  repo's Makefile has (when it has one and the command isn't `make -C`).

Paths and make targets are heuristic: docs also name other repos' files and
targets. So with `--base REF` (what scripts/verify.sh passes: the branch the
change will merge into) only problems the change *adds* fail; older ones are
printed as warnings. Without it, everything found fails, which is what
`make docs-check` uses for an estate-wide audit.

This catches the mechanical half of doc drift (a renamed script, a dropped
make target, a moved doc, a retitled heading). Whether the prose is still
true is the docs step in the /change and /sweep skills.

A line containing `docs-check: ignore` is skipped, as is the line after one
containing `docs-check: ignore-next-line` (put either in an HTML comment).
CHANGELOG.md is skipped: it records the past.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import unicodedata
from collections import Counter
from dataclasses import dataclass
from functools import cache
from pathlib import Path

SKIP_FILES = {"CHANGELOG.md"}
KINDS = ("links", "paths", "make")
LINK = re.compile(r"\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
REFDEF = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*<?(\S+?)>?(?:\s|$)")
INLINE_CODE = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
# `make`, then flags (with the argument of those that take one) and VAR=value
# assignments, then the first target.
MAKE = re.compile(
    r"(?:^|[\s;&|(])make((?:\s+(?:-[CfIjloW]\s+\S+|-\S+|[\w.-]+=\S*))*)\s+([A-Za-z0-9][\w.-]*)(?![\w.=-])"
)
HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$")
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
SETEXT = re.compile(r"^\s{0,3}(=+|-+)\s*$")
HTML_ANCHOR = re.compile(r"<a\s+(?:name|id)=\"([^\"]+)\"", re.I)
PATHISH = re.compile(r"^(?:\./)?[\w.+-]+(?:/[\w.+-]+)*/?$")
SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.I)
DOT_DIRS = (".github", ".claude", ".vscode", ".devcontainer")


@dataclass(frozen=True)
class Problem:
    kind: str
    file: str
    line: int
    ref: str
    why: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line}: {self.ref}: {self.why}"

    @property
    def key(self) -> tuple[str, str, str]:
        # Line numbers and file names shift with unrelated edits and renames.
        return (self.kind, self.ref, self.why)


# A git hook (pre-commit runs this as one) exports GIT_DIR, GIT_INDEX_FILE and
# friends, which would point every `git -C <dir>` here at the hook's repo.
GIT_ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=True, env=GIT_ENV,
    ).stdout.strip()


def slug(text: str) -> str:
    """The anchor GitHub gives a heading."""
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]+>", "", text).replace("`", "").lower()
    text = "".join(c for c in text if c in " -_" or unicodedata.category(c)[0] in "LN")
    return text.replace(" ", "-")


def numbered_lines(path: Path):
    """(line number, text, in_fence), with in_fence None on the fence lines.

    A fence closes only on the same character, at least as long, as opened it.
    """
    fence = ""
    for n, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
        m = FENCE.match(line)
        if m and not fence:
            fence = m.group(1)
            yield n, line, None
        elif m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence) and not line.strip()[len(m.group(1)):]:
            fence = ""
            yield n, line, None
        else:
            yield n, line, bool(fence)


@cache
def anchors(path: Path) -> frozenset[str]:
    seen: Counter[str] = Counter()
    found = set()
    previous = ""  # the line before, for setext headings (text over === or ---)
    for _, line, in_fence in numbered_lines(path):
        if in_fence is not False:
            previous = ""
            continue
        found.update(a.lower() for a in HTML_ANCHOR.findall(line))
        title = None
        if m := HEADING.match(line):
            title = m.group(1)
        elif SETEXT.match(line) and previous.strip() and not previous.lstrip().startswith(("-", "*", "+", ">", "|")):
            title = previous.strip()
        if title is not None:
            base = slug(title)
            found.add(f"{base}-{seen[base]}" if seen[base] else base)
            seen[base] += 1
        previous = line
    return frozenset(found)


@cache
def make_targets(makefile: Path) -> frozenset[str] | None:
    if not makefile.is_file():
        return None
    # make's printed database includes targets from included makefiles.
    out = subprocess.run(
        ["make", "-pRrq", "-f", makefile.name, ":"],
        cwd=makefile.parent, capture_output=True, text=True,
    ).stdout
    targets = set()
    for line in out.splitlines():
        if line.startswith(("\t", "#", " ")):
            continue
        if m := re.match(r"^([\w./-]+(?:\s+[\w./-]+)*)\s*::?(?![=:])", line):
            targets.update(m.group(1).split())
    return frozenset(targets)


def looks_like_path(token: str) -> bool:
    """Inline code that is probably a path in this repo."""
    if not PATHISH.match(token) or "/" not in token.rstrip("/"):
        return False  # bare names (`main.tf`) could live in any directory
    first = token.removeprefix("./").split("/")[0]
    if first in ("repos", "worktrees", ".git"):
        return False  # other checkouts, git internals
    if "." in first and first not in DOT_DIRS:
        return False  # hosts and namespaces: ghcr.io/..., Microsoft.App/...
    if token.count("/") == 1 and not token.endswith("/") and "." not in token.split("/")[1]:
        return False  # owner/repo, Azure/naming and similar
    return True


class Repo:
    def __init__(self, root: Path, files: set[str] | None = None):
        """A checkout at ROOT, or with FILES, an extracted tree holding them."""
        self.root = root.resolve()
        if files is None:
            listed = git(self.root, "ls-files", "--cached", "--others", "--exclude-standard")
            files = {f for f in listed.splitlines() if (self.root / f).exists()}
        self.files = files
        self.dirs = {p.as_posix() for f in self.files for p in Path(f).parents}
        self.all = self.files | self.dirs

    def has_tail(self, token: str) -> bool:
        tail = "/" + token.removeprefix("./").rstrip("/")
        return any(("/" + p).endswith(tail) for p in self.all)

    def has(self, target: Path) -> bool:
        try:
            rel = target.resolve().relative_to(self.root).as_posix()
        except ValueError:
            return target.exists()  # outside the repo: trust the disk
        return rel in self.files or rel in self.dirs

    def problems(self, only: set[str]) -> list[Problem]:
        targets = make_targets(self.root / "Makefile") if "make" in only else None
        found: list[Problem] = []
        for rel in sorted(self.files):
            if rel.endswith(".md") and Path(rel).name not in SKIP_FILES:
                found += self.check_file(rel, targets)
        return [p for p in found if p.kind in only]

    def check_file(self, rel: str, targets: frozenset[str] | None) -> list[Problem]:
        doc = self.root / rel
        found: list[Problem] = []
        skip_next = False
        for n, line, in_fence in numbered_lines(doc):
            skip, skip_next = skip_next, "docs-check: ignore-next-line" in line
            if skip or "docs-check: ignore" in line or in_fence is None:
                continue
            # In a code block, a `# comment` is prose: "# make sure ..." isn't a command.
            spans = [re.sub(r"(^|\s)#.*", "", line)] if in_fence else INLINE_CODE.findall(line)

            if not in_fence:
                prose = INLINE_CODE.sub("``", line)
                urls = LINK.findall(prose)
                if m := REFDEF.match(prose):
                    urls.append(m.group(1))
                for url in urls:
                    if why := self.broken_link(doc, url):
                        found.append(Problem("links", rel, n, f"link {url}", why))
                for span in spans:
                    token = span.strip()
                    if looks_like_path(token) and not (
                        self.has(self.root / token) or self.has(doc.parent / token)
                        or (not token.startswith("../") and self.has_tail(token))
                    ):
                        found.append(Problem("paths", rel, n, f"`{token}`", "no such file or directory"))

            if targets is not None:
                for span in spans:
                    for m in MAKE.finditer(span):
                        flags, target = m.group(1), m.group(2)
                        if re.search(r"(^|\s)-(C|f|-directory|-file)", flags):
                            continue  # another Makefile
                        if target not in targets:
                            found.append(Problem("make", rel, n, f"`make {target}`", "no such target in the Makefile"))
        return found

    def broken_link(self, doc: Path, url: str) -> str | None:
        if SCHEME.match(url) or url.startswith("//"):
            return None
        url = url.replace("\\", "")  # terraform-docs writes #input\_name
        target, _, anchor = url.partition("#")
        target = target.split("?")[0]
        dest = doc
        if target:
            dest = self.root / target.lstrip("/") if target.startswith("/") else doc.parent / target
            if not self.has(dest):
                return "no such file"
        if anchor and dest.suffix.lower() == ".md" and dest.is_file():
            if anchor.lower() not in anchors(dest.resolve()):
                return f"no heading #{anchor}"
        return None


def problems_at(root: Path, ref: str, only: set[str]) -> list[Problem]:
    """Problems in the repo as it was at REF, from a plain extract of its tree.

    `git archive` rather than a worktree: nothing to clean up in the repo if
    this is interrupted, and no checkout hooks or LFS filters run.
    """
    with tempfile.TemporaryDirectory(prefix="docs-check-") as tmp:
        archive = subprocess.run(["git", "-C", str(root), "archive", "--format=tar", ref],
                                 capture_output=True, check=True, env=GIT_ENV).stdout
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(tmp, filter="data")
        files = set(git(root, "ls-tree", "-r", "--name-only", ref).splitlines())
        return Repo(Path(tmp), files).problems(only)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("dirs", nargs="*", type=Path)
    ap.add_argument("--base", help="fail only on problems not already present at this ref")
    ap.add_argument("--only", action="append", choices=KINDS, help="check only this kind (repeatable)")
    args = ap.parse_args()
    only = set(args.only or KINDS)
    dirs = args.dirs or [Path.cwd()]

    failed = warned = 0
    for d in dirs:
        try:
            root = Path(git(d, "rev-parse", "--show-toplevel"))
        except (subprocess.CalledProcessError, FileNotFoundError, NotADirectoryError):
            print(f"docs-check: {d} is not a git checkout", file=sys.stderr)
            return 2
        prefix = f"{d}: " if len(dirs) > 1 else ""
        old = Counter(p.key for p in problems_at(root, args.base, only)) if args.base else Counter()
        for p in Repo(root).problems(only):
            if old[p.key]:
                old[p.key] -= 1
                warned += 1
                print(f"{prefix}warning, broken before this change: {p}")
            else:
                failed += 1
                print(f"{prefix}{p}")

    sys.stdout.flush()
    if warned:
        print(f"docs-check: {warned} older broken reference(s), worth fixing while you're here", file=sys.stderr)
    if failed:
        what = "new broken reference(s)" if args.base else "broken reference(s)"
        print(f"docs-check: {failed} {what}. Fix the doc or the reference. If one is right as it stands "
              "(another repo's file, a target the doc says not to run), mark its line "
              "<!-- docs-check: ignore -->.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
