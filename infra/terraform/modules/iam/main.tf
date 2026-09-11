locals {
  name = lower(
    trimspace(var.name)
  )

  execution_role_name = (
    "${local.name}-execution"
  )

  task_role_name = (
    "${local.name}-task"
  )

  execution_extra_permissions_enabled = (
    length(var.execution_secretsmanager_secret_arns) > 0 ||
    length(var.execution_ssm_parameter_arns) > 0 ||
    length(var.execution_kms_key_arns) > 0
  )

  # task_policy_json is IAM policy configuration rather than a
  # credential. nonsensitive() allows the boolean resource-count
  # decision to remain usable even if the input variable is marked
  # sensitive by the caller/module interface.
  task_policy_json = (
    nonsensitive(var.task_policy_json)
  )

  task_policy_enabled = (
    local.task_policy_json != null &&
    length(trimspace(local.task_policy_json)) > 0
  )

  common_tags = merge(
    {
      ManagedBy = "Terraform"
      Component = "ContainerIdentity"
    },
    var.tags,
  )
}


# ============================================================
# Current AWS Identity / Partition
#
# Used for:
#
# - Portable AWS partition handling
# - ECS trust-policy confused-deputy protection
# - Current-account trust restriction
# ============================================================

data "aws_caller_identity" "current" {}


data "aws_partition" "current" {}


# ============================================================
# ECS Task Trust Policy
#
# Both roles:
#
# - ECS task execution role
# - ECS application task role
#
# may only be assumed by ECS tasks.
#
# Security controls:
#
# - Service principal restricted to ecs-tasks.amazonaws.com
# - SourceAccount restricted to current AWS account
# - SourceArn restricted to ECS resources in current account
#
# This provides confused-deputy protection for the role trust
# relationship.
# ============================================================

data "aws_iam_policy_document" "ecs_task_assume_role" {
  statement {
    sid    = "AllowEcsTasksAssumeRole"
    effect = "Allow"

    actions = [
      "sts:AssumeRole",
    ]

    principals {
      type = "Service"

      identifiers = [
        "ecs-tasks.amazonaws.com",
      ]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"

      values = [
        data.aws_caller_identity.current.account_id,
      ]
    }

    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"

      values = [
        "${data.aws_partition.current.partition}:ecs:*:${data.aws_caller_identity.current.account_id}:*",
      ]
    }
  }
}


# ============================================================
# ECS Task Execution Role
#
# This role belongs to ECS / Fargate infrastructure.
#
# It is NOT the RealStock application runtime identity.
#
#
# Responsibilities:
#
# - Authenticate with Amazon ECR
# - Pull container images
# - Deliver container logs to CloudWatch Logs
# - Retrieve explicitly allowed Secrets Manager secrets
# - Retrieve explicitly allowed SSM parameters
# - Decrypt explicitly allowed KMS keys
#
#
# Application boto3/AWS SDK calls use the separate task role.
# ============================================================

resource "aws_iam_role" "execution" {
  name = (
    local.execution_role_name
  )

  assume_role_policy = (
    data.aws_iam_policy_document.ecs_task_assume_role.json
  )

  permissions_boundary = (
    var.permissions_boundary_arn
  )

  tags = merge(
    local.common_tags,
    {
      Name = local.execution_role_name
      Role = "EcsTaskExecution"
    },
  )
}


# ============================================================
# Standard ECS Task Execution Policy
#
# AWS-managed baseline policy used by ECS for common execution
# operations such as ECR image pull and CloudWatch Logs.
#
# This policy belongs only to the EXECUTION role.
# ============================================================

resource "aws_iam_role_policy_attachment" "execution_standard" {
  role = (
    aws_iam_role.execution.name
  )

  policy_arn = (
    "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
  )
}


# ============================================================
# Additional Execution Role Permissions
#
# Created only when at least one explicit resource ARN is
# supplied.
#
# Secrets Manager, SSM Parameter Store, and KMS permissions are
# deliberately separated into independent statements so each
# action is scoped only to resources of the appropriate type.
# ============================================================

