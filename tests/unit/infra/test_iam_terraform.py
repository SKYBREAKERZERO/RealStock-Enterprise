from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

IAM_MODULE_DIR = (
    PROJECT_ROOT
    / "infra"
    / "terraform"
    / "modules"
    / "iam"
)

MAIN_TF = IAM_MODULE_DIR / "main.tf"
VARIABLES_TF = IAM_MODULE_DIR / "variables.tf"
OUTPUTS_TF = IAM_MODULE_DIR / "outputs.tf"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _strip_hcl_comments(content: str) -> str:
    """Remove line comments before checking security contracts."""
    lines: list[str] = []

    for line in content.splitlines():
        stripped = line.lstrip()

        if stripped.startswith("#"):
            continue

        if stripped.startswith("//"):
            continue

        lines.append(line)

    return "\n".join(lines)


def test_iam_module_files_exist() -> None:
    assert MAIN_TF.is_file()
    assert VARIABLES_TF.is_file()
    assert OUTPUTS_TF.is_file()


def test_iam_creates_separate_execution_and_task_roles() -> None:
    content = _read(MAIN_TF)

    assert 'resource "aws_iam_role" "execution"' in content
    assert 'resource "aws_iam_role" "task"' in content

    assert "local.execution_role_name" in content
    assert "local.task_role_name" in content


def test_iam_roles_trust_ecs_tasks_service() -> None:
    content = _read(MAIN_TF)

    assert (
        'data "aws_iam_policy_document" '
        '"ecs_task_assume_role"'
    ) in content

    assert "ecs-tasks.amazonaws.com" in content
    assert "sts:AssumeRole" in content


def test_iam_task_trust_has_confused_deputy_protection() -> None:
    content = _read(MAIN_TF)

    assert 'data "aws_caller_identity" "current"' in content
    assert 'data "aws_partition" "current"' in content

    assert "aws:SourceAccount" in content
    assert "aws:SourceArn" in content

    assert (
        "data.aws_caller_identity.current.account_id"
        in content
    )

    assert (
        "data.aws_partition.current.partition"
        in content
    )


def test_execution_role_uses_standard_ecs_execution_policy() -> None:
    content = _read(MAIN_TF)

    assert (
        'resource "aws_iam_role_policy_attachment" '
        '"execution_standard"'
    ) in content

    assert "AmazonECSTaskExecutionRolePolicy" in content
    assert "aws_iam_role.execution.name" in content


def test_task_role_has_no_broad_managed_policy_attachment() -> None:
    content = _strip_hcl_comments(
        _read(MAIN_TF)
    )

    assert (
        'resource "aws_iam_role_policy_attachment" "task"'
        not in content
    )

    assert (
        "iam::aws:policy/AdministratorAccess"
        not in content
    )

    assert (
        "iam::aws:policy/PowerUserAccess"
        not in content
    )


def test_iam_separates_secrets_manager_permissions() -> None:
    main = _read(MAIN_TF)
    variables = _read(VARIABLES_TF)

    assert (
        'variable "execution_secretsmanager_secret_arns"'
        in variables
    )

    assert (
        "var.execution_secretsmanager_secret_arns"
        in main
    )

    assert "secretsmanager:GetSecretValue" in main
    assert "ReadSecretsManagerSecrets" in main


def test_iam_separates_ssm_parameter_permissions() -> None:
    main = _read(MAIN_TF)
    variables = _read(VARIABLES_TF)

    assert (
        'variable "execution_ssm_parameter_arns"'
        in variables
    )

    assert (
        "var.execution_ssm_parameter_arns"
        in main
    )

    assert "ssm:GetParameters" in main
    assert "ReadSsmParameters" in main


def test_iam_supports_kms_decrypt_for_container_secrets() -> None:
    main = _read(MAIN_TF)
    variables = _read(VARIABLES_TF)

    assert (
        'variable "execution_kms_key_arns"'
        in variables
    )

    assert "var.execution_kms_key_arns" in main
    assert "kms:Decrypt" in main
    assert "DecryptContainerSecrets" in main


def test_legacy_combined_secret_variable_is_removed() -> None:
    main = _read(MAIN_TF)
    variables = _read(VARIABLES_TF)

    assert "execution_secret_arns" not in main
    assert "execution_secret_arns" not in variables


def test_iam_supports_permissions_boundary() -> None:
    main = _read(MAIN_TF)
    variables = _read(VARIABLES_TF)

    assert (
        'variable "permissions_boundary_arn"'
        in variables
    )

    assert main.count(
        "permissions_boundary"
    ) >= 2


def test_task_role_defaults_to_no_business_permissions() -> None:
    variables = _read(VARIABLES_TF)
    main = _read(MAIN_TF)

    assert 'variable "task_policy_json"' in variables
    assert "default   = null" in variables

    assert (
        "nonsensitive(var.task_policy_json)"
        in main
    )

    assert (
        "local.task_policy_json != null"
        in main
    )

    assert (
        "length(trimspace(local.task_policy_json)) > 0"
        in main
    )

    assert (
        "local.task_policy_enabled"
        in main
    )


def test_task_role_policy_is_explicitly_attached() -> None:
    content = _read(MAIN_TF)

    assert (
        'resource "aws_iam_role_policy" "task"'
        in content
    )

    assert "local.task_policy_enabled" in content
    assert "local.task_policy_json" in content
    assert "aws_iam_role.task.id" in content


def test_iam_module_does_not_define_wildcard_permissions() -> None:
    content = _strip_hcl_comments(
        _read(MAIN_TF)
    )

    wildcard_actions = re.search(
        r'actions\s*=\s*\[\s*"\*"\s*,?\s*\]',
        content,
        flags=re.MULTILINE,
    )

    wildcard_resources = re.search(
        r'resources\s*=\s*\[\s*"\*"\s*,?\s*\]',
        content,
        flags=re.MULTILINE,
    )

    assert wildcard_actions is None
    assert wildcard_resources is None

    assert (
        "iam::aws:policy/AdministratorAccess"
        not in content
    )

    assert (
        "iam::aws:policy/PowerUserAccess"
        not in content
    )


def test_iam_exports_execution_role_identity() -> None:
    content = _read(OUTPUTS_TF)

    assert (
        'output "execution_role_name"'
        in content
    )

    assert (
        'output "execution_role_arn"'
        in content
    )

    assert (
        "aws_iam_role.execution.name"
        in content
    )

    assert (
        "aws_iam_role.execution.arn"
        in content
    )


def test_iam_exports_task_role_identity() -> None:
    content = _read(OUTPUTS_TF)

    assert 'output "task_role_name"' in content
    assert 'output "task_role_arn"' in content

    assert "aws_iam_role.task.name" in content
    assert "aws_iam_role.task.arn" in content