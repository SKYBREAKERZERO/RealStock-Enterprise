from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

ECS_MODULE_DIR = (
    PROJECT_ROOT
    / "infra"
    / "terraform"
    / "modules"
    / "ecs"
)

MAIN_TF = ECS_MODULE_DIR / "main.tf"
VARIABLES_TF = ECS_MODULE_DIR / "variables.tf"
OUTPUTS_TF = ECS_MODULE_DIR / "outputs.tf"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_ecs_module_files_exist() -> None:
    assert MAIN_TF.is_file()
    assert VARIABLES_TF.is_file()
    assert OUTPUTS_TF.is_file()


def test_ecs_creates_fargate_cluster_service_and_task() -> None:
    content = _read(MAIN_TF)

    assert 'resource "aws_ecs_cluster" "this"' in content
    assert 'resource "aws_ecs_task_definition" "this"' in content
    assert 'resource "aws_ecs_service" "this"' in content

    assert '"FARGATE"' in content
    assert 'launch_type = "FARGATE"' in content


def test_ecs_uses_awsvpc_networking() -> None:
    content = _read(MAIN_TF)

    assert 'network_mode = "awsvpc"' in content
    assert "network_configuration" in content


def test_ecs_requires_execution_and_task_roles() -> None:
    content = _read(MAIN_TF)
    variables = _read(VARIABLES_TF)

    assert "execution_role_arn" in content
    assert "task_role_arn" in content

    assert 'variable "execution_role_arn"' in variables
    assert 'variable "task_role_arn"' in variables


def test_ecs_defaults_to_two_tasks_for_high_availability() -> None:
    content = _read(VARIABLES_TF)

    assert 'variable "desired_count"' in content
    assert "default     = 2" in content


def test_ecs_requires_at_least_two_subnets() -> None:
    content = _read(VARIABLES_TF)

    assert 'variable "subnet_ids"' in content
    assert "length(var.subnet_ids) >= 2" in content


def test_ecs_does_not_assign_public_ip_by_default() -> None:
    content = _read(VARIABLES_TF)

    assert 'variable "assign_public_ip"' in content
    assert "default     = false" in content


def test_ecs_enables_container_insights() -> None:
    content = _read(MAIN_TF)

    assert 'name  = "containerInsights"' in content
    assert 'value = "enabled"' in content


def test_ecs_sends_container_logs_to_cloudwatch() -> None:
    content = _read(MAIN_TF)

    assert 'resource "aws_cloudwatch_log_group" "this"' in content
    assert 'logDriver = "awslogs"' in content
    assert "awslogs-group" in content
    assert "awslogs-region" in content
    assert "awslogs-stream-prefix" in content


def test_ecs_container_healthcheck_uses_liveness() -> None:
    content = _read(MAIN_TF)

    expected = (
        "urllib.request.urlopen("
        "'http://127.0.0.1:${var.container_port}/health'"
    )

    assert "healthCheck" in content
    assert expected in content


def test_ecs_container_healthcheck_does_not_use_readiness() -> None:
    content = _read(MAIN_TF)

    forbidden = (
        "'http://127.0.0.1:"
        "${var.container_port}/health/ready'"
    )

    assert forbidden not in content


def test_ecs_supports_graceful_shutdown_timeout() -> None:
    main = _read(MAIN_TF)
    variables = _read(VARIABLES_TF)

    assert "stopTimeout" in main
    assert "var.stop_timeout_seconds" in main

    assert 'variable "stop_timeout_seconds"' in variables
    assert "default     = 30" in variables


def test_ecs_uses_safe_rolling_deployment_policy() -> None:
    content = _read(MAIN_TF)

    assert "deployment_minimum_healthy_percent = 100" in content
    assert "deployment_maximum_percent         = 200" in content


def test_ecs_enables_deployment_circuit_breaker_and_rollback() -> None:
    content = _read(MAIN_TF)

    assert "deployment_circuit_breaker" in content
    assert "enable   = true" in content
    assert "rollback = true" in content


def test_ecs_supports_optional_alb_attachment() -> None:
    content = _read(MAIN_TF)
    variables = _read(VARIABLES_TF)

    assert 'variable "target_group_arn"' in variables
    assert "default     = null" in variables

    assert 'dynamic "load_balancer"' in content
    assert "var.target_group_arn != null" in content
    assert "target_group_arn" in content


def test_ecs_exports_runtime_identity() -> None:
    content = _read(OUTPUTS_TF)

    assert 'output "cluster_id"' in content
    assert 'output "cluster_arn"' in content
    assert 'output "cluster_name"' in content
    assert 'output "service_id"' in content
    assert 'output "service_name"' in content
    assert 'output "task_definition_arn"' in content
    assert 'output "log_group_name"' in content
    assert 'output "container_name"' in content
    assert 'output "container_port"' in content

def test_ecs_validates_fargate_cpu_memory_combinations() -> None:
    content = _read(MAIN_TF)

    assert "precondition" in content
    assert "var.cpu == 256" in content
    assert "var.cpu == 512" in content
    assert "var.cpu == 1024" in content
    assert "var.cpu == 2048" in content
    assert "var.cpu == 4096" in content
    assert "var.cpu == 8192" in content
    assert "var.cpu == 16384" in content
    assert "supported AWS Fargate task size" in content