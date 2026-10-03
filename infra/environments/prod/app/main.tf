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
}
