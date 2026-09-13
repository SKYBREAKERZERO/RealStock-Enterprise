# ============================================================
# Availability Zones
# ============================================================

data "aws_availability_zones" "available" {
  state = "available"
}


locals {
  project_name = lower(
    trimspace(var.project_name)
  )

  environment = lower(
    trimspace(var.environment)
  )

  api_service_name = lower(
    trimspace(var.api_service_name)
  )


  # ----------------------------------------------------------
  # Naming
  # ----------------------------------------------------------

  environment_name = (
    "${local.project_name}-${local.environment}"
  )

  api_runtime_name = (
    "${local.environment_name}-${local.api_service_name}"
  )

  api_ecr_repository_name = (
    local.api_runtime_name
  )


  # ----------------------------------------------------------
  # Availability Zones
  #
  # Explicit environment override wins.
  #
  # Otherwise select two currently available AZs from the
  # configured AWS region.
  # ----------------------------------------------------------

  availability_zones = (
    length(var.availability_zones) == 2
    ? var.availability_zones
    : slice(
      data.aws_availability_zones.available.names,
      0,
      2,
    )
  )


  # ----------------------------------------------------------
  # CIDR Layout
  #
  # Default VPC:
  #
  # 10.20.0.0/16
  #
  # public:
  #   10.20.0.0/24
  #   10.20.1.0/24
  #
  # private-app:
  #   10.20.16.0/24
  #   10.20.17.0/24
  #
  # private-data:
  #   10.20.32.0/24
  #   10.20.33.0/24
  # ----------------------------------------------------------

  public_subnet_cidrs = [
    for index in range(length(local.availability_zones)) :
    cidrsubnet(
      var.vpc_cidr,
      8,
      index,
    )
  ]

  private_app_subnet_cidrs = [
    for index in range(length(local.availability_zones)) :
    cidrsubnet(
      var.vpc_cidr,
      8,
      index + 16,
    )
  ]

  private_data_subnet_cidrs = [
    for index in range(length(local.availability_zones)) :
    cidrsubnet(
      var.vpc_cidr,
      8,
      index + 32,
    )
  ]


  # ----------------------------------------------------------
  # API Image
  #
  # ECR repository uses IMMUTABLE tags.
  # The root environment supplies an explicit release tag.
  # ----------------------------------------------------------

  api_image_uri = (
    "${module.api_ecr.repository_url}:${trimspace(var.api_image_tag)}"
  )


  # ----------------------------------------------------------
  # ECS Execution-Role Secret Permissions
  #
  # Derive exact execution-role permissions from the same secret
  # ARNs supplied to the ECS task definition.
  # ----------------------------------------------------------

  api_secretsmanager_secret_arns = distinct(
    [
      for arn in values(var.api_secrets) :
      arn
      if can(
        regex(
          "^arn:aws[a-zA-Z-]*:secretsmanager:",
          trimspace(arn),
        )
      )
    ]
  )

  api_ssm_parameter_arns = distinct(
    [
      for arn in values(var.api_secrets) :
      arn
      if can(
        regex(
          "^arn:aws[a-zA-Z-]*:ssm:",
          trimspace(arn),
        )
      )
    ]
  )


  # ----------------------------------------------------------
  # Common Resource Tags
  # ----------------------------------------------------------

  common_tags = {
    Project     = local.project_name
    Environment = local.environment
    ManagedBy   = "Terraform"
  }
}


# ============================================================
# API Container Registry
# ============================================================

module "api_ecr" {
  source = "../../modules/ecr"

  repository_name = (
    local.api_ecr_repository_name
  )

  image_tag_mutability = "IMMUTABLE"
  scan_on_push         = true
  force_delete         = false

  enable_lifecycle_policy     = true
  max_image_count             = 30
  untagged_image_max_age_days = 7

  tags = merge(
    local.common_tags,
    {
      Component = "ContainerRegistry"
      Service   = local.api_service_name
    },
  )
}


# ============================================================
# VPC / Multi-AZ Network
#
# Dev intentionally defaults to one NAT Gateway to control cost.
#
# Staging / production will use per-AZ NAT topology.
# ============================================================

module "network" {
  source = "../../modules/vpc"

  name = (
    local.environment_name
  )

  vpc_cidr = (
    var.vpc_cidr
  )

  availability_zones = (
    local.availability_zones
  )

