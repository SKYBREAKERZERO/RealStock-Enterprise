variable "name" {
  description = "Base name used for Application Load Balancer resources."
  type        = string

  validation {
    condition = (
      length(trimspace(var.name)) > 0
    )

    error_message = "name must not be empty."
  }
}


variable "vpc_id" {
  description = "VPC ID containing the ALB target group."
  type        = string

  validation {
    condition = (
      length(trimspace(var.vpc_id)) > 0
    )

    error_message = "vpc_id must not be empty."
  }
}


variable "public_subnet_ids" {
  description = "Public subnet IDs used by the internet-facing ALB."
  type        = list(string)

  validation {
    condition = (
      length(var.public_subnet_ids) >= 2 &&
      length(distinct(var.public_subnet_ids)) ==
      length(var.public_subnet_ids)
    )

    error_message = (
      "public_subnet_ids must contain at least two distinct subnets."
    )
  }
}


variable "security_group_ids" {
  description = "Security group IDs attached to the ALB."
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


variable "certificate_arn" {
  description = "ACM certificate ARN used by the HTTPS listener."
  type        = string

  validation {
    condition = can(
      regex(
        "^arn:aws[a-zA-Z-]*:acm:[^:]+:[0-9]{12}:certificate/.+$",
        trimspace(var.certificate_arn),
      )
    )

    error_message = (
      "certificate_arn must be a valid ACM certificate ARN."
    )
  }
}


variable "application_port" {
  description = "Port on which ECS application targets receive traffic."
  type        = number
  default     = 8000

  validation {
    condition = (
      var.application_port >= 1 &&
      var.application_port <= 65535
    )

    error_message = (
      "application_port must be between 1 and 65535."
    )
  }
}


variable "https_port" {
  description = "HTTPS listener port."
  type        = number
  default     = 443

  validation {
    condition = (
      var.https_port >= 1 &&
      var.https_port <= 65535
    )

    error_message = (
      "https_port must be between 1 and 65535."
    )
  }
}


variable "http_port" {
  description = "Optional HTTP listener port used only for HTTPS redirect."
  type        = number
  default     = 80

  validation {
    condition = (
      var.http_port >= 1 &&
      var.http_port <= 65535
    )

    error_message = (
      "http_port must be between 1 and 65535."
    )
  }
}


variable "enable_http_redirect" {
  description = "Create an HTTP listener that redirects all traffic to HTTPS."
  type        = bool
  default     = false
}


variable "ssl_policy" {
  description = "TLS security policy used by the HTTPS listener."
  type        = string
  default     = "ELBSecurityPolicy-TLS13-1-2-2021-06"

  validation {
    condition = (
      length(trimspace(var.ssl_policy)) > 0
    )

    error_message = "ssl_policy must not be empty."
  }
}


variable "health_check_path" {
  description = "ALB readiness endpoint used by the target group."
  type        = string
  default     = "/health/ready"

  validation {
    condition = (
      startswith(var.health_check_path, "/") &&
      length(trimspace(var.health_check_path)) > 1
    )

    error_message = (
      "health_check_path must be a non-empty absolute HTTP path."
    )
  }
}


variable "health_check_interval_seconds" {
  description = "Seconds between target health checks."
  type        = number
  default     = 30

  validation {
    condition = (
      var.health_check_interval_seconds >= 5 &&
      var.health_check_interval_seconds <= 300
    )

    error_message = (
      "health_check_interval_seconds must be between 5 and 300."
    )
  }
}


variable "health_check_timeout_seconds" {
  description = "Seconds before an ALB health check times out."
  type        = number
  default     = 5

  validation {
    condition = (
      var.health_check_timeout_seconds >= 2 &&
      var.health_check_timeout_seconds <= 120
    )

    error_message = (
      "health_check_timeout_seconds must be between 2 and 120."
    )
  }
}


variable "healthy_threshold" {
  description = "Consecutive successful checks required before a target becomes healthy."
  type        = number
  default     = 2

  validation {
    condition = (
      var.healthy_threshold >= 2 &&
      var.healthy_threshold <= 10
    )

    error_message = (
      "healthy_threshold must be between 2 and 10."
    )
  }
}


variable "unhealthy_threshold" {
  description = "Consecutive failed checks required before a target becomes unhealthy."
  type        = number
  default     = 3

  validation {
    condition = (
      var.unhealthy_threshold >= 2 &&
      var.unhealthy_threshold <= 10
    )

    error_message = (
      "unhealthy_threshold must be between 2 and 10."
    )
  }
}


variable "deregistration_delay_seconds" {
  description = "Seconds ALB waits for in-flight requests when deregistering a target."
  type        = number
  default     = 30

  validation {
    condition = (
      var.deregistration_delay_seconds >= 0 &&
      var.deregistration_delay_seconds <= 3600
    )

    error_message = (
      "deregistration_delay_seconds must be between 0 and 3600."
    )
  }
}


variable "idle_timeout_seconds" {
  description = "ALB idle connection timeout."
  type        = number
  default     = 60

  validation {
    condition = (
      var.idle_timeout_seconds >= 1 &&
      var.idle_timeout_seconds <= 4000
    )

    error_message = (
      "idle_timeout_seconds must be between 1 and 4000."
    )
  }
}


variable "enable_deletion_protection" {
  description = "Protect the ALB from accidental deletion."
  type        = bool
  default     = true
}


variable "access_logs_bucket" {
  description = "Optional S3 bucket name used for ALB access logs."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition = (
      var.access_logs_bucket == null ||
      length(trimspace(var.access_logs_bucket)) > 0
    )

    error_message = (
      "access_logs_bucket must be null or a non-empty S3 bucket name."
    )
  }
}


variable "access_logs_prefix" {
  description = "Optional prefix used for ALB access log objects."
  type        = string
  default     = "alb"
}


variable "tags" {
  description = "Additional tags applied to ALB resources."
  type        = map(string)
  default     = {}
}