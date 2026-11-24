#!/usr/bin/env bash
# SessionStart hook: bring repos/ up to date before Claude reads anything, so
# every session answers from the latest default branch of every repo. Runs
# scripts/sync.sh (clone new repos, fast-forward clean ones, rewrite
# CATALOG.md), then checks the architecture deck still names every repo
# (scripts/architecture-check.py). Best effort: offline, logged out or slow, it says so and lets
# the session start anyway. Whatever it prints goes into Claude's context, so
# it keeps to the summary and any clone that was skipped.
set -uo pipefail

root="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"

if ! timeout 5 gh api user --silent >/dev/null 2>&1; then
  echo "repos/ not synced at session start: gh is offline or not logged in" \
    "(run \`make login\`). Clones may be stale."
  exit 0
fi

if out="$(timeout 120 "$root/scripts/sync.sh" 2>&1)"; then
  grep -E '^[!?+] |^Synced ' <<<"$out" | sed 's/^/repos\/ sync: /'
  # A repo added, archived or renamed since the architecture deck was last
  # updated: say so, so the session that notices can fix slide 1.
  [[ -x "$root/scripts/architecture-check.py" && -f "$root/docs/architecture.md" ]] &&
    "$root/scripts/architecture-check.py" 2>&1 | sed 's/^/deck check: /'
else
  echo "repos/ sync at session start failed or timed out; clones may be stale." \
    "Last output:"
  tail -n 5 <<<"$out"
fi
exit 0
