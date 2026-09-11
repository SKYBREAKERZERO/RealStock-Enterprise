variable "name" {
  description = "Base name used for application security groups."
  type        = string

  validation {
    condition = (
      length(trimspace(var.name)) > 0
    )

    error_message = "name must not be empty."
  }
}


variable "vpc_id" {
  description = "VPC ID in which security groups are created."
  type        = string

  validation {
    condition = (
      length(trimspace(var.vpc_id)) > 0
    )

    error_message = "vpc_id must not be empty."
  }
}


variable "application_port" {
  description = "TCP port exposed by the ECS application container."
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
  description = "HTTPS listener port exposed by the public ALB."
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


variable "alb_ingress_cidrs" {
  description = "IPv4 CIDR blocks allowed to reach the ALB over HTTPS."
  type        = list(string)

  default = [
    "0.0.0.0/0",
  ]

  validation {
    condition = alltrue(
      [
        for cidr in var.alb_ingress_cidrs :
        can(cidrnetmask(cidr))
      ]
    )

    error_message = (
      "alb_ingress_cidrs must contain only valid IPv4 CIDR blocks."
    )
  }
}


variable "enable_http_ingress" {
  description = "Allow HTTP ingress to the ALB for optional HTTP-to-HTTPS redirect."
  type        = bool
  default     = false
}


variable "http_port" {
  description = "Optional HTTP listener port."
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


variable "ecs_https_egress_cidrs" {
  description = <<-EOT
IPv4 CIDR blocks ECS tasks may reach over HTTPS.

This supports AWS public service endpoints and external HTTPS
providers through NAT. More specific service connectivity can
later move to VPC endpoints.
EOT

  type = list(string)

  default = [
    "0.0.0.0/0",
  ]

  validation {
    condition = alltrue(
      [
        for cidr in var.ecs_https_egress_cidrs :
        can(cidrnetmask(cidr))
      ]
    )

    error_message = (
      "ecs_https_egress_cidrs must contain only valid IPv4 CIDR blocks."
    )
  }
}


variable "tags" {
  description = "Additional tags applied to security groups."
  type        = map(string)
  default     = {}
}