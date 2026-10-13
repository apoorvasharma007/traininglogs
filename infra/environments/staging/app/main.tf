# staging's app layer: the Cloud Run service, its image repository, its secrets and its runtime
# account. Applied by the pipeline on a push to dev.

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

# The project layer's outputs (the app-deploy account), read from its state rather than copied.
data "terraform_remote_state" "project" {
  backend = "gcs"
  config = {
    bucket = "staging-project-ff63b6ae-c18e-4350-961-terraform-state"
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
  supabase_url               = "https://sjpxpjilamtumdmdvmtg.supabase.co"
}

# The secret is made and filled with gcloud before this applies (infra/README.md, Secrets), so the
# first revision that reads it can start. This adopts it into Terraform.
import {
  to = module.app.google_secret_manager_secret.supabase_publishable_key
  id = "projects/${local.project_id}/secrets/supabase-publishable-key"
}

import {
  to = module.app.google_secret_manager_secret.discord_webhook_url
  id = "projects/${local.project_id}/secrets/discord-webhook-url"
}
