from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

# ==============================================================
# Project bootstrap
# ==============================================================

ROOT_DIR = Path(__file__).resolve().parents[2]

# When this file is executed directly:
#
#   python scripts/bootstrap/check_environment.py
#
# Python normally puts scripts/bootstrap on sys.path rather than
# the project root. Explicitly add the project root so packages
# such as libs.config / libs.aws / libs.database / libs.cache
# are always importable.
root_path = str(ROOT_DIR)

if root_path not in sys.path:
    sys.path.insert(0, root_path)


ENV_FILE = ROOT_DIR / ".env"

DEFAULT_LOCALSTACK_ENDPOINT = "http://localhost:4566"
DEFAULT_AWS_REGION = "ap-northeast-1"

LOCAL_S3_HEALTH_BUCKET = "realstock-market-data-local"
LOCAL_S3_HEALTH_KEY = "health/check-environment.txt"
LOCAL_S3_HEALTH_BODY = b"RealStock Environment Gate PASS"

REDIS_HEALTH_KEY = "realstock:environment-gate"

COMMAND_TIMEOUT_SECONDS = 15
HTTP_TIMEOUT_SECONDS = 10


# ==============================================================
# Result model
# ==============================================================


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str


# ==============================================================
# Environment helpers
# ==============================================================


def load_env_file(path: Path) -> dict[str, str]:
    """
    Load simple KEY=VALUE values from the project .env file.

    This function intentionally does not print secrets.
    """

    values: dict[str, str] = {}

    if not path.exists():
        return values

    for raw_line in path.read_text(
        encoding="utf-8",
    ).splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("#"):
            continue

        if "=" not in line:
            continue

        key, value = line.split("=", 1)

        key = key.strip()

        value = (
            value
            .strip()
            .strip('"')
            .strip("'")
        )

        if key:
            values[key] = value

    return values


FILE_ENV = load_env_file(ENV_FILE)


def get_setting(
    name: str,
    default: str = "",
) -> str:
    """
    Environment variable priority:

    1. Process environment
    2. Project .env
    3. Supplied default
    """

    return (
        os.environ.get(name)
        or FILE_ENV.get(name)
        or default
    )


# ==============================================================
# Command helpers
# ==============================================================


