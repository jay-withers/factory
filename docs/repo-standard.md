# The standard repo shape

What every `jay-withers` repo looks like, read off the estate as it is
(2026-10-31). Use it to build a new repo, to check an old one, and to tell
a deliberate exception from drift. Each repo's own CLAUDE.md wins where it
says otherwise. Where a row below lists exceptions, those are the only ones
known.

## Every repo

| Path | What | Notes |
| --- | --- | --- |
| `README.md` | Why, how to run, first-time setup | The person-facing half |
| `CLAUDE.md` | Traps and decisions not to undo | Not a copy of the README |
| `LICENSE` | | |
| `Makefile` | `make` with no target prints help | `help`, `install`, `lint` at minimum |
| `.pre-commit-config.yaml` | Hooks pinned by SHA, tag as a comment | Base hooks, gitleaks, actionlint, shellcheck, commitlint |
| `commitlint.config.js` | Conventional Commits | `no-commit-to-branch` blocks commits to `main` |
| `renovate.json` | Extends `github>jay-withers/renovate` | Never the old `template-renovate` name |
| `.devcontainer/devcontainer.json` | A `ghcr.io/jay-withers/dev-containers/*` image by tag | Exceptions: dev-containers, toolchain |
| `.github/workflows/` | Thin callers of `jay-withers/workflows`, pinned by SHA | See below |

git-demo is the deliberate exception to all of it: no CI, hooks there to fail
on purpose.

Repo settings (merge methods, the "Protect main" ruleset, required checks,
description, topics) are never set in the repo. They live in
`repos/github-repos/terraform/terraform.tfvars`.

## Workflows

The name says when it runs: `ci-` on pull requests, `cd-` after merge,
`schedule-` on a cron. Each one calls a workflow in `jay-withers/workflows`
and holds only what is specific to the repo.

| File | Calls | Required check | Who has it |
| --- | --- | --- | --- |
| `ci-pre-commit.yml` | `pre-commit.yml` | `pre-commit / Pre-commit` | Every repo (named `ci-lint.yml` in github-repos, renovate, template-repo-base) |
| `ci-codeql.yml` | `codeql.yml` | none (blocks on new high/critical alerts) | Every repo |
| `cd-tag.yml` | `release.yml` | | Every repo |
| `ci-terraform.yml` | `terraform.yml` (+ `terraform-deploy.yml` plan) | `terraform / Terraform`, `terraform-plan` | Terraform repos |
| `cd-terraform.yml` | `terraform-deploy.yml` | | Terraform repos with a backend |
| `schedule-drift.yml` | `terraform-deploy.yml` with `drift: true` | | Every repo with `cd-terraform` |
| `ci-python.yml` | `python.yml` | `test / Test` | Python apps |
| `ci-container-build.yml` | `docker.yml` | `container-build` (gate) | Image repos |
| `cd-publish.yml` | `docker.yml` + `container-apps-deploy.yml` | | Container Apps apps, called from `cd-tag` |

Rules that hold everywhere:

- **A required check reports on every PR.** No path filter on the trigger.
  Filter in a `changes` job and add an always-reporting gate job. Put the
  gate in the repo before requiring it in github-repos.
- **Credentials only in a GitHub environment** (`dev`, or a main-only
  `apply`), never as repo-level variables. The shared workflow sets
  `environment:`. The calling job passes no credentials and never gates on
  `vars.AZURE_CLIENT_ID`.
- **Pins move through Renovate**, not by hand, unless a fix can't wait for
  Monday.

## Terraform repos

```text
terraform/
  versions.tf              # terraform{} + provider{}, the only place for both
  main.tf, main.<topic>.tf # resources
  data.tf, locals.tf, outputs.tf (or <kind>.<topic>.tf)
  variables.required.tf    # (or variables.tf) no defaults
  variables.optional.tf
  backends/dev.hcl         # partial azurerm backend; Entra auth
  environments/dev.tfvars  # only dev is applied
  README.md                # prose above, terraform-docs block below
.terraform-version
scripts/check-tf-standards.sh  # shared verbatim; re-copy, never edit
```

- **Layout is enforced** by `check-tf-standards.sh` in pre-commit.
- **The lock file has hashes for** linux_amd64, linux_arm64 and darwin_arm64.
- **terraform-docs runs with `lockfile: false`.**
- **Look shared resources up by name**, never with `terraform_remote_state`.
  Read the resource group with a data source: github-repos (or the landing
  zone, for a spoke) owns it.
- **Never grant to "whoever applies".** Grants go to explicit object IDs from
  `TF_VAR_*` variables. github-repos sets them.
- **Roots that differ on purpose:** azure-landingzone (one directory per
  component, backend in `backend.tf`, `terraform.tfvars`) and github-repos
  (single `terraform.tfvars`, `environment-files: false`). Both apply from a
  main-only `apply` environment with no PR plan.

## App repos (Container Apps)

`src/`, `tests/`, `pyproject.toml` + `uv.lock`, `Dockerfile` (built on
dev-containers' `python-app` images), `.env.example`, and `make run`, `test`,
`build`, `deploy`, `deployed-tag`, `smoke`, `secrets`, `logs`, `url`.

- **`scripts/smoke.sh` is shared verbatim** between career, finances,
  gym-log, market-agent, repo-agent and security-testing. observability has
  its own.
- **`/healthz` reports `version`**, and **`selfcheck`** is side-effect free
  and checks every secret a job reads.
- **Create apps on `dev-containers/placeholder:latest`** with the image under
  `ignore_changes`. Set `args`, never `command`, and
  `workload_profile_name = "Consumption"`.
- **The full checklist for a new app** is in [delivery.md](delivery.md#adding-an-app-repo-to-this-flow).
  Copy from gym-log.

## Known drift from this standard

Fix these when you're in the repo for something else, or in a sweep:

- template-repo-terraform-root's CLAUDE.md still names `template-pipelines`
  (now `workflows`). So does workflows' own README.
- renovate's README still uses the `template-renovate` name.
- market-agent still sets `command` on its workloads.
- terraform-root-aks still uses readable OIDC subjects, not the immutable
  form.
- azure-container-apps' README "Bootstrapping" still says to create its state
  container by hand. github-repos creates it now, so on a fresh subscription
  that step collides (see [greenfield.md](greenfield.md)).
