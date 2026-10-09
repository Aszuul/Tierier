locals {
  required_apis = toset([
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "iam.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "sqladmin.googleapis.com",
  ])
}

resource "google_project_service" "required" {
  for_each           = local.required_apis
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "app" {
  project       = var.project_id
  location      = var.region
  repository_id = var.artifact_repository_id
  description   = "Container images for Tierier"
  format        = "DOCKER"

  depends_on = [google_project_service.required]
}

resource "google_sql_database_instance" "app" {
  project             = var.project_id
  name                = var.sql_instance_name
  region              = var.region
  database_version    = var.sql_database_version
  deletion_protection = var.sql_deletion_protection

  settings {
    tier              = var.sql_tier
    availability_type = var.sql_availability_type
    disk_type         = "PD_SSD"
    disk_size         = 20
    disk_autoresize   = true

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
    }

    ip_configuration {
      ipv4_enabled = true
    }
  }

  depends_on = [google_project_service.required]
}

resource "google_sql_database" "app" {
  project  = var.project_id
  name     = var.sql_database_name
  instance = google_sql_database_instance.app.name
}

resource "google_secret_manager_secret" "django_secret_key" {
  project   = var.project_id
  secret_id = var.django_secret_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret" "database_url" {
  project   = var.project_id
  secret_id = var.database_url_secret_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.required]
}

resource "google_service_account" "runtime" {
  project      = var.project_id
  account_id   = var.runtime_service_account_id
  display_name = "Tierier Cloud Run runtime"

  depends_on = [google_project_service.required]
}

resource "google_service_account" "cloud_build" {
  project      = var.project_id
  account_id   = var.cloud_build_service_account_id
  display_name = "Tierier Cloud Build deployer"

  depends_on = [google_project_service.required]
}

resource "google_project_iam_member" "runtime_cloud_sql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_secret_manager_secret_iam_member" "runtime_django_secret" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.django_secret_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_secret_manager_secret_iam_member" "runtime_database_url" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.database_url.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_artifact_registry_repository_iam_member" "cloud_build_writer" {
  project    = var.project_id
  location   = google_artifact_registry_repository.app.location
  repository = google_artifact_registry_repository.app.repository_id
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.cloud_build.email}"
}

resource "google_project_iam_member" "cloud_build_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.cloud_build.email}"
}

resource "google_project_iam_member" "cloud_build_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.cloud_build.email}"
}

resource "google_service_account_iam_member" "cloud_build_use_runtime" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.cloud_build.email}"
}