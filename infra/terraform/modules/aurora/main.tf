locals {
  name = lower(trimspace(var.name))

  common_tags = merge(
    {
      ManagedBy = "Terraform"
      Component = "Database"
    },
    var.tags,
  )
}


# ============================================================
# Aurora Security Group
# ============================================================

resource "aws_security_group" "this" {
  name        = "${local.name}-aurora"
  description = "Security group for Aurora PostgreSQL."
  vpc_id      = var.vpc_id

  revoke_rules_on_delete = true

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name}-aurora"
      Tier = "PrivateData"
    },
  )
}


resource "aws_vpc_security_group_ingress_rule" "postgresql" {
  for_each = toset(var.allowed_security_group_ids)

  security_group_id = aws_security_group.this.id

  description = "PostgreSQL traffic from approved security groups"

  ip_protocol = "tcp"
  from_port   = var.port
  to_port     = var.port

  referenced_security_group_id = each.value
}


# ============================================================
# DB Subnet Group
# ============================================================

resource "aws_db_subnet_group" "this" {
  name = "${local.name}-aurora"

  subnet_ids = var.subnet_ids

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name}-aurora"
    },
  )
}


# ============================================================
# Aurora PostgreSQL Cluster
#
# AWS manages the master password in Secrets Manager.
# No database password is stored in Terraform source.
# ============================================================

resource "aws_rds_cluster" "this" {
  cluster_identifier = "${local.name}-aurora"

  engine         = "aurora-postgresql"
  engine_version = var.engine_version

  database_name   = var.database_name
  master_username = var.master_username

  manage_master_user_password = true

  port = var.port

  db_subnet_group_name = aws_db_subnet_group.this.name

  vpc_security_group_ids = [
    aws_security_group.this.id,
  ]

  storage_encrypted = true

  kms_key_id = var.kms_key_arn

  backup_retention_period = var.backup_retention_days
  preferred_backup_window = var.preferred_backup_window

  preferred_maintenance_window = var.preferred_maintenance_window

  deletion_protection = var.deletion_protection
  skip_final_snapshot = var.skip_final_snapshot

  copy_tags_to_snapshot = true

  enabled_cloudwatch_logs_exports = [
    "postgresql",
  ]

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name}-aurora"
    },
  )
}


# ============================================================
# Aurora Instances
#
# At least two instances are required by this module contract.
# ============================================================

resource "aws_rds_cluster_instance" "this" {
  count = var.instance_count

  identifier = (
    "${local.name}-aurora-${count.index + 1}"
  )

  cluster_identifier = aws_rds_cluster.this.id

  instance_class = var.instance_class

  engine         = aws_rds_cluster.this.engine
  engine_version = aws_rds_cluster.this.engine_version

  publicly_accessible = false

  db_subnet_group_name = aws_db_subnet_group.this.name

  performance_insights_enabled = (
    var.performance_insights_enabled
  )

  monitoring_interval = (
    var.monitoring_interval
  )

  auto_minor_version_upgrade = true

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name}-aurora-${count.index + 1}"
    },
  )
}