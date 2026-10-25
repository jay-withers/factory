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
- **Redeploy an existing tag:** run `cd-publish` from the Actions tab with the
  tag. Do this after a failed deploy, or after an apply that recreated a job
  (it comes back on Terraform's placeholder image).
- **Only dev** is ever applied or deployed.

Repos with this flow: repo-agent, gym-log, finances, career, security-testing
(app + infra); azure-container-apps (infra); azure-support-agent (infra, with
the image version in Terraform, so a Renovate image bump is an infra change).
market-agent, azure-landingzone and terraform-root-aks have no CD identity:
you apply and deploy those by hand.

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
- **Grants:** Contributor on the repo's own resource group(s); Reader on the
  subscription (plans resolve shared resources); Storage Blob Data Contributor
  on its state container; **Container Apps Environment Joiner** (custom role:
  read + join) on `cae-platform-dev`. Writing any container app or job checks
  `managedEnvironments/join/action` on the environment
  (`LinkedAuthorizationFailed` without it).
- **Not granted: role assignments.** A change that adds or replaces a role
  assignment fails in CD, so run `make apply` locally for it.
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

## Adding an app repo to this flow

1. github-repos: add the repo to `var.repos` and `state_consumers` with
   `deploy_resource_groups` and `join_container_app_environments`, then
   `make apply`.
2. In the repo: `ci-terraform` (plan via `terraform-deploy.yml` +
   `terraform-plan` gate), `cd-terraform`, `ci-container-build` (`changes` job
   + `container-build` gate), `cd-tag` → `cd-publish` with a `deploy` job
   (`container-apps-deploy.yml`), and a `make deploy` target that takes
   `IMAGE_TAG` and `ENV`. Copy from gym-log.
3. Grant admin RBAC to explicit object IDs, never to "whoever applies", and
   set `workload_profile_name = "Consumption"` on each app and job.
4. First `make apply` locally (it creates the resource group and grants), then
   require `terraform-plan` and `container-build` in github-repos.
