variable "project_name" {
  description = "Project name used for resource naming."
  type        = string
  default     = "realstock"

  validation {
    condition = (
      length(trimspace(var.project_name)) > 0
    )

    error_message = (
      "project_name must not be empty."
    )
  }
}


variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "dev"

  validation {
    condition = (
      lower(trimspace(var.environment)) == "dev"
    )

    error_message = (
      "This Terraform root module is restricted to the dev environment."
    )
  }
}


variable "api_service_name" {
  description = "Name of the RealStock API service."
  type        = string
  default     = "api"

  validation {
    condition = (
      length(trimspace(var.api_service_name)) > 0
    )

    error_message = (
      "api_service_name must not be empty."
    )
  }
}


# ============================================================
# AWS / Network
# ============================================================

variable "aws_region" {
  description = "AWS region used by the dev environment."
  type        = string
  default     = "ap-northeast-1"

  validation {
    condition = (
      length(trimspace(var.aws_region)) > 0
    )

    error_message = (
      "aws_region must not be empty."
    )
  }
}


variable "vpc_cidr" {
  description = "IPv4 CIDR block assigned to the dev VPC."
  type        = string
  default     = "10.20.0.0/16"

  validation {
    condition = (
      can(cidrnetmask(var.vpc_cidr))
    )

    error_message = (
      "vpc_cidr must be a valid IPv4 CIDR."
    )
  }
}


variable "availability_zones" {
  description = <<-EOT
Optional two-AZ override.

When empty, the environment automatically uses the first two
available AZs in aws_region.
EOT

  type    = list(string)
  default = []

  validation {
    condition = (
      length(var.availability_zones) == 0 ||
      (
        length(var.availability_zones) == 2 &&
        length(distinct(var.availability_zones)) == 2
      )
    )

    error_message = (
      "availability_zones must be empty or contain exactly two distinct AZs."
    )
  }
}


variable "nat_gateway_mode" {
  description = "NAT topology used by the dev VPC."
  type        = string
  default     = "single"

  validation {
    condition = contains(
      [
        "per_az",
        "single",
        "none",
      ],
      lower(trimspace(var.nat_gateway_mode)),
    )

    error_message = (
      "nat_gateway_mode must be per_az, single, or none."
    )
  }
}


# ============================================================
# API Container Deployment
# ============================================================

variable "api_image_tag" {
  description = <<-EOT
Immutable ECR image tag deployed to ECS.

Use a Git commit SHA or another immutable release identifier.
The mutable latest tag is deliberately forbidden.
EOT

  type = string

  validation {
    condition = (
      length(trimspace(var.api_image_tag)) > 0 &&
      lower(trimspace(var.api_image_tag)) != "latest" &&
      can(
        regex(
          "^[A-Za-z0-9_][A-Za-z0-9._-]{0,127}$",
          trimspace(var.api_image_tag),
        )
      )
    )

    error_message = (
      "api_image_tag must be a valid immutable ECR tag and must not be latest."
    )
  }
}


variable "api_certificate_arn" {
  description = "Existing ACM certificate ARN used by the API HTTPS listener."
  type        = string

  validation {
    condition = can(
      regex(
        "^arn:aws[a-zA-Z-]*:acm:[^:]+:[0-9]{12}:certificate/.+$",
        trimspace(var.api_certificate_arn),
      )
    )

    error_message = (
      "api_certificate_arn must be a valid ACM certificate ARN."
    )
  }
}


variable "enable_http_redirect" {
  description = "Enable public HTTP ingress only for HTTP-to-HTTPS redirect."
  type        = bool
  default     = false
}


variable "enable_alb_deletion_protection" {
  description = "Protect the dev ALB from accidental deletion."
  type        = bool
  default     = false
}


variable "api_desired_count" {
  description = "Desired number of API ECS tasks."
  type        = number
  default     = 2

  validation {
    condition = (
      var.api_desired_count >= 2
    )

    error_message = (
      "api_desired_count must be at least 2 for the HA deployment contract."
    )
  }
}


