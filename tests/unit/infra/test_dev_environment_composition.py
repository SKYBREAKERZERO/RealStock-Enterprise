from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

DEV_DIR = (
    PROJECT_ROOT
    / "infra"
    / "terraform"
    / "environments"
    / "dev"
)

MAIN_TF = DEV_DIR / "main.tf"
VARIABLES_TF = DEV_DIR / "variables.tf"
OUTPUTS_TF = DEV_DIR / "outputs.tf"
PROVIDERS_TF = DEV_DIR / "providers.tf"
VERSIONS_TF = DEV_DIR / "versions.tf"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_dev_environment_files_exist() -> None:
    assert MAIN_TF.is_file()
    assert VARIABLES_TF.is_file()
    assert OUTPUTS_TF.is_file()
    assert PROVIDERS_TF.is_file()
    assert VERSIONS_TF.is_file()


def test_dev_configures_aws_provider_without_static_credentials() -> None:
    content = _read(PROVIDERS_TF)

    assert 'provider "aws"' in content
    assert "var.aws_region" in content

    assert "access_key" not in content
    assert "secret_key" not in content


def test_dev_declares_terraform_and_aws_provider_versions() -> None:
    content = _read(VERSIONS_TF)

    assert "required_version" in content
    assert "hashicorp/aws" in content
    assert "required_providers" in content


def test_dev_wires_all_runtime_modules() -> None:
    content = _read(MAIN_TF)

    expected_modules = {
        "api_ecr": "../../modules/ecr",
        "network": "../../modules/vpc",
        "network_security": "../../modules/security",
        "api_iam": "../../modules/iam",
        "api_alb": "../../modules/alb",
        "api_ecs": "../../modules/ecs",
    }

    for module_name, source in expected_modules.items():
        assert f'module "{module_name}"' in content
        assert f'source = "{source}"' in content


def test_dev_uses_two_availability_zones() -> None:
    content = _read(MAIN_TF)
    variables = _read(VARIABLES_TF)

    assert 'data "aws_availability_zones" "available"' in content
    assert 'variable "availability_zones"' in variables
    assert "slice(" in content
    assert "0," in content
    assert "2," in content


def test_dev_builds_three_subnet_tiers() -> None:
    content = _read(MAIN_TF)

    assert "public_subnet_cidrs" in content
    assert "private_app_subnet_cidrs" in content
    assert "private_data_subnet_cidrs" in content
    assert "cidrsubnet(" in content


def test_dev_defaults_to_cost_optimized_single_nat() -> None:
    content = _read(VARIABLES_TF)

    assert 'variable "nat_gateway_mode"' in content
    assert 'default     = "single"' in content


def test_dev_wires_alb_to_public_subnets() -> None:
    content = _read(MAIN_TF)

    assert "module.network.public_subnet_ids" in content
    assert "module.network_security.alb_security_group_id" in content


def test_dev_wires_ecs_to_private_application_subnets() -> None:
    content = _read(MAIN_TF)

    assert "module.network.private_app_subnet_ids" in content
    assert "module.network_security.ecs_security_group_id" in content
    assert "assign_public_ip = false" in content


def test_dev_wires_ecs_to_alb_target_group() -> None:
    content = _read(MAIN_TF)

    assert "module.api_alb.target_group_arn" in content
    assert "target_group_arn" in content


def test_dev_wires_separate_ecs_execution_and_task_roles() -> None:
    content = _read(MAIN_TF)

    assert "module.api_iam.execution_role_arn" in content
    assert "module.api_iam.task_role_arn" in content


def test_dev_builds_image_uri_from_ecr_and_immutable_tag() -> None:
    main = _read(MAIN_TF)
    variables = _read(VARIABLES_TF)

    assert "module.api_ecr.repository_url" in main
    assert "var.api_image_tag" in main
    assert '"latest"' in variables
    assert "!= \"latest\"" in variables


def test_dev_preserves_https_and_readiness_contract() -> None:
    content = _read(MAIN_TF)

    assert 'health_check_path = "/health/ready"' in content
    assert "certificate_arn" in content


def test_http_redirect_and_security_ingress_share_one_switch() -> None:
    content = _read(MAIN_TF)

    assert content.count("var.enable_http_redirect") >= 2
    assert "enable_http_ingress" in content
    assert "enable_http_redirect" in content


def test_dev_passes_secret_arns_to_execution_role() -> None:
    content = _read(MAIN_TF)

    assert "api_secretsmanager_secret_arns" in content
    assert "api_ssm_parameter_arns" in content
    assert "execution_secretsmanager_secret_arns" in content
    assert "execution_ssm_parameter_arns" in content


def test_dev_requires_database_and_redis_secret_references() -> None:
    content = _read(VARIABLES_TF)

    assert '"DATABASE_URL"' in content
    assert '"REDIS_URL"' in content
    assert "Secrets Manager" in content
    assert "SSM Parameter Store" in content


def test_dev_does_not_configure_localstack_endpoint() -> None:
    content = _read(MAIN_TF) + _read(PROVIDERS_TF)

    assert "AWS_ENDPOINT_URL" not in content
    assert "localhost:4566" not in content


def test_dev_does_not_grant_fake_business_permissions() -> None:
    content = _read(MAIN_TF)

    assert "task_policy_json = (" in content
    assert "var.api_task_policy_json" in content

    assert '"dynamodb:*"' not in content
    assert '"kinesis:*"' not in content
    assert '"s3:*"' not in content


def test_dev_exports_primary_runtime_identity() -> None:
    content = _read(OUTPUTS_TF)

    assert 'output "vpc_id"' in content
    assert 'output "api_alb_dns_name"' in content
    assert 'output "api_ecs_cluster_name"' in content
    assert 'output "api_ecs_service_name"' in content
    assert 'output "api_task_definition_arn"' in content