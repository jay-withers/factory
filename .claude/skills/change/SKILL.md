---
name: change
description: Make one change in one jay-withers repository and ship it as a PR - worktree, edit with tests, run locally, review the diff, verify, Conventional Commit, push, open PR, watch checks. Use for any request that targets a single repo.
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
4. **Make the change**, matching the surrounding code, with tests:
   - A `fix:` comes with a regression test. Write it first and see it fail
     for the reported reason, then make it pass.
   - A `feat:` comes with tests for the new behaviour, not just an existing
     suite that still passes.
   - Where the repo has no test suite (most Terraform repos), say so in the
     report rather than inventing one.
5. **Check it works**, from the worktree:
   - Iterate with `make test` (and `make lint`).
   - For an app: `make run` in the background with a free `PORT=`. Smoke-test
     the thing you changed (curl the endpoint, load the page, run the CLI),
     then stop it.
   - Fix what fails. If something fails for a reason unrelated to the change
     (for example, a tool missing from the machine), say so rather than
     working around it.
6. **Review the diff** before committing: from the worktree, run the
   `code-review` skill at `medium` on the uncommitted change. Fix every
   finding that holds up, adding a regression test for each real bug. Any
   you leave, and why, go in the report.
7. **Verify and commit.** Run `../../scripts/verify.sh` from the worktree: it
   runs `make lint` and `make test` and records the exact tree that passed.
   Then commit with a Conventional Commit message. The pre-commit and
   commit-msg hooks run; fix and re-commit if they reject it, and never use
   `--no-verify`. A Claude Code hook blocks `git push` and `gh pr create`
   unless the commit's tree is the one `verify.sh` passed, so if anything
   changed after verifying (a hook's fix, a later edit), run it again and
   commit what it changed (a new commit, never an amend of a pushed one).
   The same goes for every later push, such as a fix for a failing CI check.
   Never work round the hook.
8. **Ship**: `git push -u origin <branch>`, then `gh pr create` with a short
   summary body, then `gh pr checks --watch`. If the change settles something
   that is the user's to choose and the request didn't (what a screen opens
   on, a default, what's hidden or dropped, a behaviour a test now pins), list
   each one under a **Decisions for you** heading in the body, in a line
   each: what you chose and the alternative. Leave the heading out when there
   are none. Once every
   required check has passed, merge it with `gh pr merge --squash`, unless the
   user asked to leave it open. If the branch is behind main (the rulesets
   require it up to date), `gh pr update-branch` and wait for the checks again.
   Never `--admin`, never round the ruleset.
9. **Report**: the PR URL, the check results, what you verified locally,
   review findings you left unfixed, any **Decisions for you** from the PR
   body, and
   anything the user still has to do: applying a Terraform change (run
   `cd-terraform` by hand, or `make apply` where a repo has no CD), and
   merging if it was left open. Never apply yourself.
