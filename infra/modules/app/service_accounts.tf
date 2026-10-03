# The identity the running app uses. It can read its own three secrets (secrets.tf) and nothing
# else; it has no project-level roles at all.
resource "google_service_account" "app_runtime" {
  project      = var.project_id
  account_id   = "app-runtime"
  display_name = "App runtime"
  description  = "The identity the traininglogs Cloud Run service runs as."
}

# A deploy launches a new revision that runs as app-runtime, which requires permission to act as
# it. Granted on this one account, not project-wide.
resource "google_service_account_iam_member" "app_deploy_runtime" {
  service_account_id = google_service_account.app_runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${var.app_deploy_service_account}"
}
