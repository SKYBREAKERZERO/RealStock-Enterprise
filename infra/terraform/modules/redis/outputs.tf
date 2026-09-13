# ============================================================
# ElastiCache Redis Runtime Identity
# ============================================================

output "replication_group_id" {
  description = "ElastiCache Redis replication group ID."

  value = (
    aws_elasticache_replication_group.this.id
  )
}


output "replication_group_arn" {
  description = "ElastiCache Redis replication group ARN."

  value = (
    aws_elasticache_replication_group.this.arn
  )
}


# ============================================================
# Redis Endpoints
# ============================================================

output "primary_endpoint_address" {
  description = "Primary Redis endpoint address used for read/write traffic."

  value = (
    aws_elasticache_replication_group.this.primary_endpoint_address
  )
}


output "reader_endpoint_address" {
  description = "Reader Redis endpoint address used for read-only traffic."

  value = (
    aws_elasticache_replication_group.this.reader_endpoint_address
  )
}


output "port" {
  description = "Redis listener port."

  value = (
    aws_elasticache_replication_group.this.port
  )
}


# ============================================================
# Network Identity
# ============================================================

output "security_group_id" {
  description = "Security group attached to the ElastiCache Redis replication group."

  value = (
    aws_security_group.this.id
  )
}


output "subnet_group_name" {
  description = "ElastiCache subnet group name used by Redis."

  value = (
    aws_elasticache_subnet_group.this.name
  )
}