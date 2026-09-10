locals {
  name = lower(
    trimspace(var.name)
  )

  container_name = lower(
    trimspace(var.container_name)
  )

  cpu_architecture = upper(
    trimspace(var.cpu_architecture)
  )

  log_group_name = (
    "/ecs/${local.name}"
  )

  # ----------------------------------------------------------
  # ECS container environment format
  #
  # Terraform input:
  #
  # {
  #   APP_ENV = "dev"
  #   LOG_LEVEL = "INFO"
  # }
  #
  # ECS format:
  #
  # [
  #   {
  #     name  = "APP_ENV"
  #     value = "dev"
  #   }
  # ]
  # ----------------------------------------------------------
  environment = [
    for key, value in var.environment_variables : {
      name  = key
      value = value
    }
  ]

  # ----------------------------------------------------------
  # ECS secret injection format
  #
  # Terraform input:
  #
  # {
  #   DATABASE_URL = "<secret ARN>"
  # }
  #
  # ECS format:
  #
  # [
  #   {
  #     name      = "DATABASE_URL"
  #     valueFrom = "<secret ARN>"
  #   }
  # ]
  #
  # Plaintext secrets must never be stored in Terraform input
  # as normal environment_variables.
  # ----------------------------------------------------------
  secrets = [
    for key, value_from in var.secrets : {
      name      = key
      valueFrom = value_from
    }
  ]

  common_tags = merge(
    {
      Name      = local.name
      ManagedBy = "Terraform"
      Component = "ContainerRuntime"
    },
    var.tags,
  )
}


# ============================================================
# CloudWatch Log Group
#
# ECS awslogs sends container stdout / stderr here.
#
# RealStock application logs are expected to remain structured
# JSON so CloudWatch Logs Insights can query fields such as:
#
#   service
#   environment
#   correlation_id
#   trace_id
#   event_id
#   severity
#
# Log retention is deliberately bounded instead of retaining
# application logs forever.
# ============================================================

resource "aws_cloudwatch_log_group" "this" {
  name = local.log_group_name

  retention_in_days = (
    var.log_retention_days
  )

  tags = local.common_tags
}


# ============================================================
# ECS Cluster
#
# Container Insights is enabled at cluster level for operational
# telemetry such as task / service CPU and memory metrics.
# ============================================================

resource "aws_ecs_cluster" "this" {
  name = local.name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = local.common_tags
}


# ============================================================
# ECS Task Definition
#
# Runtime contract:
#
#   AWS Fargate
#       |
#       +-- Linux
#       +-- awsvpc
#       +-- explicit CPU / memory
#       +-- explicit execution role
#       +-- explicit application task role
#       +-- CloudWatch Logs
#       +-- environment variables
#       +-- Secrets Manager / SSM injection
#       +-- container liveness
#       +-- graceful SIGTERM shutdown
#
#
# IAM boundary:
#
# execution_role_arn
#     |
#     +-- ECR image pull
#     +-- CloudWatch log delivery
#     +-- ECS secret injection
#
#
# task_role_arn
#     |
#     +-- permissions used by RealStock application code
#     +-- DynamoDB
#     +-- Kinesis
#     +-- EventBridge
#     +-- SQS
#     +-- SNS
#     +-- other explicitly granted AWS APIs
#
#
# Health semantics:
#
# /health
#     |
#     +-- process / container liveness
#     +-- ECS container health check
#
#
# /health/ready
#     |
#     +-- dependency readiness
#     +-- ALB target health
#
#
# A downstream outage must not create a restart storm:
#
# PostgreSQL unavailable
#       |
#       +-- /health       -> 200
#       |
#       +-- /health/ready -> 503
#
# Therefore ECS keeps the process alive while ALB can remove
# the task from traffic.
# ============================================================

