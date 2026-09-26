from __future__ import annotations

import pytest

from scripts.aws.run_api_migration import (
    DEFAULT_MIGRATION_COMMAND,
    MigrationError,
    _build_migration_task_definition_request,
    _select_application_container,
    _terraform_output_value,
    _validate_image_tag,
    _validate_runtime_contract,
)


def _source_task_definition() -> dict[str, object]:
    return {
        "family": "realstock-dev-api",
        "taskRoleArn": "arn:aws:iam::123456789012:role/task",
        "executionRoleArn": "arn:aws:iam::123456789012:role/execution",
        "networkMode": "awsvpc",
        "requiresCompatibilities": [
            "FARGATE",
        ],
        "cpu": "512",
        "memory": "1024",
        "runtimePlatform": {
            "operatingSystemFamily": "LINUX",
            "cpuArchitecture": "X86_64",
        },
        "containerDefinitions": [
            {
                "name": "api",
                "image": "example.invalid/old:image",
                "essential": True,
                "portMappings": [
                    {
                        "containerPort": 8000,
                        "hostPort": 8000,
                        "protocol": "tcp",
                    },
                ],
                "environment": [
                    {
                        "name": "DATABASE_HOST",
                        "value": "proxy.example.internal",
                    },
                    {
                        "name": "DATABASE_PORT",
                        "value": "5432",
                    },
                    {
                        "name": "DATABASE_NAME",
                        "value": "realstock",
                    },
                    {
                        "name": "DATABASE_SSLMODE",
                        "value": "require",
                    },
                ],
                "secrets": [
                    {
                        "name": "DATABASE_USERNAME",
                        "valueFrom": (
                            "arn:aws:secretsmanager:ap-northeast-1:"
                            "123456789012:secret:database:username::"
                        ),
                    },
                    {
                        "name": "DATABASE_PASSWORD",
                        "valueFrom": (
                            "arn:aws:secretsmanager:ap-northeast-1:"
                            "123456789012:secret:database:password::"
                        ),
                    },
                ],
                "healthCheck": {
                    "command": [
                        "CMD-SHELL",
                        "curl -f http://localhost:8000/health || exit 1",
                    ],
                },
            },
        ],
    }


def test_validate_image_tag_accepts_immutable_tag() -> None:
    assert _validate_image_tag("2937c74") == "2937c74"


def test_validate_image_tag_rejects_latest() -> None:
    with pytest.raises(MigrationError):
        _validate_image_tag("latest")


def test_terraform_output_value_requires_output() -> None:
    outputs = {
        "api_ecs_cluster_name": {
            "value": "realstock-dev-api",
        },
    }

    assert (
        _terraform_output_value(
            outputs,
            "api_ecs_cluster_name",
        )
        == "realstock-dev-api"
    )

    with pytest.raises(MigrationError):
        _terraform_output_value(
            outputs,
            "missing",
        )


def test_select_application_container_uses_single_essential_container() -> None:
    task_definition = _source_task_definition()

    container = _select_application_container(
        task_definition,
        None,
    )

    assert container["name"] == "api"


def test_runtime_contract_accepts_rds_proxy_and_secret_keys() -> None:
    task_definition = _source_task_definition()

    container = _select_application_container(
        task_definition,
        None,
    )

    _validate_runtime_contract(
        container=container,
        expected_proxy_endpoint="proxy.example.internal",
    )


def test_runtime_contract_rejects_wrong_database_endpoint() -> None:
    task_definition = _source_task_definition()

    container = _select_application_container(
        task_definition,
        None,
    )

    with pytest.raises(MigrationError):
        _validate_runtime_contract(
            container=container,
            expected_proxy_endpoint="different-proxy.example.internal",
        )


def test_migration_task_definition_uses_candidate_image_and_alembic() -> None:
    task_definition = _source_task_definition()

    container = _select_application_container(
        task_definition,
        None,
    )

    request = _build_migration_task_definition_request(
        source_task_definition=task_definition,
        application_container=container,
        image_uri=(
            "123456789012.dkr.ecr.ap-northeast-1.amazonaws.com/"
            "realstock-dev-api@sha256:abc123"
        ),
        command=DEFAULT_MIGRATION_COMMAND,
    )

    assert request["family"] == "realstock-dev-api-migration"
    assert request["networkMode"] == "awsvpc"
    assert request["requiresCompatibilities"] == ["FARGATE"]

    migration_container = request["containerDefinitions"][0]

    assert migration_container["name"] == "api"
    assert migration_container["command"] == DEFAULT_MIGRATION_COMMAND
    assert migration_container["image"].endswith("@sha256:abc123")

    assert "healthCheck" not in migration_container
    assert "portMappings" not in migration_container

    assert migration_container["secrets"]
    assert migration_container["environment"]
