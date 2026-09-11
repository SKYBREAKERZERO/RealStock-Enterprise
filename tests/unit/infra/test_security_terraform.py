from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]

SECURITY_MODULE_DIR = (
    PROJECT_ROOT
    / "infra"
    / "terraform"
    / "modules"
    / "security"
)

MAIN_TF = SECURITY_MODULE_DIR / "main.tf"
VARIABLES_TF = SECURITY_MODULE_DIR / "variables.tf"
OUTPUTS_TF = SECURITY_MODULE_DIR / "outputs.tf"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_security_module_files_exist() -> None:
    assert MAIN_TF.is_file()
    assert VARIABLES_TF.is_file()
    assert OUTPUTS_TF.is_file()


def test_security_module_creates_alb_and_ecs_groups() -> None:
    content = _read(MAIN_TF)

    assert 'resource "aws_security_group" "alb"' in content
    assert 'resource "aws_security_group" "ecs"' in content


def test_alb_https_defaults_to_443() -> None:
    content = _read(VARIABLES_TF)

    assert 'variable "https_port"' in content
    assert "default     = 443" in content


def test_application_port_defaults_to_8000() -> None:
    content = _read(VARIABLES_TF)

    assert 'variable "application_port"' in content
    assert "default     = 8000" in content


def test_alb_accepts_https_ingress() -> None:
    content = _read(MAIN_TF)

    assert (
        'resource "aws_vpc_security_group_ingress_rule" '
        '"alb_https"'
        in content
    )
    assert "var.https_port" in content
    assert "var.alb_ingress_cidrs" in content


def test_http_ingress_is_disabled_by_default() -> None:
    content = _read(VARIABLES_TF)

    assert 'variable "enable_http_ingress"' in content
    assert "default     = false" in content


def test_alb_egress_targets_ecs_security_group() -> None:
    content = _read(MAIN_TF)

    assert (
        'resource "aws_vpc_security_group_egress_rule" '
        '"alb_to_ecs"'
        in content
    )
    assert (
        "referenced_security_group_id = (\n"
        "    aws_security_group.ecs.id"
        in content
    )


def test_ecs_ingress_accepts_only_alb_security_group() -> None:
    content = _read(MAIN_TF)

    assert (
        'resource "aws_vpc_security_group_ingress_rule" '
        '"ecs_from_alb"'
        in content
    )
    assert (
        "referenced_security_group_id = (\n"
        "    aws_security_group.alb.id"
        in content
    )


def test_security_module_has_no_ssh_ingress() -> None:
    content = _read(MAIN_TF)

    assert "from_port = 22" not in content
    assert "to_port   = 22" not in content


def test_security_module_has_no_rdp_ingress() -> None:
    content = _read(MAIN_TF)

    assert "from_port = 3389" not in content
    assert "to_port   = 3389" not in content


def test_ecs_https_egress_is_explicit() -> None:
    content = _read(MAIN_TF)

    assert (
        'resource "aws_vpc_security_group_egress_rule" '
        '"ecs_https"'
        in content
    )
    assert "from_port = 443" in content
    assert "to_port   = 443" in content


def test_security_groups_use_standalone_rule_resources() -> None:
    content = _read(MAIN_TF)

    assert "aws_vpc_security_group_ingress_rule" in content
    assert "aws_vpc_security_group_egress_rule" in content


def test_security_module_exports_alb_identity() -> None:
    content = _read(OUTPUTS_TF)

    assert 'output "alb_security_group_id"' in content
    assert 'output "alb_security_group_arn"' in content


def test_security_module_exports_ecs_identity() -> None:
    content = _read(OUTPUTS_TF)

    assert 'output "ecs_security_group_id"' in content
    assert 'output "ecs_security_group_arn"' in content