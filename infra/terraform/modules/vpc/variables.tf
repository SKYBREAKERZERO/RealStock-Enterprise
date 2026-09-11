variable "name" {
  description = "Base name used for VPC networking resources."
  type        = string

  validation {
    condition = (
      length(trimspace(var.name)) > 0
    )

    error_message = "name must not be empty."
  }
}


variable "vpc_cidr" {
  description = "IPv4 CIDR block assigned to the VPC."
  type        = string
  default     = "10.20.0.0/16"

  validation {
    condition = (
      can(cidrnetmask(var.vpc_cidr))
    )

    error_message = "vpc_cidr must be a valid IPv4 CIDR block."
  }
}


variable "availability_zones" {
  description = "Availability Zones used by the VPC."
  type        = list(string)

  validation {
    condition = (
      length(var.availability_zones) >= 2 &&
      length(distinct(var.availability_zones)) ==
      length(var.availability_zones) &&
      alltrue(
        [
          for az in var.availability_zones :
          length(trimspace(az)) > 0
        ]
      )
    )

    error_message = (
      "availability_zones must contain at least two distinct Availability Zones."
    )
  }
}


variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets, one per Availability Zone."
  type        = list(string)

  validation {
    condition = alltrue(
      [
        for cidr in var.public_subnet_cidrs :
        can(cidrnetmask(cidr))
      ]
    )

    error_message = (
      "public_subnet_cidrs must contain only valid CIDR blocks."
    )
  }
}


variable "private_app_subnet_cidrs" {
  description = "CIDR blocks for private application subnets, one per Availability Zone."
  type        = list(string)

  validation {
    condition = alltrue(
      [
        for cidr in var.private_app_subnet_cidrs :
        can(cidrnetmask(cidr))
      ]
    )

    error_message = (
      "private_app_subnet_cidrs must contain only valid CIDR blocks."
    )
  }
}


variable "private_data_subnet_cidrs" {
  description = "CIDR blocks for isolated private data subnets, one per Availability Zone."
  type        = list(string)

  validation {
    condition = alltrue(
      [
        for cidr in var.private_data_subnet_cidrs :
        can(cidrnetmask(cidr))
      ]
    )

    error_message = (
      "private_data_subnet_cidrs must contain only valid CIDR blocks."
    )
  }
}


variable "nat_gateway_mode" {
  description = <<-EOT
NAT Gateway topology for private application subnets.

per_az:
  One NAT Gateway per Availability Zone. Production HA baseline.

single:
  One NAT Gateway shared by all application subnets. Lower cost but
  introduces a single-AZ dependency.

none:
  No NAT Gateway or internet default route for application subnets.
EOT

  type    = string
  default = "per_az"

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


variable "enable_dns_support" {
  description = "Enable Amazon-provided DNS resolution in the VPC."
  type        = bool
  default     = true
}


variable "enable_dns_hostnames" {
  description = "Enable DNS hostnames for resources in the VPC."
  type        = bool
  default     = true
}


variable "tags" {
  description = "Additional tags applied to VPC networking resources."
  type        = map(string)
  default     = {}
}