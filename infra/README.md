# infra/

Everything traininglogs runs on in Google Cloud, in Terraform.

```
modules/
  project/          a project layer: switched-on APIs, GitHub sign-in, terraform + app-deploy accounts
  app/              an app layer: Cloud Run service, image registry, secrets, app-runtime account
environments/
  prod/
    project/        prod's project layer — applied by hand
    app/            prod's app layer — applied by the pipeline
```

Each environment is its own Google Cloud project. `modules/` hold the resources, written once;
each folder under `environments/` is where Terraform runs: which module, with which values, and
where its state lives.

## Who applies what

| Layer | Applied by | Why |
|---|---|---|
| `environments/<env>/project` | You, from your laptop | It creates the account the pipeline runs as, so the pipeline can't create it |
| `environments/<env>/app` | GitHub Actions: plan on a pull request, apply on merge to `main` | Everyday infrastructure changes |

Both always go through `terraform plan` first.

## The one manual step, once per environment

Terraform keeps its state in a bucket, and can't store state in a bucket it hasn't created yet.
Create it once by hand (prod shown):

```bash
gcloud storage buckets create gs://prod-traininglogs-510513-terraform-state \
  --project=traininglogs-510513 --location=us-east1 \
  --uniform-bucket-level-access --public-access-prevention
gcloud storage buckets update gs://prod-traininglogs-510513-terraform-state \
  --versioning --update-labels=environment=prod,app=traininglogs
```

Versioning keeps every earlier state, so a bad apply can be undone. The name starts with the
environment because bucket names are global across all of Google Cloud.

## Running the project layer

```bash
gcloud auth application-default login          # once per machine; no key files
cd infra/environments/prod/project
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

## Naming

- Environment prefix only on globally named things (the state bucket). Everything else lives in a
  project that already belongs to one environment.
- Every resource that supports labels carries `environment` and `app`.
- Terraform names use underscores (`app_deploy`); Google Cloud IDs use hyphens (`app-deploy`).
