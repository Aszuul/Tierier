# Tierier Google Cloud infrastructure

This Terraform root provisions the shared infrastructure used by the existing Cloud Build deployment:

- Required Google Cloud APIs
- Artifact Registry Docker repository
- A private VPC and subnet shared by Cloud Run direct VPC egress and a PostgreSQL Compute Engine VM (`e2-micro`)
- Secret Manager secret versions populated from required credential inputs
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

Run these commands from this directory. Copy `terraform.tfvars.example` to `terraform.tfvars`, set the project ID, and replace both credential placeholders with independently generated values. For example, `openssl rand -hex 32` produces a 64-character hexadecimal value suitable for each variable. Use the same `postgres_database_password` when setting the PostgreSQL login password below. `terraform.tfvars` is intentionally not committed. The PostgreSQL VM uses Ubuntu 24.04's PostgreSQL package and a 20 GB standard persistent disk.

```sh
terraform init -backend-config="bucket=UNIQUE_STATE_BUCKET" -backend-config="prefix=tierier/prod"
terraform fmt -check
terraform validate
terraform plan -var-file=terraform.tfvars -out=tfplan
terraform apply tfplan
```

The credential inputs are marked sensitive in Terraform, but Terraform state and saved plans can still contain their values. Restrict access to the state bucket and local plan/state files; do not commit `terraform.tfvars` or saved plans. For production, run Terraform through a protected CI identity using Workload Identity Federation or service-account impersonation rather than a downloaded service-account key.

This replaces the former Cloud SQL resources. If they already exist in the Terraform state or contain data, back up and migrate that data before applying; Terraform will plan to delete Cloud SQL.

## Tests

Run the plan-only unit tests from the repository root. They use a mocked Google provider and do not create cloud resources:

```powershell
tofu -chdir=infra/terraform test -filter=tests/resources.tftest.hcl
```

After applying the infrastructure and completing PostgreSQL setup, run the live integration checks:

```powershell
.\infra\terraform\tests\postgres.integration.ps1 -ProjectId YOUR_PROJECT_ID
```

The integration check describes the VM and firewall, then uses IAP SSH to check PostgreSQL and the application database. It requires `gcloud` authentication and permission to inspect the resources and connect through IAP; `gcloud compute ssh` may register an SSH key in project or OS Login metadata.

## Connect Cloud Build and Cloud Run

After apply, use the Terraform outputs when configuring the Cloud Build trigger and deployment substitutions:

- Set the trigger's service account to `cloud_build_service_account_email`.
- Set Cloud Run's runtime service account to `runtime_service_account_email`.
- Keep the Cloud Build substitutions `_VPC_NETWORK` and `_VPC_SUBNET` aligned with the Terraform outputs `vpc_network_name` and `vpc_subnet_name`. Cloud Run uses direct VPC egress to reach the database's private IP.
- Set `DATABASE_URL` and `DJANGO_SECRET_KEY` from the secret IDs in the outputs.
- Set the image repository to `artifact_registry_repository`.

The build-trigger creator needs permission to use the configured build service account (`roles/iam.serviceAccountUser`). The deployer account has Artifact Registry write access, Cloud Run administration, logging, and permission to act as the runtime account; review these grants against your organization policy before production use.

## Database credentials and secrets

Terraform installs PostgreSQL and creates the application database and a `DATABASE_URL` secret version using `postgres_database_password`. Terraform does not create the PostgreSQL login. After the VM starts, create the login using the same password configured in `terraform.tfvars`, using IAP SSH:

```sh
gcloud compute ssh tierier-postgres-vm --zone=us-central1-a --tunnel-through-iap --command="sudo -u postgres psql"
```

In the PostgreSQL prompt, create the login (use the `postgres_user` output value):

```sql
CREATE ROLE tierier LOGIN;
\password tierier
GRANT CONNECT ON DATABASE tierier TO tierier;
\c tierier
GRANT USAGE, CREATE ON SCHEMA public TO tierier;
```

The `\password` command prompts without echoing the password. Replace the example database and role names if you changed their Terraform defaults.

Store a `DATABASE_URL` secret version using the VM's `postgres_private_ip` output:

```text
postgresql://DB_USER:URL_ENCODED_PASSWORD@PRIVATE_IP:5432/DATABASE_NAME
```

URL-encode special characters in the username/password. PostgreSQL ingress is restricted to the VPC subnet; do not open port 5432 to the public internet. The VM has an external IP for operating-system package updates, but the firewall does not allow public database or SSH ingress.

## Migrations

Run Django migrations as a serialized release step after the image is built and before deploying it, preferably as a Cloud Run Job using the same image and secret references. Execute `python manage.py migrate --noinput` once per release. Keep schema changes backward-compatible with the currently serving revision; perform destructive schema cleanup in a later release.

The current `cloudbuild.yaml` configures Cloud Run network egress but does not select the Terraform-created service accounts or run migrations. Wire those values into the Cloud Build trigger/deploy workflow separately; do not add the Terraform apply to every application deployment. This single-VM database has no managed backups or high availability; arrange backups before relying on it for important data.