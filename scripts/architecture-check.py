#!/usr/bin/env python3
"""Check that the architecture deck's estate map names every repo.

    scripts/architecture-check.py [--catalog CATALOG.md] [--self NAME] [DOC]

The estate map is the Mermaid block in DOC (default docs/architecture.md)
containing a `%% estate-map` comment. Every node declared in it, as
`name["label"]` (or with `(`, `{` or `>` brackets) on its own line, must be a
repo in CATALOG.md, and every repo in CATALOG.md must be one of those nodes.
This repo must be on it too, though the catalogue leaves it out. Edges and
inline declarations (`a["a"] --> b`) don't count: give each repo its own line.

So adding, archiving or renaming a repo fails this until the deck is
updated. It runs at every session sync (scripts/hooks/session-sync.sh, as a
warning), in `make docs-check`, and in scripts/verify.sh for a factory
worktree. Whether the rest of the deck is still true is the docs step in
/change: this only catches the repo list.

Exit status: 0 when the map matches, 1 when it doesn't, 2 when the catalogue
or the map can't be read.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_ENTRY = re.compile(r"^- \*\*([\w.-]+)\*\*")
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})\s*(\S*)")
QUOTED = re.compile(r'"[^"]*"')
NODE = re.compile(r"^\s*([A-Za-z0-9_][\w.-]*)\s*[\[({>]")
MARKER = "%% estate-map"


def catalog_repos(text: str) -> set[str]:
    return {m.group(1) for line in text.splitlines() if (m := CATALOG_ENTRY.match(line))}


def mermaid_blocks(text: str) -> list[list[str]]:
    blocks, current, fence = [], None, None
    for line in text.splitlines():
        m = FENCE.match(line)
        if current is None:
            if m and m.group(2) == "mermaid":
                current, fence = [], m.group(1)
        elif m and m.group(1).startswith(fence) and not m.group(2):
            blocks.append(current)
            current = None
        else:
            current.append(line)
    return blocks


def estate_nodes(text: str) -> set[str] | None:
    for block in mermaid_blocks(text):
        if any(line.strip().startswith(MARKER) for line in block):
            nodes = set()
            for line in block:
                stripped = line.strip()
                if stripped.startswith(("subgraph", "%%", "classDef", "class ", "style ")):
                    continue
                unquoted = QUOTED.sub('""', stripped)
                if "--" in unquoted or "==" in unquoted:
                    continue  # an edge, not a declaration
                if m := NODE.match(line):
                    nodes.add(m.group(1))
            return nodes
    return None


def compare(repos: set[str], nodes: set[str], self_name: str) -> list[str]:
    problems = [
        f"{name}: in CATALOG.md but not on the estate map; add it to slide 1 "
        "(and any slide that should draw it)"
        for name in sorted((repos | {self_name}) - nodes)
    ]
    problems += [
        f"{name}: on the estate map but not in CATALOG.md (archived, renamed or "
        "a typo?); take it off every slide"
        for name in sorted(nodes - repos - {self_name})
    ]
    return problems


def own_name() -> str:
    try:
        url = subprocess.run(
            ["git", "-C", str(ROOT), "remote", "get-url", "origin"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return Path(url).stem
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "factory"  # a worktree's directory is factory--<branch>


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("doc", nargs="?", type=Path, default=ROOT / "docs" / "architecture.md")
    ap.add_argument("--catalog", type=Path, default=ROOT / "CATALOG.md")
    ap.add_argument("--self", dest="self_name", default=None, help="this repo's name (default: from its origin)")
    args = ap.parse_args()

    if not args.catalog.is_file():
        print(f"{args.catalog}: missing; run `make sync` first", file=sys.stderr)
        return 2
    if not args.doc.is_file():
        print(f"{args.doc}: missing", file=sys.stderr)
        return 2
    nodes = estate_nodes(args.doc.read_text(encoding="utf-8"))
    if nodes is None:
        print(f"{args.doc}: no Mermaid block with a `{MARKER}` comment", file=sys.stderr)
        return 2

    problems = compare(
        catalog_repos(args.catalog.read_text(encoding="utf-8")),
        nodes,
        args.self_name or own_name(),
    )
    for problem in problems:
        print(f"{args.doc.name}: {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