resource "aws_ecs_task_definition" "this" {
  family = local.name

  requires_compatibilities = [
    "FARGATE",
  ]

  network_mode = "awsvpc"

  cpu = tostring(
    var.cpu
  )

  memory = tostring(
    var.memory
  )

  execution_role_arn = (
    var.execution_role_arn
  )

  task_role_arn = (
    var.task_role_arn
  )

  runtime_platform {
    operating_system_family = "LINUX"

    cpu_architecture = (
      local.cpu_architecture
    )
  }

  container_definitions = jsonencode(
    [
      {
        # ------------------------------------------------------
        # Main application container
        # ------------------------------------------------------
        name = local.container_name

        image = trimspace(
          var.image_uri
        )

        essential = true

        # ------------------------------------------------------
        # Network
        #
        # For awsvpc/Fargate the host and container port are the
        # same port on the task ENI.
        # ------------------------------------------------------
        portMappings = [
          {
            containerPort = (
              var.container_port
            )

            hostPort = (
              var.container_port
            )

            protocol = "tcp"
          }
        ]

        # ------------------------------------------------------
        # Non-secret environment
        # ------------------------------------------------------
        environment = local.environment

        # ------------------------------------------------------
        # Secrets Manager / SSM values
        # ------------------------------------------------------
        secrets = local.secrets

        # ------------------------------------------------------
        # Graceful shutdown
        #
        # ECS:
        #
        # SIGTERM
        #    |
        #    v
        # Uvicorn graceful shutdown
        #    |
        #    v
        # stopTimeout
        #    |
        #    v
        # SIGKILL only if process has not stopped
        #
        # Day16 Docker image already declares:
        #
        # STOPSIGNAL SIGTERM
        # ------------------------------------------------------
        stopTimeout = (
          var.stop_timeout_seconds
        )

        # ------------------------------------------------------
        # CloudWatch Logs
        # ------------------------------------------------------
        logConfiguration = {
          logDriver = "awslogs"

          options = {
            awslogs-group = (
              aws_cloudwatch_log_group.this.name
            )

            awslogs-region = (
              var.aws_region
            )

            awslogs-stream-prefix = (
              local.container_name
            )
          }
        }

        # ------------------------------------------------------
        # Container liveness
        #
        # IMPORTANT:
        #
        # This deliberately uses /health rather than
        # /health/ready.
        #
        # Dependency failures must not cause ECS task restart
        # loops.
        # ------------------------------------------------------
        healthCheck = {
          command = [
            "CMD-SHELL",
            "python -c \"import urllib.request; urllib.request.urlopen('http://127.0.0.1:${var.container_port}/health', timeout=3).read()\" || exit 1",
          ]

          interval = 30
          timeout  = 5
          retries  = 3

          startPeriod = 10
        }
      },
    ]
  )


  # ==========================================================
  # Fargate CPU / Memory Contract
  #
  # Amazon ECS Fargate accepts only defined CPU/memory pairs.
  #
  # Reject invalid combinations during Terraform evaluation
  # instead of waiting for ECS RegisterTaskDefinition to fail.
  #
  # Supported Linux ranges represented here:
  #
  # CPU 256:
  #   512, 1024, 2048 MiB
  #
  # CPU 512:
  #   1024 - 4096 MiB
  #
  # CPU 1024:
  #   2048 - 8192 MiB, step 1024
  #
  # CPU 2048:
  #   4096 - 16384 MiB, step 1024
  #
  # CPU 4096:
  #   8192 - 30720 MiB, step 1024
  #
  # CPU 8192:
  #   16384 - 61440 MiB, step 4096
  #
  # CPU 16384:
  #   32768 - 122880 MiB, step 8192
  # ==========================================================

  lifecycle {
    precondition {
      condition = (
        (
          var.cpu == 256 &&
          contains(
            [
              512,
              1024,
              2048,
            ],
            var.memory,
          )
        ) ||
        (
          var.cpu == 512 &&
          contains(
            [
              1024,
              2048,
              3072,
              4096,
            ],
            var.memory,
          )
        ) ||
        (
          var.cpu == 1024 &&
          var.memory >= 2048 &&
          var.memory <= 8192 &&
          var.memory % 1024 == 0
        ) ||
        (
          var.cpu == 2048 &&
          var.memory >= 4096 &&
          var.memory <= 16384 &&
          var.memory % 1024 == 0
        ) ||
        (
          var.cpu == 4096 &&
          var.memory >= 8192 &&
          var.memory <= 30720 &&
          var.memory % 1024 == 0
        ) ||
        (
          var.cpu == 8192 &&
          var.memory >= 16384 &&
          var.memory <= 61440 &&
          var.memory % 4096 == 0
        ) ||
        (
          var.cpu == 16384 &&
          var.memory >= 32768 &&
          var.memory <= 122880 &&
          var.memory % 8192 == 0
        )
      )

      error_message = (
        "cpu and memory must form a supported AWS Fargate task size."
      )
    }
  }

  tags = local.common_tags
}


