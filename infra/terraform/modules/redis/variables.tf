variable "name" {
  description = "Base name used for ElastiCache Redis resources."
  type        = string

  validation {
    condition = (
      length(trimspace(var.name)) > 0
    )

    error_message = (
      "name must not be empty."
    )
  }
}


variable "vpc_id" {
  description = "VPC containing the ElastiCache Redis replication group."
  type        = string

  validation {
    condition = (
      length(trimspace(var.vpc_id)) > 0
    )

    error_message = (
      "vpc_id must not be empty."
    )
  }
}


# ============================================================
# Network
# ============================================================

variable "subnet_ids" {
  description = <<-EOT
Private subnet IDs used by the ElastiCache subnet group.

At least two distinct private subnets are required so Redis can
provide the Multi-AZ high-availability baseline.
EOT

  type = list(string)

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


variable "client_security_group_ids" {
  description = <<-EOT
Security group IDs allowed to connect to Redis.

The module creates security-group-referenced ingress rules on
the Redis security group and matching Redis-only egress rules
on the approved client security groups.
EOT

  type = list(string)

  validation {
    condition = (
      length(var.client_security_group_ids) >= 1 &&
      length(distinct(var.client_security_group_ids)) ==
      length(var.client_security_group_ids)
    )

    error_message = (
      "client_security_group_ids must contain at least one unique security group."
    )
  }
}


# ============================================================
# Redis Engine
# ============================================================

variable "engine_version" {
  description = "Redis engine version."
  type        = string
  default     = "7.1"

  validation {
    condition = (
      length(trimspace(var.engine_version)) > 0
    )

    error_message = (
      "engine_version must not be empty."
    )
  }
}


variable "parameter_group_name" {
  description = "ElastiCache Redis parameter group name."
  type        = string
  default     = "default.redis7"

  validation {
    condition = (
      length(trimspace(var.parameter_group_name)) > 0
    )

    error_message = (
      "parameter_group_name must not be empty."
    )
  }
}


variable "port" {
  description = "Redis listener port."
  type        = number
  default     = 6379

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


# ============================================================
# Capacity / High Availability
# ============================================================

variable "node_type" {
  description = "ElastiCache node type used by Redis."
  type        = string
  default     = "cache.t4g.micro"

  validation {
    condition = (
      length(trimspace(var.node_type)) > 0
    )

    error_message = (
      "node_type must not be empty."
    )
  }
}


variable "num_cache_clusters" {
  description = <<-EOT
Number of cache nodes in the Redis replication group.

At least two nodes are required for the module's HA contract:
one primary plus at least one replica with automatic failover.
EOT

  type    = number
  default = 2

  validation {
    condition = (
      var.num_cache_clusters >= 2 &&
      var.num_cache_clusters <= 6
    )

    error_message = (
      "num_cache_clusters must be between 2 and 6."
    )
  }
}


# ============================================================
# Backup / Maintenance
# ============================================================

variable "snapshot_retention_days" {
  description = "Number of days automated Redis snapshots are retained."
  type        = number
  default     = 7

  validation {
    condition = (
      var.snapshot_retention_days >= 0 &&
      var.snapshot_retention_days <= 35
    )

    error_message = (
      "snapshot_retention_days must be between 0 and 35."
    )
  }
}


variable "snapshot_window" {
  description = "UTC daily time window in which Redis snapshots are created."
  type        = string
  default     = "17:00-18:00"

  validation {
    condition = (
      length(trimspace(var.snapshot_window)) > 0
    )

    error_message = (
      "snapshot_window must not be empty."
    )
  }
}


variable "maintenance_window" {
  description = "UTC weekly maintenance window for ElastiCache Redis."
  type        = string
  default     = "sun:18:00-sun:19:00"

  validation {
    condition = (
      length(trimspace(var.maintenance_window)) > 0
    )

    error_message = (
      "maintenance_window must not be empty."
    )
  }
}


# ============================================================
# Encryption
# ============================================================

variable "kms_key_arn" {
  description = <<-EOT
Optional customer-managed KMS key ARN used for Redis encryption
at rest.

When null, ElastiCache uses the AWS-managed encryption key.
EOT

  type     = string
  default  = null
  nullable = true

  validation {
    condition = (
      var.kms_key_arn == null ||
      can(
        regex(
          "^arn:aws[a-zA-Z-]*:kms:[^:]+:[0-9]{12}:key/.+$",
          trimspace(var.kms_key_arn),
        )
      )
    )

    error_message = (
      "kms_key_arn must be null or a valid KMS key ARN."
    )
  }
}


# ============================================================
# Deployment Behaviour
# ============================================================

variable "apply_immediately" {
  description = <<-EOT
Apply ElastiCache modifications immediately instead of waiting
for the configured maintenance window.

Production environments should normally leave this false unless
an immediate infrastructure change is explicitly required.
EOT

  type    = bool
  default = false
}


# ============================================================
# Tags
# ============================================================

variable "tags" {
  description = "Additional tags applied to Redis resources."
  type        = map(string)
  default     = {}
}