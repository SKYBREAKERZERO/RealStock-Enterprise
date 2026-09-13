# ============================================================
# ECR
# ============================================================

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


output "api_image_uri" {
  description = "Immutable image URI configured for the API ECS task."

  value = (
    local.api_image_uri
  )
}


# ============================================================
# Network
# ============================================================

output "vpc_id" {
  description = "ID of the dev VPC."

  value = (
    module.network.vpc_id
  )
}


output "public_subnet_ids" {
  description = "Public subnet IDs used by the ALB."

  value = (
    module.network.public_subnet_ids
  )
}


output "private_app_subnet_ids" {
  description = "Private application subnet IDs used by ECS."

  value = (
    module.network.private_app_subnet_ids
  )
}


output "private_data_subnet_ids" {
  description = "Private data subnet IDs used by stateful services."

  value = (
    module.network.private_data_subnet_ids
  )
}


# ============================================================
# Security
# ============================================================

output "alb_security_group_id" {
  description = "Security group attached to the ALB."

  value = (
    module.network_security.alb_security_group_id
  )
}


output "ecs_security_group_id" {
  description = "Security group attached to ECS task ENIs."

  value = (
    module.network_security.ecs_security_group_id
  )
}


# ============================================================
# IAM
# ============================================================

output "api_execution_role_arn" {
  description = "ECS task execution role ARN."

  value = (
    module.api_iam.execution_role_arn
  )
}


output "api_task_role_arn" {
  description = "Application ECS task role ARN."

  value = (
    module.api_iam.task_role_arn
  )
}


# ============================================================
# ALB
# ============================================================

output "api_alb_dns_name" {
  description = "Public DNS name of the API ALB."

  value = (
    module.api_alb.dns_name
  )
}


output "api_alb_zone_id" {
  description = "Route53 zone ID of the API ALB."

  value = (
    module.api_alb.zone_id
  )
}


output "api_target_group_arn" {
  description = "Target group ARN attached to the ECS API service."

  value = (
    module.api_alb.target_group_arn
  )
}


# ============================================================
# ECS
# ============================================================

output "api_ecs_cluster_name" {
  description = "Name of the API ECS cluster."

  value = (
    module.api_ecs.cluster_name
  )
}


output "api_ecs_service_name" {
  description = "Name of the API ECS service."

  value = (
    module.api_ecs.service_name
  )
}


output "api_task_definition_arn" {
  description = "Current API ECS task definition ARN."

  value = (
    module.api_ecs.task_definition_arn
  )
}


output "api_log_group_name" {
  description = "CloudWatch log group used by the API container."

  value = (
    module.api_ecs.log_group_name
  )
}


# ============================================================
# Aurora PostgreSQL
# ============================================================

output "database_cluster_id" {
  description = "Aurora PostgreSQL cluster identifier."

  value = (
    module.database.cluster_id
  )
}


output "database_cluster_arn" {
  description = "Aurora PostgreSQL cluster ARN."

  value = (
    module.database.cluster_arn
  )
}


# Stable environment-level database endpoint contract.
#
# This currently points to the Aurora writer endpoint.
# Application traffic should normally use database_proxy_endpoint.
output "database_endpoint" {
  description = "Aurora PostgreSQL writer endpoint."

  value = (
    module.database.endpoint
  )
}


output "database_writer_endpoint" {
  description = "Aurora PostgreSQL writer endpoint."

  value = (
    module.database.endpoint
  )
}


output "database_reader_endpoint" {
  description = "Aurora PostgreSQL reader endpoint."

  value = (
    module.database.reader_endpoint
  )
}


output "database_security_group_id" {
  description = "Security group attached to Aurora PostgreSQL."

  value = (
    module.database.security_group_id
  )
}


output "database_master_secret_arn" {
  description = "AWS-managed Secrets Manager ARN for Aurora master credentials."

  value = (
    module.database.master_user_secret_arn
  )

  sensitive = true
}


# ============================================================
# RDS Proxy
# ============================================================

output "database_proxy_name" {
  description = "RDS Proxy name."

  value = (
    module.database_proxy.proxy_name
  )
}


output "database_proxy_arn" {
  description = "RDS Proxy ARN."

  value = (
    module.database_proxy.proxy_arn
  )
}


output "database_proxy_endpoint" {
  description = "RDS Proxy endpoint used by application database traffic."

  value = (
    module.database_proxy.endpoint
  )
}


output "database_proxy_security_group_id" {
  description = "Security group attached to RDS Proxy."

  value = (
    module.database_proxy.security_group_id
  )
}


# ============================================================
# ElastiCache Redis
# ============================================================

output "redis_replication_group_id" {
  description = "ElastiCache Redis replication group identifier."

  value = (
    module.redis.replication_group_id
  )
}


output "redis_replication_group_arn" {
  description = "ElastiCache Redis replication group ARN."

  value = (
    module.redis.replication_group_arn
  )
}


output "redis_primary_endpoint" {
  description = "Primary Redis endpoint address used for read/write traffic."

  value = (
    module.redis.primary_endpoint_address
  )
}


output "redis_reader_endpoint" {
  description = "Reader Redis endpoint address used for read-only traffic."

  value = (
    module.redis.reader_endpoint_address
  )
}


output "redis_port" {
  description = "Redis listener port."

  value = (
    module.redis.port
  )
}


output "redis_security_group_id" {
  description = "Security group attached to the ElastiCache Redis replication group."

  value = (
    module.redis.security_group_id
  )
}


output "redis_subnet_group_name" {
  description = "ElastiCache subnet group name used by Redis."

  value = (
    module.redis.subnet_group_name
  )
}


output "redis_url" {
  description = "TLS Redis URL used by the API runtime."

  value = (
    "rediss://${module.redis.primary_endpoint_address}:${module.redis.port}"
  )
}