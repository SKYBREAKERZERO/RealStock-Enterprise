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


def _normalize_hcl(content: str) -> str:
    return " ".join(content.split())


def test_dev_wires_redis_module() -> None:
    content = _read(MAIN_TF)

    assert 'module "redis"' in content
    assert 'source = "../../modules/redis"' in _normalize_hcl(content)


def test_redis_uses_private_data_subnets() -> None:
    content = _read(MAIN_TF)

    redis_block = content.split(
        'module "redis"',
        maxsplit=1,
    )[1]

    assert (
        "module.network.private_data_subnet_ids"
        in redis_block
    )


def test_redis_accepts_ecs_security_group() -> None:
    content = _read(MAIN_TF)

    redis_block = content.split(
        'module "redis"',
        maxsplit=1,
    )[1]

    assert (
        "module.network_security.ecs_security_group_id"
        in redis_block
    )

    assert "client_security_group_ids" in redis_block


def test_redis_uses_standard_port() -> None:
    content = _normalize_hcl(_read(MAIN_TF))

    assert "port = 6379" in content


def test_dev_redis_preserves_ha_baseline() -> None:
    content = _read(MAIN_TF)

    redis_block = content.split(
        'module "redis"',
        maxsplit=1,
    )[1]

    assert "var.redis_num_cache_clusters" in redis_block


def test_dev_redis_variables_exist() -> None:
    content = _read(VARIABLES_TF)

    assert 'variable "redis_engine_version"' in content
    assert 'variable "redis_node_type"' in content
    assert 'variable "redis_num_cache_clusters"' in content

    assert (
        'variable "redis_snapshot_retention_days"'
        in content
    )

    assert 'variable "redis_kms_key_arn"' in content
    assert 'variable "redis_apply_immediately"' in content


def test_dev_redis_defaults_to_two_nodes() -> None:
    content = _read(VARIABLES_TF)

    block = content.split(
        'variable "redis_num_cache_clusters"',
        maxsplit=1,
    )[1]

    normalized = _normalize_hcl(block)

    assert "default = 2" in normalized
    assert "var.redis_num_cache_clusters >= 2" in normalized


def test_dev_redis_snapshot_retention_defaults_to_seven_days() -> None:
    content = _read(VARIABLES_TF)

    block = content.split(
        'variable "redis_snapshot_retention_days"',
        maxsplit=1,
    )[1]

    normalized = _normalize_hcl(block)

    assert "default = 7" in normalized


def test_dev_redis_supports_customer_managed_kms() -> None:
    content = _read(MAIN_TF)

    redis_block = content.split(
        'module "redis"',
        maxsplit=1,
    )[1]

    assert "redis_kms_key_arn" in redis_block


def test_dev_redis_has_no_public_cidr_wiring() -> None:
    content = _read(MAIN_TF)

    redis_block = content.split(
        'module "redis"',
        maxsplit=1,
    )[1].split(
        'module "api_iam"',
        maxsplit=1,
    )[0]

    assert "0.0.0.0/0" not in redis_block
    assert "::/0" not in redis_block


def test_dev_exports_redis_runtime_identity() -> None:
    content = _read(OUTPUTS_TF)

    assert 'output "redis_replication_group_id"' in content
    assert 'output "redis_primary_endpoint"' in content
    assert 'output "redis_reader_endpoint"' in content
    assert 'output "redis_port"' in content
    assert 'output "redis_security_group_id"' in content


def test_dev_does_not_store_redis_password() -> None:
    content = (
        _read(MAIN_TF)
        + _read(VARIABLES_TF)
        + _read(OUTPUTS_TF)
    ).lower()

    assert "redis_password" not in content
    assert "auth_token" not in content