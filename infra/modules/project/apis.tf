# Every Google service the project uses, switched on here so the terraform and app-deploy
# accounts never need permission to turn services on or off.
locals {
  apis = [
    "artifactregistry.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "serviceusage.googleapis.com",
    "storage.googleapis.com",
    "sts.googleapis.com",
  ]
}

resource "google_project_service" "enabled" {
  for_each = toset(local.apis)

  project = var.project_id
  service = each.value
  # Removing an API from this list must not switch it off under running resources.
  disable_on_destroy = false
}