def run_command(
    command: list[str],
    *,
    env: dict[str, str] | None = None,
    timeout: int = COMMAND_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT_DIR,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def first_output_line(
    process: subprocess.CompletedProcess[str],
) -> str:
    output = (
        process.stdout
        or process.stderr
    ).strip()

    if not output:
        return "command completed"

    return output.splitlines()[0].strip()


def build_command(
    executable: str,
    args: list[str],
) -> tuple[list[str] | None, str | None]:
    """
    Resolve executable safely on Windows.

    Windows command shims such as mvn.cmd must be executed
    through cmd.exe.
    """

    path = shutil.which(executable)

    if path is None:
        return None, None

    if (
        os.name == "nt"
        and path.lower().endswith(
            (".cmd", ".bat")
        )
    ):
        command = [
            os.environ.get(
                "COMSPEC",
                "cmd.exe",
            ),
            "/d",
            "/c",
            path,
            *args,
        ]
    else:
        command = [
            path,
            *args,
        ]

    return command, path


# ==============================================================
# Toolchain checks
# ==============================================================


def check_python() -> CheckResult:
    version = sys.version_info

    expected_venv = (
        ROOT_DIR / ".venv"
    ).resolve()

    current_python = Path(
        sys.executable
    ).resolve()

    correct_version = (
        version.major == 3
        and version.minor == 12
    )

    correct_venv = (
        expected_venv
        in current_python.parents
    )

    passed = (
        correct_version
        and correct_venv
    )

    if not correct_version:
        detail = (
            "Expected Python 3.12, "
            f"got {version.major}."
            f"{version.minor}."
            f"{version.micro} "
            f"({current_python})"
        )

    elif not correct_venv:
        detail = (
            "Wrong virtual environment: "
            f"{current_python}; "
            f"expected under {expected_venv}"
        )

    else:
        detail = (
            f"Python "
            f"{version.major}."
            f"{version.minor}."
            f"{version.micro} "
            f"({current_python})"
        )

    return CheckResult(
        "Python 3.12",
        passed,
        detail,
    )


def check_command(
    *,
    name: str,
    executable: str,
    args: list[str],
) -> CheckResult:
    command, path = build_command(
        executable,
        args,
    )

    if command is None or path is None:
        return CheckResult(
            name,
            False,
            f"{executable} not found in PATH",
        )

    try:
        result = run_command(
            command
        )

    except subprocess.TimeoutExpired:
        return CheckResult(
            name,
            False,
            f"{executable} command timed out",
        )

    except OSError as exc:
        return CheckResult(
            name,
            False,
            str(exc),
        )

    return CheckResult(
        name,
        result.returncode == 0,
        first_output_line(result),
    )


def check_git() -> CheckResult:
    return check_command(
        name="Git",
        executable="git",
        args=["--version"],
    )


def check_docker() -> CheckResult:
    command, _ = build_command(
        "docker",
        [
            "version",
            "--format",
            "{{.Server.Version}}",
        ],
    )

    if command is None:
        return CheckResult(
            "Docker Engine",
            False,
            "docker not found in PATH",
        )

    try:
        result = run_command(
            command
        )

    except subprocess.TimeoutExpired:
        return CheckResult(
            "Docker Engine",
            False,
            "Docker daemon check timed out",
        )

    except OSError as exc:
        return CheckResult(
            "Docker Engine",
            False,
            str(exc),
        )

    if result.returncode != 0:
        return CheckResult(
            "Docker Engine",
            False,
            first_output_line(result),
        )

    return CheckResult(
        "Docker Engine",
        True,
        f"Server {result.stdout.strip()}",
    )


def check_docker_compose() -> CheckResult:
    return check_command(
        name="Docker Compose",
        executable="docker",
        args=[
            "compose",
            "version",
            "--short",
        ],
    )


def check_terraform() -> CheckResult:
    return check_command(
        name="Terraform",
        executable="terraform",
        args=["version"],
    )


def check_aws_cli() -> CheckResult:
    return check_command(
        name="AWS CLI",
        executable="aws",
        args=["--version"],
    )


def check_java() -> CheckResult:
    command, _ = build_command(
        "java",
        ["--version"],
    )

    if command is None:
        return CheckResult(
            "Java 17",
            False,
            "java not found in PATH",
        )

    try:
        result = run_command(
            command
        )

    except subprocess.TimeoutExpired:
        return CheckResult(
            "Java 17",
            False,
            "java --version timed out",
        )

    except OSError as exc:
        return CheckResult(
            "Java 17",
            False,
            str(exc),
        )

    output = (
        result.stdout
        or result.stderr
    ).strip()

    if not output:
        return CheckResult(
            "Java 17",
            False,
            "java --version returned no output",
        )

    first_line = (
        output
        .splitlines()[0]
        .strip()
    )

    passed = (
        result.returncode == 0
        and (
            first_line.startswith(
                "openjdk 17."
            )
            or first_line.startswith(
                "java 17."
            )
        )
    )

    return CheckResult(
        "Java 17",
        passed,
        first_line,
    )


def check_maven() -> CheckResult:
    return check_command(
        name="Maven",
        executable="mvn",
        args=["--version"],
    )


# ==============================================================
# Git / secrets checks
# ==============================================================


def check_git_env_protection() -> CheckResult:
    """
    Verify that:

    1. .env exists locally
    2. .env is NOT tracked by Git
    3. .env has an effective ignore rule
    """

    if not ENV_FILE.exists():
        return CheckResult(
            ".env Git Protection",
            False,
            ".env file does not exist",
        )

    tracked_command, _ = build_command(
        "git",
        [
            "ls-files",
            "--error-unmatch",
            ".env",
        ],
    )

    if tracked_command is None:
        return CheckResult(
            ".env Git Protection",
            False,
            "git not found in PATH",
        )

    try:
        tracked_result = run_command(
            tracked_command
        )

    except subprocess.TimeoutExpired:
        return CheckResult(
            ".env Git Protection",
            False,
            "git ls-files timed out",
        )

    except OSError as exc:
        return CheckResult(
            ".env Git Protection",
            False,
            str(exc),
        )

    if tracked_result.returncode == 0:
        return CheckResult(
            ".env Git Protection",
            False,
            ".env is TRACKED by Git",
        )

    ignore_command, _ = build_command(
        "git",
        [
            "check-ignore",
            "-q",
            "--no-index",
            ".env",
        ],
    )

    if ignore_command is None:
        return CheckResult(
            ".env Git Protection",
            False,
            "git not found in PATH",
        )

    try:
        ignore_result = run_command(
            ignore_command
        )

    except subprocess.TimeoutExpired:
        return CheckResult(
            ".env Git Protection",
            False,
            "git check-ignore timed out",
        )

    except OSError as exc:
        return CheckResult(
            ".env Git Protection",
            False,
            str(exc),
        )

    passed = (
        ignore_result.returncode == 0
    )

    return CheckResult(
        ".env Git Protection",
        passed,
        (
            ".env is untracked and ignored by Git"
            if passed
            else
            ".env has no effective Git ignore rule"
        ),
    )


# ==============================================================
# Application settings
# ==============================================================


def check_settings() -> CheckResult:
    try:
        from libs.config import get_settings

        settings = get_settings()

        passed = bool(
            settings.app_env
            and settings.aws_region
            and settings.database_url
            and settings.redis_url
        )

        detail = (
            f"env={settings.app_env}; "
            f"region={settings.aws_region}; "
            f"localstack={settings.use_localstack}; "
            "database=configured; "
            "redis=configured"
        )

        return CheckResult(
            "Settings",
            passed,
            detail,
        )

    except Exception as exc:
        return CheckResult(
            "Settings",
            False,
            f"{type(exc).__name__}: {exc}",
        )


# ==============================================================
# LocalStack base health
# ==============================================================


def check_localstack() -> CheckResult:
    endpoint = get_setting(
        "AWS_ENDPOINT_URL",
        DEFAULT_LOCALSTACK_ENDPOINT,
    ).rstrip("/")

    url = (
        f"{endpoint}/_localstack/health"
    )

    try:
        with urllib.request.urlopen(
            url,
            timeout=HTTP_TIMEOUT_SECONDS,
        ) as response:
            payload = json.loads(
                response
                .read()
                .decode("utf-8")
            )

    except (
        urllib.error.URLError,
        TimeoutError,
        json.JSONDecodeError,
    ) as exc:
        return CheckResult(
            "LocalStack",
            False,
            f"{url}: {exc}",
        )

    version = payload.get(
        "version",
        "unknown",
    )

    edition = payload.get(
        "edition",
        "unknown",
    )

    features = payload.get(
        "features",
        {},
    )

    persistence = features.get(
        "persistence",
        "unknown",
    )

    services = payload.get(
        "services",
        {},
    )

    required_services = (
        "s3",
        "dynamodb",
        "kinesis",
        "events",
        "sqs",
        "sns",
        "secretsmanager",
        "kms",
        "sts",
    )

    healthy_states = {
        "available",
        "running",
    }

    unhealthy_services = [
        service
        for service in required_services
        if services.get(service)
        not in healthy_states
    ]

    passed = (
        not unhealthy_services
    )

    if passed:
        detail = (
            f"LocalStack {version} "
            f"({edition}); "
            f"persistence={persistence}"
        )

    else:
        detail = (
            f"LocalStack {version} "
            f"({edition}); "
            "unhealthy="
            f"{','.join(unhealthy_services)}"
        )

    return CheckResult(
        "LocalStack",
        passed,
        detail,
    )


# ==============================================================
# LocalStack STS
# ==============================================================


def check_localstack_sts() -> CheckResult:
    try:
        from libs.aws import get_sts_client

        response = (
            get_sts_client()
            .get_caller_identity()
        )

        account = response.get(
            "Account",
            "unknown",
        )

        status = (
            response
            .get(
                "ResponseMetadata",
                {},
            )
            .get(
                "HTTPStatusCode",
                0,
            )
        )

        passed = (
            status == 200
        )

        return CheckResult(
            "LocalStack STS",
            passed,
            (
                f"Account {account}; "
                f"HTTP {status}"
            ),
        )

    except Exception as exc:
        return CheckResult(
            "LocalStack STS",
            False,
            f"{type(exc).__name__}: {exc}",
        )


# ==============================================================
# LocalStack S3 integration
# ==============================================================


def check_localstack_s3() -> CheckResult:
    """
    Integration check:

    - List buckets
    - Create health bucket if missing
    - PUT health object
    - GET health object
    - Verify body
    """

    try:
        from libs.aws import get_s3_client
        from libs.config import get_settings

        settings = get_settings()
        s3 = get_s3_client()

        response = s3.list_buckets()

        existing_buckets = {
            bucket["Name"]
            for bucket
            in response.get(
                "Buckets",
                [],
            )
        }

        if (
            LOCAL_S3_HEALTH_BUCKET
            not in existing_buckets
        ):
            if (
                settings.aws_region
                == "us-east-1"
            ):
                s3.create_bucket(
                    Bucket=(
                        LOCAL_S3_HEALTH_BUCKET
                    ),
                )

            else:
                s3.create_bucket(
                    Bucket=(
                        LOCAL_S3_HEALTH_BUCKET
                    ),
                    CreateBucketConfiguration={
                        "LocationConstraint":
                            settings.aws_region,
                    },
                )

        put_response = s3.put_object(
            Bucket=LOCAL_S3_HEALTH_BUCKET,
            Key=LOCAL_S3_HEALTH_KEY,
            Body=LOCAL_S3_HEALTH_BODY,
        )

        put_status = (
            put_response
            .get(
                "ResponseMetadata",
                {},
            )
            .get(
                "HTTPStatusCode",
                0,
            )
        )

        get_response = s3.get_object(
            Bucket=LOCAL_S3_HEALTH_BUCKET,
            Key=LOCAL_S3_HEALTH_KEY,
        )

        body = (
            get_response["Body"]
            .read()
        )

        body_verified = (
            body
            == LOCAL_S3_HEALTH_BODY
        )

        passed = (
            put_status == 200
            and body_verified
        )

        return CheckResult(
            "LocalStack S3",
            passed,
            (
                f"bucket="
                f"{LOCAL_S3_HEALTH_BUCKET}; "
                f"PUT={put_status}; "
                f"GET="
                f"{'verified' if body_verified else 'failed'}"
            ),
        )

    except Exception as exc:
        return CheckResult(
            "LocalStack S3",
            False,
            f"{type(exc).__name__}: {exc}",
        )


# ==============================================================
# PostgreSQL container health
# ==============================================================


def check_postgres() -> CheckResult:
    user = get_setting(
        "POSTGRES_USER",
        "realstock",
    )

    database = get_setting(
        "POSTGRES_DB",
        "realstock",
    )

    command, _ = build_command(
        "docker",
        [
            "exec",
            "realstock-postgres",
            "pg_isready",
            "-U",
            user,
            "-d",
            database,
        ],
    )

    if command is None:
        return CheckResult(
            "PostgreSQL",
            False,
            "docker not found in PATH",
        )

    try:
        result = run_command(
            command
        )

    except subprocess.TimeoutExpired:
        return CheckResult(
            "PostgreSQL",
            False,
            "pg_isready timed out",
        )

    except OSError as exc:
        return CheckResult(
            "PostgreSQL",
            False,
            str(exc),
        )

    return CheckResult(
        "PostgreSQL",
        result.returncode == 0,
        first_output_line(result),
    )


# ==============================================================
# PostgreSQL container SQL
# ==============================================================


def check_postgres_sql() -> CheckResult:
    user = get_setting(
        "POSTGRES_USER",
        "realstock",
    )

    database = get_setting(
        "POSTGRES_DB",
        "realstock",
    )

    command, _ = build_command(
        "docker",
        [
            "exec",
            "realstock-postgres",
            "psql",
            "-U",
            user,
            "-d",
            database,
            "-tAc",
            "SELECT 1;",
        ],
    )

    if command is None:
        return CheckResult(
            "PostgreSQL SQL",
            False,
            "docker not found in PATH",
        )

    try:
        result = run_command(
            command
        )

    except subprocess.TimeoutExpired:
        return CheckResult(
            "PostgreSQL SQL",
            False,
            "SQL query timed out",
        )

    except OSError as exc:
        return CheckResult(
            "PostgreSQL SQL",
            False,
            str(exc),
        )

    output = (
        result.stdout
        .strip()
    )

    passed = (
        result.returncode == 0
        and output == "1"
    )

    return CheckResult(
        "PostgreSQL SQL",
        passed,
        (
            "SELECT 1 -> "
            f"{output or 'no output'}"
        ),
    )


# ==============================================================
# Python -> PostgreSQL integration
# ==============================================================


def check_python_postgres() -> CheckResult:
    try:
        from sqlalchemy import text

        from libs.database import get_engine

        engine = get_engine()

        with engine.connect() as connection:
            result = (
                connection.execute(
                    text("SELECT 1")
                )
                .scalar_one()
            )

        # Dispose only after the check. A future FastAPI
        # process would normally retain the connection pool.
        engine.dispose()

        passed = (
            result == 1
        )

        return CheckResult(
            "Python PostgreSQL",
            passed,
            (
                "SQLAlchemy SELECT 1 "
                f"-> {result}"
            ),
        )

    except Exception as exc:
        return CheckResult(
            "Python PostgreSQL",
            False,
            f"{type(exc).__name__}: {exc}",
        )


# ==============================================================
# Redis container health
# ==============================================================


def check_redis() -> CheckResult:
    command, _ = build_command(
        "docker",
        [
            "exec",
            "realstock-redis",
            "redis-cli",
            "ping",
        ],
    )

    if command is None:
        return CheckResult(
            "Redis",
            False,
            "docker not found in PATH",
        )

    try:
        result = run_command(
            command
        )

    except subprocess.TimeoutExpired:
        return CheckResult(
            "Redis",
            False,
            "redis-cli timed out",
        )

    except OSError as exc:
        return CheckResult(
            "Redis",
            False,
            str(exc),
        )

    output = (
        result.stdout
        .strip()
    )

    passed = (
        result.returncode == 0
        and output == "PONG"
    )

    return CheckResult(
        "Redis",
        passed,
        (
            output
            or first_output_line(result)
        ),
    )


# ==============================================================
# Python -> Redis integration
# ==============================================================


def check_python_redis() -> CheckResult:
    try:
        from libs.cache import get_redis_client

        redis_client = (
            get_redis_client()
        )

        ping_result = (
            redis_client.ping()
        )

        set_result = (
            redis_client.set(
                REDIS_HEALTH_KEY,
                "ok",
                ex=60,
            )
        )

        value = (
            redis_client.get(
                REDIS_HEALTH_KEY
            )
        )

        ttl = (
            redis_client.ttl(
                REDIS_HEALTH_KEY
            )
        )

        redis_client.delete(
            REDIS_HEALTH_KEY
        )

        passed = (
            ping_result is True
            and set_result is True
            and value == "ok"
            and ttl > 0
        )

        return CheckResult(
            "Python Redis",
            passed,
            (
                f"PING={ping_result}; "
                f"SET={set_result}; "
                f"GET={value}; "
                f"TTL={ttl}"
            ),
        )

    except Exception as exc:
        return CheckResult(
            "Python Redis",
            False,
            f"{type(exc).__name__}: {exc}",
        )


# ==============================================================
# Output
# ==============================================================


def print_header() -> None:
    print()

    print("=" * 78)

    print(
        "RealStock Enterprise - "
        "Environment & Integration Gate"
    )

    print("=" * 78)

    print(
        f"Project : {ROOT_DIR}"
    )

    print(
        f"OS      : "
        f"{platform.system()} "
        f"{platform.release()}"
    )

    print(
        f"Python  : {sys.executable}"
    )

    print("=" * 78)

    print()


def print_result(
    result: CheckResult,
) -> None:
    status = (
        "PASS"
        if result.passed
        else "FAIL"
    )

    print(
        f"[{status:<4}] "
        f"{result.name:<24} "
        f"{result.detail}"
    )


# ==============================================================
# Main
# ==============================================================


def main() -> int:
    print_header()

    checks = (
        # ------------------------------------------------------
        # Toolchain
        # ------------------------------------------------------
        check_python,
        check_git,
        check_docker,
        check_docker_compose,
        check_terraform,
        check_aws_cli,
        check_java,
        check_maven,

        # ------------------------------------------------------
        # Security / configuration
        # ------------------------------------------------------
        check_git_env_protection,
        check_settings,

        # ------------------------------------------------------
        # Local AWS
        # ------------------------------------------------------
        check_localstack,
        check_localstack_sts,
        check_localstack_s3,

        # ------------------------------------------------------
        # PostgreSQL
        # ------------------------------------------------------
        check_postgres,
        check_postgres_sql,
        check_python_postgres,

        # ------------------------------------------------------
        # Redis
        # ------------------------------------------------------
        check_redis,
        check_python_redis,
    )

    results: list[CheckResult] = []

    for check in checks:
        try:
            result = check()

        except Exception as exc:
            result = CheckResult(
                check.__name__,
                False,
                (
                    "unexpected error: "
                    f"{type(exc).__name__}: "
                    f"{exc}"
                ),
            )

        results.append(result)

        print_result(result)

    passed_count = sum(
        result.passed
        for result in results
    )

    failed = [
        result
        for result in results
        if not result.passed
    ]

    print()

    print("=" * 78)

    print(
        f"Result: "
        f"{passed_count}/"
        f"{len(results)} "
        "checks passed"
    )

    if failed:
        print()

        print(
            "Environment Gate: FAILED"
        )

        print()

        print("Failed checks:")

        for result in failed:
            print(
                f"  - {result.name}: "
                f"{result.detail}"
            )

        print("=" * 78)

        return 1

    print(
        "Environment Gate: PASSED"
    )

    print("=" * 78)

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )