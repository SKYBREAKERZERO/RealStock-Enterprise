from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

VPC_MODULE_DIR = (
    PROJECT_ROOT
    / "infra"
    / "terraform"
    / "modules"
    / "vpc"
)

MAIN_TF = VPC_MODULE_DIR / "main.tf"
VARIABLES_TF = VPC_MODULE_DIR / "variables.tf"
OUTPUTS_TF = VPC_MODULE_DIR / "outputs.tf"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_vpc_module_files_exist() -> None:
    assert MAIN_TF.is_file()
    assert VARIABLES_TF.is_file()
    assert OUTPUTS_TF.is_file()


def test_vpc_resource_exists() -> None:
    content = _read(MAIN_TF)

    assert 'resource "aws_vpc" "this"' in content


def test_vpc_defaults_to_realstock_network_range() -> None:
    content = _read(VARIABLES_TF)

    assert 'default     = "10.20.0.0/16"' in content


def test_vpc_dns_defaults_to_enabled() -> None:
    content = _read(VARIABLES_TF)

    assert 'variable "enable_dns_support"' in content
    assert 'variable "enable_dns_hostnames"' in content
    assert content.count("default     = true") >= 2


def test_vpc_requires_multi_az_topology() -> None:
    content = _read(VARIABLES_TF)

    assert 'variable "availability_zones"' in content
    assert "length(var.availability_zones) >= 2" in content
    assert "distinct(var.availability_zones)" in content


def test_vpc_creates_three_network_tiers() -> None:
    content = _read(MAIN_TF)

    assert 'resource "aws_subnet" "public"' in content
    assert 'resource "aws_subnet" "private_app"' in content
    assert 'resource "aws_subnet" "private_data"' in content


def test_vpc_subnets_do_not_auto_assign_public_ips() -> None:
    content = _read(MAIN_TF)

    assert "map_public_ip_on_launch = true" not in content
    assert content.count("map_public_ip_on_launch = false") == 3


def test_vpc_creates_internet_gateway() -> None:
    content = _read(MAIN_TF)

    assert 'resource "aws_internet_gateway" "this"' in content


def test_public_subnets_route_to_internet_gateway() -> None:
    content = _read(MAIN_TF)

    assert 'resource "aws_route" "public_internet"' in content
    assert 'destination_cidr_block = "0.0.0.0/0"' in content
    assert "aws_internet_gateway.this.id" in content


def test_nat_gateway_mode_supports_ha_and_cost_modes() -> None:
    content = _read(VARIABLES_TF)

    assert 'variable "nat_gateway_mode"' in content
    assert '"per_az"' in content
    assert '"single"' in content
    assert '"none"' in content


def test_nat_gateway_defaults_to_per_az() -> None:
    content = _read(VARIABLES_TF)

    assert 'default = "per_az"' in content


def test_vpc_creates_nat_eips_and_gateways() -> None:
    content = _read(MAIN_TF)

    assert 'resource "aws_eip" "nat"' in content
    assert 'resource "aws_nat_gateway" "this"' in content
    assert 'domain = "vpc"' in content


def test_private_app_subnets_route_through_nat() -> None:
    content = _read(MAIN_TF)

    assert 'resource "aws_route" "private_app_default"' in content
    assert "nat_gateway_id" in content


def test_private_data_subnets_have_no_default_internet_route() -> None:
    content = _read(MAIN_TF)

    assert 'resource "aws_route_table" "private_data"' in content
    assert 'resource "aws_route" "private_data_default"' not in content


def test_vpc_associates_all_three_subnet_tiers() -> None:
    content = _read(MAIN_TF)

    assert (
        'resource "aws_route_table_association" "public"'
        in content
    )
    assert (
        'resource "aws_route_table_association" "private_app"'
        in content
    )
    assert (
        'resource "aws_route_table_association" "private_data"'
        in content
    )


def test_vpc_enforces_one_subnet_per_tier_per_az() -> None:
    content = _read(MAIN_TF)

    assert "length(var.public_subnet_cidrs)" in content
    assert "length(var.private_app_subnet_cidrs)" in content
    assert "length(var.private_data_subnet_cidrs)" in content
    assert "length(var.availability_zones)" in content


def test_vpc_exports_network_identity_and_subnets() -> None:
    content = _read(OUTPUTS_TF)

    assert 'output "vpc_id"' in content
    assert 'output "vpc_arn"' in content
    assert 'output "public_subnet_ids"' in content
    assert 'output "private_app_subnet_ids"' in content
    assert 'output "private_data_subnet_ids"' in content


def test_vpc_exports_nat_identity() -> None:
    content = _read(OUTPUTS_TF)

    assert 'output "nat_gateway_ids"' in content
    assert 'output "nat_gateway_public_ips"' in content