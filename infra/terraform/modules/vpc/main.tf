locals {
  name = lower(
    trimspace(var.name)
  )

  nat_gateway_mode = lower(
    trimspace(var.nat_gateway_mode)
  )

  subnet_map = {
    for index, az in var.availability_zones :
    tostring(index) => {
      index             = index
      availability_zone = az
      public_cidr       = var.public_subnet_cidrs[index]
      private_app_cidr  = var.private_app_subnet_cidrs[index]
      private_data_cidr = var.private_data_subnet_cidrs[index]
    }
  }

  nat_gateway_keys = (
    local.nat_gateway_mode == "none"
    ? toset([])
    : local.nat_gateway_mode == "single"
    ? toset(["0"])
    : toset(keys(local.subnet_map))
  )

  private_app_nat_gateway_keys = (
    local.nat_gateway_mode == "none"
    ? tomap({})
    : tomap(
      {
        for key, subnet in local.subnet_map :
        key => (
          local.nat_gateway_mode == "single"
          ? "0"
          : key
        )
      }
    )
  )

  common_tags = merge(
    {
      Project   = local.name
      ManagedBy = "Terraform"
      Component = "Network"
    },
    var.tags,
  )
}


# ============================================================
# VPC
# ============================================================

resource "aws_vpc" "this" {
  cidr_block = var.vpc_cidr

  enable_dns_support = (
    var.enable_dns_support
  )

  enable_dns_hostnames = (
    var.enable_dns_hostnames
  )

  instance_tenancy = "default"

  tags = merge(
    local.common_tags,
    {
      Name = local.name
    },
  )

  lifecycle {
    precondition {
      condition = (
        length(var.public_subnet_cidrs) ==
        length(var.availability_zones) &&
        length(var.private_app_subnet_cidrs) ==
        length(var.availability_zones) &&
        length(var.private_data_subnet_cidrs) ==
        length(var.availability_zones)
      )

      error_message = (
        "Each subnet CIDR list must contain exactly one CIDR per Availability Zone."
      )
    }

    precondition {
      condition = (
        length(
          distinct(
            concat(
              var.public_subnet_cidrs,
              var.private_app_subnet_cidrs,
              var.private_data_subnet_cidrs,
            )
          )
        ) ==
        (
          length(var.public_subnet_cidrs) +
          length(var.private_app_subnet_cidrs) +
          length(var.private_data_subnet_cidrs)
        )
      )

      error_message = (
        "Subnet CIDR blocks must not contain exact duplicates."
      )
    }
  }
}


# ============================================================
# Internet Gateway
#
# Only the public subnet route table receives an internet route.
# ============================================================

resource "aws_internet_gateway" "this" {
  vpc_id = (
    aws_vpc.this.id
  )

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name}-igw"
    },
  )
}


# ============================================================
# Public Subnets
#
# Used by internet-facing infrastructure such as ALB and NAT
# Gateways.
#
# Instances/tasks do not automatically receive public IPs.
# ============================================================

resource "aws_subnet" "public" {
  for_each = local.subnet_map

  vpc_id = (
    aws_vpc.this.id
  )

  availability_zone = (
    each.value.availability_zone
  )

  cidr_block = (
    each.value.public_cidr
  )

  map_public_ip_on_launch = false

  tags = merge(
    local.common_tags,
    {
      Name = (
        "${local.name}-public-${each.value.availability_zone}"
      )

      Tier = "Public"
    },
  )
}


# ============================================================
# Private Application Subnets
#
# ECS/Fargate application workloads belong here.
#
# These subnets may use NAT for controlled outbound internet
# access, but never receive public IP addresses by default.
# ============================================================

resource "aws_subnet" "private_app" {
  for_each = local.subnet_map

  vpc_id = (
    aws_vpc.this.id
  )

  availability_zone = (
    each.value.availability_zone
  )

  cidr_block = (
    each.value.private_app_cidr
  )

  map_public_ip_on_launch = false

  tags = merge(
    local.common_tags,
    {
      Name = (
        "${local.name}-private-app-${each.value.availability_zone}"
      )

      Tier = "PrivateApp"
    },
  )
}


