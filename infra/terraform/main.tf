locals {
  required_apis = toset([
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "compute.googleapis.com",
    "iap.googleapis.com",
    "iam.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
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

resource "google_compute_network" "app" {
  project                 = var.project_id
  name                    = var.vpc_network_name
  auto_create_subnetworks = false

  depends_on = [google_project_service.required]
}

resource "google_compute_subnetwork" "app" {
  project       = var.project_id
  name          = var.vpc_subnet_name
  region        = var.region
  network       = google_compute_network.app.id
  ip_cidr_range = var.vpc_subnet_cidr
}

resource "google_compute_firewall" "postgres" {
  project       = var.project_id
  name          = "${var.vpc_network_name}-postgres"
  network       = google_compute_network.app.name
  direction     = "INGRESS"
  source_ranges = [var.vpc_subnet_cidr]
  target_tags   = ["tierier-postgres"]

  allow {
    protocol = "tcp"
    ports    = ["5432"]
  }
}

resource "google_compute_firewall" "iap_ssh" {
  project       = var.project_id
  name          = "${var.vpc_network_name}-iap-ssh"
  network       = google_compute_network.app.name
  direction     = "INGRESS"
  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["tierier-postgres"]

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }
}

resource "google_compute_instance" "postgres" {
  project      = var.project_id
  name         = var.postgres_instance_name
  zone         = "${var.region}-a"
  machine_type = "e2-micro"
  tags         = ["tierier-postgres"]

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2404-lts-amd64"
      size  = 20
      type  = "pd-standard"
    }
  }

  network_interface {
    network    = google_compute_network.app.id
    subnetwork = google_compute_subnetwork.app.id

    access_config {}
  }

  metadata_startup_script = <<-EOT
    #!/bin/bash
    set -euo pipefail
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y postgresql

    pg_version="$(ls /etc/postgresql | sort -V | tail -n 1)"
    pg_config="/etc/postgresql/$pg_version/main/postgresql.conf"
    pg_hba="/etc/postgresql/$pg_version/main/pg_hba.conf"

    sed -i "s/^#listen_addresses = 'localhost'/listen_addresses = '*'/" "$pg_config"
    sed -i -E 's/^#?max_connections = .*/max_connections = 30/' "$pg_config"
    printf '\nhost %s %s %s scram-sha-256\n' '${var.postgres_database_name}' '${var.postgres_user}' '${var.vpc_subnet_cidr}' >> "$pg_hba"

    sudo -u postgres psql --set=db_name='${var.postgres_database_name}' <<'SQL'
    SELECT format('CREATE DATABASE %I', :'db_name')
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = :'db_name')
    \gexec
    SQL

    systemctl restart postgresql
  EOT

  depends_on = [google_project_service.required]
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

resource "google_compute_subnetwork_iam_member" "cloud_build_network_user" {
  project    = var.project_id
  region     = google_compute_subnetwork.app.region
  subnetwork = google_compute_subnetwork.app.name
  role       = "roles/compute.networkUser"
  member     = "serviceAccount:${google_service_account.cloud_build.email}"
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