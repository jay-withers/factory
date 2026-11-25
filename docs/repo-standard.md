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
| `CLAUDE.md` | Traps and decisions not to undo | Not a copy of the README. Declined changes go under `## Decisions not to re-litigate`, so the next review doesn't propose them again |
| `LICENSE` | | |
| `Makefile` | `make` with no target prints help | `help`, `install`, `lint` at minimum |
| `.pre-commit-config.yaml` | Hooks pinned by SHA, tag as a comment | Base hooks, gitleaks, actionlint, shellcheck, commitlint |
| `commitlint.config.js` | Conventional Commits | `no-commit-to-branch` blocks commits to `main` |
| `renovate.json` | Extends `github>jay-withers/renovate` | Never the old `template-renovate` name |
| `mise.toml` | Every developer and CI tool, by exact version | Replaced `.devcontainer/` and `.terraform-version`; set a machine up with toolchain |
| `mise.lock` | Each tool's download URL and checksum, per platform | CI installs `--locked` when it exists; Renovate regenerates it in mise PRs; after a hand edit of `mise.toml`, run `mise lock` |
| `.vscode/extensions.json` | Recommended VS Code extensions | |
| `.github/workflows/` | Thin callers of `jay-withers/workflows`, pinned by SHA | See below |

git-demo is the deliberate exception to all of it: no CI, hooks there to fail
on purpose.

Repo settings (merge methods, the "Protect main" ruleset, required checks,
description, topics) are never set in the repo. They live in
`repos/github-repos/terraform/terraform.tfvars`.

## Workflows

The name says when it runs: `ci-` on pull requests, `cd-` after merge,
`schedule-` on a cron, `manual-` only when someone runs it. Each one calls a workflow in `jay-withers/workflows`
and holds only what is specific to the repo.

| File | Calls | Required check | Who has it |
| --- | --- | --- | --- |
| `ci-pre-commit.yml` | `pre-commit.yml` | `pre-commit / Pre-commit` | Every repo (named `ci-lint.yml` in github-repos, renovate, template-repo-base) |
| `ci-codeql.yml` | `codeql.yml` | none (blocks on new high/critical alerts) | Every repo |
| `cd-tag.yml` | `release.yml` | | Every repo |
| `ci-terraform.yml` | `terraform.yml` (+ `terraform-deploy.yml` plan) | `terraform / Terraform`, `terraform-plan` | Terraform repos |
| `cd-terraform.yml` | `terraform-deploy.yml` | | Terraform repos with a backend |
| `schedule-drift.yml` | `terraform-deploy.yml` with `drift: true` | | Every repo with `cd-terraform` |
| `manual-terraform-unlock.yml` | `terraform-unlock.yml` | | Every repo with `cd-terraform` |
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
`typecheck`, `build`, `deploy`, `deployed-tag`, `smoke`, `secrets`, `logs`, `url`.

- **`mise.toml`'s `python` is the image's Python** (major.minor). Local runs
  and `ci-python` test on it, so `ci-container-build` passes `"python":
  "python"` on the image (workflows v1.35.0+, `"python3"` for the ZAP image)
  and lists `mise.toml` in its path filter, and the build fails when they
  differ. No `python-version` input in `ci-python`: under mise it is ignored.

- **Shared Python comes from [appkit](https://github.com/jay-withers/appkit)**,
  never a copy: security headers, `/healthz` and `/readyz`, the passcode
  gate, secret resolution, the R2 backup job, the selfcheck loop and the
  browser-test helpers. Pin it by
  tag in `[tool.uv.sources]`
  (`appkit = { git = "https://github.com/jay-withers/appkit", tag = "vX.Y.Z" }`,
  with `"appkit[...]"` in `dependencies`), never as a PEP 508
  `appkit @ git+https://...` reference: Renovate bumps a uv git source's tag
  (running `uv lock`) but skips a direct reference. Take only the extras you
  use: `web` (headers, health, passcode), `azure` (keyvault), `backup`, and `e2e` in
  the dev extra. The builder needs dev-containers v0.22.0+, which has git. A
  fix to one of those goes in appkit with its regression test. career,
  finances, health, market-agent and repo-agent use it. security-testing is
  the deliberate exception: it runs on the ZAP image's Python 3.11 (appkit
  needs 3.12+), and its secret lookup is one env-then-vault helper.
