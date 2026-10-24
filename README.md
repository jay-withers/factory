# factory

One place to work on every `jay-withers` repository with Claude Code. Open
this repo, describe the change, and get a PR in the repo it belongs to, made
in an isolated worktree, linted, tested and (for apps) run locally first.

## Getting started

1. Open the repo in its dev container (VS Code: **Reopen in Container**).
2. Run `gh auth login` and, if you'll work on anything Azure-backed,
   `az login`.
3. Run `make sync` to clone every repo into `repos/` and write `CATALOG.md`.
   After this, it runs on every container start.
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
  checks. Merging and `terraform apply` stay with you:
  `.claude/settings.json` denies them, and `CLAUDE.md` makes them hard rules.
- **After merge.** Apps and infrastructure deploy to dev on their own:
  `cd-publish` builds and deploys the image, and `cd-terraform` applies once a
  plan's PR has been approved. [docs/delivery.md](docs/delivery.md) covers the
  whole flow, the approvals, the permissions and the traps.
- **Local runs.** The container uses the host's Docker, and app repos expose
  `make run` / `make test`, so Claude can run and smoke-test a change before
  opening the PR.

## Commands

```bash
make install           # install pre-commit hooks (run once after cloning)
make lint              # run all pre-commit hooks against every file
make sync              # clone/fast-forward every repo, regenerate CATALOG.md
make task REPO=x BRANCH=feat/y   # create worktrees/x--feat-y, print its path
make status            # uncommitted/unpushed work, and every open PR
make clean-worktrees   # remove worktrees whose PR is merged or closed
```

## Known gaps

- The `dev-containers/terraform` image has Python 3.12 but no `pip`/`uv`, and
  no `kubectl`/`helm`. Python app repos may not be able to `make test` here
  until a broader image exists in
  [dev-containers](https://github.com/jay-withers/dev-containers).
- App repos don't all have `make run` / `make test` yet. Adding them is the
  first planned `/sweep`.
