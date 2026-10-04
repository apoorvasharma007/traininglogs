variable "project_id" {
  description = "The Google Cloud project this environment runs in."
  type        = string
}

variable "region" {
  description = "Default region. Cloud Run's always-free tier covers North American regions."
  type        = string
}

variable "environment" {
  description = "Which environment this project is, e.g. prod."
  type        = string
}

variable "github_repository" {
  description = "The only GitHub repository allowed to sign in, as owner/name."
  type        = string
}

variable "terraform_state_bucket" {
  description = "The state bucket created by hand (infra/README.md); the terraform account gets access to it."
  type        = string
}

variable "deploy_branch" {
  description = "The branch whose workflow runs may deploy the app: main for prod, dev for staging."
  type        = string
  default     = "main"
}
