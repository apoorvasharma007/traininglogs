# infra/

Everything traininglogs runs on in Google Cloud, as Terraform.

```
modules/
  project/          a project layer: APIs, GitHub sign-in, terraform and app-deploy accounts
  app/              an app layer: Cloud Run service, Artifact Registry, secrets, app-runtime account
environments/
  prod/
    project/        prod's project layer, applied by hand
    app/            prod's app layer, applied by the pipeline on main
  staging/
    project/        staging's project layer, applied by hand
    app/            staging's app layer, applied by the pipeline on dev
```

Staging is a practice copy in its own project (`project-ff63b6ae-c18e-4350-961`), with its own
Supabase database. A push to `dev` deploys it with no approval; a merge to `main` deploys prod
after approval. Each environment's variables live in its GitHub environment (`staging`), or for
prod on the repository itself.

Each environment is its own Google Cloud project. The modules hold the resources, written once.
Each folder under `environments/` is where Terraform runs: it names a module, gives it that
environment's values, and says where the state lives.

## Who applies what

| Layer | Applied by | Why |
|---|---|---|
| `environments/<env>/project` | You, from your laptop | It creates the account the pipeline runs as, so the pipeline can't create it |
| `environments/<env>/app` | The deploy at the end of CI: staging on a push to `dev`, prod on `main` after you approve | Everyday changes |

Both go through `terraform plan` before every `apply`. Local runs sign in with your own Google
account, once per machine:

```bash
gcloud auth application-default login
```

## Setting up a new environment

This is the order prod was built in. Each step needs the one before it.

1. Create the state bucket. Terraform can't keep its state in a bucket that doesn't exist yet,
   so this is the only thing made by hand:

   ```bash
   gcloud storage buckets create gs://prod-traininglogs-510513-terraform-state \
     --project=traininglogs-510513 --location=us-east1 \
     --uniform-bucket-level-access --public-access-prevention
   gcloud storage buckets update gs://prod-traininglogs-510513-terraform-state \
     --versioning --update-labels=environment=prod,app=traininglogs
   ```

2. Apply the project layer:

   ```bash
   cd infra/environments/prod/project
   terraform init
   terraform plan -out=tfplan
   terraform apply tfplan
   ```

3. Create the secrets, empty. Cloud Run won't start a revision that reads a secret with no
   value, so you create and fill the secrets before the service:

   ```bash
   cd infra/environments/prod/app
   terraform init
   terraform plan -out=tfplan \
     -target=module.app.google_secret_manager_secret.database_url \
     -target=module.app.google_secret_manager_secret.api_key \
     -target=module.app.google_secret_manager_secret.anthropic_api_key \
     -target=module.app.google_secret_manager_secret.supabase_publishable_key
   terraform apply tfplan
   ```

4. Add each secret's value. See [Secrets](#secrets).

5. Apply the rest of the app layer:

   ```bash
   terraform plan -out=tfplan
   terraform apply tfplan
   ```

   The service starts on Google's sample image. The next deploy replaces it with the app.

## Everyday changes

Edit `infra/` on a branch and open a pull request. CI checks the format, validates both layers and
posts the plan for `prod/app` as a comment on the pull request. Read it. Once it's merged to
`main`, the deploy waits for your approval, then applies that layer and deploys the app.

The project layer never runs in the pipeline. Change it from your laptop with plan, then apply.

## Secrets

The app reads `database-url`, `api-key`, `anthropic-api-key` and `supabase-publishable-key` from
Secret Manager. Terraform creates them but never holds their values, so no secret ends up in
Terraform's state. `supabase-publishable-key` was made with gcloud first and adopted by an
`import` block in each environment's `main.tf`:

```bash
gcloud secrets create supabase-publishable-key --replication-policy=automatic
printf '%s' "$VALUE" | gcloud secrets versions add supabase-publishable-key --data-file=-
```

To add or change a value, add a new version. From a terminal, without the value appearing on
screen:

```bash
printf '%s' "$VALUE" | gcloud secrets versions add api-key --data-file=-
```

Or use the Secret Manager page in the console. Every instance that starts after the new version
exists uses it. To switch over at once instead of waiting for instances to recycle, re-run the
latest CI run's deploy: it starts a new revision.

Once the new value works, disable the old version, or it keeps working too.

## Naming

- Only globally named things carry the environment prefix, which today means the state bucket.
  Everything else lives in a project that already belongs to one environment.
- Every resource that supports labels has `environment` and `app`.
- Terraform names use underscores (`app_deploy`). Google Cloud IDs use hyphens (`app-deploy`).
