variable "name" {
  description = "Base name used for ECS IAM roles."
  type        = string

  validation {
    condition = (
      length(trimspace(var.name)) > 0
    )

    error_message = "name must not be empty."
  }
}


variable "permissions_boundary_arn" {
  description = "Optional IAM permissions boundary applied to ECS roles."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition = (
      var.permissions_boundary_arn == null ||
      can(
        regex(
          "^arn:aws[a-zA-Z-]*:iam::[0-9]{12}:policy/.+$",
          trimspace(var.permissions_boundary_arn),
        )
      )
    )

    error_message = (
      "permissions_boundary_arn must be null or a valid IAM policy ARN."
    )
  }
}


# ============================================================
# ECS Execution Role - Secrets Manager
#
# These ARNs are used only by the ECS execution role when ECS
# injects Secrets Manager values into container definitions.
# ============================================================

variable "execution_secretsmanager_secret_arns" {
  description = "Secrets Manager secret ARNs available for ECS container secret injection."
  type        = list(string)
  default     = []

  validation {
    condition = alltrue(
      [
        for arn in var.execution_secretsmanager_secret_arns :
        can(
          regex(
            "^arn:aws[a-zA-Z-]*:secretsmanager:",
            trimspace(arn),
          )
        )
      ]
    )

    error_message = (
      "execution_secretsmanager_secret_arns must contain only Secrets Manager ARNs."
    )
  }
}


# ============================================================
# ECS Execution Role - SSM Parameter Store
#
# These ARNs are used only when ECS injects Parameter Store
# values into container definitions.
# ============================================================

variable "execution_ssm_parameter_arns" {
  description = "SSM Parameter Store ARNs available for ECS container secret injection."
  type        = list(string)
  default     = []

  validation {
    condition = alltrue(
      [
        for arn in var.execution_ssm_parameter_arns :
        can(
          regex(
            "^arn:aws[a-zA-Z-]*:ssm:",
            trimspace(arn),
          )
        )
      ]
    )

    error_message = (
      "execution_ssm_parameter_arns must contain only SSM Parameter Store ARNs."
    )
  }
}


# ============================================================
# ECS Execution Role - KMS
#
# Customer-managed KMS keys required for decrypting configured
# Secrets Manager or SSM values.
# ============================================================

variable "execution_kms_key_arns" {
  description = "KMS key ARNs permitted for decrypting ECS container secrets."
  type        = list(string)
  default     = []

  validation {
    condition = alltrue(
      [
        for arn in var.execution_kms_key_arns :
        can(
          regex(
            "^arn:aws[a-zA-Z-]*:kms:",
            trimspace(arn),
          )
        )
      ]
    )

    error_message = (
      "execution_kms_key_arns must contain only AWS KMS ARNs."
    )
  }
}


# ============================================================
# Application Task Role Policy
#
# The reusable IAM module intentionally does not know which
# business resources RealStock uses.
#
# Environment composition should build this JSON policy from
# actual resource ARNs, for example:
#
# - DynamoDB
# - Kinesis
# - EventBridge
# - SQS
# - SNS
# - S3
#
# The task role has no application permissions when this value
# is null.
# ============================================================

variable "task_policy_json" {
  description = <<-EOT
Optional least-privilege JSON policy assigned to the application
task role.

Environment layers should build this policy from the ARNs of
resources actually used by the application.

When null, the application task role receives no additional
business permissions.
EOT

  type      = string
  default   = null
  nullable  = true
  sensitive = true

  validation {
    condition = (
      var.task_policy_json == null ||
      length(trimspace(var.task_policy_json)) > 0
    )

    error_message = (
      "task_policy_json must be null or a non-empty JSON policy string."
    )
  }
}


variable "tags" {
  description = "Additional tags applied to IAM roles."
  type        = map(string)
  default     = {}
}