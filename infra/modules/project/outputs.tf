output "workload_identity_provider" {
  description = "Full provider name, for google-github-actions/auth's workload_identity_provider input."
  value       = google_iam_workload_identity_pool_provider.github_actions.name
}

output "terraform_service_account" {
  value = google_service_account.terraform.email
}

output "app_deploy_service_account" {
  value = google_service_account.app_deploy.email
}
