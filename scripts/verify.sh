#!/usr/bin/env bash
# Verify a worktree before it ships: run its lint, the docs check
# (scripts/docs-check.py), its type check (where it has `make typecheck`) and
# its tests, then record the exact file tree that passed. Run it from the
# worktree (`../../scripts/verify.sh`) or pass the path
# (`make verify DIR=worktrees/<name>`).
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

scripts="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
dir="${1:-.}"
cd "$dir"
top="$(git rev-parse --show-toplevel)"
cd "$top"

has_target() { make -n "$1" >/dev/null 2>&1; }

echo "==> lint ($top)"
# pre-commit always, where the repo has it: it's what the commit hook and CI's
# pre-commit check run, and some repos' `make lint` is something else entirely
# (workflows' runs only actionlint). `make lint` as well when it does more than
# pre-commit, so neither half is skipped.
if [[ -f .pre-commit-config.yaml ]]; then
  pre-commit run --all-files
fi
if has_target lint && ! make -n lint 2>/dev/null | grep -q "pre-commit run"; then
  make lint
fi

# Docs: fail on any link, path or make target in the Markdown that this change
# broke (a renamed script, a dropped target, a retitled heading). References
# that were already broken on the base branch are warnings, not failures.
# factory's own docs mostly name other repos' files and targets, so a factory
# worktree gets the links check only (as its pre-commit hook does).
echo "==> docs"
kinds=()
if [[ "$(git rev-parse --path-format=absolute --git-common-dir)" \
  == "$(git -C "$scripts" rev-parse --path-format=absolute --git-common-dir)" ]]; then
  kinds=(--only links)
fi
if default="$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD)" \
  && base="$(git merge-base HEAD "$default")"; then
  "$scripts/docs-check.py" "${kinds[@]}" --base "$base" .
else
  echo "    no origin/HEAD to compare with: checking links only"
  "$scripts/docs-check.py" --only links .
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
