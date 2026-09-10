locals {
  project_name = lower(
    trimspace(var.project_name)
  )

  environment = lower(
    trimspace(var.environment)
  )

  api_service_name = lower(
    trimspace(var.api_service_name)
  )

  api_ecr_repository_name = (
    "${local.project_name}-${local.environment}-${local.api_service_name}"
  )

  common_tags = {
    Project     = local.project_name
    Environment = local.environment
    ManagedBy   = "Terraform"
  }
}


# ============================================================
# API Container Registry
#
# Security policy for RealStock dev:
#
# - Immutable image tags
# - Scan on push
# - No destructive repository deletion
# - Lifecycle cleanup enabled
#
# Expected repository:
#
#   realstock-dev-api
#
# Deployment chain:
#
#   Git commit
#       |
#       v
#   Docker image
#       |
#       v
#   ECR repository
#       |
#       v
#   ECS Task Definition
# ============================================================

module "api_ecr" {
  source = "../../modules/ecr"

  repository_name = (
    local.api_ecr_repository_name
  )

  image_tag_mutability = "IMMUTABLE"
  scan_on_push         = true
  force_delete         = false

  enable_lifecycle_policy     = true
  max_image_count             = 30
  untagged_image_max_age_days = 7

  tags = merge(
    local.common_tags,
    {
      Component = "ContainerRegistry"
      Service   = local.api_service_name
    }
  )
}