variable "api_cpu" {
  description = "Fargate CPU units assigned to the API task."
  type        = number
  default     = 512

  validation {
    condition = (
      var.api_cpu > 0
    )

    error_message = (
      "api_cpu must be greater than zero."
    )
  }
}


variable "api_memory" {
  description = "Fargate memory in MiB assigned to the API task."
  type        = number
  default     = 1024

  validation {
    condition = (
      var.api_memory > 0
    )

    error_message = (
      "api_memory must be greater than zero."
    )
  }
}


variable "enable_ecs_exec" {
  description = "Enable ECS Exec for controlled operational access."
  type        = bool
  default     = false
}


# ============================================================
# Application Configuration
# ============================================================

variable "api_environment_variables" {
  description = "Additional non-secret API environment variables."
  type        = map(string)
  default     = {}

  validation {
    condition = (
      !contains(keys(var.api_environment_variables), "REDIS_URL")
    )

    error_message = (
      "REDIS_URL is managed by Terraform from the ElastiCache endpoint and must not be overridden."
    )
  }
}


variable "api_secrets" {
  description = <<-EOT
Secret environment-variable mapping consumed by ECS.

Values must be Secrets Manager or SSM Parameter Store ARNs.

DATABASE_URL remains an application secret because it contains
database credential material.

REDIS_URL is generated by Terraform from the private ElastiCache
endpoint and must not be supplied through this secret map.
EOT

  type      = map(string)
  sensitive = true

  validation {
    condition = (
      contains(keys(var.api_secrets), "DATABASE_URL")
    )

    error_message = (
      "api_secrets must contain DATABASE_URL."
    )
  }

  validation {
    condition = (
      !contains(keys(var.api_secrets), "REDIS_URL")
    )

    error_message = (
      "REDIS_URL must not be supplied through api_secrets because Terraform generates it from ElastiCache."
    )
  }

  validation {
    condition = alltrue(
      [
        for arn in values(var.api_secrets) :
        (
          can(
            regex(
              "^arn:aws[a-zA-Z-]*:secretsmanager:",
              trimspace(arn),
            )
          ) ||
          can(
            regex(
              "^arn:aws[a-zA-Z-]*:ssm:",
              trimspace(arn),
            )
          )
        )
      ]
    )

    error_message = (
      "api_secrets values must be Secrets Manager or SSM Parameter Store ARNs."
    )
  }
}


variable "api_kms_key_arns" {
  description = "Customer-managed KMS keys required to decrypt API secrets."
  type        = list(string)
  default     = []

  validation {
    condition = alltrue(
      [
        for arn in var.api_kms_key_arns :
        can(
          regex(
            "^arn:aws[a-zA-Z-]*:kms:[^:]+:[0-9]{12}:key/.+$",
            trimspace(arn),
          )
        )
      ]
    )

    error_message = (
      "api_kms_key_arns must contain valid KMS key ARNs."
    )
  }
}


variable "api_task_policy_json" {
  description = <<-EOT
Optional least-privilege application task policy.

Business-resource permissions for DynamoDB, Kinesis, EventBridge,
SQS, SNS and S3 should only be introduced when their real
Terraform resource ARNs are available.
EOT

  type      = string
  default   = null
  nullable  = true
  sensitive = true
}


# ============================================================
# Aurora PostgreSQL / RDS Proxy
# ============================================================

variable "database_name" {
  description = "Initial Aurora PostgreSQL database name."
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


variable "database_master_username" {
  description = "Aurora PostgreSQL master username."
  type        = string
  default     = "realstock_admin"

  validation {
    condition = (
      length(trimspace(var.database_master_username)) > 0
    )

    error_message = (
      "database_master_username must not be empty."
    )
  }
}


variable "database_engine_version" {
  description = "Optional Aurora PostgreSQL engine version."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition = (
      var.database_engine_version == null ||
      length(trimspace(var.database_engine_version)) > 0
    )

    error_message = (
      "database_engine_version must be null or a non-empty string."
    )
  }
}


