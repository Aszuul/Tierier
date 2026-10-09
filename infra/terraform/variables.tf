variable "project_id" {
  description = "Google Cloud project ID with billing enabled."
  type        = string
}

variable "region" {
  description = "Region for Cloud Run, Artifact Registry, and Cloud SQL."
  type        = string
  default     = "us-central1"
}

variable "artifact_repository_id" {
  description = "Artifact Registry Docker repository ID."
  type        = string
  default     = "tierier"
}

variable "sql_instance_name" {
  description = "Cloud SQL instance name."
  type        = string
  default     = "tierier-postgres"
}

variable "sql_database_name" {
  description = "Application database name created in Cloud SQL."
  type        = string
  default     = "tierier"
}

variable "sql_database_version" {
  description = "Cloud SQL PostgreSQL major version."
  type        = string
  default     = "POSTGRES_16"
}

variable "sql_tier" {
  description = "Cloud SQL machine tier. Choose a size appropriate for the workload and budget."
  type        = string
  default     = "db-custom-1-3840"
}

variable "sql_availability_type" {
  description = "Cloud SQL availability: ZONAL or REGIONAL. REGIONAL costs more but provides HA."
  type        = string
  default     = "ZONAL"

  validation {
    condition     = contains(["ZONAL", "REGIONAL"], var.sql_availability_type)
    error_message = "sql_availability_type must be ZONAL or REGIONAL."
  }
}

variable "sql_deletion_protection" {
  description = "Prevent accidental Terraform deletion of the Cloud SQL instance."
  type        = bool
  default     = true
}

variable "runtime_service_account_id" {
  description = "Account ID for the Cloud Run runtime service account."
  type        = string
  default     = "tierier-runtime"
}

variable "cloud_build_service_account_id" {
  description = "Account ID for the Cloud Build deployment service account. Configure the build trigger to use it."
  type        = string
  default     = "tierier-deployer"
}

variable "django_secret_id" {
  description = "Secret Manager secret ID for DJANGO_SECRET_KEY. Terraform creates the secret, not its value."
  type        = string
  default     = "django-secret"
}

variable "database_url_secret_id" {
  description = "Secret Manager secret ID for DATABASE_URL. Terraform creates the secret, not its value."
  type        = string
  default     = "database-url"
}