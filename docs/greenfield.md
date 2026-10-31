# Greenfield: rebuilding the estate in a new tenant

How to stand the whole Azure estate up from nothing in a new tenant or
subscription, in dependency order. Written 2026-10-31 from the repos as they
are. Nobody has run it end to end yet, so check each step against that repo's
README as you go, and fix this page when it's wrong.

**GitHub stays as it is.** Repos, environments, rulesets and the OIDC owner
and repo IDs don't move with Azure. What changes is every Azure resource,
every identity, and the handful of literals listed under
[Values tied to the old tenant](#values-tied-to-the-old-tenant).

Every apply here is the user's, run locally with `make apply` as an Owner of
the new subscription, until step 6. cd-terraform can't work before then: the
`AZURE_*` variables on every GitHub environment still point at the old
tenant until github-repos is applied in the new one.

## Before you leave the old tenant

None of this comes back from Terraform. Copy it out first:

- **App data in storage accounts:** gym-log's training history (the one
  account with `prevent_destroy`), plus finances' and career's accounts. Use
  `azcopy` or download the blobs.
- **PostgreSQL:** market-agent's own server, and the `grafana` database on
  the platform's shared server (users and preferences only; dashboards ship
  in the image). Use `pg_dump`.
- **Key Vault secret values** for every app (`make secrets` lists the names
  per repo). The new vaults start empty.
- **Anything in `.env` files** you only have on the old machine.

Terraform state does not need copying: every root starts fresh.

## Order

```text
0  prerequisites
1  azure-landingzone bootstrap (local state)
2  github-repos: shared state account (script)
3  azure-landingzone management → governance → connectivity → landingzones
4  github-repos, pass 1: azure-container-apps' state container only
5  azure-container-apps
6  github-repos, full apply   ◄── cd-terraform works for every repo after this
7  cloudflare
8  apps: repo-agent, gym-log, finances, career, security-testing, market-agent
9  observability
10 terraform-root-aks (only when you want the cluster)
```

### 0. Prerequisites

- An Owner on the new subscription, signed in: `az login --tenant <tenant>`
  and `az account set -s <subscription>`. Also `gh auth login` and
  PowerShell 7 (for step 2). The `dev-containers/terraform` image has all of
  this.
- Register the resource providers the platform needs. `Microsoft.App`
  fails with `MissingSubscriptionRegistration` otherwise:

  ```bash
  for ns in Microsoft.App Microsoft.OperationalInsights Microsoft.Insights; do
    az provider register --namespace "$ns"
  done
  ```

- Decide whether the old subscription will still exist. Storage account
  names are global, so while `sttfsharedjw` exists anywhere you can't reuse
  the name (see step 2).
- Get the operator's new Entra object ID and UPN:
  `az ad signed-in-user show --query '{id:id,upn:userPrincipalName}'`.

### 1. azure-landingzone `bootstrap`

Its state is local and gitignored. **Move the old `terraform.tfstate` out of
`terraform/bootstrap/` first**, or the plan tries to manage the old tenant's
resources.

1. In `terraform/bootstrap/terraform.tfvars`, set both `blob_contributors`
   object IDs to the new operator. Leave `pipeline_identity.subject` alone:
   it names GitHub IDs, not Azure ones.
2. `make apply C=bootstrap`. It creates both state accounts (names seeded
   from the subscription ID, so they're new) and the landing zone's apply
   identity.
3. Put the new account names in the backend literals: the four
   `terraform/<component>/backend.tf` files (the platform account), and
   terraform-root-aks' `terraform/backends/dev.hcl` (the landing zone
   account). Open a PR in each repo for this. You'll apply from the
   azure-landingzone branch in step 3, and merge the PR afterwards.

### 2. github-repos: the shared state account

`make bootstrap` (`scripts/bootstrap-state.ps1`) creates `rg-tfstate-shared`,
`sttfsharedjw`, github-repos' own container and the operator's blob grant.

If the old `sttfsharedjw` still exists, choose a new name and change it in
one sweep before running the script. It appears in:

- github-repos: `scripts/bootstrap-state.ps1`, `terraform/versions.tf`, and
  the `storage_account_name` default in `terraform/variables.tf`.
- azure-landingzone: the `github_repos_apply.storage_account_name` default in
  `terraform/governance/variables.tf`.
- `terraform/backends/*.hcl` in azure-container-apps, cloudflare, market-agent,
  repo-agent, gym-log, finances, career, security-testing and observability.

### 3. azure-landingzone components

From the step 1 branch, in order:

```bash
make apply C=management
make apply C=governance     # needs management's workspace and step 2's account
make apply C=connectivity
make apply C=landingzones   # needs the hub and the private DNS zones
```

