from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

MODULE_DIR = (
    PROJECT_ROOT
    / "infra"
    / "terraform"
    / "modules"
    / "redis"
)

MAIN_TF = MODULE_DIR / "main.tf"
VARIABLES_TF = MODULE_DIR / "variables.tf"
OUTPUTS_TF = MODULE_DIR / "outputs.tf"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _normalize_hcl(content: str) -> str:
    return " ".join(content.split())


def test_redis_module_files_exist() -> None:
    assert MAIN_TF.is_file()
    assert VARIABLES_TF.is_file()
    assert OUTPUTS_TF.is_file()


def test_redis_uses_elasticache_replication_group() -> None:
    content = _read(MAIN_TF)
    normalized = _normalize_hcl(content)

    assert (
        'resource "aws_elasticache_replication_group" "this"'
        in content
    )

    assert 'engine = "redis"' in normalized


def test_redis_uses_private_subnet_group() -> None:
    content = _read(MAIN_TF)
    normalized = _normalize_hcl(content)

    assert (
        'resource "aws_elasticache_subnet_group" "this"'
        in content
    )

    assert (
        "subnet_ids = var.subnet_ids"
        in normalized
    )


def test_redis_requires_multiple_subnets() -> None:
    content = _read(VARIABLES_TF)
    normalized = _normalize_hcl(content)

    assert (
        "length(var.subnet_ids) >= 2"
        in normalized
    )

    assert "distinct(var.subnet_ids)" in normalized


def test_redis_has_dedicated_security_group() -> None:
    content = _read(MAIN_TF)
    normalized = _normalize_hcl(content)

    assert (
        'resource "aws_security_group" "this"'
        in content
    )

    assert "vpc_id = var.vpc_id" in normalized


def test_ecs_to_redis_is_security_group_referenced() -> None:
    content = _read(MAIN_TF)
    normalized = _normalize_hcl(content)

    assert (
        'resource "aws_vpc_security_group_ingress_rule" '
        '"client_to_redis"'
        in content
    )

    assert (
        "referenced_security_group_id = each.value"
        in normalized
    )

    assert (
        "var.client_security_group_ids"
        in normalized
    )


def test_client_security_group_gets_redis_egress() -> None:
    content = _read(MAIN_TF)
    normalized = _normalize_hcl(content)

    assert (
        'resource "aws_vpc_security_group_egress_rule" '
        '"client_to_redis"'
        in content
    )

    assert (
        "security_group_id = each.value"
        in normalized
    )

    assert (
        "referenced_security_group_id = "
        "aws_security_group.this.id"
        in normalized
    )


def test_redis_has_no_public_cidr_access() -> None:
    content = _read(MAIN_TF)

    assert "0.0.0.0/0" not in content
    assert "::/0" not in content


def test_redis_uses_standard_port() -> None:
    variables = _read(VARIABLES_TF)
    main = _read(MAIN_TF)

    normalized_variables = _normalize_hcl(variables)
    normalized_main = _normalize_hcl(main)

    assert 'variable "port"' in variables

    assert (
        "default = 6379"
        in normalized_variables
    )

    assert (
        "port = var.port"
        in normalized_main
    )


def test_redis_enables_transit_encryption() -> None:
    content = _read(MAIN_TF)
    normalized = _normalize_hcl(content)

    assert (
        "transit_encryption_enabled = true"
        in normalized
    )


def test_redis_enables_at_rest_encryption() -> None:
    content = _read(MAIN_TF)
    normalized = _normalize_hcl(content)

    assert (
        "at_rest_encryption_enabled = true"
        in normalized
    )


def test_redis_enables_automatic_failover() -> None:
    content = _read(MAIN_TF)
    normalized = _normalize_hcl(content)

    assert (
        "automatic_failover_enabled = true"
        in normalized
    )


def test_redis_enables_multi_az() -> None:
    content = _read(MAIN_TF)
    normalized = _normalize_hcl(content)

    assert (
        "multi_az_enabled = true"
        in normalized
    )


def test_redis_defaults_to_two_cache_nodes() -> None:
    variables = _read(VARIABLES_TF)
    main = _read(MAIN_TF)

    normalized_variables = _normalize_hcl(variables)
    normalized_main = _normalize_hcl(main)

    assert (
        'variable "num_cache_clusters"'
        in variables
    )

    assert (
        "default = 2"
        in normalized_variables
    )

    assert (
        "var.num_cache_clusters >= 2"
        in normalized_variables
    )

    assert (
        "num_cache_clusters = "
        "var.num_cache_clusters"
        in normalized_main
    )


def test_redis_configures_snapshot_retention() -> None:
    variables = _read(VARIABLES_TF)
    main = _read(MAIN_TF)

    normalized_variables = _normalize_hcl(variables)
    normalized_main = _normalize_hcl(main)

    assert (
        'variable "snapshot_retention_days"'
        in variables
    )

    assert (
        "default = 7"
        in normalized_variables
    )

    assert (
        "snapshot_retention_limit = "
        "var.snapshot_retention_days"
        in normalized_main
    )


def test_redis_supports_customer_managed_kms() -> None:
    variables = _read(VARIABLES_TF)
    main = _read(MAIN_TF)

    normalized_main = _normalize_hcl(main)

    assert (
        'variable "kms_key_arn"'
        in variables
    )

    assert (
        "kms_key_id = var.kms_key_arn"
        in normalized_main
    )


def test_redis_does_not_store_static_auth_token() -> None:
    content = (
        _read(MAIN_TF)
        + _read(VARIABLES_TF)
    ).lower()

    assert "auth_token" not in content
    assert "redis_password" not in content


def test_redis_exports_runtime_identity() -> None:
    content = _read(OUTPUTS_TF)

    assert 'output "replication_group_id"' in content

    assert (
        'output "replication_group_arn"'
        in content
    )

    assert (
        'output "primary_endpoint_address"'
        in content
    )

    assert (
        'output "reader_endpoint_address"'
        in content
    )

    assert 'output "port"' in content

    assert (
        'output "security_group_id"'
        in content
    )

    assert (
        'output "subnet_group_name"'
        in content
    )