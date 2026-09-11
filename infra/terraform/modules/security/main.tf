locals {
  name = lower(
    trimspace(var.name)
  )

  common_tags = merge(
    {
      ManagedBy = "Terraform"
      Component = "NetworkSecurity"
    },
    var.tags,
  )
}


# ============================================================
# ALB Security Group
#
# Public trust boundary.
#
# Internet
#     |
#     | HTTPS
#     v
#    ALB
#
# The ALB may forward only to the ECS security group on the
# application port.
# ============================================================

resource "aws_security_group" "alb" {
  name = (
    "${local.name}-alb"
  )

  description = (
    "Security group for the public application load balancer."
  )

  vpc_id = (
    var.vpc_id
  )

  revoke_rules_on_delete = true

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name}-alb"
      Tier = "PublicIngress"
    },
  )
}


# ============================================================
# ECS Security Group
#
# Private application trust boundary.
#
# There is intentionally no CIDR-based public ingress rule.
#
# Application traffic can originate only from the ALB security
# group.
# ============================================================

resource "aws_security_group" "ecs" {
  name = (
    "${local.name}-ecs"
  )

  description = (
    "Security group for private ECS application tasks."
  )

  vpc_id = (
    var.vpc_id
  )

  revoke_rules_on_delete = true

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name}-ecs"
      Tier = "PrivateApplication"
    },
  )
}


# ============================================================
# Internet -> ALB HTTPS
# ============================================================

resource "aws_vpc_security_group_ingress_rule" "alb_https" {
  for_each = toset(
    var.alb_ingress_cidrs
  )

  security_group_id = (
    aws_security_group.alb.id
  )

  description = (
    "Public HTTPS ingress"
  )

  ip_protocol = "tcp"

  from_port = (
    var.https_port
  )

  to_port = (
    var.https_port
  )

  cidr_ipv4 = each.value
}


# ============================================================
# Optional Internet -> ALB HTTP
#
# Disabled by default.
#
# When enabled, the ALB layer should use this port only for an
# HTTP -> HTTPS redirect.
# ============================================================

resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  for_each = (
    var.enable_http_ingress
    ? toset(var.alb_ingress_cidrs)
    : toset([])
  )

  security_group_id = (
    aws_security_group.alb.id
  )

  description = (
    "Optional HTTP ingress for HTTPS redirect"
  )

  ip_protocol = "tcp"

  from_port = (
    var.http_port
  )

  to_port = (
    var.http_port
  )

  cidr_ipv4 = each.value
}


# ============================================================
# ALB -> ECS
#
# Security-group reference is deliberately used instead of a
# CIDR rule.
#
# Only workloads carrying the ALB security group may initiate
# application traffic to ECS.
# ============================================================

resource "aws_vpc_security_group_egress_rule" "alb_to_ecs" {
  security_group_id = (
    aws_security_group.alb.id
  )

  description = (
    "Forward application traffic from ALB to ECS"
  )

  ip_protocol = "tcp"

  from_port = (
    var.application_port
  )

  to_port = (
    var.application_port
  )

  referenced_security_group_id = (
    aws_security_group.ecs.id
  )
}


resource "aws_vpc_security_group_ingress_rule" "ecs_from_alb" {
  security_group_id = (
    aws_security_group.ecs.id
  )

  description = (
    "Accept application traffic only from ALB"
  )

  ip_protocol = "tcp"

  from_port = (
    var.application_port
  )

  to_port = (
    var.application_port
  )

  referenced_security_group_id = (
    aws_security_group.alb.id
  )
}


# ============================================================
# ECS HTTPS Egress
#
# Required for examples such as:
#
# - ECR / AWS service endpoints when using NAT
# - Secrets Manager
# - Systems Manager
# - CloudWatch / OTLP endpoints
# - External HTTPS market-data providers
#
# Database and cache traffic are deliberately not granted here.
# Their security boundaries will later use security-group
# references on the exact PostgreSQL / Redis ports.
# ============================================================

resource "aws_vpc_security_group_egress_rule" "ecs_https" {
  for_each = toset(
    var.ecs_https_egress_cidrs
  )

  security_group_id = (
    aws_security_group.ecs.id
  )

  description = (
    "HTTPS egress through private subnet routing"
  )

  ip_protocol = "tcp"

  from_port = 443
  to_port   = 443

  cidr_ipv4 = each.value
}