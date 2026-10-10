# The app: API and web UI in one container, scaled to zero when idle.
#
# Terraform owns how the service is configured. The deploy workflow owns which image runs: it
# rolls the service onto each new image with gcloud, so Terraform ignores the image (and the
# client fields gcloud stamps) instead of trying to put it back. The first image is Google's
# sample container, until the first real deploy replaces it.
resource "google_cloud_run_v2_service" "traininglogs" {
  project  = var.project_id
  location = var.region
  name     = "traininglogs"
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.app_runtime.email

    scaling {
      min_instance_count = 0
      max_instance_count = var.max_instances
    }

    containers {
      image = "us-docker.pkg.dev/cloudrun/container/hello"

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = var.memory
        }
        # CPU only while handling a request (the free-tier-friendly setting), with a boost while
        # an instance starts to shorten the wait after idle.
        cpu_idle          = true
        startup_cpu_boost = true
      }

      env {
        name  = "ANTHROPIC_WORKSPACE_ID"
        value = var.anthropic_workspace_id
      }

      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.database_url.secret_id
            version = "latest"
          }
        }
      }

      env {
        name  = "SUPABASE_URL"
        value = var.supabase_url
      }

      env {
        name = "SUPABASE_PUBLISHABLE_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.supabase_publishable_key.secret_id
            version = "latest"
          }
        }
      }

      # Only the code from before accounts reads this. It stays for one release, so that release's
      # Terraform step (which restarts the old code before the new image goes out) still starts;
      # the release after removes it and the api-key secret (db-redesign-plan.md).
      env {
        name = "API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.api_key.secret_id
            version = "latest"
          }
        }
      }

      env {
        name = "ANTHROPIC_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.anthropic_api_key.secret_id
            version = "latest"
          }
        }
      }
    }
  }

  lifecycle {
    ignore_changes = [
      template[0].containers[0].image,
      client,
      client_version,
    ]
  }

  # Secret access must exist before a revision that reads the secrets starts.
  depends_on = [google_secret_manager_secret_iam_member.app_runtime]
}

# Anyone may open the URL -- the page itself is public. Every data endpoint still requires a
# Supabase sign-in pass from SUPABASE_URL's project (api/auth.py).
resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = var.project_id
  location = google_cloud_run_v2_service.traininglogs.location
  name     = google_cloud_run_v2_service.traininglogs.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
