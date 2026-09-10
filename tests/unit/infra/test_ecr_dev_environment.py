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


def test_dev_ecr_environment_files_exist() -> None:
    assert MAIN_TF.is_file()
    assert VARIABLES_TF.is_file()
    assert OUTPUTS_TF.is_file()


def test_dev_wires_api_ecr_module() -> None:
    content = _read(MAIN_TF)

    assert 'module "api_ecr"' in content
    assert 'source = "../../modules/ecr"' in content


def test_dev_ecr_repository_name_is_environment_scoped() -> None:
    content = _read(MAIN_TF)

    assert "local.project_name" in content
    assert "local.environment" in content
    assert "local.api_service_name" in content
    assert "api_ecr_repository_name" in content


def test_dev_enforces_immutable_ecr_tags() -> None:
    content = _read(MAIN_TF)

    assert 'image_tag_mutability = "IMMUTABLE"' in content


def test_dev_enforces_scan_on_push() -> None:
    content = _read(MAIN_TF)

    assert "scan_on_push" in content
    assert "= true" in content


def test_dev_prevents_destructive_repository_delete() -> None:
    content = _read(MAIN_TF)

    assert "force_delete" in content
    assert "= false" in content


def test_dev_enables_ecr_lifecycle_management() -> None:
    content = _read(MAIN_TF)

    assert "enable_lifecycle_policy" in content
    assert "max_image_count" in content
    assert "untagged_image_max_age_days" in content


def test_dev_environment_is_locked_to_dev() -> None:
    content = _read(VARIABLES_TF)

    assert 'variable "environment"' in content
    assert 'default     = "dev"' in content
    assert '== "dev"' in content


def test_dev_ecr_has_standard_tags() -> None:
    content = _read(MAIN_TF)

    assert "Project" in content
    assert "Environment" in content
    assert "ManagedBy" in content
    assert "Component" in content
    assert "Service" in content


def test_dev_exposes_ecr_repository_url() -> None:
    content = _read(OUTPUTS_TF)

    assert 'output "api_ecr_repository_url"' in content
    assert "module.api_ecr.repository_url" in content


def test_dev_exposes_ecr_repository_identity() -> None:
    content = _read(OUTPUTS_TF)

    assert 'output "api_ecr_repository_name"' in content
    assert 'output "api_ecr_repository_arn"' in content
    assert 'output "api_ecr_registry_id"' in content