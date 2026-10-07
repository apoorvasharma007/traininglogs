terraform {
  required_version = ">= 1.16.4, < 2.0.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 8.5"
    }
  }

  backend "gcs" {
    bucket = "staging-project-ff63b6ae-c18e-4350-961-terraform-state"
    prefix = "app"
  }
}