# ============================================================
# Private Data Subnets
#
# Intended for Aurora, Redis and other data-plane resources.
#
# Deliberately isolated:
#
# - No Internet Gateway route
# - No NAT Gateway default route
#
# Only VPC-local routing exists unless an explicit private
# connectivity mechanism is added later.
# ============================================================

resource "aws_subnet" "private_data" {
  for_each = local.subnet_map

  vpc_id = (
    aws_vpc.this.id
  )

  availability_zone = (
    each.value.availability_zone
  )

  cidr_block = (
    each.value.private_data_cidr
  )

  map_public_ip_on_launch = false

  tags = merge(
    local.common_tags,
    {
      Name = (
        "${local.name}-private-data-${each.value.availability_zone}"
      )

      Tier = "PrivateData"
    },
  )
}


# ============================================================
# Public Routing
# ============================================================

resource "aws_route_table" "public" {
  vpc_id = (
    aws_vpc.this.id
  )

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name}-public"
      Tier = "Public"
    },
  )
}


resource "aws_route" "public_internet" {
  route_table_id = (
    aws_route_table.public.id
  )

  destination_cidr_block = "0.0.0.0/0"

  gateway_id = (
    aws_internet_gateway.this.id
  )
}


resource "aws_route_table_association" "public" {
  for_each = local.subnet_map

  subnet_id = (
    aws_subnet.public[each.key].id
  )

  route_table_id = (
    aws_route_table.public.id
  )
}


# ============================================================
# NAT Gateway
#
# per_az:
#
#   private-app-A -> NAT-A
#   private-app-B -> NAT-B
#
# This removes a single NAT/AZ failure dependency.
#
# single:
#
#   all private-app subnets -> NAT in first public subnet
#
# none:
#
#   no NAT resources
# ============================================================

resource "aws_eip" "nat" {
  for_each = local.nat_gateway_keys

  domain = "vpc"

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name}-nat-eip-${each.key}"
    },
  )
}


resource "aws_nat_gateway" "this" {
  for_each = local.nat_gateway_keys

  allocation_id = (
    aws_eip.nat[each.key].id
  )

  subnet_id = (
    aws_subnet.public[each.key].id
  )

  connectivity_type = "public"

  depends_on = [
    aws_internet_gateway.this,
  ]

  tags = merge(
    local.common_tags,
    {
      Name = "${local.name}-nat-${each.key}"
    },
  )
}


# ============================================================
# Private Application Routing
# ============================================================

resource "aws_route_table" "private_app" {
  for_each = local.subnet_map

  vpc_id = (
    aws_vpc.this.id
  )

  tags = merge(
    local.common_tags,
    {
      Name = (
        "${local.name}-private-app-${each.value.availability_zone}"
      )

      Tier = "PrivateApp"
    },
  )
}


resource "aws_route" "private_app_default" {
  for_each = local.private_app_nat_gateway_keys

  route_table_id = (
    aws_route_table.private_app[each.key].id
  )

  destination_cidr_block = "0.0.0.0/0"

  nat_gateway_id = (
    aws_nat_gateway.this[each.value].id
  )
}


resource "aws_route_table_association" "private_app" {
  for_each = local.subnet_map

  subnet_id = (
    aws_subnet.private_app[each.key].id
  )

  route_table_id = (
    aws_route_table.private_app[each.key].id
  )
}


# ============================================================
# Private Data Routing
#
# No 0.0.0.0/0 route is intentionally created.
# ============================================================

resource "aws_route_table" "private_data" {
  for_each = local.subnet_map

  vpc_id = (
    aws_vpc.this.id
  )

  tags = merge(
    local.common_tags,
    {
      Name = (
        "${local.name}-private-data-${each.value.availability_zone}"
      )

      Tier = "PrivateData"
    },
  )
}


resource "aws_route_table_association" "private_data" {
  for_each = local.subnet_map

  subnet_id = (
    aws_subnet.private_data[each.key].id
  )

  route_table_id = (
    aws_route_table.private_data[each.key].id
  )
}