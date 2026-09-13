locals {
  name = lower(trimspace(var.name))

  common_tags = merge(
    {
      ManagedBy = "Terraform"
      Component = "DatabaseProxy"
    },
    var.tags,
  )
}


# ============================================================
# AWS Account Context
# ============================================================

data "aws_caller_identity" "current" {}


# ============================================================
# RDS Proxy Security Group
#
# Traffic path:
#
# ECS SG
#   |
#   | TCP 5432
#   v
# RDS Proxy SG
#   |
#   | TCP 5432
#   v
# Aurora SG
#
# No CIDR-based database ingress is created.
# ============================================================

resource "aws_security_group" "this" {
  name        = "${local.name}-rds-proxy"
  description = "Security group for PostgreSQL RDS Proxy."
  vpc_id      = var.vpc_id

  revoke_rules_on_delete = true

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name}-rds-proxy"
      Tier = "PrivateDataAccess"
    },
  )
}


# ============================================================
# Application -> RDS Proxy
# ============================================================

resource "aws_vpc_security_group_ingress_rule" "client_to_proxy" {
  for_each = toset(var.client_security_group_ids)

  security_group_id = aws_security_group.this.id

  description = "PostgreSQL traffic from approved application clients"

  ip_protocol = "tcp"
  from_port   = var.port
  to_port     = var.port

  referenced_security_group_id = each.value
}


# The application/ECS security group intentionally has restricted
# outbound access. Add only the PostgreSQL path required to reach
# this RDS Proxy.
resource "aws_vpc_security_group_egress_rule" "client_to_proxy" {
  for_each = toset(var.client_security_group_ids)

  security_group_id = each.value

  description = "PostgreSQL egress to RDS Proxy"

  ip_protocol = "tcp"
  from_port   = var.port
  to_port     = var.port

  referenced_security_group_id = aws_security_group.this.id
}


# ============================================================
# RDS Proxy -> Aurora
# ============================================================

resource "aws_vpc_security_group_egress_rule" "proxy_to_database" {
  security_group_id = aws_security_group.this.id

  description = "PostgreSQL traffic from RDS Proxy to Aurora"

  ip_protocol = "tcp"
  from_port   = var.port
  to_port     = var.port

  referenced_security_group_id = var.target_security_group_id
}


# Aurora accepts PostgreSQL only from the dedicated RDS Proxy SG.
resource "aws_vpc_security_group_ingress_rule" "proxy_to_database" {
  security_group_id = var.target_security_group_id

  description = "PostgreSQL traffic from RDS Proxy"

  ip_protocol = "tcp"
  from_port   = var.port
  to_port     = var.port

  referenced_security_group_id = aws_security_group.this.id
}


# ============================================================
# RDS Proxy IAM Trust Policy
#
# RDS assumes this role so the proxy can read the exact database
# credential secret from AWS Secrets Manager.
# ============================================================

data "aws_iam_policy_document" "assume_role" {
  statement {
    sid    = "AllowRDSProxyAssumeRole"
    effect = "Allow"

    actions = [
      "sts:AssumeRole",
    ]

    principals {
      type = "Service"

      identifiers = [
        "rds.amazonaws.com",
      ]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"

      values = [
        data.aws_caller_identity.current.account_id,
      ]
    }
  }
}


resource "aws_iam_role" "this" {
  name = "${local.name}-rds-proxy"

  assume_role_policy = (
    data.aws_iam_policy_document.assume_role.json
  )

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name}-rds-proxy"
    },
  )
}


# ============================================================
# Secret Access Policy
#
# Least privilege:
#
# - only GetSecretValue
# - only the configured database secret ARN
# - optional kms:Decrypt only for explicitly supplied CMKs
# ============================================================

data "aws_iam_policy_document" "secret_access" {
  statement {
    sid    = "ReadDatabaseSecret"
    effect = "Allow"

    actions = [
      "secretsmanager:GetSecretValue",
    ]

    resources = [
      var.secret_arn,
    ]
  }

  dynamic "statement" {
    for_each = (
      length(var.kms_key_arns) > 0
      ? [1]
      : []
    )

    content {
      sid    = "DecryptDatabaseSecret"
      effect = "Allow"

      actions = [
        "kms:Decrypt",
      ]

      resources = var.kms_key_arns
    }
  }
}


resource "aws_iam_role_policy" "secret_access" {
  name = "${local.name}-database-secret"

  role = aws_iam_role.this.id

  policy = (
    data.aws_iam_policy_document.secret_access.json
  )
}


# ============================================================
# RDS Proxy
#
# Application traffic terminates at the proxy endpoint instead
# of connecting directly to Aurora.
#
# require_tls should remain true for AWS environments.
# ============================================================

resource "aws_db_proxy" "this" {
  name = "${local.name}-postgres"

  engine_family = "POSTGRESQL"

  role_arn = aws_iam_role.this.arn

  vpc_subnet_ids = (
    var.subnet_ids
  )

  vpc_security_group_ids = [
    aws_security_group.this.id,
  ]

  require_tls = (
    var.require_tls
  )

  idle_client_timeout = (
    var.idle_client_timeout
  )

  debug_logging = false

  auth {
    auth_scheme = "SECRETS"

    secret_arn = (
      var.secret_arn
    )

    iam_auth = upper(
      trimspace(var.iam_auth)
    )
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name}-postgres"
    },
  )

  depends_on = [
    aws_iam_role_policy.secret_access,
  ]
}


# ============================================================
# Default Connection Pool
# ============================================================

resource "aws_db_proxy_default_target_group" "this" {
  db_proxy_name = (
    aws_db_proxy.this.name
  )

  connection_pool_config {
    connection_borrow_timeout = (
      var.connection_borrow_timeout
    )

    max_connections_percent = (
      var.max_connections_percent
    )

    max_idle_connections_percent = (
      var.max_idle_connections_percent
    )
  }
}


# ============================================================
# Aurora Cluster Target
# ============================================================

resource "aws_db_proxy_target" "cluster" {
  db_proxy_name = (
    aws_db_proxy.this.name
  )

  target_group_name = (
    aws_db_proxy_default_target_group.this.name
  )

  db_cluster_identifier = (
    var.db_cluster_identifier
  )
}