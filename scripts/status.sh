#!/usr/bin/env bash
# What's in flight: every clone or worktree with uncommitted or unpushed work,
# then every open PR across $FACTORY_OWNER's repos.
set -euo pipefail

owner="${FACTORY_OWNER:-jay-withers}"
root="$(cd "$(dirname "$0")/.." && pwd)"

echo "Local work:"
found=0
for dir in "$root"/repos/*/ "$root"/worktrees/*/; do
  [[ -e "$dir/.git" ]] || continue
  rel="${dir#"$root"/}"
  rel="${rel%/}"
  notes=()
  [[ -n "$(git -C "$dir" status --porcelain)" ]] && notes+=("uncommitted changes")
  if upstream="$(git -C "$dir" rev-parse --abbrev-ref '@{upstream}' 2>/dev/null)"; then
    ahead="$(git -C "$dir" rev-list --count "$upstream..HEAD")"
    [[ "$ahead" -gt 0 ]] && notes+=("$ahead commit(s) not pushed")
  elif [[ "$rel" == worktrees/* ]]; then
    notes+=("branch not pushed")
  fi
  if [[ ${#notes[@]} -gt 0 ]]; then
    found=1
    joined="$(printf '%s; ' "${notes[@]}")"
    printf '  %-50s %s\n' "$rel" "${joined%; }"
  fi
done
[[ "$found" -eq 0 ]] && echo "  (nothing uncommitted or unpushed)"

echo
echo "Open PRs in $owner:"
gh search prs --owner "$owner" --state open --limit 100 \
  --json repository,number,title,url \
  --template '{{range .}}{{printf "  %-24s #%-5v %s\n" .repository.name .number .title}}{{end}}'
