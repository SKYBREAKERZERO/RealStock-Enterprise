locals {
  common_tags = merge(
    {
      Name      = var.repository_name
      ManagedBy = "Terraform"
      Component = "ContainerRegistry"
    },
    var.tags,
  )
}


# ==============================================================
# Amazon ECR Repository
# ==============================================================
resource "aws_ecr_repository" "this" {
  name                 = var.repository_name
  image_tag_mutability = var.image_tag_mutability
  force_delete         = var.force_delete

  image_scanning_configuration {
    scan_on_push = var.scan_on_push
  }

  encryption_configuration {
    encryption_type = var.kms_key_arn == null ? "AES256" : "KMS"
    kms_key         = var.kms_key_arn
  }

  tags = local.common_tags
}


# ==============================================================
# ECR Lifecycle Policy
# ==============================================================
#
# Rule 1:
# Remove untagged images after the configured retention period.
#
# Rule 2:
# Bound total repository growth by retaining only the newest
# configured number of images.
#
# The "any" rule intentionally has the highest rule priority
# because Amazon ECR requires tagStatus = "any" to be evaluated
# last.
# ==============================================================
resource "aws_ecr_lifecycle_policy" "this" {
  count = var.enable_lifecycle_policy ? 1 : 0

  repository = aws_ecr_repository.this.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1

        description = "Expire untagged images older than ${var.untagged_image_max_age_days} days"

        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = var.untagged_image_max_age_days
        }

        action = {
          type = "expire"
        }
      },
      {
        rulePriority = 2

        description = "Retain only the newest ${var.max_image_count} images"

        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = var.max_image_count
        }

        action = {
          type = "expire"
        }
      },
    ]
  })
}