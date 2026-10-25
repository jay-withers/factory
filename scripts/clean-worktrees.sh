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

  # The repo the worktree belongs to: repos/<repo> for most, but this repo
  # itself for factory's own worktrees, which have no clone under repos/.
  common="$(git -C "$worktree" rev-parse --path-format=absolute --git-common-dir)"
  git --git-dir="$common" worktree remove "$worktree"
  git --git-dir="$common" branch --quiet -D "$branch"
  echo "- $name: PR ${state,,} - removed"
done
