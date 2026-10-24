#!/usr/bin/env bash
# Make sure gh is logged in. Run from every interactive shell (hooked into
# ~/.bashrc on container create), so a fresh container asks for a GitHub login
# in the first terminal you open, points git at that login for github.com,
# then runs make sync. Does nothing once logged in.
set -euo pipefail

[[ -t 0 && -t 1 ]] || exit 0
gh auth token >/dev/null 2>&1 && exit 0

root="$(cd "$(dirname "$0")/.." && pwd)"

echo "GitHub CLI is not logged in. Logging in (Ctrl-C to skip until the next terminal)."
gh auth login --hostname github.com --git-protocol https --web
gh auth setup-git --hostname github.com
make -C "$root" sync
