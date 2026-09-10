from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

ECR_MODULE_DIR = (
    PROJECT_ROOT
    / "infra"
    / "terraform"
    / "modules"
    / "ecr"
)

MAIN_TF = ECR_MODULE_DIR / "main.tf"
VARIABLES_TF = ECR_MODULE_DIR / "variables.tf"
OUTPUTS_TF = ECR_MODULE_DIR / "outputs.tf"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_ecr_module_files_exist() -> None:
    assert MAIN_TF.is_file()
    assert VARIABLES_TF.is_file()
    assert OUTPUTS_TF.is_file()


def test_ecr_repository_resource_exists() -> None:
    content = _read(MAIN_TF)

    assert 'resource "aws_ecr_repository" "this"' in content


def test_ecr_defaults_to_immutable_tags() -> None:
    content = _read(VARIABLES_TF)

    assert 'variable "image_tag_mutability"' in content
    assert 'default     = "IMMUTABLE"' in content


def test_ecr_repository_uses_configured_tag_mutability() -> None:
    content = _read(MAIN_TF)

    assert "var.image_tag_mutability" in content
    assert "image_tag_mutability" in content


def test_ecr_scanning_defaults_to_enabled() -> None:
    content = _read(VARIABLES_TF)

    assert 'variable "scan_on_push"' in content
    assert "default     = true" in content


def test_ecr_repository_configures_scan_on_push() -> None:
    content = _read(MAIN_TF)

    assert "image_scanning_configuration" in content
    assert "var.scan_on_push" in content


def test_ecr_force_delete_defaults_to_false() -> None:
    content = _read(VARIABLES_TF)

    assert 'variable "force_delete"' in content
    assert "default     = false" in content


def test_ecr_supports_aes256_and_kms_encryption() -> None:
    content = _read(MAIN_TF)

    assert "encryption_configuration" in content
    assert '"AES256"' in content
    assert '"KMS"' in content
    assert "var.kms_key_arn" in content


def test_ecr_lifecycle_policy_defaults_to_enabled() -> None:
    content = _read(VARIABLES_TF)

    assert 'variable "enable_lifecycle_policy"' in content
    assert "default     = true" in content


def test_ecr_lifecycle_policy_bounds_repository_growth() -> None:
    content = _read(MAIN_TF)

    assert 'resource "aws_ecr_lifecycle_policy" "this"' in content
    assert '"untagged"' in content
    assert '"sinceImagePushed"' in content
    assert '"imageCountMoreThan"' in content
    assert "var.untagged_image_max_age_days" in content
    assert "var.max_image_count" in content


def test_ecr_outputs_repository_identity() -> None:
    content = _read(OUTPUTS_TF)

    assert 'output "repository_name"' in content
    assert 'output "repository_arn"' in content
    assert 'output "repository_url"' in content
    assert 'output "registry_id"' in content