data "aws_iam_policy_document" "execution_extra" {
  count = (
    local.execution_extra_permissions_enabled
    ? 1
    : 0
  )


  # ----------------------------------------------------------
  # AWS Secrets Manager
  # ----------------------------------------------------------

  dynamic "statement" {
    for_each = (
      length(var.execution_secretsmanager_secret_arns) > 0
      ? [1]
      : []
    )

    content {
      sid    = "ReadSecretsManagerSecrets"
      effect = "Allow"

      actions = [
        "secretsmanager:GetSecretValue",
      ]

      resources = (
        var.execution_secretsmanager_secret_arns
      )
    }
  }


  # ----------------------------------------------------------
  # AWS Systems Manager Parameter Store
  # ----------------------------------------------------------

  dynamic "statement" {
    for_each = (
      length(var.execution_ssm_parameter_arns) > 0
      ? [1]
      : []
    )

    content {
      sid    = "ReadSsmParameters"
      effect = "Allow"

      actions = [
        "ssm:GetParameters",
      ]

      resources = (
        var.execution_ssm_parameter_arns
      )
    }
  }


  # ----------------------------------------------------------
  # AWS KMS
  #
  # Required when a configured secret or parameter is encrypted
  # with a customer-managed KMS key.
  # ----------------------------------------------------------

  dynamic "statement" {
    for_each = (
      length(var.execution_kms_key_arns) > 0
      ? [1]
      : []
    )

    content {
      sid    = "DecryptContainerSecrets"
      effect = "Allow"

      actions = [
        "kms:Decrypt",
      ]

      resources = (
        var.execution_kms_key_arns
      )
    }
  }
}


# ============================================================
# Attach Optional Execution Permissions
#
# No inline policy resource is created when no additional
# secret/parameter/KMS permissions are required.
# ============================================================

resource "aws_iam_role_policy" "execution_extra" {
  count = (
    local.execution_extra_permissions_enabled
    ? 1
    : 0
  )

  name = (
    "${local.execution_role_name}-secrets"
  )

  role = (
    aws_iam_role.execution.id
  )

  policy = (
    data.aws_iam_policy_document.execution_extra[0].json
  )
}


# ============================================================
# ECS Application Task Role
#
# This role becomes the AWS identity used by RealStock
# application code running inside the Fargate task.
#
#
# Example runtime AWS calls:
#
# RealStock API
#      |
#      +-- DynamoDB
#      |
#      +-- Kinesis
#      |
#      +-- EventBridge
#      |
#      +-- SQS
#      |
#      +-- SNS
#      |
#      +-- S3
#
#
# Security baseline:
#
# - No broad AWS managed business policy
# - No AdministratorAccess
# - No PowerUserAccess
# - No wildcard application permissions defined here
#
# Business permissions must be constructed by the environment
# layer from real resource ARNs.
# ============================================================

resource "aws_iam_role" "task" {
  name = (
    local.task_role_name
  )

  assume_role_policy = (
    data.aws_iam_policy_document.ecs_task_assume_role.json
  )

  permissions_boundary = (
    var.permissions_boundary_arn
  )

  tags = merge(
    local.common_tags,
    {
      Name = local.task_role_name
      Role = "ApplicationTask"
    },
  )
}


# ============================================================
# Optional Application Task Policy
#
# When task_policy_json is null or empty:
#
#     application task role
#             |
#             v
#       no business policy
#
#
# Later environment composition:
#
# DynamoDB ARN ---------+
# Kinesis ARN ----------+
# EventBridge ARN ------+
# SQS ARN --------------+
# SNS ARN --------------+----> aws_iam_policy_document
# S3 ARN ---------------+               |
#                                       v
#                                task_policy_json
#                                       |
#                                       v
#                               Application Task Role
#
#
# This keeps application authorization separate from the
# reusable identity module.
# ============================================================

resource "aws_iam_role_policy" "task" {
  count = (
    local.task_policy_enabled
    ? 1
    : 0
  )

  name = (
    "${local.task_role_name}-application"
  )

  role = (
    aws_iam_role.task.id
  )

  policy = (
    local.task_policy_json
  )
}