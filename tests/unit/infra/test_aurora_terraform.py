from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

MODULE_DIR = (
    PROJECT_ROOT
    / "infra"
    / "terraform"
    / "modules"
    / "aurora"
)

MAIN_TF = MODULE_DIR / "main.tf"
VARIABLES_TF = MODULE_DIR / "variables.tf"
OUTPUTS_TF = MODULE_DIR / "outputs.tf"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_aurora_module_files_exist() -> None:
    assert MAIN_TF.is_file()
    assert VARIABLES_TF.is_file()
    assert OUTPUTS_TF.is_file()


def test_aurora_uses_postgresql() -> None:
    assert 'engine         = "aurora-postgresql"' in _read(MAIN_TF)


def test_aurora_uses_private_subnet_group() -> None:
    content = _read(MAIN_TF)

    assert 'resource "aws_db_subnet_group" "this"' in content
    assert "var.subnet_ids" in content


def test_aurora_requires_multiple_subnets() -> None:
    content = _read(VARIABLES_TF)

    assert "length(var.subnet_ids) >= 2" in content
    assert "distinct(var.subnet_ids)" in content


def test_aurora_instances_are_not_public() -> None:
    assert "publicly_accessible = false" in _read(MAIN_TF)


def test_aurora_defaults_to_two_instances() -> None:
    content = _read(VARIABLES_TF)

    assert 'variable "instance_count"' in content
    assert "default     = 2" in content


def test_aurora_enforces_ha_instance_count() -> None:
    assert "var.instance_count >= 2" in _read(VARIABLES_TF)


def test_aurora_storage_is_encrypted() -> None:
    assert "storage_encrypted = true" in _read(MAIN_TF)


def test_aurora_uses_managed_master_password() -> None:
    content = _read(MAIN_TF)

    assert "manage_master_user_password = true" in content
    assert "master_password" not in content


def test_aurora_supports_customer_managed_kms() -> None:
    content = _read(MAIN_TF)

    assert "kms_key_id = var.kms_key_arn" in content


def test_aurora_exports_postgresql_logs() -> None:
    content = _read(MAIN_TF)

    assert "enabled_cloudwatch_logs_exports" in content
    assert '"postgresql"' in content


def test_aurora_has_deletion_protection() -> None:
    variables = _read(VARIABLES_TF)
    main = _read(MAIN_TF)

    assert 'variable "deletion_protection"' in variables
    assert "default     = true" in variables
    assert "deletion_protection = var.deletion_protection" in main


def test_aurora_security_group_uses_postgresql_port() -> None:
    content = _read(MAIN_TF)

    assert "aws_vpc_security_group_ingress_rule" in content
    assert "var.port" in content


def test_aurora_exports_database_identity() -> None:
    content = _read(OUTPUTS_TF)

    assert 'output "cluster_arn"' in content
    assert 'output "endpoint"' in content
    assert 'output "reader_endpoint"' in content


def test_aurora_exports_master_secret() -> None:
    content = _read(OUTPUTS_TF)

    assert 'output "master_user_secret_arn"' in content
    assert "master_user_secret[0].secret_arn" in content


def test_aurora_exports_security_group() -> None:
    assert 'output "security_group_id"' in _read(OUTPUTS_TF)