output "artifact_registry_repository" {
  description = "Artifact Registry repository path for the Cloud Build image tag."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.app.repository_id}"
}

output "cloud_sql_connection_name" {
  description = "Connection name to attach to Cloud Run with --add-cloudsql-instances."
  value       = google_sql_database_instance.app.connection_name
}

output "cloud_sql_database_name" {
  description = "PostgreSQL database created for the application."
  value       = google_sql_database.app.name
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