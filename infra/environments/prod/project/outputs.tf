output "workload_identity_provider" {
  value = module.project.workload_identity_provider
}

output "terraform_service_account" {
  value = module.project.terraform_service_account
}

output "app_deploy_service_account" {
  value = module.project.app_deploy_service_account
}
