variable "project_id" {
  description = "The Google Cloud project this environment runs in."
  type        = string
}

variable "region" {
  description = "Region for the Cloud Run service and the image registry."
  type        = string
}

variable "environment" {
  description = "Which environment this project is, e.g. prod."
  type        = string
}

variable "app_deploy_service_account" {
  description = "Email of the app-deploy account (project layer output); it may launch the app as app-runtime."
  type        = string
}

variable "anthropic_workspace_id" {
  description = "Anthropic workspace the API key belongs to (sent as anthropic-workspace-id). Not a secret."
  type        = string
}

variable "supabase_url" {
  description = "The Supabase project whose sign-in passes the server accepts, https://<ref>.supabase.co. Not a secret."
  type        = string
}

variable "supabase_publishable_key" {
  description = "That project's publishable key, which the app sends with sign-in requests. Public by design."
  type        = string
}

variable "memory" {
  description = "Memory per Cloud Run instance."
  type        = string
  default     = "512Mi"
}

variable "max_instances" {
  description = "Hard cap on Cloud Run instances, so traffic can never scale up a bill."
  type        = number
  default     = 2
}
