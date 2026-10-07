# staging's project layer: switched-on APIs, GitHub sign-in, and the terraform / app-deploy
# accounts. Applied by hand (your own Google login), not by the pipeline -- the pipeline's own
# account is created here.

locals {
  project_id  = "project-ff63b6ae-c18e-4350-961"
  region      = "us-east1"
  environment = "staging"
}

provider "google" {
  project = local.project_id
  region  = local.region

  default_labels = {
    environment = local.environment
    app         = "traininglogs"
  }
}

module "project" {
  source = "../../../modules/project"

  project_id             = local.project_id
  region                 = local.region
  environment            = local.environment
  github_repository      = "apoorvasharma007/traininglogs"
  terraform_state_bucket = "staging-project-ff63b6ae-c18e-4350-961-terraform-state"
  # CD deploys staging from dev, prod from main.
  deploy_branch = "dev"
}
