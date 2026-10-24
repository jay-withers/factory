# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo does

A language-agnostic GitHub repository template. It provides a dev container,
generic pre-commit hooks, PR/merge CI workflows (linting via a shared reusable
workflow, and auto-tagging on merge), Renovate dependency updates, Conventional
Commits enforcement, and Makefile scaffolding. It ships no application code on
purpose — a repo created from it adds its own source and layers
project-specific hooks/CI on top of this baseline.

## Dev container

The repo is built around the dev container at `.devcontainer/devcontainer.json`,
which uses the image `ghcr.io/jay-withers/dev-containers/base:latest` and runs
`make install` on creation to wire up the pre-commit hooks. Prefer working
inside the container so tooling versions match CI.

## Commands

`make` with no target prints the self-documenting help (the default goal).

```bash
make install           # install pre-commit hooks (run once after cloning)
make lint              # run all pre-commit hooks against every file
```

## Commit messages

Commits must follow [Conventional Commits](https://www.conventionalcommits.org/) — enforced by commitlint at commit-msg time. Examples: `feat: add health check endpoint`, `fix: correct retry backoff`, `chore: bump dependency`.

## Pre-commit config

Hooks are in `.pre-commit-config.yaml` at the repo root, all pinned by commit
SHA with the tag as a frozen comment. They're intentionally language-agnostic:
`pre-commit/pre-commit-hooks` basics (large-file / case-conflict /
merge-conflict / symlink / YAML / EOF / whitespace / line-ending / shebang
checks, and `no-commit-to-branch` which blocks direct commits to `main`),
`gitleaks` (secret scanning), `actionlint` (GitHub Actions linting),
`shellcheck` (shell scripts), `hadolint` (Dockerfile linting, via the
`hadolint-docker` hook so no local hadolint install is required — only
activates on repos that actually have a Dockerfile), and `commitlint`
(Conventional Commits, at the `commit-msg` stage). When a repo derived from
this template gains a language, add its formatter/linter hooks here rather
than replacing these.

## CI

Workflows are prefixed `ci-` (pull-request checks) or `cd-` (post-merge delivery):

- **ci-lint** (`.github/workflows/ci-lint.yml`): runs all linters
  on PRs to `main` via the `pre-commit` job, which calls the reusable workflow
  `jay-withers/workflows/.github/workflows/pre-commit.yml` (pinned by
  commit SHA, with the tag as a comment) rather than inlining the steps. Because
  it's a reusable-workflow call, the status-check context it reports on a PR is
  `pre-commit / Pre-commit` (`<caller job id> / <reusable job name>`), not the
  bare `pre-commit` job id — see the `CHECKS` note under GitHub repo settings.
  The reusable workflow's `terraform` input defaults to `false` and is left
  unset here. It runs `pre-commit run --all-files` directly against whatever
  `.pre-commit-config.yaml` the calling repo has, so hooks like `hadolint`
  need no changes on the workflow side — a Docker-capable `ubuntu-latest`
  runner is all `hadolint-docker` needs.
- **cd-tag** (`.github/workflows/cd-tag.yml`): auto-creates a semver tag (and a
  matching GitHub release) on every merge to `main` from the Conventional
  Commits since the last release, via the shared
  `jay-withers/workflows/.github/workflows/release.yml` reusable
  workflow (default bump: patch).

## Renovate

`renovate.json` extends the shared preset
`github>jay-withers/renovate` (see that repo for the policy: batched
Monday schedule, automerge of non-major dev deps/pins/digests via
`platformAutomerge` — which needs repo-level auto-merge, see GitHub repo
settings below — dependency dashboard, semantic commits, and the
`pre-commit` manager that keeps frozen hook revisions in
`.pre-commit-config.yaml` up to date), plus a local `autoApprove: true` so
those low-risk updates can clear the branch-protection review requirement.
Docker/GitHub Actions/Terraform/npm groupings are included in the shared
preset and activate automatically if a derived repo adds those ecosystems.

## GitHub repo settings

Settings that can't be templated as files — repo-level auto-merge (required
for `renovate.json`'s `platformAutomerge`), delete-branch-on-merge, and a
branch-protection ruleset requiring status checks and approving reviews —
aren't bootstrapped by anything in this template. A repo just created from
this template gets GitHub's defaults until it's added to `var.repos` in
[jay-withers/github-repos](https://github.com/jay-withers/github-repos)'
`terraform/terraform.tfvars` and applied — that Terraform root module is now
the single source of truth for these settings across every jay-withers repo,
this template included.
