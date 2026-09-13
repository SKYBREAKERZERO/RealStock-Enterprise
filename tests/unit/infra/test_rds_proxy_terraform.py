from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

MODULE_DIR = (
    PROJECT_ROOT
    / "infra"
    / "terraform"
    / "modules"
    / "rds-proxy"
)

MAIN_TF = MODULE_DIR / "main.tf"
VARIABLES_TF = MODULE_DIR / "variables.tf"
OUTPUTS_TF = MODULE_DIR / "outputs.tf"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_rds_proxy_module_files_exist() -> None:
    assert MAIN_TF.is_file()
    assert VARIABLES_TF.is_file()
    assert OUTPUTS_TF.is_file()


def test_proxy_uses_postgresql_engine_family() -> None:
    content = _read(MAIN_TF)

    assert 'engine_family = "POSTGRESQL"' in content


def test_proxy_requires_tls_by_default() -> None:
    variables = _read(VARIABLES_TF)
    main = _read(MAIN_TF)

    assert 'variable "require_tls"' in variables
    assert "default     = true" in variables

    assert "require_tls" in main
    assert "var.require_tls" in main


def test_proxy_requires_multiple_subnets() -> None:
    content = _read(VARIABLES_TF)

    assert "length(var.subnet_ids) >= 2" in content
    assert "distinct(var.subnet_ids)" in content


def test_proxy_uses_secrets_manager_authentication() -> None:
    content = _read(MAIN_TF)

    assert 'auth_scheme = "SECRETS"' in content
    assert "secret_arn" in content
    assert "var.secret_arn" in content


def test_proxy_has_dedicated_iam_role() -> None:
    content = _read(MAIN_TF)

    assert 'resource "aws_iam_role" "this"' in content
    assert '"rds.amazonaws.com"' in content
    assert '"sts:AssumeRole"' in content


def test_proxy_role_is_account_scoped() -> None:
    content = _read(MAIN_TF)

    assert 'data "aws_caller_identity" "current"' in content
    assert 'variable = "aws:SourceAccount"' in content
    assert "data.aws_caller_identity.current.account_id" in content


def test_proxy_role_reads_only_database_secret() -> None:
    content = _read(MAIN_TF)

    assert '"secretsmanager:GetSecretValue"' in content
    assert "var.secret_arn" in content

    assert '"secretsmanager:*"' not in content
    assert 'resources = ["*"]' not in content


def test_proxy_supports_kms_decrypt() -> None:
    content = _read(MAIN_TF)

    assert '"kms:Decrypt"' in content
    assert "var.kms_key_arns" in content


def test_ecs_to_proxy_is_security_group_referenced() -> None:
    content = _read(MAIN_TF)

    assert (
        'resource "aws_vpc_security_group_ingress_rule" '
        '"client_to_proxy"'
        in content
    )

    assert (
        "referenced_security_group_id = each.value"
        in content
    )

    assert "var.client_security_group_ids" in content


def test_client_security_group_gets_postgres_egress() -> None:
    content = _read(MAIN_TF)

    assert (
        'resource "aws_vpc_security_group_egress_rule" '
        '"client_to_proxy"'
        in content
    )

    assert "security_group_id = each.value" in content

    assert (
        "referenced_security_group_id = "
        "aws_security_group.this.id"
        in content
    )


def test_proxy_egress_targets_database_security_group() -> None:
    content = _read(MAIN_TF)

    assert (
        'resource "aws_vpc_security_group_egress_rule" '
        '"proxy_to_database"'
        in content
    )

    assert (
        "referenced_security_group_id = "
        "var.target_security_group_id"
        in content
    )


def test_database_accepts_postgres_only_from_proxy_security_group() -> None:
    content = _read(MAIN_TF)

    assert (
        'resource "aws_vpc_security_group_ingress_rule" '
        '"proxy_to_database"'
        in content
    )

    assert (
        "security_group_id = var.target_security_group_id"
        in content
    )

    assert (
        "referenced_security_group_id = "
        "aws_security_group.this.id"
        in content
    )


def test_proxy_registers_aurora_cluster() -> None:
    content = _read(MAIN_TF)

    assert (
        'resource "aws_db_proxy_target" "cluster"'
        in content
    )

    assert "db_cluster_identifier" in content
    assert "var.db_cluster_identifier" in content


def test_proxy_configures_connection_pool() -> None:
    content = _read(MAIN_TF)

    assert "connection_pool_config" in content

    assert "connection_borrow_timeout" in content
    assert "var.connection_borrow_timeout" in content

    assert "max_connections_percent" in content
    assert "var.max_connections_percent" in content

    assert "max_idle_connections_percent" in content
    assert "var.max_idle_connections_percent" in content


def test_proxy_debug_logging_is_disabled() -> None:
    content = _read(MAIN_TF)

    assert "debug_logging = false" in content


def test_proxy_exports_runtime_identity() -> None:
    content = _read(OUTPUTS_TF)

    assert 'output "proxy_name"' in content
    assert 'output "proxy_arn"' in content
    assert 'output "endpoint"' in content
    assert 'output "security_group_id"' in content
    assert 'output "iam_role_arn"' in content

    assert "aws_db_proxy.this.endpoint" in content
    assert "aws_security_group.this.id" in content
    assert "aws_iam_role.this.arn" in content