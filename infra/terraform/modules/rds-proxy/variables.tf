variable "name" {
  description = "Base name used for RDS Proxy resources."
  type        = string

  validation {
    condition     = length(trimspace(var.name)) > 0
    error_message = "name must not be empty."
  }
}


variable "vpc_id" {
  description = "VPC containing the proxy."
  type        = string
}


variable "subnet_ids" {
  description = "Private subnet IDs used by RDS Proxy."
  type        = list(string)

  validation {
    condition = (
      length(var.subnet_ids) >= 2 &&
      length(distinct(var.subnet_ids)) == length(var.subnet_ids)
    )

    error_message = "subnet_ids must contain at least two distinct subnets."
  }
}


variable "client_security_group_ids" {
  description = "Client security groups allowed to connect to the proxy."
  type        = list(string)

  validation {
    condition     = length(var.client_security_group_ids) >= 1
    error_message = "At least one client security group is required."
  }
}


variable "target_security_group_id" {
  description = "Aurora security group receiving proxy traffic."
  type        = string
}


variable "db_cluster_identifier" {
  description = "Aurora cluster identifier registered with the proxy."
  type        = string
}


variable "secret_arn" {
  description = "Secrets Manager secret ARN used for database authentication."
  type        = string
}


variable "kms_key_arns" {
  description = "Optional KMS key ARNs required to decrypt the database secret."
  type        = list(string)
  default     = []
}


variable "port" {
  description = "PostgreSQL port."
  type        = number
  default     = 5432
}


variable "require_tls" {
  description = "Require TLS for client connections to RDS Proxy."
  type        = bool
  default     = true
}


variable "iam_auth" {
  description = "RDS Proxy IAM authentication mode."
  type        = string
  default     = "DISABLED"

  validation {
    condition = contains(
      [
        "DISABLED",
        "REQUIRED",
      ],
      upper(trimspace(var.iam_auth)),
    )

    error_message = "iam_auth must be DISABLED or REQUIRED."
  }
}


variable "idle_client_timeout" {
  description = "Seconds before an idle client connection is closed."
  type        = number
  default     = 1800
}


variable "connection_borrow_timeout" {
  description = "Seconds a client waits for an available DB connection."
  type        = number
  default     = 120
}


variable "max_connections_percent" {
  description = "Maximum percentage of database connections used by the proxy."
  type        = number
  default     = 90
}


variable "max_idle_connections_percent" {
  description = "Maximum percentage of idle database connections retained."
  type        = number
  default     = 50
}


variable "tags" {
  description = "Additional tags."
  type        = map(string)
  default     = {}
}