  public_subnet_cidrs = (
    local.public_subnet_cidrs
  )

  private_app_subnet_cidrs = (
    local.private_app_subnet_cidrs
  )

  private_data_subnet_cidrs = (
    local.private_data_subnet_cidrs
  )

  nat_gateway_mode = (
    var.nat_gateway_mode
  )

  tags = merge(
    local.common_tags,
    {
      Component = "Network"
    },
  )
}


# ============================================================
# Application Network Security
# ============================================================

module "network_security" {
  source = "../../modules/security"

  name = (
    local.api_runtime_name
  )

  vpc_id = (
    module.network.vpc_id
  )

  application_port = 8000
  https_port       = 443

  enable_http_ingress = (
    var.enable_http_redirect
  )

  http_port = 80

  tags = merge(
    local.common_tags,
    {
      Component = "NetworkSecurity"
      Service   = local.api_service_name
    },
  )
}


# ============================================================
# ECS Runtime Identity
#
# Execution Role:
#   ECS agent -> ECR / Logs / Secrets / KMS
#
# Task Role:
#   application boto3 calls
#
# No fabricated business-resource permissions are introduced.
# ============================================================

module "api_iam" {
  source = "../../modules/iam"

  name = (
    local.api_runtime_name
  )

  execution_secretsmanager_secret_arns = (
    local.api_secretsmanager_secret_arns
  )

  execution_ssm_parameter_arns = (
    local.api_ssm_parameter_arns
  )

  execution_kms_key_arns = (
    var.api_kms_key_arns
  )

  task_policy_json = (
    var.api_task_policy_json
  )

  tags = merge(
    local.common_tags,
    {
      Component = "ContainerIdentity"
      Service   = local.api_service_name
    },
  )
}


# ============================================================
# Public Application Load Balancer
#
# TLS terminates here.
#
# Internet
#     |
# HTTPS :443
#     |
#     v
# ALB
#     |
# HTTP :8000
#     |
#     v
# ECS
# ============================================================

module "api_alb" {
  source = "../../modules/alb"

  name = (
    local.api_runtime_name
  )

  vpc_id = (
    module.network.vpc_id
  )

  public_subnet_ids = (
    module.network.public_subnet_ids
  )

  security_group_ids = [
    module.network_security.alb_security_group_id,
  ]

  certificate_arn = (
    var.api_certificate_arn
  )

  application_port = 8000

  enable_http_redirect = (
    var.enable_http_redirect
  )

  enable_deletion_protection = (
    var.enable_alb_deletion_protection
  )

  health_check_path = "/health/ready"

  tags = merge(
    local.common_tags,
    {
      Component = "ApplicationLoadBalancer"
      Service   = local.api_service_name
    },
  )
}


# ============================================================
# ECS Fargate API Runtime
#
# Dependency wiring:
#
# ECR --------------------> image_uri
# IAM --------------------> execution/task roles
# VPC --------------------> private app subnets
# Security ---------------> ECS security group
# ALB --------------------> target group
# ============================================================

module "api_ecs" {
  source = "../../modules/ecs"

  name = (
    local.api_runtime_name
  )

  aws_region = (
    var.aws_region
  )

  image_uri = (
    local.api_image_uri
  )

  execution_role_arn = (
    module.api_iam.execution_role_arn
  )

  task_role_arn = (
    module.api_iam.task_role_arn
  )

  subnet_ids = (
    module.network.private_app_subnet_ids
  )

  security_group_ids = [
    module.network_security.ecs_security_group_id,
  ]

  target_group_arn = (
    module.api_alb.target_group_arn
  )

  container_name = (
    local.api_service_name
  )

  container_port = 8000

  desired_count = (
    var.api_desired_count
  )

  cpu = (
    var.api_cpu
  )

  memory = (
    var.api_memory
  )

  assign_public_ip = false

  enable_execute_command = (
    var.enable_ecs_exec
  )

  health_check_grace_period_seconds = 60
  stop_timeout_seconds              = 30
  log_retention_days                = 30

  environment_variables = merge(
    {
      APP_ENV    = local.environment
      APP_NAME   = local.api_runtime_name
      AWS_REGION = var.aws_region
    },
    var.api_environment_variables,
  )

  secrets = (
    var.api_secrets
  )

  tags = merge(
    local.common_tags,
    {
      Component = "ApplicationRuntime"
      Service   = local.api_service_name
    },
  )
}