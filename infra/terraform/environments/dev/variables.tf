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
  description = "Name of the RealStock API SERVICE."
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