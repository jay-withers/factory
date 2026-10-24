#!/usr/bin/env bash
# Remove each worktree whose PR has been merged or closed, and its local
# branch. Asks GitHub rather than `git branch --merged`, because every repo
# squash-merges, so a merged branch's commits never appear on main. A worktree
# with uncommitted changes is always kept.
set -euo pipefail

owner="${FACTORY_OWNER:-jay-withers}"
root="$(cd "$(dirname "$0")/.." && pwd)"

for worktree in "$root"/worktrees/*/; do
  [[ -e "$worktree/.git" ]] || continue
  worktree="${worktree%/}"
  name="$(basename "$worktree")"
  repo="${name%%--*}"
  branch="$(git -C "$worktree" symbolic-ref --quiet --short HEAD || true)"
  [[ -n "$branch" ]] || { echo "! $name: detached HEAD - kept"; continue; }

  state="$(gh pr view "$branch" -R "$owner/$repo" --json state --jq .state 2>/dev/null || echo NONE)"
  case "$state" in
    MERGED | CLOSED) ;;
    *)
      echo "  $name: PR ${state,,} - kept"
      continue
      ;;
  esac
  if [[ -n "$(git -C "$worktree" status --porcelain)" ]]; then
    echo "! $name: PR ${state,,} but has uncommitted changes - kept"
    continue
  fi

  git -C "$root/repos/$repo" worktree remove "$worktree"
  git -C "$root/repos/$repo" branch --quiet -D "$branch"
  echo "- $name: PR ${state,,} - removed"
done
