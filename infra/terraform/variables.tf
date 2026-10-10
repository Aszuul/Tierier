variable "project_id" {
  description = "Google Cloud project ID with billing enabled."
  type        = string
}

variable "region" {
  description = "Region for Cloud Run, Artifact Registry, the VPC subnet, and PostgreSQL VM."
  type        = string
  default     = "us-central1"
}

variable "vpc_network_name" {
  description = "VPC network used by Cloud Run and the PostgreSQL VM."
  type        = string
  default     = "tierier-vpc"
}

variable "vpc_subnet_name" {
  description = "Subnet used by Cloud Run direct VPC egress and the PostgreSQL VM."
  type        = string
  default     = "tierier-subnet"
}

variable "vpc_subnet_cidr" {
  description = "IPv4 range for the Cloud Run and PostgreSQL subnet."
  type        = string
  default     = "10.10.0.0/24"
}

variable "artifact_repository_id" {
  description = "Artifact Registry Docker repository ID."
  type        = string
  default     = "tierier"
}

variable "postgres_instance_name" {
  description = "Compute Engine VM name for PostgreSQL."
  type        = string
  default     = "tierier-postgres-vm"
}

variable "postgres_database_name" {
  description = "Application database name created on the PostgreSQL VM."
  type        = string
  default     = "tierier"

  validation {
    condition     = can(regex("^[a-z][a-z0-9_]{0,62}$", var.postgres_database_name))
    error_message = "postgres_database_name must start with a lowercase letter and contain only lowercase letters, digits, and underscores."
  }
}

variable "postgres_user" {
  description = "PostgreSQL login allowed to connect from the VPC subnet. Create it with a password after the VM starts."
  type        = string
  default     = "tierier"

  validation {
    condition     = can(regex("^[a-z][a-z0-9_]{0,62}$", var.postgres_user))
    error_message = "postgres_user must start with a lowercase letter and contain only lowercase letters, digits, and underscores."
  }
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