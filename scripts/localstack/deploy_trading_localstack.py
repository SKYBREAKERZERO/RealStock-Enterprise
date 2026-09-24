from __future__ import annotations

import http.client
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import boto3
import psycopg
from botocore.config import Config

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCALSTACK_ENDPOINT = "http://127.0.0.1:4566"
AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-1")

REQUIRED_TRADING_TABLES = {
    "paper_accounts",
    "paper_executions",
    "paper_orders",
    "paper_positions",
}

HEALTH_CONTAINERS = {
    "realstock-localstack",
    "realstock-postgres",
    "realstock-redis",
}

API_URL = "http://127.0.0.1:18000"
WAIT_TIMEOUT_SECONDS = 120


def _load_dotenv() -> dict[str, str]:
    values: dict[str, str] = {}
    path = PROJECT_ROOT / ".env"

    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {'"', "'"}
        ):
            value = value[1:-1]

        values[key] = value

    return values


DOTENV = _load_dotenv()


def _setting(name: str, default: str) -> str:
    return os.getenv(name, DOTENV.get(name, default))


POSTGRES_DB = _setting("POSTGRES_DB", "realstock")
POSTGRES_USER = _setting("POSTGRES_USER", "realstock")
POSTGRES_PASSWORD = _setting(
    "POSTGRES_PASSWORD",
    "realstock_local_password",
)


def configure_proxy_bypass() -> None:
    existing = (
        os.environ.get("NO_PROXY")
        or os.environ.get("no_proxy")
        or ""
    )

    values = [
        item.strip()
        for item in existing.split(",")
        if item.strip()
    ]

    for host in (
        "127.0.0.1",
        "localhost",
        "localstack",
        "postgres",
        "redis",
    ):
        if host not in values:
            values.append(host)

    merged = ",".join(values)
    os.environ["NO_PROXY"] = merged
    os.environ["no_proxy"] = merged


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("      $", " ".join(args))

    result = subprocess.run(
        list(args),
        cwd=PROJECT_ROOT,
        text=True,
        check=False,
    )

    if check and result.returncode != 0:
        raise RuntimeError(
            f"Command failed with exit code {result.returncode}: "
            + " ".join(args)
        )

    return result


def aws_client(service: str) -> Any:
    return boto3.client(
        service,
        region_name=AWS_REGION,
        endpoint_url=LOCALSTACK_ENDPOINT,
        aws_access_key_id="test",
        aws_secret_access_key="test",
        config=Config(
            connect_timeout=5,
            read_timeout=20,
            retries={
                "max_attempts": 2,
                "mode": "standard",
            },
        ),
    )


