output "service_url" {
  description = "Where the app is reached."
  value       = google_cloud_run_v2_service.traininglogs.uri
}

output "image_repository" {
  description = "Where the deploy workflow pushes images: <region>-docker.pkg.dev/<project>/images."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}

output "app_runtime_service_account" {
  value = google_service_account.app_runtime.email
}
