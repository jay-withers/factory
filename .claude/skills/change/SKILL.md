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
5. **Bring the docs up to date in the same change.** It isn't done while any
   doc still describes the old behaviour. Collect the names the change
   touched (files, make targets, env vars, settings, workflow inputs,
   endpoints, resources, behaviours), then:
   - **This repo:** grep its Markdown for each name, and reread the README,
     CLAUDE.md and `docs/` sections about the area you changed. Update
     whatever is now false or missing, along with `.env.example`, Makefile
     `##` help text and comments next to the change. Regenerate generated
     docs (terraform-docs runs in pre-commit).
   - **Factory:** grep this repo's `docs/`, `README.md`, `CLAUDE.md` and
     `.claude/skills/` for the repo name and the same names. Each doc owns a
     kind of fact. [delivery.md](../../../docs/delivery.md) owns CI/CD,
     identities, required checks, pending/failed issues and Renovate.
     [repo-standard.md](../../../docs/repo-standard.md) owns the shape every
     repo has (targets, files, tooling, exceptions).
     [greenfield.md](../../../docs/greenfield.md) owns apply order and
     tenant-bound literals. [autonomy.md](../../../docs/autonomy.md) owns when
     to ask. [architecture.md](../../../docs/architecture.md) owns how the
     pieces connect: a new or removed repo, shared resource, dependency,
     trust path or delivery stage changes the slide that draws it, diagram
     and speaker notes both. A change in one of those areas almost always needs its doc
     updated.
   - **Other repos:** grep `repos/*/` Markdown for the names too, since a
     changed workflow input or appkit API is documented by its callers.
   Fix the target repo's docs in this PR. Put factory's in a companion PR:
   `make task REPO=factory BRANCH=docs/<slug>`, the same verify-and-ship
   steps, merged once the main PR has merged. Another repo's docs get their
   own /change, or a follow-up line in the report if they're out of scope.
   `verify.sh` fails on any link, path or `make` target in the Markdown that
   the change broke. It can't tell whether prose is still true. That part
   is this step.
6. **Check it works**, from the worktree:
   - Iterate with `make test` (and `make lint`).
   - For an app: `make run` in the background with a free `PORT=`. Smoke-test
     the thing you changed (curl the endpoint, load the page, run the CLI),
     then stop it.
   - Fix what fails. If something fails for a reason unrelated to the change
     (for example, a tool missing from the machine), say so rather than
     working around it.
7. **Review the diff** before committing: from the worktree, run the
   `code-review` skill at `medium` on the uncommitted change. Fix every
   finding that holds up, adding a regression test for each real bug. Any
   you leave, and why, go in the report.
8. **Verify and commit.** Run `../../scripts/verify.sh` from the worktree: it
   runs `make lint`, the docs check and `make test`, and records the exact
   tree that passed.
   Then commit with a Conventional Commit message. The pre-commit and
   commit-msg hooks run; fix and re-commit if they reject it, and never use
   `--no-verify`. A Claude Code hook blocks `git push` and `gh pr create`
   unless the commit's tree is the one `verify.sh` passed, so if anything
   changed after verifying (a hook's fix, a later edit), run it again and
   commit what it changed (a new commit, never an amend of a pushed one).
   The same goes for every later push, such as a fix for a failing CI check.
   Never work round the hook.
9. **Ship**: `git push -u origin <branch>`, then `gh pr create` with a short
   summary body, then `gh pr checks --watch`. The body has a **Docs** line:
   the docs this PR updated, the companion factory PR, or "none needed" and
   why. If the change settles something
   that is the user's to choose and the request didn't (what a screen opens
   on, a default, what's hidden or dropped, a behaviour a test now pins), list
   each one under a **Decisions for you** heading in the body, in a line
   each: what you chose and the alternative. Leave the heading out when there
   are none. Once every
   required check has passed, merge it with `gh pr merge --squash`, unless the
   user asked to leave it open. If the branch is behind main (the rulesets
   require it up to date), `gh pr update-branch` and wait for the checks again.
   Never `--admin`, never round the ruleset.
10. **Report**: the PR URL (and the companion factory docs PR, if any), the
    check results, the **Docs** line, what you verified locally, review
    findings you left unfixed, any **Decisions for you** from the PR body,
    docs elsewhere that still need updating, and anything the user still has
    to do: applying a Terraform change (run `cd-terraform` by hand, or
    `make apply` where a repo has no CD), and merging if it was left open.
    Never apply yourself.
