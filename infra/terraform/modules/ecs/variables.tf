variable "name" {
  description = "Base name used for ECS resources."
  type        = string

  validation {
    condition = (
      length(trimspace(var.name)) > 0
    )

    error_message = "name must not be empty."
  }
}


variable "aws_region" {
  description = "AWS region used by ECS and CloudWatch Logs."
  type        = string

  validation {
    condition = (
      length(trimspace(var.aws_region)) > 0
    )

    error_message = "aws_region must not be empty."
  }
}


variable "image_uri" {
  description = "Immutable container image URI deployed by the ECS task."
  type        = string

  validation {
    condition = (
      length(trimspace(var.image_uri)) > 0
    )

    error_message = "image_uri must not be empty."
  }
}


variable "execution_role_arn" {
  description = <<-EOT
IAM execution role ARN used by the ECS agent for operations such
as pulling ECR images and writing container logs.
EOT

  type = string

  validation {
    condition = (
      length(trimspace(var.execution_role_arn)) > 0
    )

    error_message = "execution_role_arn must not be empty."
  }
}


variable "task_role_arn" {
  description = <<-EOT
IAM task role ARN assumed by the application container for AWS
API access. This must remain separate from the execution role.
EOT

  type = string

  validation {
    condition = (
      length(trimspace(var.task_role_arn)) > 0
    )

    error_message = "task_role_arn must not be empty."
  }
}


variable "subnet_ids" {
  description = "Subnets used by ECS tasks through awsvpc networking."
  type        = list(string)

  validation {
    condition = (
      length(var.subnet_ids) >= 2
    )

    error_message = (
      "subnet_ids must contain at least two subnets for high availability."
    )
  }
}


variable "security_group_ids" {
  description = "Security groups attached to ECS task ENIs."
  type        = list(string)

  validation {
    condition = (
      length(var.security_group_ids) >= 1
    )

    error_message = (
      "security_group_ids must contain at least one security group."
    )
  }
}


variable "target_group_arn" {
  description = "Optional ALB target group ARN attached to the ECS service."
  type        = string
  default     = null
  nullable    = true
}


variable "container_name" {
  description = "Name of the application container."
  type        = string
  default     = "api"

  validation {
    condition = (
      length(trimspace(var.container_name)) > 0
    )

    error_message = "container_name must not be empty."
  }
}


variable "container_port" {
  description = "Application container port."
  type        = number
  default     = 8000

  validation {
    condition = (
      var.container_port >= 1 &&
      var.container_port <= 65535
    )

    error_message = (
      "container_port must be between 1 and 65535."
    )
  }
}


variable "desired_count" {
  description = "Desired number of running ECS tasks."
  type        = number
  default     = 2

  validation {
    condition = (
      var.desired_count >= 1
    )

    error_message = "desired_count must be at least 1."
  }
}


variable "cpu" {
  description = "Fargate task CPU units."
  type        = number
  default     = 512

  validation {
    condition = contains(
      [
        256,
        512,
        1024,
        2048,
        4096,
        8192,
        16384,
      ],
      var.cpu,
    )

    error_message = "cpu must be a supported Fargate CPU value."
  }
}


variable "memory" {
  description = "Fargate task memory in MiB."
  type        = number
  default     = 1024

  validation {
    condition = (
      var.memory >= 512
    )

    error_message = "memory must be at least 512 MiB."
  }
}


variable "cpu_architecture" {
  description = "CPU architecture used by the Fargate task."
  type        = string
  default     = "X86_64"

  validation {
    condition = contains(
      [
        "X86_64",
        "ARM64",
      ],
      upper(trimspace(var.cpu_architecture)),
    )

    error_message = (
      "cpu_architecture must be X86_64 or ARM64."
    )
  }
}


variable "assign_public_ip" {
  description = "Whether ECS task ENIs receive public IP addresses."
  type        = bool
  default     = false
}


variable "enable_execute_command" {
  description = "Enable ECS Exec for controlled operational access."
  type        = bool
  default     = false
}


variable "health_check_grace_period_seconds" {
  description = "Grace period before ECS evaluates task health."
  type        = number
  default     = 60

  validation {
    condition = (
      var.health_check_grace_period_seconds >= 0
    )

    error_message = (
      "health_check_grace_period_seconds must not be negative."
    )
  }
}


variable "stop_timeout_seconds" {
  description = "Seconds ECS waits after SIGTERM before forcefully stopping the container."
  type        = number
  default     = 30

  validation {
    condition = (
      var.stop_timeout_seconds >= 2 &&
      var.stop_timeout_seconds <= 120
    )

    error_message = (
      "stop_timeout_seconds must be between 2 and 120 seconds."
    )
  }
}


variable "log_retention_days" {
  description = "CloudWatch Logs retention period."
  type        = number
  default     = 30

  validation {
    condition = (
      var.log_retention_days >= 1
    )

    error_message = (
      "log_retention_days must be at least 1."
    )
  }
}


variable "environment_variables" {
  description = "Non-secret environment variables passed to the application container."
  type        = map(string)
  default     = {}
}


variable "secrets" {
  description = <<-EOT
Secret environment variables mapped to Secrets Manager or
SSM Parameter Store valueFrom ARNs.
EOT

  type    = map(string)
  default = {}
}


variable "tags" {
  description = "Additional tags applied to ECS resources."
  type        = map(string)
  default     = {}
}