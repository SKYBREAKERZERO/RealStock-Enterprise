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

    error_message = "aws_region must not be empty."
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

    error_message = "vpc_cidr must be a valid IPv4 CIDR."
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
}


variable "api_memory" {
  description = "Fargate memory in MiB assigned to the API task."
  type        = number
  default     = 1024
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
}


variable "api_secrets" {
  description = <<-EOT
Secret environment-variable mapping consumed by ECS.

Values must be Secrets Manager or SSM Parameter Store ARNs.

The production API requires DATABASE_URL and REDIS_URL. Their
secret values must never be stored directly in Terraform source.
EOT

  type      = map(string)
  sensitive = true

  validation {
    condition = (
      contains(keys(var.api_secrets), "DATABASE_URL") &&
      contains(keys(var.api_secrets), "REDIS_URL")
    )

    error_message = (
      "api_secrets must contain DATABASE_URL and REDIS_URL."
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
}


variable "api_task_policy_json" {
  description = <<-EOT
Optional least-privilege application task policy.

Day22 does not fabricate permissions for DynamoDB, Kinesis,
EventBridge, SQS, SNS or S3. Those permissions will later be
built from real Terraform resource ARNs.
EOT

  type      = string
  default   = null
  nullable  = true
  sensitive = true
}