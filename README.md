# factory

One place to work on every `jay-withers` repository with Claude Code. Open
this repo, describe the change, and get a PR in the repo it belongs to, made
in an isolated worktree, linted, tested and (for apps) run locally first.

## Getting started

1. Set the machine up once with
   [toolchain](https://github.com/jay-withers/toolchain)'s `setup.sh` (mise
   and every tool), then run `make install` here.
2. Run `make login` (`gh auth login`, then a first `make sync` that clones
   every repo into `repos/` and writes `CATALOG.md`) and, if you'll work on
   anything Azure-backed, `az login`.
3. Open the folder in VS Code and install the recommended extensions when it
   asks. Allow its automatic tasks once, and `make sync` runs every time the
   folder opens. Claude Code syncs too: a `SessionStart` hook
   (`scripts/hooks/session-sync.sh`) runs it whenever a session starts,
   resumes or is cleared, and reports any clone it had to skip.
4. Start Claude Code and ask for what you want:

   ```text
   /change repo-agent add a --dry-run flag that prints the digest instead of emailing it
   /sweep bump jay-withers/workflows to the latest release topic:python
   which repos still don't have a make test target?
   ```

## How it works

```text
repos/<name>/                 clean mirror of every repo (make sync) - never edited
worktrees/<name>--<branch>/   one per task (make task) - all changes happen here
CATALOG.md                    generated repo list, imported by CLAUDE.md
```

- **Catalogue.** `make sync` reads `gh repo list jay-withers`. Descriptions
  and topics there are set by Terraform from
  [github-repos](https://github.com/jay-withers/github-repos)'
  `terraform.tfvars`, so the two lists can't drift.
- **Isolation.** Each task gets its own git worktree on a fresh branch from
  the target's default branch. Parallel tasks don't collide, and `make sync`
  can always fast-forward the mirrors. It skips, and reports, any clone that
  is dirty or off its default branch.
- **Delivery.** Every change is a normal PR, gated by that repo's required
  checks. Claude merges once they're all green (squash, never bypassing the
  ruleset); `terraform apply` stays with you: `.claude/settings.json` denies
  it, and `CLAUDE.md` makes it a hard rule.
- **After merge.** `cd-publish` builds every app image and deploys routine
  Renovate releases to dev on its own. Your own changes and majors open a
  `deploy-pending` issue instead. `cd-terraform` only plans: a plan with
  changes opens a `terraform-pending` issue, and you apply it with Run
  workflow. [docs/delivery.md](docs/delivery.md) covers the whole flow, the
  approvals, the permissions and the traps.
- **Quality gate.** Before a change leaves its worktree, Claude reviews the
  diff with the `code-review` skill and runs `scripts/verify.sh` (pre-commit,
  `make lint`, `make typecheck` where the repo has it, and `make test`). A Claude Code hook refuses `git push` and `gh pr create` unless the
  commit being pushed is exactly what passed.
- **Local runs.** App repos expose
  `make run` / `make test`, so Claude can run and smoke-test a change before
  opening the PR.

## Commands

```bash
make install           # mise install, then the pre-commit hooks (run once after cloning)
make login             # log gh in to GitHub if it isn't already, then sync
make lint              # run all pre-commit hooks against every file
make sync              # clone/fast-forward every repo, regenerate CATALOG.md
make task REPO=x BRANCH=feat/y   # create worktrees/x--feat-y, print its path
make verify DIR=worktrees/x--feat-y  # lint + test it; pushes are blocked until this passes
make status            # uncommitted/unpushed work, and every open PR
make clean-worktrees   # remove worktrees whose PR is merged or closed
```

## The docs

- [docs/delivery.md](docs/delivery.md): what deploys on merge, the
  `terraform-pending`, `deploy-pending`, `deploy-failed` and `build-failed`
  issues, required checks, and the Azure permission traps.
- [docs/autonomy.md](docs/autonomy.md): when Claude asks and when it just
  proceeds.
- [docs/repo-standard.md](docs/repo-standard.md): the shape every repo should
  have, to build new ones to and to tell a deliberate exception from drift.
- [docs/greenfield.md](docs/greenfield.md): the apply order for rebuilding the
  estate in a new tenant, with every tenant-bound literal.
- [CLAUDE.md](CLAUDE.md): the rules Claude works by, including the hard rules
  that stay human (applies, force-pushes, deleting repos).

## This repo's own CI

Built on [template-repo-base](https://github.com/jay-withers/template-repo-base).
`ci-lint` runs every pre-commit hook (`pre-commit / Pre-commit`, the required
check), `ci-codeql` scans the workflows, and `cd-tag` tags a release on every
merge. Changes here go through a branch and PR like any other repo.

## Known gaps

- market-agent and security-testing have `make test` but no `make run`.
