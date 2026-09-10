output "repository_name" {
  description = "Name of the ECR repository."

  value = (
    aws_ecr_repository.this.name
  )
}


output "repository_arn" {
  description = "ARN of the ECR repository."

  value = (
    aws_ecr_repository.this.arn
  )
}


output "repository_url" {
  description = "Repository URI used for Docker push and ECS images."

  value = (
    aws_ecr_repository.this.repository_url
  )
}


output "registry_id" {
  description = "AWS account registry ID that owns the repository."

  value = (
    aws_ecr_repository.this.registry_id
  )
}


output "image_tag_mutability" {
  description = "Configured image tag mutability mode."

  value = (
    aws_ecr_repository.this.image_tag_mutability
  )
}


output "lifecycle_policy_enabled" {
  description = "Whether lifecycle management is enabled."

  value = (
    var.enable_lifecycle_policy
  )
}