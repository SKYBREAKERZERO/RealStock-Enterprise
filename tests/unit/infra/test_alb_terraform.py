from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]

ALB_MODULE_DIR = (
    PROJECT_ROOT
    / "infra"
    / "terraform"
    / "modules"
    / "alb"
)

MAIN_TF = ALB_MODULE_DIR / "main.tf"
VARIABLES_TF = ALB_MODULE_DIR / "variables.tf"
OUTPUTS_TF = ALB_MODULE_DIR / "outputs.tf"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_alb_module_files_exist() -> None:
    assert MAIN_TF.is_file()
    assert VARIABLES_TF.is_file()
    assert OUTPUTS_TF.is_file()


def test_alb_is_internet_facing_application_load_balancer() -> None:
    content = _read(MAIN_TF)

    assert 'resource "aws_lb" "this"' in content
    assert "internal = false" in content
    assert 'load_balancer_type = "application"' in content


def test_alb_requires_multiple_public_subnets() -> None:
    content = _read(VARIABLES_TF)

    assert 'variable "public_subnet_ids"' in content
    assert "length(var.public_subnet_ids) >= 2" in content
    assert "distinct(var.public_subnet_ids)" in content


def test_alb_uses_explicit_security_groups() -> None:
    main = _read(MAIN_TF)
    variables = _read(VARIABLES_TF)

    assert 'variable "security_group_ids"' in variables
    assert "security_groups = (" in main
    assert "var.security_group_ids" in main


def test_alb_drops_invalid_http_headers() -> None:
    content = _read(MAIN_TF)

    assert "drop_invalid_header_fields = true" in content


def test_alb_deletion_protection_defaults_to_enabled() -> None:
    content = _read(VARIABLES_TF)

    assert 'variable "enable_deletion_protection"' in content
    assert "default     = true" in content


def test_target_group_is_ip_based_for_fargate() -> None:
    content = _read(MAIN_TF)

    assert 'resource "aws_lb_target_group" "api"' in content
    assert 'target_type = "ip"' in content


def test_target_group_defaults_to_application_port_8000() -> None:
    content = _read(VARIABLES_TF)

    assert 'variable "application_port"' in content
    assert "default     = 8000" in content


def test_target_group_healthcheck_uses_readiness_endpoint() -> None:
    content = _read(VARIABLES_TF)

    assert 'variable "health_check_path"' in content
    assert 'default     = "/health/ready"' in content
    assert 'default     = "/health"' not in content


def test_target_group_healthcheck_requires_http_200() -> None:
    content = _read(MAIN_TF)

    assert 'matcher = "200"' in content


def test_target_group_supports_graceful_deregistration() -> None:
    main = _read(MAIN_TF)
    variables = _read(VARIABLES_TF)

    assert 'variable "deregistration_delay_seconds"' in variables
    assert "deregistration_delay" in main


def test_https_listener_requires_acm_certificate() -> None:
    main = _read(MAIN_TF)
    variables = _read(VARIABLES_TF)

    assert 'variable "certificate_arn"' in variables
    assert 'resource "aws_lb_listener" "https"' in main
    assert 'protocol = "HTTPS"' in main
    assert "certificate_arn" in main


def test_https_listener_uses_tls_security_policy() -> None:
    main = _read(MAIN_TF)
    variables = _read(VARIABLES_TF)

    assert 'variable "ssl_policy"' in variables
    assert "ELBSecurityPolicy-TLS13-1-2-2021-06" in variables
    assert "ssl_policy" in main


def test_https_listener_forwards_to_api_target_group() -> None:
    content = _read(MAIN_TF)

    assert 'type = "forward"' in content
    assert "aws_lb_target_group.api.arn" in content


def test_http_redirect_is_optional_and_disabled_by_default() -> None:
    main = _read(MAIN_TF)
    variables = _read(VARIABLES_TF)

    assert 'variable "enable_http_redirect"' in variables
    assert "default     = false" in variables
    assert 'resource "aws_lb_listener" "http"' in main
    assert 'type = "redirect"' in main
    assert 'status_code = "HTTP_301"' in main


def test_alb_supports_optional_access_logs() -> None:
    main = _read(MAIN_TF)
    variables = _read(VARIABLES_TF)

    assert 'variable "access_logs_bucket"' in variables
    assert 'dynamic "access_logs"' in main
    assert "enabled = true" in main


def test_alb_exports_load_balancer_identity() -> None:
    content = _read(OUTPUTS_TF)

    assert 'output "load_balancer_arn"' in content
    assert 'output "load_balancer_name"' in content
    assert 'output "dns_name"' in content
    assert 'output "zone_id"' in content


def test_alb_exports_target_group_and_listener_identity() -> None:
    content = _read(OUTPUTS_TF)

    assert 'output "target_group_arn"' in content
    assert 'output "target_group_name"' in content
    assert 'output "https_listener_arn"' in content
    assert 'output "http_listener_arn"' in content