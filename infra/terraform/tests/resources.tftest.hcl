mock_provider "google" {
  mock_resource "google_service_account" {
    defaults = {
      name  = "projects/tierier-test/serviceAccounts/tierier-runtime@tierier-test.iam.gserviceaccount.com"
      email = "tierier-runtime@tierier-test.iam.gserviceaccount.com"
    }
  }
}

variables {
  project_id = "tierier-test"
}

run "postgres_vm_and_bootstrap" {
  command = plan

  assert {
    condition     = google_compute_instance.postgres.machine_type == "e2-micro"
    error_message = "PostgreSQL must run on an e2-micro VM."
  }

  assert {
    condition     = google_compute_instance.postgres.boot_disk[0].initialize_params[0].image == "ubuntu-os-cloud/ubuntu-2404-lts-amd64"
    error_message = "The PostgreSQL VM must use the supported Ubuntu 24.04 image."
  }

  assert {
    condition     = google_compute_instance.postgres.boot_disk[0].initialize_params[0].type == "pd-standard" && google_compute_instance.postgres.boot_disk[0].initialize_params[0].size == 20
    error_message = "The PostgreSQL VM must use a 20 GB standard persistent disk."
  }

  assert {
    condition     = strcontains(google_compute_instance.postgres.metadata_startup_script, "apt-get install -y postgresql") && strcontains(google_compute_instance.postgres.metadata_startup_script, "CREATE DATABASE")
    error_message = "The VM startup script must install PostgreSQL and create the application database."
  }

  assert {
    condition     = strcontains(google_compute_instance.postgres.metadata_startup_script, "scram-sha-256") && strcontains(google_compute_instance.postgres.metadata_startup_script, "10.10.0.0/24")
    error_message = "PostgreSQL host authentication must use SCRAM and be scoped to the VPC subnet."
  }
}

run "private_network_and_firewall" {
  command = plan

  assert {
    condition     = google_compute_network.app.auto_create_subnetworks == false
    error_message = "The application VPC must use explicitly managed subnets."
  }

  assert {
    condition     = google_compute_subnetwork.app.ip_cidr_range == "10.10.0.0/24"
    error_message = "The application subnet CIDR must match the configured default."
  }

  assert {
    condition     = length(google_compute_firewall.postgres.source_ranges) == 1 && contains(google_compute_firewall.postgres.source_ranges, "10.10.0.0/24") && one(google_compute_firewall.postgres.allow).protocol == "tcp" && length(one(google_compute_firewall.postgres.allow).ports) == 1 && contains(one(google_compute_firewall.postgres.allow).ports, "5432")
    error_message = "PostgreSQL ingress must allow TCP 5432 only from the application subnet."
  }

  assert {
    condition     = length(google_compute_firewall.iap_ssh.source_ranges) == 1 && contains(google_compute_firewall.iap_ssh.source_ranges, "35.235.240.0/20") && length(one(google_compute_firewall.iap_ssh.allow).ports) == 1 && contains(one(google_compute_firewall.iap_ssh.allow).ports, "22")
    error_message = "SSH ingress must be limited to the IAP TCP forwarding range."
  }
}

run "service_accounts_and_secret_access" {
  command = plan

  assert {
    condition     = google_compute_subnetwork_iam_member.cloud_build_network_user.role == "roles/compute.networkUser"
    error_message = "The Cloud Build deployer must be allowed to use the Cloud Run subnet."
  }

  assert {
    condition     = google_secret_manager_secret_iam_member.runtime_django_secret.role == "roles/secretmanager.secretAccessor" && google_secret_manager_secret_iam_member.runtime_database_url.role == "roles/secretmanager.secretAccessor"
    error_message = "The runtime service account must be able to access both application secrets."
  }
}

run "reject_invalid_postgres_user" {
  command = plan

  variables {
    postgres_user = "Invalid-User"
  }

  expect_failures = [var.postgres_user]
}