from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

COMPOSE_FILE = REPOSITORY_ROOT / "docker-compose.yml"

LOCAL_COLLECTOR_CONFIG_FILE = (
    REPOSITORY_ROOT
    / "infra"
    / "observability"
    / "otel-collector"
    / "config.yaml"
)

ADOT_COLLECTOR_CONFIG_FILE = (
    REPOSITORY_ROOT
    / "infra"
    / "observability"
    / "adot-collector"
    / "config.yaml"
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_local_collector_configuration_exists() -> None:
    assert LOCAL_COLLECTOR_CONFIG_FILE.is_file()


def test_collector_image_is_version_pinned() -> None:
    compose = _read(COMPOSE_FILE)

    assert (
        "otel/opentelemetry-collector-contrib:0.160.0"
        in compose
    )

    assert (
        "otel/opentelemetry-collector-contrib:latest"
        not in compose
    )


def test_local_collector_config_is_read_only() -> None:
    compose = _read(COMPOSE_FILE)

    assert (
        "./infra/observability/otel-collector/config.yaml:"
        "/etc/otelcol-contrib/config.yaml:ro"
        in compose
    )


def test_otlp_http_is_bound_to_loopback() -> None:
    compose = _read(COMPOSE_FILE)

    assert '"127.0.0.1:4318:4318"' in compose
    assert '"4318:4318"' not in compose


def test_health_endpoint_is_bound_to_loopback() -> None:
    compose = _read(COMPOSE_FILE)

    assert '"127.0.0.1:13133:13133"' in compose
    assert '"13133:13133"' not in compose


def test_local_collector_has_otlp_http_receiver() -> None:
    config = _read(
        LOCAL_COLLECTOR_CONFIG_FILE
    )

    assert "receivers:" in config
    assert "otlp:" in config
    assert "http:" in config
    assert "0.0.0.0:4318" in config


def test_local_collector_has_memory_limiter() -> None:
    config = _read(
        LOCAL_COLLECTOR_CONFIG_FILE
    )

    assert "memory_limiter:" in config
    assert "limit_mib: 256" in config
    assert "spike_limit_mib: 64" in config


def test_local_collector_has_batch_processor() -> None:
    config = _read(
        LOCAL_COLLECTOR_CONFIG_FILE
    )

    assert "batch:" in config
    assert "send_batch_size: 512" in config


def test_memory_limiter_precedes_batch() -> None:
    config = _read(
        LOCAL_COLLECTOR_CONFIG_FILE
    )

    pipeline = config.split(
        "pipelines:",
        maxsplit=1,
    )[1]

    memory_position = pipeline.find(
        "- memory_limiter"
    )

    batch_position = pipeline.find(
        "- batch"
    )

    assert memory_position >= 0
    assert batch_position >= 0
    assert memory_position < batch_position


def test_local_collector_has_health_extension() -> None:
    config = _read(
        LOCAL_COLLECTOR_CONFIG_FILE
    )

    assert "health_check:" in config
    assert "0.0.0.0:13133" in config


def test_local_trace_pipeline_uses_debug_exporter() -> None:
    config = _read(
        LOCAL_COLLECTOR_CONFIG_FILE
    )

    assert "traces:" in config
    assert "- otlp" in config
    assert "- memory_limiter" in config
    assert "- batch" in config
    assert "- debug" in config


def test_adot_configuration_exists() -> None:
    assert ADOT_COLLECTOR_CONFIG_FILE.is_file()


def test_adot_has_otlp_receiver() -> None:
    config = _read(
        ADOT_COLLECTOR_CONFIG_FILE
    )

    assert "otlp:" in config
    assert "0.0.0.0:4318" in config


def test_adot_exports_to_xray() -> None:
    config = _read(
        ADOT_COLLECTOR_CONFIG_FILE
    )

    assert "awsxray:" in config
    assert "- awsxray" in config


def test_adot_region_is_environment_driven() -> None:
    config = _read(
        ADOT_COLLECTOR_CONFIG_FILE
    )

    assert (
        "region: ${env:AWS_REGION}"
        in config
    )


def test_adot_keeps_memory_and_batch_processors() -> None:
    config = _read(
        ADOT_COLLECTOR_CONFIG_FILE
    )

    assert "- memory_limiter" in config
    assert "- batch" in config


def test_adot_does_not_use_debug_exporter() -> None:
    config = _read(
        ADOT_COLLECTOR_CONFIG_FILE
    )

    assert "debug:" not in config