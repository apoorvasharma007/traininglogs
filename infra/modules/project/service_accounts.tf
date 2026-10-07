# The two identities GitHub Actions works as. Each has only what its job needs, and every grant
# the app layer makes is on a single resource, so neither needs project-level IAM admin.

# --- terraform: plans and applies the app layer ---------------------------------------------

resource "google_service_account" "terraform" {
  project      = var.project_id
  account_id   = "terraform"
  display_name = "Terraform"
  description  = "Plans and applies infra/environments/${var.environment}/app from GitHub Actions."
}

locals {
  terraform_roles = [
    "roles/run.admin",
    "roles/artifactregistry.admin",
    "roles/secretmanager.admin",
    "roles/iam.serviceAccountAdmin",
    "roles/iam.serviceAccountUser",
  ]
}

resource "google_project_iam_member" "terraform" {
  for_each = toset(local.terraform_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.terraform.email}"
}

resource "google_storage_bucket_iam_member" "terraform_state" {
  bucket = var.terraform_state_bucket
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.terraform.email}"
}

# Any branch: pull requests need it to show a plan. Applying only happens on the deploy branch, by workflow.
resource "google_service_account_iam_member" "terraform_workload_identity" {
  service_account_id = google_service_account.terraform.name
  role               = "roles/iam.workloadIdentityUser"
  member             = local.github_repository_principal
}

# --- app-deploy: pushes an image and rolls Cloud Run onto it ---------------------------------

resource "google_service_account" "app_deploy" {
  project      = var.project_id
  account_id   = "app-deploy"
  display_name = "App deploy"
  description  = "Pushes app images and deploys them to Cloud Run from GitHub Actions, ${var.deploy_branch} only."
}

locals {
  # Acting as the app's runtime account is granted on that one account, in the app layer.
  app_deploy_roles = [
    "roles/run.developer",
    "roles/artifactregistry.writer",
  ]
}

resource "google_project_iam_member" "app_deploy" {
  for_each = toset(local.app_deploy_roles)

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.app_deploy.email}"
}

# The deploy branch only: no other branch can deploy.
resource "google_service_account_iam_member" "app_deploy_workload_identity" {
  service_account_id = google_service_account.app_deploy.name
  role               = "roles/iam.workloadIdentityUser"
  member             = local.github_deploy_principal
}
