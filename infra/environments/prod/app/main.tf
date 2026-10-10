# prod's app layer: the Cloud Run service, its image repository, its secrets and its runtime
# account. Applied by the pipeline (plan on a pull request, apply on merge to main).

locals {
  project_id  = "traininglogs-510513"
  region      = "us-east1"
  environment = "prod"
}

provider "google" {
  project = local.project_id
  region  = local.region

  default_labels = {
    environment = local.environment
    app         = "traininglogs"
  }
}

# The project layer's outputs (the app-deploy account), read from its state rather than copied.
data "terraform_remote_state" "project" {
  backend = "gcs"
  config = {
    bucket = "prod-traininglogs-510513-terraform-state"
    prefix = "project"
  }
}

module "app" {
  source = "../../../modules/app"

  project_id                 = local.project_id
  region                     = local.region
  environment                = local.environment
  app_deploy_service_account = data.terraform_remote_state.project.outputs.app_deploy_service_account
  anthropic_workspace_id     = "wrkspc_011QiVX8TkGjpXRWKN8trAtn"
  supabase_url               = "https://rjmkdhmvmbbpkmjrqrdc.supabase.co"
  supabase_publishable_key   = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJqbWtkaG12bWJicGttanJxcmRjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzgxNDYwMDksImV4cCI6MjA5MzcyMjAwOX0.0zGQzkp1q4EnlWHh4gNIN1xLe2MXsGAvfNLpNv2Rka0"
}