- **Web apps have browser tests in `tests/e2e/`** (Playwright, through
  `appkit.testing`): the real app on a free port against seeded local data,
  covering the passcode gate, every screen, and each main write checked after
  a reload, with an autouse check that fails on any console error (a CSP
  block is one). `ci-python.yml` passes `playwright: true` (workflows
  v1.29.0+), so they run inside `test / Test` with no new required check.
  They skip locally without Chromium and fail under CI; `make e2e` installs
  it. career, finances and health have them.
- **The smoke test is jay-withers/workflows' `scripts/smoke.sh`**
  (workflows v1.30.0+), never a copy: `make smoke` fetches it at the commit
  `cd-publish.yml` pins `container-apps-deploy.yml` to, so CI and a local run
  agree and Renovate's pin bump moves it. The README of workflows has the
  Makefile snippet. A web app whose `/` answers 200 unauthenticated (the
  login page or a redirect to it) sets `browser-check: true` in
  `cd-publish.yml`: career, finances, health and observability.
  market-agent's dashboard is the deliberate exception: its nginx gate
  answers `/` with the login form as a 401 body so deep links survive, which
  the check reads as a failure. Its own Playwright suite covers it in CI.
  Renovate keeps the check's Playwright pin current (workflows' renovate.json).
- **mypy, configured in `pyproject.toml`** (`check_untyped_defs`, the pydantic
  plugin), pinned in the dev dependencies and run by `make typecheck`.
  `ci-python.yml` passes `typecheck: mypy`, `lint: true`, `coverage-min: "90"`
  and `diff-coverage: "90"` (workflows v1.34.0+), all inside `test / Test`:
  ruff (`ruff check` and `ruff format --check`, from the locked dev extra, so
  the same ruff as `make lint` and the pre-commit hook), at least 90% total
  coverage on every run, main included, and at least 90% of the lines a PR
  changes run by a test. **No PR coverage comment**: the floors enforce it,
  and the table is in the job summary, so callers grant no
  `pull-requests: write`. Every Python repo was at 90% or more when the floor
  went on (2026-11-25). Don't meet a floor with a test that only asserts a
  mock.
- **`/healthz` reports `version`**, and **`selfcheck`** is side-effect free
  and checks every secret a job reads.
- **A web app shows its release beside its name** in the header of every
  signed-in page: `IMAGE_TAG`, trimmed, through an `app_version` template
  global, small and dimmed, and nothing when it is unset (a local run). Not
  on the sign-in page. That is a choice about the page, not a secret, since
  `/healthz` reports the tag to anyone. Keep it beside the home link, not
  inside it, so the link's name is stable. career, finances, health and
  observability do this; market-agent's dashboard does the same from its
  `config.json`.
- **Create apps on `dev-containers/placeholder:latest`** with the image under
  `ignore_changes`. Set `args`, never `command`, and
  `workload_profile_name = "Consumption"`.
- **The full checklist for a new app** is in [delivery.md](delivery.md#adding-an-app-repo-to-this-flow).
  Copy from health.

## Known drift from this standard

- **terraform-root-aks issues readable OIDC subjects**, not the immutable
  form. Moving needs its repo's OIDC customisation changed and new subjects
  applied in azure-landingzone's `landingzones`. Do it when the cluster comes
  back.
- **market-agent sets `command`** and creates its workloads on a real release
  tag rather than the placeholder. It works, because the image's ENTRYPOINT is
  the same `marketagent` and `command` is under `ignore_changes`. Don't copy
  it. Move it to the placeholder and `args` only if those resources are being
  recreated anyway.
