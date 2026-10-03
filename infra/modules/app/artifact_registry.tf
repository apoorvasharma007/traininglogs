# Where the app's container images live. Only the 2 newest are kept: the running one and the one
# before it, for a rollback. Older images are deleted, which keeps storage inside the 0.5 GB free
# tier however many times the app is deployed.
resource "google_artifact_registry_repository" "images" {
  project       = var.project_id
  location      = var.region
  repository_id = "images"
  description   = "traininglogs app images (${var.environment})"
  format        = "DOCKER"

  cleanup_policy_dry_run = false

  cleanup_policies {
    id     = "keep-newest-2"
    action = "KEEP"
    most_recent_versions {
      keep_count = 2
    }
  }

  # KEEP takes precedence over DELETE, so this removes everything except the 2 above.
  cleanup_policies {
    id     = "delete-the-rest"
    action = "DELETE"
    condition {
      tag_state = "ANY"
    }
  }
}
