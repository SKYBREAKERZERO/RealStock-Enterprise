locals {
  name = lower(
    trimspace(var.name)
  )

  # AWS ALB and target-group names have length restrictions.
  alb_name = substr(
    "${local.name}-alb",
    0,
    32,
  )

  target_group_name = substr(
    "${local.name}-api",
    0,
    32,
  )

  access_logs_enabled = (
    var.access_logs_bucket != null &&
    length(trimspace(var.access_logs_bucket)) > 0
  )

  common_tags = merge(
    {
      ManagedBy = "Terraform"
      Component = "ApplicationLoadBalancer"
    },
    var.tags,
  )
}


# ============================================================
# Application Load Balancer
#
# Internet-facing entry point.
#
# Network contract:
#
# Internet
#      |
#      v
# Public subnets across multiple AZs
#      |
#      v
# Application Load Balancer
#
# The ALB security group is supplied by the separate security
# module.
# ============================================================

resource "aws_lb" "this" {
  name = (
    local.alb_name
  )

  internal = false

  load_balancer_type = "application"

  security_groups = (
    var.security_group_ids
  )

  subnets = (
    var.public_subnet_ids
  )

  enable_deletion_protection = (
    var.enable_deletion_protection
  )

  # Reject malformed HTTP headers at the edge instead of
  # forwarding them into the application tier.
  drop_invalid_header_fields = true

  enable_http2 = true

  idle_timeout = (
    var.idle_timeout_seconds
  )

  # ----------------------------------------------------------
  # Optional ALB access logs
  #
  # Bucket creation and bucket policy deliberately remain
  # outside this module.
  # ----------------------------------------------------------

  dynamic "access_logs" {
    for_each = (
      local.access_logs_enabled
      ? [1]
      : []
    )

    content {
      bucket = (
        trimspace(var.access_logs_bucket)
      )

      prefix = (
        trimspace(var.access_logs_prefix)
      )

      enabled = true
    }
  }

  tags = merge(
    local.common_tags,
    {
      Name = local.alb_name
      Tier = "PublicIngress"
    },
  )
}


# ============================================================
# ECS Fargate Target Group
#
# Fargate + awsvpc gives each task its own ENI/IP.
#
# Therefore:
#
# target_type = "ip"
#
# not:
#
# target_type = "instance"
# ============================================================

resource "aws_lb_target_group" "api" {
  name = (
    local.target_group_name
  )

  port = (
    var.application_port
  )

  protocol = "HTTP"

  protocol_version = "HTTP1"

  target_type = "ip"

  vpc_id = (
    var.vpc_id
  )

  deregistration_delay = (
    var.deregistration_delay_seconds
  )

  # ----------------------------------------------------------
  # Readiness health check
  #
  # IMPORTANT:
  #
  # ECS container health:
  #     /health
  #
  # ALB traffic readiness:
  #     /health/ready
  #
  # PostgreSQL/Redis/AWS dependency outage may therefore remove
  # a task from incoming traffic without forcing the ECS process
  # into a restart loop.
  # ----------------------------------------------------------

  health_check {
    enabled = true

    protocol = "HTTP"

    port = "traffic-port"

    path = (
      var.health_check_path
    )

    matcher = "200"

    interval = (
      var.health_check_interval_seconds
    )

    timeout = (
      var.health_check_timeout_seconds
    )

    healthy_threshold = (
      var.healthy_threshold
    )

    unhealthy_threshold = (
      var.unhealthy_threshold
    )
  }

  tags = merge(
    local.common_tags,
    {
      Name = local.target_group_name
      Tier = "PrivateApplication"
    },
  )
}


# ============================================================
# HTTPS Listener
#
# TLS terminates at the ALB.
#
# ACM certificate lifecycle remains outside this module.
# ============================================================

resource "aws_lb_listener" "https" {
  load_balancer_arn = (
    aws_lb.this.arn
  )

  port = (
    var.https_port
  )

  protocol = "HTTPS"

  ssl_policy = (
    var.ssl_policy
  )

  certificate_arn = (
    trimspace(var.certificate_arn)
  )

  default_action {
    type = "forward"

    target_group_arn = (
      aws_lb_target_group.api.arn
    )
  }
}


# ============================================================
# Optional HTTP -> HTTPS Redirect
#
# Disabled by default.
#
# If enabled by the environment layer, the ALB security group
# must also explicitly allow the configured HTTP listener port.
# ============================================================

resource "aws_lb_listener" "http" {
  count = (
    var.enable_http_redirect
    ? 1
    : 0
  )

  load_balancer_arn = (
    aws_lb.this.arn
  )

  port = (
    var.http_port
  )

  protocol = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port = tostring(
        var.https_port
      )

      protocol = "HTTPS"

      status_code = "HTTP_301"
    }
  }
}