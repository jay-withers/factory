# template-generic-repo

A language-agnostic GitHub repository template. It gives a new repo a working
baseline on day one — a dev container, generic pre-commit hooks, PR/merge CI
workflows, Renovate dependency updates, and Conventional Commits enforcement —
with no application code, so you add your own source and layer
project-specific tooling on top.

## Getting started

1. Create a repo from this template (**Use this template** on GitHub, or `gh
   repo create --template`).
2. Open it in the dev container (VS Code: **Reopen in Container**, or GitHub
   Codespaces). The container runs `make install` on creation to wire up the
   pre-commit hooks.
3. Outside a dev container, install the hooks manually:

   ```bash
   make install
   ```

## Commands

Run `make` (or `make help`) to list the available targets:

```bash
make install           # install pre-commit hooks (run once after cloning)
make lint              # run all pre-commit hooks against every file
```

## Pre-commit hooks

Hooks live in `.pre-commit-config.yaml`, pinned by commit SHA with the tag as a
frozen comment. They're deliberately language-agnostic:

- `pre-commit/pre-commit-hooks` — large-file, case-conflict, merge-conflict,
  symlink, YAML, end-of-file, trailing-whitespace, line-ending and shebang
  checks, plus `no-commit-to-branch` (blocks direct commits to `main`)
- `gitleaks` — secret scanning
- `actionlint` — GitHub Actions workflow linting
- `shellcheck` — shell scripts
- `commitlint` — [Conventional Commits](https://www.conventionalcommits.org/),
  at the `commit-msg` stage

As your repo gains a language, add its formatter/linter hooks here — don't
remove these. Renovate keeps the frozen hook revisions up to date.

## Commit messages

Commits must follow [Conventional Commits](https://www.conventionalcommits.org/),
enforced by commitlint at commit-msg time. The commit type drives the automatic
version bump on merge (see below). Examples:

```text
feat: add health check endpoint
fix: correct retry backoff
chore: bump dependency
```

## CI/CD

Workflows are prefixed `ci-` (pull-request checks) or `cd-` (post-merge delivery):

- **`.github/workflows/ci-lint.yml`** — runs all pre-commit hooks on PRs
  to `main`, by calling the shared reusable workflow
  `jay-withers/template-pipelines/.github/workflows/pre-commit.yml`. Its status
  check reports as `pre-commit / Pre-commit`.
- **`.github/workflows/cd-tag.yml`** — on every merge to `main`, creates a
  semver tag and matching GitHub release from the Conventional Commits since the
  last release (default bump: patch), via
  `jay-withers/template-pipelines/.github/workflows/release.yml`.

Both pin the reusable workflow by commit SHA with the tag as a comment. Add your
own `ci-*` workflows (build, test, etc.) as you add code, and require their
checks in branch protection (below).

## Renovate

`renovate.json` extends `config:recommended` on a weekly schedule with
auto-approve and automerge. `platformAutomerge` needs repo-level auto-merge to
be enabled — see [Configuring GitHub](#configuring-github-for-a-repo-created-from-this-template).
The `pre-commit` manager updates the frozen hook revisions in
`.pre-commit-config.yaml`; add language/ecosystem managers as your repo grows.

## Configuring GitHub for a repo created from this template

Settings that can't be templated as files — repo-level auto-merge, delete
branch on merge, and a branch-protection ruleset requiring status checks and
approving reviews — aren't bootstrapped by anything in this template anymore.
A repo just created from this template gets GitHub's defaults until it's
added to `var.repos` in
[jay-withers/github-repos](https://github.com/jay-withers/github-repos)'
`terraform/terraform.tfvars` and applied — that Terraform root module is now
the single source of truth for these settings across every jay-withers repo,
this template included.

## Structure

```text
.devcontainer/
  devcontainer.json    # dev container (ghcr.io/jay-withers/dev-containers/base)
.github/
  workflows/
    ci-lint.yml        # lints all files on PRs to main (reusable workflow)
    cd-tag.yml         # auto-tags + releases on merge to main (semver, conventional commits)
.editorconfig          # baseline editor settings (aligned with pre-commit hooks)
.gitattributes         # git-level LF normalization
.pre-commit-config.yaml
commitlint.config.js   # commitlint (Conventional Commits) config
renovate.json          # automated dependency updates
CLAUDE.md              # guidance for Claude Code
LICENSE
Makefile
```
