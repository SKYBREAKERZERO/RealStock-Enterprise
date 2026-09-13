variable "name" {
  description = "Base name used for Aurora resources."
  type        = string

  validation {
    condition     = length(trimspace(var.name)) > 0
    error_message = "name must not be empty."
  }
}


variable "vpc_id" {
  description = "VPC containing the Aurora cluster."
  type        = string

  validation {
    condition     = length(trimspace(var.vpc_id)) > 0
    error_message = "vpc_id must not be empty."
  }
}


variable "subnet_ids" {
  description = "Private data subnet IDs used by Aurora."
  type        = list(string)

  validation {
    condition = (
      length(var.subnet_ids) >= 2 &&
      length(distinct(var.subnet_ids)) == length(var.subnet_ids)
    )

    error_message = (
      "subnet_ids must contain at least two distinct private subnets."
    )
  }
}


variable "allowed_security_group_ids" {
  description = "Security groups allowed to reach Aurora PostgreSQL."
  type        = list(string)
  default     = []
}


variable "database_name" {
  description = "Name of the database to create in Aurora."
  type        = string
  default     = "realstock"

  validation {
    condition = (
      length(trimspace(var.database_name)) > 0
    )

    error_message = (
      "database_name must not be empty."
    )
  }
}


variable "master_username" {
  description = "Aurora PostgreSQL master username."
  type        = string
  default     = "realstock_admin"

  validation {
    condition = (
      length(trimspace(var.master_username)) > 0
    )

    error_message = (
      "master_username must not be empty."
    )
  }
}


variable "engine_version" {
  description = "Aurora PostgreSQL engine version. Null allows AWS to select a compatible default."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition = (
      var.engine_version == null ||
      length(trimspace(var.engine_version)) > 0
    )

    error_message = (
      "engine_version must be null or a non-empty version string."
    )
  }
}


variable "instance_count" {
  description = "Number of Aurora instances."
  type        = number
  default     = 2

  validation {
    condition = (
      var.instance_count >= 2
    )

    error_message = (
      "instance_count must be at least 2 for the HA baseline."
    )
  }
}


variable "instance_class" {
  description = "Aurora DB instance class."
  type        = string
  default     = "db.t4g.medium"

  validation {
    condition = (
      length(trimspace(var.instance_class)) > 0
    )

    error_message = (
      "instance_class must not be empty."
    )
  }
}


variable "port" {
  description = "PostgreSQL listener port."
  type        = number
  default     = 5432

  validation {
    condition = (
      var.port >= 1 &&
      var.port <= 65535
    )

    error_message = (
      "port must be between 1 and 65535."
    )
  }
}


variable "backup_retention_days" {
  description = "Automated backup retention period."
  type        = number
  default     = 7

  validation {
    condition = (
      var.backup_retention_days >= 1 &&
      var.backup_retention_days <= 35
    )

    error_message = (
      "backup_retention_days must be between 1 and 35."
    )
  }
}


variable "preferred_backup_window" {
  description = "UTC backup window."
  type        = string
  default     = "18:00-19:00"
}


variable "preferred_maintenance_window" {
  description = "UTC weekly maintenance window."
  type        = string
  default     = "sun:19:00-sun:20:00"
}


variable "deletion_protection" {
  description = "Protect the cluster from accidental deletion."
  type        = bool
  default     = true
}


variable "skip_final_snapshot" {
  description = "Skip the final snapshot when the cluster is destroyed."
  type        = bool
  default     = false
}


variable "kms_key_arn" {
  description = "Optional customer-managed KMS key ARN for Aurora encryption."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition = (
      var.kms_key_arn == null ||
      can(
        regex(
          "^arn:aws[a-zA-Z-]*:kms:",
          trimspace(var.kms_key_arn),
        )
      )
    )

    error_message = (
      "kms_key_arn must be null or a valid KMS ARN."
    )
  }
}


variable "performance_insights_enabled" {
  description = "Enable Performance Insights on Aurora instances."
  type        = bool
  default     = true
}


variable "monitoring_interval" {
  description = "Enhanced Monitoring interval. Zero disables it."
  type        = number
  default     = 0

  validation {
    condition = contains(
      [
        0,
        1,
        5,
        10,
        15,
        30,
        60,
      ],
      var.monitoring_interval,
    )

    error_message = (
      "monitoring_interval must be one of 0, 1, 5, 10, 15, 30, or 60."
    )
  }
}


variable "tags" {
  description = "Additional tags applied to Aurora resources."
  type        = map(string)
  default     = {}
}