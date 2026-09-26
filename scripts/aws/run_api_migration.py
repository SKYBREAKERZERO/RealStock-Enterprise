from __future__ import annotations

import argparse
import copy
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TERRAFORM_DIR = PROJECT_ROOT / "infra" / "terraform" / "environments" / "dev"

DEFAULT_MIGRATION_COMMAND = [
    "python",
    "-m",
    "alembic",
    "-c",
    "database/alembic.ini",
    "upgrade",
    "head",
]

IMAGE_TAG_PATTERN = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]{0,127}$")

REGISTER_TASK_DEFINITION_FIELDS = (
    "taskRoleArn",
    "executionRoleArn",
    "networkMode",
    "volumes",
    "placementConstraints",
    "requiresCompatibilities",
    "cpu",
    "memory",
    "pidMode",
    "ipcMode",
    "proxyConfiguration",
    "inferenceAccelerators",
    "ephemeralStorage",
    "runtimePlatform",
    "enableFaultInjection",
)


class MigrationError(RuntimeError):
    """Raised when the AWS migration gate cannot safely continue."""


def _run(command: list[str], *, cwd: Path) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip()
        raise MigrationError(
            f"Command failed ({result.returncode}): {' '.join(command)}\n{details}"
        )
    return result.stdout


def _load_terraform_outputs(terraform_dir: Path) -> dict[str, Any]:
    raw = _run(["terraform", "output", "-json"], cwd=terraform_dir)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MigrationError("terraform output -json returned invalid JSON.") from exc
    if not isinstance(parsed, dict):
        raise MigrationError("terraform output -json did not return an object.")
    return parsed


def _terraform_output_value(outputs: dict[str, Any], name: str) -> Any:
    item = outputs.get(name)
    if not isinstance(item, dict) or "value" not in item:
        raise MigrationError(f"Required Terraform output is missing: {name}")
    return item["value"]


def _validate_image_tag(image_tag: str) -> str:
    normalized = image_tag.strip()
    if not normalized:
        raise MigrationError("image tag must not be empty.")
    if normalized.lower() == "latest":
        raise MigrationError('The mutable "latest" tag is not allowed.')
    if IMAGE_TAG_PATTERN.fullmatch(normalized) is None:
        raise MigrationError(f"Invalid ECR image tag: {normalized}")
    return normalized


def _create_boto3_session(
    *,
    profile: str | None,
    region: str | None,
) -> tuple[boto3.Session, str]:
    session = boto3.Session(profile_name=profile, region_name=region)
    resolved_region = region or session.region_name
    if not resolved_region:
        raise MigrationError(
            "AWS region is not configured. Use --region, AWS_REGION, "
            "AWS_DEFAULT_REGION, or an AWS profile with a default region."
        )
    return session, resolved_region


def _resolve_candidate_image(
    *,
    ecr_client: Any,
    repository_name: str,
    repository_url: str,
    image_tag: str,
) -> tuple[str, str]:
    try:
        response = ecr_client.describe_images(
            repositoryName=repository_name,
            imageIds=[{"imageTag": image_tag}],
        )
    except ClientError as exc:
        raise MigrationError(
            f"ECR image tag does not exist or cannot be read: {image_tag}"
        ) from exc

    details = response.get("imageDetails", [])
    if len(details) != 1:
        raise MigrationError(f"Expected exactly one ECR image for tag {image_tag}.")

    digest = details[0].get("imageDigest")
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        raise MigrationError(f"ECR did not return a valid digest for tag {image_tag}.")

    return f"{repository_url}@{digest}", digest


def _select_application_container(
    task_definition: dict[str, Any],
    container_name: str | None,
) -> dict[str, Any]:
    containers = task_definition.get("containerDefinitions", [])
    if not isinstance(containers, list) or not containers:
        raise MigrationError("Source ECS task definition has no containers.")

    if container_name is not None:
        for container in containers:
            if container.get("name") == container_name:
                return container
        raise MigrationError(
            f"Container not found in source task definition: {container_name}"
        )

    essential = [
        container
        for container in containers
        if container.get("essential", True)
    ]
    if len(essential) != 1:
        raise MigrationError(
            "Source task definition has multiple essential containers. "
            "Specify --container-name explicitly."
        )
    return essential[0]


