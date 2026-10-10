output "artifact_registry_repository" {
  description = "Artifact Registry repository path for the Cloud Build image tag."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.app.repository_id}"
}

output "postgres_private_ip" {
  description = "Private IP address for the PostgreSQL VM; use it as the DATABASE_URL host."
  value       = google_compute_instance.postgres.network_interface[0].network_ip
}

output "postgres_database_name" {
  description = "PostgreSQL database created on the VM."
  value       = var.postgres_database_name
}

output "postgres_user" {
  description = "PostgreSQL login to create on the VM."
  value       = var.postgres_user
}

output "vpc_network_name" {
  description = "VPC network name to configure on the Cloud Build trigger."
  value       = google_compute_network.app.name
}

output "vpc_subnet_name" {
  description = "VPC subnet name to configure on the Cloud Build trigger."
  value       = google_compute_subnetwork.app.name
}

output "runtime_service_account_email" {
  description = "Set this as the Cloud Run service's runtime service account."
  value       = google_service_account.runtime.email
}

output "cloud_build_service_account_email" {
  description = "Set this as the Cloud Build trigger's service account."
  value       = google_service_account.cloud_build.email
}

output "django_secret_id" {
  description = "Secret Manager secret ID for DJANGO_SECRET_KEY. Add a secret version before deployment."
  value       = google_secret_manager_secret.django_secret_key.secret_id
}

output "database_url_secret_id" {
  description = "Secret Manager secret ID for DATABASE_URL. Add a secret version before deployment."
  value       = google_secret_manager_secret.database_url.secret_id
}