output "api_ecr_repository_name" {
  description = "Name of the API ECR repository."

  value = (
    module.api_ecr.repository_name
  )
}

output "api_ecr_repository_arn" {
  description = "ARN of the API ECR repository."

  value = (
    module.api_ecr.repository_arn
  )
}

output "api_ecr_repository_url" {
  description = "Repository URI used by CI/CD and ECS."

  value = (
    module.api_ecr.repository_url
  )
}

output "api_ecr_registry_id" {
  description = "AWS registry account ID for the API repository."

  value = (
    module.api_ecr.registry_id
  )
}