def _environment_map(container: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in container.get("environment", []):
        name = item.get("name")
        value = item.get("value")
        if isinstance(name, str) and isinstance(value, str):
            values[name] = value
    return values


def _secret_map(container: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in container.get("secrets", []):
        name = item.get("name")
        value_from = item.get("valueFrom")
        if isinstance(name, str) and isinstance(value_from, str):
            values[name] = value_from
    return values


def _validate_runtime_contract(
    *,
    container: dict[str, Any],
    expected_proxy_endpoint: str,
) -> None:
    environment = _environment_map(container)
    secrets = _secret_map(container)

    required_environment = {
        "DATABASE_HOST",
        "DATABASE_PORT",
        "DATABASE_NAME",
        "DATABASE_SSLMODE",
    }
    missing_environment = sorted(required_environment.difference(environment))
    if missing_environment:
        raise MigrationError(
            "Source task definition does not have the structured database "
            "environment required for migrations: "
            + ", ".join(missing_environment)
        )

    required_secrets = {"DATABASE_USERNAME", "DATABASE_PASSWORD"}
    missing_secrets = sorted(required_secrets.difference(secrets))
    if missing_secrets:
        raise MigrationError(
            "Source task definition does not inject Aurora database "
            "credentials from Secrets Manager: "
            + ", ".join(missing_secrets)
        )

    if environment["DATABASE_HOST"] != expected_proxy_endpoint:
        raise MigrationError(
            "DATABASE_HOST does not match the Terraform-managed RDS Proxy "
            "endpoint. Apply the database wiring before running migrations."
        )
    if environment["DATABASE_PORT"] != "5432":
        raise MigrationError(
            "DATABASE_PORT must be 5432 for the current PostgreSQL contract."
        )
    if environment["DATABASE_SSLMODE"].lower() != "require":
        raise MigrationError("DATABASE_SSLMODE must be require for AWS migrations.")
    if ":username::" not in secrets["DATABASE_USERNAME"]:
        raise MigrationError(
            "DATABASE_USERNAME is not mapped to the username JSON key in Secrets Manager."
        )
    if ":password::" not in secrets["DATABASE_PASSWORD"]:
        raise MigrationError(
            "DATABASE_PASSWORD is not mapped to the password JSON key in Secrets Manager."
        )


def _build_migration_task_definition_request(
    *,
    source_task_definition: dict[str, Any],
    application_container: dict[str, Any],
    image_uri: str,
    command: list[str],
) -> dict[str, Any]:
    source_family = source_task_definition.get("family")
    if not isinstance(source_family, str) or not source_family.strip():
        raise MigrationError("Source task definition does not contain a valid family.")

    family = f"{source_family}-migration"
    if len(family) > 255:
        raise MigrationError("Migration task-definition family exceeds 255 characters.")

    migration_container = copy.deepcopy(application_container)
    migration_container["image"] = image_uri
    migration_container["command"] = list(command)
    migration_container["essential"] = True
    migration_container.pop("healthCheck", None)
    migration_container.pop("portMappings", None)

    request: dict[str, Any] = {
        "family": family,
        "containerDefinitions": [migration_container],
        "tags": [
            {"key": "ManagedBy", "value": "DeploymentPipeline"},
            {"key": "Component", "value": "DatabaseMigration"},
        ],
    }

    for field in REGISTER_TASK_DEFINITION_FIELDS:
        value = source_task_definition.get(field)
        if value is not None:
            request[field] = copy.deepcopy(value)

    if "FARGATE" not in request.get("requiresCompatibilities", []):
        raise MigrationError("Source task definition is not Fargate-compatible.")
    if request.get("networkMode") != "awsvpc":
        raise MigrationError("Source task definition must use awsvpc networking.")

    return request


def _register_migration_task_definition(
    *,
    ecs_client: Any,
    request: dict[str, Any],
) -> str:
    try:
        response = ecs_client.register_task_definition(**request)
    except (ClientError, BotoCoreError) as exc:
        raise MigrationError(
            "Failed to register the migration ECS task definition."
        ) from exc

    arn = response.get("taskDefinition", {}).get("taskDefinitionArn")
    if not isinstance(arn, str) or not arn:
        raise MigrationError("ECS did not return a migration task-definition ARN.")
    return arn


def _run_migration_task(
    *,
    ecs_client: Any,
    cluster_name: str,
    task_definition_arn: str,
    subnet_ids: list[str],
    security_group_id: str,
) -> str:
    try:
        response = ecs_client.run_task(
            cluster=cluster_name,
            taskDefinition=task_definition_arn,
            launchType="FARGATE",
            platformVersion="LATEST",
            count=1,
            startedBy="realstock-migration",
            enableECSManagedTags=True,
            networkConfiguration={
                "awsvpcConfiguration": {
                    "subnets": subnet_ids,
                    "securityGroups": [security_group_id],
                    "assignPublicIp": "DISABLED",
                },
            },
            tags=[
                {"key": "ManagedBy", "value": "DeploymentPipeline"},
                {"key": "Component", "value": "DatabaseMigration"},
            ],
        )
    except (ClientError, BotoCoreError) as exc:
        raise MigrationError("Failed to start the ECS migration task.") from exc

    failures = response.get("failures", [])
    if failures:
        failure_text = "; ".join(
            f"{item.get('arn', '<unknown>')}: {item.get('reason', '<unknown>')}"
            for item in failures
        )
        raise MigrationError(f"ECS rejected the migration task: {failure_text}")

    tasks = response.get("tasks", [])
    if len(tasks) != 1:
        raise MigrationError("ECS did not start exactly one migration task.")

    task_arn = tasks[0].get("taskArn")
    if not isinstance(task_arn, str) or not task_arn:
        raise MigrationError("ECS did not return a migration task ARN.")
    return task_arn


def _wait_for_migration(
    *,
    ecs_client: Any,
    cluster_name: str,
    task_arn: str,
    container_name: str,
    wait_delay_seconds: int,
    wait_max_attempts: int,
) -> dict[str, Any]:
    waiter = ecs_client.get_waiter("tasks_stopped")
    try:
        waiter.wait(
            cluster=cluster_name,
            tasks=[task_arn],
            WaiterConfig={
                "Delay": wait_delay_seconds,
                "MaxAttempts": wait_max_attempts,
            },
        )
    except (ClientError, BotoCoreError) as exc:
        raise MigrationError(
            "Failed while waiting for the ECS migration task to stop."
        ) from exc

    response = ecs_client.describe_tasks(
        cluster=cluster_name,
        tasks=[task_arn],
    )
    failures = response.get("failures", [])
    if failures:
        raise MigrationError(
            f"Unable to describe stopped migration task: {failures}"
        )

    tasks = response.get("tasks", [])
    if len(tasks) != 1:
        raise MigrationError("ECS did not return the stopped migration task.")

    task = tasks[0]
    migration_container = next(
        (
            container
            for container in task.get("containers", [])
            if container.get("name") == container_name
        ),
        None,
    )
    if migration_container is None:
        raise MigrationError(
            f"Stopped task did not contain container {container_name}."
        )

    exit_code = migration_container.get("exitCode")
    if exit_code != 0:
        container_reason = migration_container.get(
            "reason",
            "<no container reason>",
        )
        stopped_reason = task.get(
            "stoppedReason",
            "<no stopped reason>",
        )
        raise MigrationError(
            "Database migration failed. "
            f"exitCode={exit_code}; "
            f"containerReason={container_reason}; "
            f"stoppedReason={stopped_reason}"
        )

    return task


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run RealStock Alembic migrations as a one-off ECS/Fargate "
            "task before API service rollout."
        ),
    )
    parser.add_argument(
        "--image-tag",
        required=True,
        help="Immutable ECR image tag to migrate, normally a Git commit SHA.",
    )
    parser.add_argument(
        "--terraform-dir",
        type=Path,
        default=DEFAULT_TERRAFORM_DIR,
        help="Terraform dev root containing the applied infrastructure state.",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="Optional AWS CLI/SDK profile name.",
    )
    parser.add_argument(
        "--region",
        default=os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION"),
        help="AWS region. Defaults to AWS_REGION/AWS_DEFAULT_REGION/profile.",
    )
    parser.add_argument(
        "--container-name",
        default=None,
        help=(
            "Application container name. Required only if the source task "
            "definition has multiple essential containers."
        ),
    )
    parser.add_argument("--wait-delay-seconds", type=int, default=6)
    parser.add_argument("--wait-max-attempts", type=int, default=100)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        image_tag = _validate_image_tag(args.image_tag)
        terraform_dir = args.terraform_dir.resolve()
        if not terraform_dir.is_dir():
            raise MigrationError(
                f"Terraform directory does not exist: {terraform_dir}"
            )

        outputs = _load_terraform_outputs(terraform_dir)

        cluster_name = str(
            _terraform_output_value(outputs, "api_ecs_cluster_name")
        )
        source_task_definition_arn = str(
            _terraform_output_value(outputs, "api_task_definition_arn")
        )
        subnet_ids_raw = _terraform_output_value(
            outputs,
            "private_app_subnet_ids",
        )
        if not isinstance(subnet_ids_raw, list) or not subnet_ids_raw:
            raise MigrationError(
                "private_app_subnet_ids must be a non-empty list."
            )
        subnet_ids = [str(item) for item in subnet_ids_raw]

        security_group_id = str(
            _terraform_output_value(outputs, "ecs_security_group_id")
        )
        repository_name = str(
            _terraform_output_value(outputs, "api_ecr_repository_name")
        )
        repository_url = str(
            _terraform_output_value(outputs, "api_ecr_repository_url")
        )
        proxy_endpoint = str(
            _terraform_output_value(outputs, "database_proxy_endpoint")
        )

        session, region = _create_boto3_session(
            profile=args.profile,
            region=args.region,
        )
        ecs_client = session.client("ecs", region_name=region)
        ecr_client = session.client("ecr", region_name=region)

        candidate_image_uri, image_digest = _resolve_candidate_image(
            ecr_client=ecr_client,
            repository_name=repository_name,
            repository_url=repository_url,
            image_tag=image_tag,
        )

        try:
            source_response = ecs_client.describe_task_definition(
                taskDefinition=source_task_definition_arn,
                include=["TAGS"],
            )
        except (ClientError, BotoCoreError) as exc:
            raise MigrationError(
                "Failed to read the source API ECS task definition."
            ) from exc

        source_task_definition = source_response.get("taskDefinition", {})
        application_container = _select_application_container(
            source_task_definition,
            args.container_name,
        )
        container_name = application_container.get("name")
        if not isinstance(container_name, str) or not container_name:
            raise MigrationError("Application container has no valid name.")

        _validate_runtime_contract(
            container=application_container,
            expected_proxy_endpoint=proxy_endpoint,
        )

        registration_request = _build_migration_task_definition_request(
            source_task_definition=source_task_definition,
            application_container=application_container,
            image_uri=candidate_image_uri,
            command=DEFAULT_MIGRATION_COMMAND,
        )
        migration_task_definition_arn = _register_migration_task_definition(
            ecs_client=ecs_client,
            request=registration_request,
        )

        print(f"candidateImage={candidate_image_uri}")
        print(f"candidateDigest={image_digest}")
        print(f"migrationTaskDefinition={migration_task_definition_arn}")

        task_arn = _run_migration_task(
            ecs_client=ecs_client,
            cluster_name=cluster_name,
            task_definition_arn=migration_task_definition_arn,
            subnet_ids=subnet_ids,
            security_group_id=security_group_id,
        )
        print(f"migrationTask={task_arn}")

        _wait_for_migration(
            ecs_client=ecs_client,
            cluster_name=cluster_name,
            task_arn=task_arn,
            container_name=container_name,
            wait_delay_seconds=args.wait_delay_seconds,
            wait_max_attempts=args.wait_max_attempts,
        )

        print("migrationStatus=SUCCEEDED")
        print(
            "releaseGate=OPEN "
            "(safe to promote this image tag to the API ECS service)"
        )
        return 0

    except MigrationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        print("releaseGate=CLOSED", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())