variable "database_instance_class" {
  description = "Aurora PostgreSQL instance class."
  type        = string
  default     = "db.t4g.medium"

  validation {
    condition = (
      length(trimspace(var.database_instance_class)) > 0
    )

    error_message = (
      "database_instance_class must not be empty."
    )
  }
}


variable "database_instance_count" {
  description = "Number of Aurora instances."
  type        = number
  default     = 2

  validation {
    condition = (
      var.database_instance_count >= 2
    )

    error_message = (
      "database_instance_count must be at least 2 for HA."
    )
  }
}


variable "database_backup_retention_days" {
  description = "Aurora automated backup retention period."
  type        = number
  default     = 7

  validation {
    condition = (
      var.database_backup_retention_days >= 1 &&
      var.database_backup_retention_days <= 35
    )

    error_message = (
      "database_backup_retention_days must be between 1 and 35."
    )
  }
}


variable "database_deletion_protection" {
  description = "Protect the dev Aurora cluster from accidental deletion."
  type        = bool
  default     = false
}


variable "database_skip_final_snapshot" {
  description = "Skip final snapshot when destroying the dev Aurora cluster."
  type        = bool
  default     = true
}


variable "database_kms_key_arn" {
  description = "Optional customer-managed KMS key ARN for Aurora storage."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition = (
      var.database_kms_key_arn == null ||
      can(
        regex(
          "^arn:aws[a-zA-Z-]*:kms:[^:]+:[0-9]{12}:key/.+$",
          trimspace(var.database_kms_key_arn),
        )
      )
    )

    error_message = (
      "database_kms_key_arn must be null or a valid KMS key ARN."
    )
  }
}


# ============================================================
# ElastiCache Redis
# ============================================================

variable "redis_engine_version" {
  description = "Redis engine version used by the dev ElastiCache replication group."
  type        = string
  default     = "7.1"

  validation {
    condition = (
      length(trimspace(var.redis_engine_version)) > 0
    )

    error_message = (
      "redis_engine_version must not be empty."
    )
  }
}


variable "redis_node_type" {
  description = "ElastiCache Redis node type."
  type        = string
  default     = "cache.t4g.micro"

  validation {
    condition = (
      length(trimspace(var.redis_node_type)) > 0
    )

    error_message = (
      "redis_node_type must not be empty."
    )
  }
}


variable "redis_num_cache_clusters" {
  description = <<-EOT
Number of Redis nodes in the replication group.

At least two nodes are required for the dev HA contract:
one primary and at least one replica.
EOT

  type    = number
  default = 2

  validation {
    condition = (
      var.redis_num_cache_clusters >= 2 &&
      var.redis_num_cache_clusters <= 6
    )

    error_message = (
      "redis_num_cache_clusters must be between 2 and 6."
    )
  }
}


variable "redis_snapshot_retention_days" {
  description = "Redis automated snapshot retention period."
  type        = number
  default     = 7

  validation {
    condition = (
      var.redis_snapshot_retention_days >= 0 &&
      var.redis_snapshot_retention_days <= 35
    )

    error_message = (
      "redis_snapshot_retention_days must be between 0 and 35."
    )
  }
}


variable "redis_kms_key_arn" {
  description = <<-EOT
Optional customer-managed KMS key ARN used for ElastiCache
encryption at rest.

When null, the AWS-managed encryption key is used.
EOT

  type     = string
  default  = null
  nullable = true

  validation {
    condition = (
      var.redis_kms_key_arn == null ||
      can(
        regex(
          "^arn:aws[a-zA-Z-]*:kms:[^:]+:[0-9]{12}:key/.+$",
          trimspace(var.redis_kms_key_arn),
        )
      )
    )

    error_message = (
      "redis_kms_key_arn must be null or a valid KMS key ARN."
    )
  }
}


variable "redis_apply_immediately" {
  description = "Apply ElastiCache changes immediately."
  type        = bool
  default     = false
}