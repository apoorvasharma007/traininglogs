# The app's three secrets. Terraform creates them empty; their values are added once with
# `gcloud secrets versions add` (infra/README.md), so no secret value is ever in Terraform state.
# Deleting one would lose its value, hence prevent_destroy.

resource "google_secret_manager_secret" "database_url" {
  project   = var.project_id
  secret_id = "database-url"
  replication {
    auto {}
  }
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_secret_manager_secret" "api_key" {
  project   = var.project_id
  secret_id = "api-key"
  replication {
    auto {}
  }
  lifecycle {
    prevent_destroy = true
  }
}

resource "google_secret_manager_secret" "anthropic_api_key" {
  project   = var.project_id
  secret_id = "anthropic-api-key"
  replication {
    auto {}
  }
  lifecycle {
    prevent_destroy = true
  }
}

# app-runtime may read these three secrets, and nothing else in Secret Manager.
resource "google_secret_manager_secret_iam_member" "app_runtime" {
  for_each = {
    database_url      = google_secret_manager_secret.database_url.id
    api_key           = google_secret_manager_secret.api_key.id
    anthropic_api_key = google_secret_manager_secret.anthropic_api_key.id
  }

  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.app_runtime.email}"
}
