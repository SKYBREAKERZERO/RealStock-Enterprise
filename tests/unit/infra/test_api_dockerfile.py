from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DOCKERFILE = PROJECT_ROOT / "services" / "api" / "Dockerfile"


def _dockerfile_text() -> str:
    return DOCKERFILE.read_text(
        encoding="utf-8",
    )


def test_api_dockerfile_exists() -> None:
    assert DOCKERFILE.is_file()


def test_api_dockerfile_uses_multi_stage_build() -> None:
    content = _dockerfile_text()

    assert " AS builder" in content
    assert " AS runtime" in content


def test_api_dockerfile_uses_python_312_runtime() -> None:
    content = _dockerfile_text()

    assert "python:3.12-slim-bookworm" in content
    assert "python:latest" not in content


def test_api_dockerfile_builds_application_wheel() -> None:
    content = _dockerfile_text()

    assert "python -m pip wheel" in content
    assert "--wheel-dir=/wheels" in content


def test_api_runtime_installs_from_local_wheels() -> None:
    content = _dockerfile_text()

    assert "--no-index" in content
    assert "--find-links=/wheels" in content
    assert "realstock-enterprise" in content


def test_api_runtime_does_not_run_as_root() -> None:
    content = _dockerfile_text()

    assert "--uid 10001" in content
    assert "--gid 10001" in content
    assert "USER 10001:10001" in content


def test_api_dockerfile_exposes_api_port() -> None:
    content = _dockerfile_text()

    assert "EXPOSE 8000" in content


def test_api_healthcheck_uses_liveness_endpoint() -> None:
    content = _dockerfile_text()

    assert "HEALTHCHECK" in content
    assert "127.0.0.1:8000/health" in content

    healthcheck_section = content.split(
        "HEALTHCHECK",
        maxsplit=1,
    )[1].split(
        "STOPSIGNAL",
        maxsplit=1,
    )[0]

    assert "/health/ready" not in healthcheck_section


def test_api_dockerfile_uses_sigterm() -> None:
    content = _dockerfile_text()

    assert "STOPSIGNAL SIGTERM" in content


def test_api_dockerfile_uses_exec_form_uvicorn_command() -> None:
    content = _dockerfile_text()

    expected = (
        'CMD ["python", "-m", "uvicorn", '
        '"services.api.main:app", "--host", '
        '"0.0.0.0", "--port", "8000"]'
    )

    assert expected in content


def test_api_runtime_does_not_upgrade_pip() -> None:
    content = _dockerfile_text()

    assert "pip install --upgrade pip" not in content