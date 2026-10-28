# Delivery: how a change reaches Azure

How code and infrastructure get from a merged PR to the `dev` environment,
across every `jay-withers` repo. The mechanics live in
[jay-withers/workflows](https://github.com/jay-withers/workflows) (shared
reusable workflows) and
[jay-withers/github-repos](https://github.com/jay-withers/github-repos)
(identities, permissions, required checks). Each repo's own workflows are thin
callers. This page is the map. Each repo's README and CLAUDE.md cover its own
details.

## The flow

```text
PR ──► required checks ──► merge (you, or Renovate auto-merge)
         │                    │
         │                    ├─► cd-tag ──► version tag
         │                    │      └─ app files changed? ──► cd-publish
         │                    │                                 ├─ build + push image (ghcr.io)
         │                    │                                 └─ deploy: `make deploy IMAGE_TAG=<tag>` to dev
         │                    │                                      └─ `make smoke` ──► fails? roll back to the previous tag
         │                    │
         │                    └─► cd-terraform (terraform/** changed) ──► plan dev
         │                           └─ changes? ──► `terraform-pending` issue
         │                                           └─ you: Run workflow ──► apply
         │
         ├─ terraform-plan: dev plan, commented on the PR (fails on error)
         └─ container-build: image builds and passes Trivy (skipped = pass)
```

- **App code:** `cd-tag` creates a tag on every merge. It calls `cd-publish`
  only when `src/`, `Dockerfile`, `pyproject.toml` or `uv.lock` changed since
  the previous tag. `cd-publish` runs as jobs inside the `cd-tag` run. Only
  manual runs appear under cd-publish in the Actions sidebar.
- **Infrastructure:** `cd-terraform` plans dev on any merge that touches
  `terraform/**` but **applies only when you run it by hand** (Actions → Run
  workflow), applying exactly the plan it prints. App code deploys itself;
  infrastructure waits for you.
- **Every app deploy is smoke-tested, and rolls back on failure.** See
  [Smoke test and rollback](#smoke-test-and-rollback).
- **Redeploy an existing tag:** run `cd-publish` from the Actions tab with the
  tag. Do this after a failed deploy, or after an apply that recreated a job
  (it comes back on Terraform's placeholder image).
- **Only dev** is ever applied or deployed.

Repos with this flow: repo-agent, gym-log, finances, career, security-testing
(app + infra); observability (Grafana; app + infra, with a smoke test of its
own because Grafana can't serve the shared `/healthz`); azure-container-apps (infra); azure-support-agent (infra, with
the image version in Terraform, so a Renovate image bump is an infra change);
market-agent (app + infra; an apply that recreates its dashboard certificate
on `cae-platform-dev` runs locally). template-repo-terraform-root ships a dormant `cd-terraform`
that switches on once a repo made from it adds `terraform/backends/dev.hcl`.
azure-landingzone and terraform-root-aks have no CD identity, on purpose:
their applies create role assignments and policy the pipeline identities are
never granted, so you apply those by hand.

## Smoke test and rollback

A green `az containerapp update` only means Azure accepted the image. Every app
scales to zero, so a revision whose container never starts can go live
unnoticed. So the shared `container-apps-deploy.yml` (workflows v1.13.0+)
proves each deploy, for any repo whose Makefile has a `smoke` target:

1. `make deployed-tag` records the tag live now (nothing for Terraform's
   placeholder image).
2. `make deploy IMAGE_TAG=<tag>`.
3. `make smoke IMAGE_TAG=<tag>` runs `scripts/smoke.sh`. For an app it checks
   that the configured image is right and that `/healthz` on the app's
   default FQDN reports `version == <tag>`, waiting up to 5 minutes for a cold
   start. Then `/readyz` must answer 200. For a job it checks the configured
   image, then starts **one `selfcheck` run** of it: the job's own template
   (image, identity, env, secret references) with its args swapped for
   `selfcheck`, through ARM's `jobs/start` API (`az containerapp job start
   --args` rebuilds the template from its flags and drops the env). The app's
   `selfcheck` command loads settings, resolves the secrets the job reads and
   reaches its storage or database, then exits. It never emails, calls an LLM,
   trades or scans. Every job's run starts before any is awaited (10 minutes
   at most).
4. If step 2 or 3 fails, the workflow redeploys and smoke-tests the recorded
   tag with `SMOKE_PHASE=rollback` (workflows v1.14.0+), then **fails the run
   anyway**. On a rollback the selfcheck runs are skipped, and so is `/readyz`
   for an image without `version`: the old image may predate them, and it has
   already run here. The `deploy-failed` issue says whether
   the rollback held.

Repos with it: gym-log, finances, career, market-agent (apps + jobs);
repo-agent, security-testing (jobs). `scripts/smoke.sh` is shared verbatim
between them, so change it in all six. azure-support-agent's image ships
through Terraform, so it has none.

- **Keep `version` in `/healthz`.** Without it the check falls back to
  "the latest ready revision runs the image", a weaker test that exists only
  so a rollback to an older image passes.
- **Keep `selfcheck` side-effect free, and complete.** It runs on every
  deploy, so anything it sends is sent every time. And a secret a job starts
  reading but `selfcheck` doesn't check deploys green and fails at the first
  scheduled run.
- **A rollback moves the image, nothing else.** A release that changes stored
  data or a schema in a way the previous version can't read must not rely on
  it.
- **One environment, one revision.** There's no staging and no blue-green: with
  one replica and one user, the gain over rolling back is seconds of downtime,
  against `revision_mode = "Multiple"` and traffic management in every app.

## Deploy history

Every run of `container-apps-deploy.yml` (workflows v1.16.0+) ends by writing
one row to `Deployments_CL` in the platform's Log Analytics workspace, through
the Logs Ingestion API: repo, app, version and previous version, outcome
(`success`, `untested`, `rolled_back`, `failed`), `renovate` or `manual`
trigger, commit, run URL and lead time. It runs whatever the outcome, after
the `deploy-failed` issue step, so a failed post turns the run red without
reading as a failed deploy.

- **It needs** `EVENTS_INGESTION_ENDPOINT` and `EVENTS_DCR_IMMUTABLE_ID` on the
  repo's `dev` environment and `Monitoring Metrics Publisher` on
  `dcr-platform-events-dev`. github-repos sets both for a consumer with
  `send_events = true`. Without the variables the step is skipped with a
  notice.
- **A repo records nothing until its pin reaches v1.16.0.**
- **`OpsEvents_CL`** sits beside it for heartbeats, drift, expiry and restore
  tests (later phases of the observability plan).
- **Grafana** ([observability](https://github.com/jay-withers/observability))
  reads both tables. Its Deployments dashboard is the queryable form of this
  history.

## What waits for you, and how you hear about it

**Terraform changes are applied by hand.** Merging (yours or Renovate's) only
plans. A plan with changes opens a **`terraform-pending`** issue (one per
directory and environment) with the plan summary and any deletes or replaces
called out. Creating it emails you, later merges only refresh it, and
repo-agent's weekly digest lists it (`delivery.terraform_pending`). Review the
plan, then run `cd-terraform` from the Actions tab: that applies it and closes
the issue. No labels, no blocked PRs.

**Failed deploys open an issue.** GitHub emails a failed run only to whoever
triggered it, and Renovate triggers most deploys. So a failed deploy or apply
on `main` opens a **`deploy-failed`** issue that @-mentions you. A repeat
failure comments on it, the next success closes it, and the digest lists it
while open (`delivery.deploy_failed`).

**Stuck Renovate PRs are named.** A Renovate PR that can't merge (a required
check failing, or a conflict) for a week appears in the digest as
`renovate.blocked_prs`, by name. Auto-merge never takes those, and every update
inside stays unapplied. The lock-file maintenance PRs sat like that for a month,
freezing CVE fixes.

repo-agent reads these issues through its GitHub App's **Issues: read**
permission; without it the delivery checks stay silent.

## Security scanning

| What | Where | Blocks |
| --- | --- | --- |
| Terraform: Checkov + tflint | pre-commit, locally and in CI | Yes (`pre-commit / Pre-commit`) |
| Container images: Trivy | shared `docker.yml`, every build | PRs on fixable CRITICAL/HIGH (`container-build`); never a publish |
| Code: CodeQL | `ci-codeql`, Python repos | No; alerts in the Security tab |
| Secrets: gitleaks | pre-commit | Locally, and in CI |

Trivy and CodeQL findings land in each repo's Security tab (code scanning),
which repo-agent's digest reads. Accepted image risks go in `.trivyignore`.
**Private vulnerability reporting** is on for every repo (github-repos): a
"Report a vulnerability" button that turns a report into a private draft
advisory, so a hole in a public repo needn't be disclosed in a public issue.

## Required checks

Set per repo in github-repos' `terraform.tfvars` (`required_status_checks`):

| Check | Meaning |
| --- | --- |
| `pre-commit / Pre-commit` | All hooks |
| `test / Test` | Test suite (app repos) |
| `terraform / Terraform` | Credential-free init + validate |
| `terraform-plan` | Dev plan; fails only on error |
| `container-build` | Image builds and has no fixable CRITICAL/HIGH vulnerability (app repos) |

**A required check must report on every PR.** One that never reports leaves
PRs pending for ever. So nothing required is path-filtered on its trigger.
Filters live in a `changes` job (dorny/paths-filter), and an always-reporting
gate job (`terraform-plan`, `container-build`) passes when the work was skipped
and fails when it failed. Add the gate to the repo first, then require it in
github-repos.

## Renovate

Shared preset: [jay-withers/renovate](https://github.com/jay-withers/renovate).
It auto-merges everything, majors included, once required checks pass, in a
batch on Mondays, and only for releases at least 3 days old. What a merged update then does:

| Update | After auto-merge |
| --- | --- |
| Python deps (`uv.lock`), base-image digest | build + deploy |
| Terraform providers, `.terraform-version`, azure-support-agent image | plan; a `terraform-pending` issue if it changes anything, applied when you run cd-terraform |
| GitHub Actions, pre-commit hooks, shared workflow pins | tag only |
| Python base-image **minor** (3.14 → 3.15) | never auto-merged; review it |

## Identities and permissions

github-repos' `state_consumers` creates one user-assigned identity per repo
(`uai-<repo>-deploy-dev` in `rg-tfstate-shared`), federated to the repo's `dev`
GitHub environment. It sets `AZURE_CLIENT_ID`, `AZURE_TENANT_ID` and
`AZURE_SUBSCRIPTION_ID` on that environment.

- **OIDC subject:** repos use GitHub's immutable form,
  `repo:jay-withers@<owner id>/<repo>@<repo id>:environment:dev`. The readable
  `repo:jay-withers/<repo>` never matches (AADSTS700213).
- **Jobs must run in the `dev` environment** to see the variables and get that
  subject. A calling job outside it reads them as empty, which is why callers
  pass no credentials and can't gate on them. The shared workflows set
  `environment:` themselves (a job that calls a reusable workflow can't).
- **Resource groups:** with `create_resource_groups = true` on its
  `state_consumers` entry, github-repos creates the repo's
  `deploy_resource_groups` itself (`prevent_destroy`, in `northeurope`, the
  environment's region) and the repo reads them by data source. Without it,
  the repo creates its own group with a local first apply and github-repos
  looks it up. Only observability has moved so far; the rest follow.
- **Grants:** Contributor on the repo's own resource group(s); Reader on the
  subscription (plans resolve shared resources); Storage Blob Data Contributor
  on its state container; **Container Apps Environment Joiner** (custom role:
  read + join) on `cae-platform-dev`. Writing any container app or job checks
  `managedEnvironments/join/action` on the environment
  (`LinkedAuthorizationFailed` without it). With `send_events`,
  **Monitoring Metrics Publisher** on the platform's events rule.
- **Role assignments inside the repo's own group** (Key Vault, storage
  containers): only with `create_resource_groups`, which also grants **Role
  Based Access Control Administrator** on each group, conditioned to exclude
  Owner, User Access Administrator and RBAC Administrator (Microsoft's "Allow
  most roles, but don't allow others to assign roles" example). Those apply in
  CD. The pipeline can't grant or remove any of the three, and can't create a
  custom role to get round it.
- **Not granted: role assignments anywhere else.** A grant outside the repo's
  own group (observability's Log Analytics Reader on the platform workspace,
  security-testing's subscription Reader), or any grant in a repo still on
  `create_resource_groups = false`, fails in CD, so run `make apply` locally
  for it.
- **Called workflows never exceed their caller's permissions.** `cd-tag`'s
  `publish` job grants `id-token: write` and `issues: write` so `cd-publish`'s
  deploy can use them.

**github-repos itself is applied by hand** (`make apply`), on purpose. It
holds rights over every repo and every pipeline's permissions.

## Traps found the hard way

- **"Whoever applies" RBAC.** Role assignments keyed on
  `data.azurerm_client_config.current.object_id` move to the pipeline identity
  on every CD apply (and fail). Grant them to explicit object IDs in
  `environments/dev.tfvars` (`key_vault_administrator_object_ids`).
- **Terraform-managed Key Vault secrets** need data-plane access just to plan.
  azure-support-agent grants its pipeline identity Secrets Officer for this.
- **Managed-certificate custom domains:** after `make bind-domain` the domain
  is `SniEnabled`. Without
  `ignore_changes = [certificate_binding_type, container_app_environment_certificate_id]`
  every plan proposes replacing it, which unbinds the certificate.
- **Set `workload_profile_name = "Consumption"` on every container app and
  job.** The shared environment is Consumption-only and the API reports that
  back. Left unset, every plan shows `"Consumption" -> null`, so every merge
  opens a `terraform-pending` issue for nothing.
- **A cached OS-upgrade layer goes stale.** CI caches image layers by
  instruction, so an `apt-get upgrade`/`apk upgrade` step is reused until its
  line or the base digest changes, and a fix published since never reaches
  the image. Trivy then fails a PR on a "fixable" CVE the step exists to fix
  (market-agent's curl and libssl3, October 2026, which also held up
  Renovate's digest PR). `docker.yml` (workflows v1.15.0+) passes
  `OS_PATCH_DATE`, today's UTC date, to every build: declare `ARG
  OS_PATCH_DATE` directly before the upgrade step and that layer re-runs once
  a day while everything above it stays cached. Declared in
  security-testing's image and market-agent's dashboard. The Python app
  images (gym-log, finances, career, repo-agent, market-agent's API) carry no
  upgrade step of their own: they build on dev-containers' `python-app` and
  `python-app-builder`, which upgrade on their own rebuild (`ARG REBUILD`),
  so they pick up OS fixes through Renovate's digest bumps of those images.
- **New Python minors break image builds** before tests notice. Compiled deps
  (httptools, pydantic-core, psycopg-binary) have no wheels yet, the slim image
  has no compiler, and `ci-python` pins its own version. Keep the Dockerfile
  and `ci-python` on the same minor.
- **terraform-docs must not read the lock file** (`lockfile: false`). Reading
  it, every lock refresh rewrote the README, Renovate's lock-file maintenance
  PRs (which can't run hooks) failed pre-commit for a month, and the
  transitive Python dependencies they carried, CVE fixes included, never
  merged.
- **Azure/naming slugs:** a user-assigned identity is `uai-…`, not `id-…`.
- **Moving a resource group to github-repos goes import first.** Add
  `create_resource_groups = true` and an `import` block for the group in
  github-repos and apply it, then drop it from the repo with
  `removed { from = azurerm_resource_group.this  lifecycle { destroy = false } }`
  and a data source of the same name. Name, region and tags must match, or
  the import shows a diff. The other order leaves the group unmanaged for a
  while; a plain delete of the resource block would destroy it. Delete the
  `import` block in a later change.

## Adding an app repo to this flow

1. github-repos: add the repo to `var.repos` and `state_consumers` with
   `deploy_resource_groups`, `create_resource_groups = true`,
   `join_container_app_environments` and `send_events = true`, then
   `make apply`. That creates the resource group, the identity and every
   grant on the group.
2. In the repo: `ci-terraform` (plan via `terraform-deploy.yml` +
   `terraform-plan` gate), `cd-terraform`, `ci-container-build` (`changes` job
   + `container-build` gate), `cd-tag` → `cd-publish` with a `deploy` job
   (`container-apps-deploy.yml`), and a `make deploy` target that takes
   `IMAGE_TAG` and `ENV`. Copy from gym-log.
3. Grant admin RBAC to explicit object IDs, never to "whoever applies", and
   set `workload_profile_name = "Consumption"` on each app and job.
   Create every app and job on `ghcr.io/jay-withers/dev-containers/placeholder:latest`
   with the image under `ignore_changes`, never on a release tag: no release
   exists before the first apply, and a guessed tag passes plan and apply and
   fails only on the pull. The placeholder answers 200 on every path on
   `$PORT` (set it to the ingress target port) and exits 0 inside a job.
   Set `args`, never `command`: a `command` replaces the placeholder's
   entrypoint, so it can't start (market-agent still sets one).
   Read the resource group with `data "azurerm_resource_group"`, never create
   it: github-repos owns it.
4. Apply through `cd-terraform`; no local first apply is needed unless the
   repo grants roles outside its own group (then `make apply` locally for
   those). Then require `terraform-plan` and `container-build` in github-repos.
