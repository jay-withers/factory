#!/usr/bin/env bash
# Verify a worktree before it ships: run its lint, type check (where it has
# `make typecheck`) and tests, then record the
# exact file tree that passed. Run it from the worktree (`../../scripts/verify.sh`)
# or pass the path (`make verify DIR=worktrees/<name>`).
#
# The record is what scripts/hooks/require-verified.py checks: a Claude Code
# hook refuses `git push` and `gh pr create` from a worktree unless the commit
# being pushed has exactly this tree. So any edit after verifying (a review
# fix, a pre-commit fixer, a CI fix) means verifying again. That's the point:
# "lint and test before the PR" is enforced rather than remembered.
#
# The tree is taken from the working directory, untracked files included and
# .gitignore respected, so verifying before `git commit` matches the commit
# that follows.
set -euo pipefail

dir="${1:-.}"
cd "$dir"
top="$(git rev-parse --show-toplevel)"
cd "$top"

has_target() { make -n "$1" >/dev/null 2>&1; }

echo "==> lint ($top)"
if has_target lint; then
  make lint
else
  pre-commit run --all-files
fi

if has_target typecheck; then
  echo "==> typecheck"
  make typecheck
fi

if has_target test; then
  echo "==> test"
  make test
else
  echo "==> test: no 'make test' target here, skipped"
fi

# Hash the working tree through a throwaway index so the real one (and
# anything staged) is left alone.
index="$(mktemp)"
trap 'rm -f "$index"' EXIT
cp "$(git rev-parse --git-path index)" "$index" 2>/dev/null || true
GIT_INDEX_FILE="$index" git add -A
tree="$(GIT_INDEX_FILE="$index" git write-tree)"

# Per-worktree (inside its .git dir), so it's never committed or shared.
printf '%s\n' "$tree" > "$(git rev-parse --git-path factory-verified)"
echo "==> verified tree $tree"
