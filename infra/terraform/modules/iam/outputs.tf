# ============================================================
# ECS Task Execution Role
#
# Used by ECS / Fargate infrastructure for:
#
# - ECR image pull
# - CloudWatch Logs delivery
# - Secrets Manager injection
# - SSM Parameter Store injection
# - KMS decrypt when explicitly authorized
#
# This is NOT the application runtime identity.
# ============================================================

output "execution_role_name" {
  description = "Name of the ECS task execution role."

  value = (
    aws_iam_role.execution.name
  )
}


output "execution_role_arn" {
  description = "ARN of the ECS task execution role."

  value = (
    aws_iam_role.execution.arn
  )
}


# ============================================================
# ECS Application Task Role
#
# Used by RealStock application code running inside ECS.
#
# Application AWS SDK calls use this identity.
#
# Business permissions are intentionally supplied separately
# through the environment-specific least-privilege task policy.
# ============================================================

output "task_role_name" {
  description = "Name of the application ECS task role."

  value = (
    aws_iam_role.task.name
  )
}


output "task_role_arn" {
  description = "ARN of the application ECS task role."

  value = (
    aws_iam_role.task.arn
  )
}