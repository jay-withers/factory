#!/usr/bin/env python3
"""Claude Code PreToolUse hook: no push or PR from an unverified worktree.

Blocks `git push` and `gh pr create` run against anything under worktrees/
unless HEAD's tree is the tree scripts/verify.sh last passed there. Commands
aimed elsewhere (this repo, repos/ mirrors, other paths) pass through.

The target directory is found the way the command would find it: `git -C <p>`,
else any `cd <p> && ...` before it, else the tool call's cwd. Exit 2 blocks
the call and shows stderr to Claude.
"""

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
WORKTREES = (ROOT / "worktrees").resolve()

SHIP = re.compile(r"\bgh\s+pr\s+create\b|\bgit\b(?:\s+-C\s+\S+)?\s+push\b")


def target_dir(command: str, cwd: Path) -> Path:
    """Directory the push/PR command runs in."""
    match = SHIP.search(command)
    head = command[: match.start()] if match else command
    shipped = command[match.start() :] if match else ""

    git_c = re.match(r"git\s+-C\s+(\S+)", shipped)
    if git_c:
        return resolve(git_c.group(1), cwd_after_cds(head, cwd))
    return cwd_after_cds(head, cwd)


def cwd_after_cds(head: str, cwd: Path) -> Path:
    for path in re.findall(r"(?:^|[;&|]\s*)cd\s+(\"[^\"]+\"|'[^']+'|\S+)", head):
        cwd = resolve(path, cwd)
    return cwd


def resolve(path: str, cwd: Path) -> Path:
    try:
        path = shlex.split(path)[0]
    except ValueError:
        pass
    p = Path(os.path.expanduser(path))
    return (p if p.is_absolute() else cwd / p).resolve()


def git(dir_: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(dir_), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def main() -> int:
    event = json.load(sys.stdin)
    command = (event.get("tool_input") or {}).get("command", "")
    if not SHIP.search(command):
        return 0
    if re.search(r"\bgit\b.*\bpush\b.*(--delete|\s-d\s)", command):
        return 0

    dir_ = target_dir(command, Path(event.get("cwd") or os.getcwd()))
    if not dir_.is_relative_to(WORKTREES):
        return 0

    try:
        top = Path(git(dir_, "rev-parse", "--show-toplevel"))
        head_tree = git(top, "rev-parse", "HEAD^{tree}")
        marker = top / git(top, "rev-parse", "--git-path", "factory-verified")
    except (subprocess.CalledProcessError, FileNotFoundError):
        return 0  # not a git checkout: nothing to ship, let the command fail on its own

    verified = marker.read_text().strip() if marker.is_file() else ""
    if verified == head_tree:
        return 0

    reason = (
        "it has never been verified"
        if not verified
        else "the code changed since it was last verified"
    )
    print(
        f"Blocked: {top.name} can't be pushed or opened as a PR because {reason}.\n"
        f"Run `{ROOT}/scripts/verify.sh {top}` (lint + tests), commit anything it "
        "changed, verify again if you did, then retry. Never bypass this.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