def wait_container_healthy(container_name: str) -> None:
    deadline = time.monotonic() + WAIT_TIMEOUT_SECONDS

    while time.monotonic() < deadline:
        result = subprocess.run(
            [
                "docker",
                "inspect",
                "--format",
                "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}",
                container_name,
            ],
            cwd=PROJECT_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        status = result.stdout.strip().lower()

        if status in {"healthy", "running"}:
            print(f"      {container_name}: {status}")
            return

        if status in {"unhealthy", "exited", "dead"}:
            raise RuntimeError(
                f"{container_name} entered terminal state: {status}"
            )

        time.sleep(1)

    raise TimeoutError(
        f"Timed out waiting for {container_name} health."
    )


def get_json(url: str) -> dict[str, Any]:
    with urllib.request.urlopen(url, timeout=5) as response:
        payload = response.read().decode("utf-8")

    parsed = json.loads(payload)

    if not isinstance(parsed, dict):
        raise RuntimeError(f"Expected JSON object from {url}")

    return parsed


def wait_api_ready() -> None:
    deadline = time.monotonic() + WAIT_TIMEOUT_SECONDS
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            payload = get_json(f"{API_URL}/health/ready")

            if payload.get("status") == "ready":
                dependencies = payload.get("dependencies", {})

                print(f"      readiness={json.dumps(payload, ensure_ascii=False)}")

                expected = {
                    "postgresql",
                    "redis",
                    "localstack",
                    "s3",
                    "dynamodb",
                }

                missing = expected - set(dependencies)

                if missing:
                    raise RuntimeError(
                        "Readiness response is missing dependencies: "
                        + ", ".join(sorted(missing))
                    )

                failed = {
                    key: value
                    for key, value in dependencies.items()
                    if key in expected and value != "ok"
                }

                if failed:
                    raise RuntimeError(
                        "Readiness dependencies are not healthy: "
                        + json.dumps(failed)
                    )

                return

        except (
            urllib.error.URLError,
            http.client.HTTPException,
            ConnectionError,
            TimeoutError,
            json.JSONDecodeError,
            RuntimeError,
        ) as exc:
            last_error = exc

        time.sleep(1)

    raise TimeoutError(
        f"API did not become ready. Last error: {last_error!r}"
    )


def verify_localstack_services() -> None:
    print("[7/9] Verifying LocalStack AWS APIs")

    identity = aws_client("sts").get_caller_identity()
    print(f"      STS account={identity.get('Account')}")

    eventbridge = aws_client("events")
    event_buses = eventbridge.list_event_buses().get("EventBuses", [])

    if not any(bus.get("Name") == "default" for bus in event_buses):
        raise RuntimeError(
            "LocalStack EventBridge default event bus was not found."
        )

    print("      EventBridge default bus: ok")

    aws_client("s3").list_buckets()
    print("      S3: ok")

    aws_client("dynamodb").list_tables(Limit=1)
    print("      DynamoDB: ok")

    aws_client("cloudwatch").list_metrics()
    print("      CloudWatch: ok")


def verify_database() -> None:
    print("[8/9] Verifying Alembic revision and trading tables")

    dsn = (
        f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
        f"@127.0.0.1:15432/{POSTGRES_DB}"
    )

    with psycopg.connect(dsn, connect_timeout=5) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT version_num FROM alembic_version"
            )

            row = cursor.fetchone()

            if row is None:
                raise RuntimeError(
                    "alembic_version does not contain a revision."
                )

            revision = str(row[0])

            cursor.execute(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                  AND tablename LIKE 'paper_%'
                ORDER BY tablename
                """
            )

            tables = {
                str(item[0])
                for item in cursor.fetchall()
            }

    missing = REQUIRED_TRADING_TABLES - tables

    if missing:
        raise RuntimeError(
            "Missing trading tables: "
            + ", ".join(sorted(missing))
        )

    print(f"      alembicRevision={revision}")
    print(
        "      tradingTables="
        + ", ".join(sorted(REQUIRED_TRADING_TABLES))
    )


def verify_runtime() -> None:
    print("[9/9] Verifying running services")
    run("docker", "compose", "ps")

    api_health = get_json(f"{API_URL}/health")

    if api_health.get("status") != "ok":
        raise RuntimeError(
            f"API liveness failed: {api_health!r}"
        )

    print("      API /health: ok")
    print("      API /health/ready: ready")
    print("      Outbox dispatcher: running under Docker Compose")


def main() -> int:
    configure_proxy_bypass()

    print("=" * 72)
    print("RealStock Enterprise - LocalStack Trading Deployment")
    print("=" * 72)
    print(
        "Mode: Docker Compose runtime + LocalStack AWS APIs "
        "(no LocalStack ECS)"
    )

    try:
        print("[1/9] Validating docker-compose.yml")
        run("docker", "compose", "config", "--quiet")

        print("[2/9] Starting infrastructure dependencies")
        run(
            "docker",
            "compose",
            "up",
            "-d",
            "localstack",
            "postgres",
            "redis",
            "otel-collector",
        )

        print("[3/9] Waiting for infrastructure health")
        for container_name in sorted(HEALTH_CONTAINERS):
            wait_container_healthy(container_name)

        print("[4/9] Building application images")
        run(
            "docker",
            "compose",
            "build",
            "api",
            "outbox-dispatcher",
        )

        print("[5/9] Running Alembic migration from API image")
        run(
            "docker",
            "compose",
            "run",
            "--rm",
            "api",
            "python",
            "-m",
            "alembic",
            "-c",
            "database/alembic.ini",
            "upgrade",
            "head",
        )

        print("[6/9] Starting API and outbox dispatcher")
        run(
            "docker",
            "compose",
            "up",
            "-d",
            "api",
            "outbox-dispatcher",
        )

        # The API container is recreated above. Docker may briefly accept
        # and then close TCP connections while Uvicorn is still starting.
        # Wait for the container healthcheck before probing readiness.
        wait_container_healthy("realstock-api")
        wait_api_ready()
        verify_localstack_services()
        verify_database()
        verify_runtime()

    except Exception as exc:
        print()
        print("FAILED")
        print(f"{type(exc).__name__}: {exc}")
        return 1

    print()
    print("SUCCESS")
    print(
        "LocalStack trading deployment is healthy. "
        "Docker Compose provides compute/runtime; "
        "LocalStack provides AWS API dependencies."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
