locals {
  name = lower(trimspace(var.name))

  common_tags = merge(
    {
      ManagedBy = "Terraform"
      Component = "Cache"
    },
    var.tags,
  )
}


# ============================================================
# Redis Security Group
#
# Traffic:
#
# ECS SG
#   |
#   | TCP 6379
#   v
# Redis SG
#
# No CIDR-based public access is created.
# ============================================================

resource "aws_security_group" "this" {
  name        = "${local.name}-redis"
  description = "Security group for ElastiCache Redis."
  vpc_id      = var.vpc_id

  revoke_rules_on_delete = true

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name}-redis"
      Tier = "PrivateData"
    },
  )
}


# ============================================================
# Client -> Redis
#
# Only explicitly approved client security groups can connect.
# No public CIDR ingress is created.
# ============================================================

resource "aws_vpc_security_group_ingress_rule" "client_to_redis" {
  for_each = toset(var.client_security_group_ids)

  security_group_id = aws_security_group.this.id

  description = "Redis traffic from approved application clients"

  ip_protocol = "tcp"
  from_port   = var.port
  to_port     = var.port

  referenced_security_group_id = each.value
}


# ============================================================
# Client -> Redis Egress
#
# Client security groups receive only the Redis-specific egress
# path required to reach this ElastiCache security group.
# ============================================================

resource "aws_vpc_security_group_egress_rule" "client_to_redis" {
  for_each = toset(var.client_security_group_ids)

  security_group_id = each.value

  description = "Redis egress to ElastiCache"

  ip_protocol = "tcp"
  from_port   = var.port
  to_port     = var.port

  referenced_security_group_id = aws_security_group.this.id
}


# ============================================================
# ElastiCache Subnet Group
#
# Redis is deployed only into private-data subnets.
# ============================================================

resource "aws_elasticache_subnet_group" "this" {
  name = "${local.name}-redis"

  subnet_ids = var.subnet_ids

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name}-redis"
      Tier = "PrivateData"
    },
  )
}


# ============================================================
# Redis Replication Group
#
# HA topology:
#
# Primary
#   |
#   +---- Replica
#
# automatic_failover_enabled = true
# multi_az_enabled           = true
#
# Security:
#
# transit encryption = enabled
# at-rest encryption = enabled
#
# Authentication:
#
# No static Redis password or auth token is stored in
# Terraform source.
# ============================================================

resource "aws_elasticache_replication_group" "this" {
  replication_group_id = "${local.name}-redis"

  description = "Highly available Redis cache for ${local.name}."

  engine         = "redis"
  engine_version = var.engine_version

  node_type = var.node_type

  port = var.port

  parameter_group_name = var.parameter_group_name

  num_cache_clusters = var.num_cache_clusters

  # ----------------------------------------------------------
  # High Availability
  # ----------------------------------------------------------

  automatic_failover_enabled = true
  multi_az_enabled           = true

  # ----------------------------------------------------------
  # Encryption
  # ----------------------------------------------------------

  transit_encryption_enabled = true
  at_rest_encryption_enabled = true

  kms_key_id = var.kms_key_arn

  # ----------------------------------------------------------
  # Network
  # ----------------------------------------------------------

  subnet_group_name = aws_elasticache_subnet_group.this.name

  security_group_ids = [
    aws_security_group.this.id,
  ]

  # ----------------------------------------------------------
  # Backup
  # ----------------------------------------------------------

  snapshot_retention_limit = var.snapshot_retention_days
  snapshot_window          = var.snapshot_window

  # ----------------------------------------------------------
  # Maintenance
  # ----------------------------------------------------------

  maintenance_window = var.maintenance_window

  apply_immediately = var.apply_immediately

  # ----------------------------------------------------------
  # Tags
  # ----------------------------------------------------------

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name}-redis"
      Tier = "PrivateData"
    },
  )
}