governance creates github-repos' apply identity. landingzones creates AKS's
resource group, identity and state container. Check the alert email lists in
the management and governance tfvars. Then merge the step 1 PR.

### 4. github-repos, pass 1

github-repos looks up `rg-platform-dev`, `cae-platform-dev` and the events
rule, and those come from azure-container-apps. But azure-container-apps
keeps its state in a container that github-repos creates. Break the cycle by
creating only that container first.

1. Set `TF_VAR_OPERATOR` on github-repos' `apply` environment by hand, with
   the new object ID and UPN (same JSON shape as now). Export the same value
   locally.
2. Apply only the container:

   ```bash
   make init
   terraform -chdir=terraform apply \
     -target='azurerm_storage_container.consumer["azure-container-apps"]'
   ```

Don't create the container with `az storage container create`, as
azure-container-apps' README says. github-repos would then fail to create it
and need an `import`.

### 5. azure-container-apps

Export the operator variables that step 6 will later set on its `dev`
environment: `TF_VAR_alert_email_address` and
`TF_VAR_postgres_entra_administrator`. Then run `make apply ENV=dev`. It
creates `rg-platform-dev`, the environment, Log Analytics, the shared
Postgres server and the events rule. Note `make outputs`: you'll need its
default domain, verification ID and Postgres FQDN below.

### 6. github-repos, full apply

`make apply`, locally, as yourself. This one apply:

- creates every app's resource group, identity, state container and grants;
- points every repo's `AZURE_CLIENT_ID`, `AZURE_TENANT_ID` and
  `AZURE_SUBSCRIPTION_ID` at the new tenant;
- sets the operator `TF_VAR_*` and events variables;
- sets the `apply` environments for itself, azure-landingzone and AKS.

From here, every repo plans on merge and applies through cd-terraform as
usual. To check, run `schedule-drift` in github-repos and azure-landingzone:
both should log in and plan with no changes.

### 7. cloudflare

Nothing in Azure, but two copied values change: `container_apps_default_domain`
and `custom_domain_verification_id` in `terraform/environments/dev.tfvars`,
from step 5's outputs. PR, merge, run cd-terraform. The `CLOUDFLARE_API_TOKEN`
secret is Cloudflare's, so it doesn't change. This has to land before any app
binds its custom domain.

### 8. Apps

For each of repo-agent, gym-log, finances, career, security-testing and
market-agent (the order doesn't matter between them):

1. Run cd-terraform. It creates the app and jobs on the placeholder image.
   Grants outside the app's own resource group are a local `make apply`
   (security-testing's subscription Reader, for example). The repo's README
   says which.
2. `make secrets`, and set the values saved before the move.
3. Restore data: gym-log, finances and career blobs into their new storage
   accounts, and market-agent's database into its new server.
4. Run `cd-publish` with the latest release tag to replace the placeholder.
   The smoke test proves it.
5. For a custom domain, run `make bind-domain` once cloudflare is applied.

### 9. observability

Set `postgres_fqdn` in `terraform/environments/dev.tfvars` to step 5's
Postgres FQDN (the server name has a random suffix). Then follow its README's
"First-time setup": local `make apply` (the workspace grant is outside its
group), `make db-role`, deploy, `make bind-domain`.

### 10. terraform-root-aks

Only when you want the cluster: it costs by the hour. It needs the landing
zone (step 3), its backend literal from step 1, and its `dev` environment
from step 6. Then run cd-terraform.

## Values tied to the old tenant

| Value | Where | Changes when |
| --- | --- | --- |
| Operator object ID (`b168eef0-…`) | azure-landingzone `bootstrap/terraform.tfvars` (×2) | New tenant |
| `TF_VAR_OPERATOR` (object ID, UPN, email) | github-repos `apply` environment, set by hand | New tenant |
| `sttfstatedev02d6`, `stlzstatedev02d6` | azure-landingzone `*/backend.tf` (×4), terraform-root-aks `backends/dev.hcl` | New subscription (names derived from its ID) |
| `sttfsharedjw` | See step 2 | Only if the old account still exists |
| `container_apps_default_domain`, `custom_domain_verification_id` | cloudflare `environments/dev.tfvars` | New Container Apps environment |
| `postgres_fqdn` | observability `environments/dev.tfvars` | New Postgres server |

These don't change:

- The GitHub OIDC subjects (`repo:jay-withers@288264678/<repo>@<id>:…`).
  They name GitHub's owner and repo IDs.
- The built-in role and policy definition IDs in governance and github-repos'
  `locals.tf`. They're the same in every tenant.
- Alert email addresses, the Cloudflare zone and token, and GitHub PATs.

Keep this table current: a new literal that names a tenant, subscription,
object ID or globally unique Azure name belongs here, or better, behind a
variable or a data source.
