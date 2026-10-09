# Tierier Google Cloud infrastructure

This Terraform root provisions the shared infrastructure used by the existing Cloud Build deployment:

- Required Google Cloud APIs
- Artifact Registry Docker repository
- Cloud SQL for PostgreSQL, an application database, automated backups, and point-in-time recovery
- Secret Manager secret containers (secret values are not managed by Terraform)
- A Cloud Run runtime service account and a dedicated Cloud Build deployer service account with scoped IAM

Cloud Build remains the owner of Cloud Run service revisions and image deployment. This avoids Terraform and `gcloud run deploy` competing over the deployed image.

## Prerequisites

- A Google Cloud project with billing enabled
- Terraform 1.6 or newer and the Google Cloud CLI
- An identity with permission to enable APIs, create the resources below, and grant their IAM roles
- Application Default Credentials for local Terraform use, for example `gcloud auth application-default login`
- A globally unique Google Cloud Storage bucket for remote Terraform state

Create the state bucket before initializing Terraform; Terraform's GCS backend cannot create its own bucket. Enable object versioning and restrict bucket access to the Terraform operators/identity:

```sh
gcloud services enable storage.googleapis.com --project=PROJECT_ID
gcloud storage buckets create gs://UNIQUE_STATE_BUCKET --project=PROJECT_ID --location=us-central1 --uniform-bucket-level-access
gcloud storage buckets update gs://UNIQUE_STATE_BUCKET --versioning
```

## Initialize and apply

Run these commands from this directory. Copy `terraform.tfvars.example` to `terraform.tfvars`, set the project ID, and adjust the database tier/availability to match your budget and reliability needs. `terraform.tfvars` is intentionally not committed.

```sh
terraform init -backend-config="bucket=UNIQUE_STATE_BUCKET" -backend-config="prefix=tierier/prod"
terraform fmt -check
terraform validate
terraform plan -var-file=terraform.tfvars -out=tfplan
terraform apply tfplan
```

Review and protect saved plan files because plans and state can contain sensitive values. Do not commit them. For production, run Terraform through a protected CI identity using Workload Identity Federation or service-account impersonation rather than a downloaded service-account key.

Cloud SQL deletion protection is enabled by default. To intentionally remove the instance, first set `sql_deletion_protection = false`, apply that change, verify backups/retention, and only then destroy.

## Connect Cloud Build and Cloud Run

After apply, use the Terraform outputs when configuring the Cloud Build trigger and deployment substitutions:

- Set the trigger's service account to `cloud_build_service_account_email`.
- Set Cloud Run's runtime service account to `runtime_service_account_email`.
- Add `--add-cloudsql-instances=CLOUD_SQL_CONNECTION_NAME` to `gcloud run deploy`.
- Set `DATABASE_URL` and `DJANGO_SECRET_KEY` from the secret IDs in the outputs.
- Set the image repository to `artifact_registry_repository`.

The build-trigger creator needs permission to use the configured build service account (`roles/iam.serviceAccountUser`). The deployer account has Artifact Registry write access, Cloud Run administration, logging, and permission to act as the runtime account; review these grants against your organization policy before production use.

## Database credentials and secrets

Terraform creates the database and secret containers, but intentionally does not create a PostgreSQL login or secret versions. This keeps database passwords out of Terraform configuration and state. Create a dedicated least-privilege PostgreSQL user through an approved secure process, then add versions to the two Secret Manager secrets. Do this before deploying the service.

For Cloud Run's Cloud SQL socket connection, configure `DATABASE_URL` in the form:

```text
postgresql://DB_USER:URL_ENCODED_PASSWORD@/tierier?host=/cloudsql/PROJECT_ID:REGION:tierier-postgres
```

URL-encode special characters in the username/password. Do not use a public authorized network for the database; Cloud Run connects through the Cloud SQL integration and the runtime service account's Cloud SQL Client permission.

## Migrations

Run Django migrations as a serialized release step after the image is built and before deploying it, preferably as a Cloud Run Job using the same image, runtime service account, secret references, and Cloud SQL attachment. Execute `python manage.py migrate --noinput` once per release. Keep schema changes backward-compatible with the currently serving revision; perform destructive schema cleanup in a later release.

The current `cloudbuild.yaml` does not yet attach Cloud SQL, select these service accounts, or run migrations. Wire those values into the Cloud Build trigger/deploy workflow separately; do not add the Terraform apply to every application deployment.