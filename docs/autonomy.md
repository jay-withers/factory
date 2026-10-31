# When to ask, and when to just do it

For Claude sessions working from this repo. The aim is that a short prompt
("bump X", "add Y to gym-log", "fix the failing drift check") runs to a
merged PR without questions. The estate's guardrails catch mistakes; the
user's attention is kept for decisions only they can make.

## The guardrails this relies on

- **Every change is a PR** through that repo's required checks and the
  "Protect main" ruleset. Nothing pushes to `main`.
- **Infrastructure never applies itself.** A merge only plans. The user reads
  the `terraform-pending` issue and runs `cd-terraform`.
- **App releases from a person are held** (`deploy-pending`), and every
  deploy is smoke-tested with rollback.
- **`.claude/settings.json` denies** the hard-rule commands (applies,
  destroys, force-pushes, admin merges).
- **Privilege alerts email the user** on any role, policy or federated
  credential change, whoever made it.

## Just do it

When the request points that way, go ahead without asking:

- Making the change, testing it, opening the PR, and squash-merging once
  every required check passes (unless asked to leave it open).
- Following the user's earlier choices without asking again.
- Choosing an approach where the code, this repo's docs or
  [repo-standard.md](repo-standard.md) already give the answer.
- Fixing what the change itself broke, including follow-up PRs, and small
  bugs found on the way that are clearly wrong.
- Read-only checks: `make plan`, `gh workflow run schedule-drift` (it only
  plans), re-running a failed CI job, reading logs and Azure state.
- Opening the next PR in a chain once the one before it has merged or been
  applied.
- Updating docs (this repo's, the repo's CLAUDE.md and README) to match what
  changed.

## Ask first, in one batched question

- **A new privileged identity**, or widening one: any new role at
  subscription scope, User Access Administrator, RBAC Administrator, or an
  admin PAT.
- **Overturning a written rule or decision**: a hard rule in CLAUDE.md, or a
  repo's "decisions not to re-litigate" (e.g. no Entra sign-in for users).
- **New ongoing cost**: anything billed by the hour or month beyond cents.
  Rebuilding the deleted AKS cluster counts.
- **Deleting data, or anything with `prevent_destroy`**: state containers,
  storage accounts, Key Vaults, the gym-log blob.
- **Something visible to other people**: making a repo or package public,
  emailing or posting anywhere outside GitHub.
- **A real choice of direction** the request leaves open and the code doesn't
  settle, where getting it wrong means redoing the work.

Put every open question in one AskUserQuestion up front, then run to the end.
Don't ask for approval of a plan once the direction has been chosen.

## Never, even when asked

These are the hard rules in [CLAUDE.md](../CLAUDE.md#hard-rules): applying
or destroying Terraform, running `cd-terraform`, pushing to a default branch,
force-pushing, admin or non-squash merges, and deleting, archiving or
renaming a repo. Say what the user needs to run instead.

## Hand-off

End with what changed (PR links), what's waiting for the user (the
`terraform-pending` or `deploy-pending` issue, and what it will do), and
anything you found but didn't fix. Report failures plainly.
