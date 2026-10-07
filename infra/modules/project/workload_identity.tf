# How GitHub Actions signs in to this project: short-lived tokens through Workload Identity
# Federation, so no service account key file exists anywhere. Tokens from any repository other
# than var.github_repository are rejected by the provider before any role is considered.

resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = "github"
  display_name              = "GitHub"

  depends_on = [google_project_service.enabled]
}

resource "google_iam_workload_identity_pool_provider" "github_actions" {
  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-actions"
  display_name                       = "GitHub Actions"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    # "owner/name@refs/heads/main" -- lets a grant be limited to one branch of one repository.
    "attribute.repository_ref" = "assertion.repository + '@' + assertion.ref"
  }
  attribute_condition = "assertion.repository == '${var.github_repository}'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# The "who" for the sign-in grants in service_accounts.tf: which GitHub workflow runs may act as
# each service account. Built here because they're made from this pool's name.
locals {
  pool = google_iam_workload_identity_pool.github.name
  # Any workflow run in the repository, on any branch or pull request.
  # Used by: google_service_account_iam_member.terraform_workload_identity
  github_repository_principal = "principalSet://iam.googleapis.com/${local.pool}/attribute.repository/${var.github_repository}"
  # Only workflow runs on the deploy branch: main for prod, dev for staging.
  # Used by: google_service_account_iam_member.app_deploy_workload_identity
  github_deploy_principal = "principalSet://iam.googleapis.com/${local.pool}/attribute.repository_ref/${var.github_repository}@refs/heads/${var.deploy_branch}"
}