# ============================================================
# ECS Fargate Service
#
# High-availability baseline:
#
# desired_count = 2
#
# Environment layer should provide subnets spanning at least two
# Availability Zones.
#
#
# Rolling deployment strategy:
#
# Desired:
#
#     2 tasks
#
# During deployment:
#
#     minimum healthy = 100%
#     maximum running = 200%
#
# Therefore ECS can conceptually run:
#
# OLD-A     healthy
# OLD-B     healthy
# NEW-A     starting
# NEW-B     starting
#
# before replacing the old revision.
#
#
# Deployment Circuit Breaker:
#
# bad task revision
#       |
#       v
# cannot reach steady state
#       |
#       v
# deployment failure
#       |
#       v
# automatic rollback
#
# This prevents an unhealthy revision from indefinitely replacing
# the last known-good service deployment.
# ============================================================

resource "aws_ecs_service" "this" {
  name = local.name

  cluster = (
    aws_ecs_cluster.this.id
  )

  task_definition = (
    aws_ecs_task_definition.this.arn
  )

  desired_count = (
    var.desired_count
  )

  launch_type = "FARGATE"

  # ----------------------------------------------------------
  # Safe rolling deployment
  # ----------------------------------------------------------
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  # ----------------------------------------------------------
  # ECS Exec
  #
  # Disabled by default.
  #
  # When enabled in a controlled environment it provides an
  # operational break-glass/debug path without SSH.
  # ----------------------------------------------------------
  enable_execute_command = (
    var.enable_execute_command
  )

  enable_ecs_managed_tags = true

  propagate_tags = "SERVICE"

  # ----------------------------------------------------------
  # ALB health grace period
  #
  # Only applies when this service is actually attached to an
  # ALB target group.
  # ----------------------------------------------------------
  health_check_grace_period_seconds = (
    var.target_group_arn != null
    ? var.health_check_grace_period_seconds
    : null
  )

  # ----------------------------------------------------------
  # Deployment safety
  # ----------------------------------------------------------
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  # ----------------------------------------------------------
  # Private task networking
  #
  # Production baseline:
  #
  # assign_public_ip = false
  #
  # Public traffic should terminate at ALB. Application tasks
  # run in private application subnets.
  # ----------------------------------------------------------
  network_configuration {
    subnets = (
      var.subnet_ids
    )

    security_groups = (
      var.security_group_ids
    )

    assign_public_ip = (
      var.assign_public_ip
    )
  }

  # ----------------------------------------------------------
  # Optional Application Load Balancer
  #
  # The reusable ECS module does not own or create the ALB.
  #
  # ALB module
  #      |
  #      v
  # target_group_arn
  #      |
  #      v
  # ECS service attachment
  #
  # When target_group_arn == null, this entire block is omitted.
  # ----------------------------------------------------------
  dynamic "load_balancer" {
    for_each = (
      var.target_group_arn != null
      ? [var.target_group_arn]
      : []
    )

    content {
      target_group_arn = (
        load_balancer.value
      )

      container_name = (
        local.container_name
      )

      container_port = (
        var.container_port
      )
    }
  }

  tags = local.common_tags
}