variable "repository_name" {
  description = "Name of the Amazon ECR repository."
  type        = string

  validation {
    condition = (
      length(trimspace(var.repository_name)) > 0 &&
      length(var.repository_name) <= 256
    )

    error_message = "repository_name must contain between 1 and 256 characters."
  }
}


variable "image_tag_mutability" {
  description = "Whether image tags are mutable or immutable."
  type        = string
  default     = "IMMUTABLE"

  validation {
    condition = contains(
      [
        "MUTABLE",
        "IMMUTABLE",
      ],
      var.image_tag_mutability,
    )

    error_message = "image_tag_mutability must be MUTABLE or IMMUTABLE."
  }
}


variable "scan_on_push" {
  description = "Enable ECR basic vulnerability scanning when an image is pushed."
  type        = bool
  default     = true
}


variable "force_delete" {
  description = "Allow Terraform to delete a non-empty ECR repository."
  type        = bool
  default     = false
}


variable "kms_key_arn" {
  description = "Optional customer-managed KMS key ARN for ECR encryption."
  type        = string
  default     = null
  nullable    = true
}


variable "enable_lifecycle_policy" {
  description = "Enable automatic ECR image lifecycle cleanup."
  type        = bool
  default     = true
}


variable "max_image_count" {
  description = "Maximum number of images retained in the repository."
  type        = number
  default     = 30

  validation {
    condition     = var.max_image_count >= 1
    error_message = "max_image_count must be at least 1."
  }
}


variable "untagged_image_max_age_days" {
  description = "Number of days untagged images are retained."
  type        = number
  default     = 7

  validation {
    condition     = var.untagged_image_max_age_days >= 1
    error_message = "untagged_image_max_age_days must be at least 1."
  }
}


variable "tags" {
  description = "Additional tags applied to ECR resources."
  type        = map(string)
  default     = {}
}