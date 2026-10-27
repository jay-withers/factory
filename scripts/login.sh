#!/usr/bin/env bash
# Make sure gh is logged in. Run from every interactive shell (hooked into
# ~/.bashrc on container create), so a fresh container asks for a GitHub login
# in the first terminal you open, points git at that login for github.com,
# then runs make sync. Does nothing once logged in.
set -euo pipefail

[[ -t 0 && -t 1 ]] || exit 0

# A stored token is not a working one: `gh auth token` succeeds on a token
# GitHub has revoked, which twice left every gh call and push failing with 401
# while new terminals stayed silent. So check it against the API - but only a
# 401 means "log in again"; a network failure or timeout must not prompt every
# terminal opened offline.
if gh auth token >/dev/null 2>&1; then
  err="$(timeout 5 gh api user --silent 2>&1 >/dev/null)" && exit 0
  [[ "${err}" == *"HTTP 401"* || "${err}" == *"Bad credentials"* ]] || exit 0
  reason="GitHub CLI's token is no longer valid."
else
  reason="GitHub CLI is not logged in."
fi

root="$(cd "$(dirname "$0")/.." && pwd)"

echo "${reason} Logging in (Ctrl-C to skip until the next terminal)."
gh auth login --hostname github.com --git-protocol https --web
gh auth setup-git --hostname github.com
make -C "$root" sync
