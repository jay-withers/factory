#!/usr/bin/env bash
# Start a task: create worktrees/<repo>--<branch> on a new branch cut from the
# repo's freshly fetched default branch, and print its path. Every change is
# made in a worktree like this, never in repos/<name>, so tasks can run side by
# side and the clones stay clean mirrors that `make sync` can fast-forward.
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <repo> <branch>" >&2
  exit 2
fi
repo="$1"
branch="$2"

root="$(cd "$(dirname "$0")/.." && pwd)"
dir="$root/repos/$repo"
worktree="$root/worktrees/$repo--${branch//\//-}"

if [[ ! -d "$dir/.git" ]]; then
  echo "repos/$repo doesn't exist - check the name in CATALOG.md, or run 'make sync'" >&2
  exit 1
fi
if [[ -e "$worktree" ]]; then
  echo "$worktree already exists - carry on in it, or remove it first" >&2
  exit 1
fi

git -C "$dir" fetch --quiet --prune origin
default="$(git -C "$dir" symbolic-ref --short refs/remotes/origin/HEAD)"
default="${default#origin/}"

mkdir -p "$root/worktrees"
git -C "$dir" worktree add --quiet -b "$branch" "$worktree" "origin/$default"
# Push to a same-named branch, not to the default it was cut from.
git -C "$worktree" branch --quiet --unset-upstream 2>/dev/null || true

echo "$worktree"
