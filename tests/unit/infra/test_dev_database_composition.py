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


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_dev_wires_aurora_module() -> None:
    content = _read(MAIN_TF)

    assert 'module "database"' in content
    assert 'source = "../../modules/aurora"' in content


def test_dev_wires_rds_proxy_module() -> None:
    content = _read(MAIN_TF)

    assert 'module "database_proxy"' in content
    assert 'source = "../../modules/rds-proxy"' in content


def test_database_uses_private_data_subnets() -> None:
    content = _read(MAIN_TF)

    assert "module.network.private_data_subnet_ids" in content

    database_block = content.split(
        'module "database"',
        maxsplit=1,
    )[1].split(
        'module "database_proxy"',
        maxsplit=1,
    )[0]

    assert (
        "subnet_ids = (\n"
        "    module.network.private_data_subnet_ids"
        in database_block
    )


def test_proxy_uses_private_data_subnets() -> None:
    content = _read(MAIN_TF)

    proxy_block = content.split(
        'module "database_proxy"',
        maxsplit=1,
    )[1]

    assert (
        "subnet_ids = (\n"
        "    module.network.private_data_subnet_ids"
        in proxy_block
    )


def test_proxy_accepts_only_ecs_security_group() -> None:
    content = _read(MAIN_TF)

    proxy_block = content.split(
        'module "database_proxy"',
        maxsplit=1,
    )[1]

    assert "client_security_group_ids" in proxy_block
    assert (
        "module.network_security.ecs_security_group_id"
        in proxy_block
    )


def test_proxy_targets_aurora_security_group() -> None:
    content = _read(MAIN_TF)

    assert (
        "target_security_group_id = (\n"
        "    module.database.security_group_id"
        in content
    )


def test_proxy_registers_dev_aurora_cluster() -> None:
    content = _read(MAIN_TF)

    assert (
        "db_cluster_identifier = (\n"
        "    module.database.cluster_id"
        in content
    )


def test_proxy_uses_aws_managed_database_secret() -> None:
    content = _read(MAIN_TF)

    assert (
        "secret_arn = (\n"
        "    module.database.master_user_secret_arn"
        in content
    )


def test_dev_does_not_put_plaintext_database_password_in_source() -> None:
    main_content = _read(MAIN_TF)
    variables_content = _read(VARIABLES_TF)

    combined_content = (
        main_content
        + variables_content
    ).lower()

    # Terraform must never define a plaintext Aurora master password.
    assert "master_password" not in combined_content

    # No Terraform input variable may accept a database password.
    assert 'variable "database_password"' not in variables_content
    assert 'variable "db_password"' not in variables_content

    # The ECS environment-variable name is allowed, but its value must
    # come from the AWS-managed Aurora Secrets Manager secret.
    assert "DATABASE_PASSWORD" in main_content
    assert (
        '"${module.database.master_user_secret_arn}:password::"'
        in main_content
    )


def test_dev_api_uses_rds_proxy_endpoint() -> None:
    content = _read(MAIN_TF)

    assert "DATABASE_HOST" in content
    assert "module.database_proxy.endpoint" in content
    assert 'DATABASE_PORT = "5432"' in content
    assert "DATABASE_NAME" in content
    assert "var.database_name" in content
    assert 'DATABASE_SSLMODE = "require"' in content


def test_dev_api_injects_aurora_credentials_from_secrets_manager() -> None:
    content = _read(MAIN_TF)

    assert "DATABASE_USERNAME" in content
    assert "DATABASE_PASSWORD" in content

    assert (
        '"${module.database.master_user_secret_arn}:username::"'
        in content
    )

    assert (
        '"${module.database.master_user_secret_arn}:password::"'
        in content
    )


def test_dev_execution_role_can_read_aurora_secret() -> None:
    content = _read(MAIN_TF)

    iam_block = content.split(
        'module "api_iam"',
        maxsplit=1,
    )[1].split(
        'module "api_alb"',
        maxsplit=1,
    )[0]

    assert "execution_secretsmanager_secret_arns" in iam_block
    assert "local.api_secretsmanager_secret_arns" in iam_block
    assert "module.database.master_user_secret_arn" in iam_block


def test_dev_does_not_require_database_url_secret() -> None:
    content = _read(VARIABLES_TF)

    api_secrets_block = content.split(
        'variable "api_secrets"',
        maxsplit=1,
    )[1].split(
        'variable "api_kms_key_arns"',
        maxsplit=1,
    )[0]

    assert "api_secrets must contain DATABASE_URL" not in api_secrets_block
    assert "default   = {}" in api_secrets_block


def test_dev_prevents_database_secret_overrides() -> None:
    content = _read(VARIABLES_TF)

    api_secrets_block = content.split(
        'variable "api_secrets"',
        maxsplit=1,
    )[1].split(
        'variable "api_kms_key_arns"',
        maxsplit=1,
    )[0]

    assert '"DATABASE_URL"' in api_secrets_block
    assert '"DATABASE_USERNAME"' in api_secrets_block
    assert '"DATABASE_PASSWORD"' in api_secrets_block
    assert '"REDIS_URL"' in api_secrets_block


def test_dev_prevents_database_environment_overrides() -> None:
    content = _read(VARIABLES_TF)

    environment_block = content.split(
        'variable "api_environment_variables"',
        maxsplit=1,
    )[1].split(
        'variable "api_secrets"',
        maxsplit=1,
    )[0]

    assert '"DATABASE_HOST"' in environment_block
    assert '"DATABASE_PORT"' in environment_block
    assert '"DATABASE_NAME"' in environment_block
    assert '"DATABASE_SSLMODE"' in environment_block
    assert '"DATABASE_URL"' in environment_block
    assert '"REDIS_URL"' in environment_block


def test_dev_database_preserves_ha_baseline() -> None:
    content = _read(MAIN_TF)

    database_block = content.split(
        'module "database"',
        maxsplit=1,
    )[1].split(
        'module "database_proxy"',
        maxsplit=1,
    )[0]

    assert "instance_count" in database_block
    assert "var.database_instance_count" in database_block


def test_dev_database_variables_exist() -> None:
    content = _read(VARIABLES_TF)

    assert 'variable "database_name"' in content
    assert 'variable "database_master_username"' in content
    assert 'variable "database_instance_class"' in content
    assert 'variable "database_instance_count"' in content
    assert 'variable "database_deletion_protection"' in content
    assert 'variable "database_skip_final_snapshot"' in content


def test_dev_database_defaults_to_two_instances() -> None:
    content = _read(VARIABLES_TF)

    block = content.split(
        'variable "database_instance_count"',
        maxsplit=1,
    )[1]

    assert "default     = 2" in block


def test_dev_exports_database_runtime_identity() -> None:
    content = _read(OUTPUTS_TF)

    assert 'output "database_cluster_id"' in content
    assert 'output "database_endpoint"' in content
    assert 'output "database_security_group_id"' in content
    assert 'output "database_master_secret_arn"' in content
    assert 'output "database_proxy_endpoint"' in content
    assert 'output "database_proxy_security_group_id"' in content


def test_database_master_secret_output_is_sensitive() -> None:
    content = _read(OUTPUTS_TF)

    block = content.split(
        'output "database_master_secret_arn"',
        maxsplit=1,
    )[1].split(
        "}",
        maxsplit=1,
    )[0]

    assert "sensitive = true" in block


def test_dev_database_has_no_public_cidr_wiring() -> None:
    content = _read(MAIN_TF)

    database_section = content.split(
        'module "database"',
        maxsplit=1,
    )[1]

    assert "0.0.0.0/0" not in database_section
    assert "::/0" not in database_section
