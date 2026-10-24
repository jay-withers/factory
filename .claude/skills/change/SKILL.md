---
name: change
description: Make one change in one jay-withers repository and ship it as a PR - worktree, edit, lint/test/run locally, Conventional Commit, push, open PR, watch checks. Use for any request that targets a single repo.
argument-hint: <repo> <what to change>
---

# /change

Request: $ARGUMENTS

1. **Identify the repo.** The first word should be a repo name from CATALOG.md.
   If it isn't, or the request fits more than one repo, say which repo(s) you
   think it belongs in and why. For more than one, use /sweep instead.
2. **Start the task.** Run `make task REPO=<repo> BRANCH=<type>/<short-slug>`,
   where `<type>` is the Conventional Commit type (`feat`, `fix`, `chore`,
   `docs`, ...). Work only in the worktree path it prints.
3. **Learn the repo.** Read the worktree's CLAUDE.md and README before
   editing. Its conventions beat the factory's wherever they differ. For
   anything touching repo settings, status checks or a new repo, read
   `repos/github-repos/terraform/terraform.tfvars` as well.
4. **Make the change**, matching the surrounding code.
5. **Verify locally**, from the worktree:
   - `make lint` (if there's no Makefile target, `pre-commit run --all-files`)
   - `make test`, if the repo has it
   - For an app: `make run` in the background with a free `PORT=`. Smoke-test
     the thing you changed (curl the endpoint, run the CLI), then stop it.
   - Fix what fails. If something fails for a reason unrelated to the change
     (for example, a tool missing from the container), say so rather than
     working around it.
6. **Commit** with a Conventional Commit message. The pre-commit and
   commit-msg hooks run. Fix and re-commit if they reject it; never use
   `--no-verify`.
7. **Ship**: `git push -u origin <branch>`, then `gh pr create --fill` (or
   write a short summary body), then `gh pr checks --watch`.
8. **Report**: the PR URL, the check results, what you verified locally, and
   anything the user still has to do. That includes merging, and `make apply`
   for Terraform repos. Never merge or apply yourself.
