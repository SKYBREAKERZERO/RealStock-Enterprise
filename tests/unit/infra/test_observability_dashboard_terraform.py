from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

OBSERVABILITY_MODULE = (
    REPO_ROOT
    / "infra"
    / "terraform"
    / "modules"
    / "observability"
)

MAIN_TF = OBSERVABILITY_MODULE / "main.tf"
DASHBOARD_TF = OBSERVABILITY_MODULE / "dashboard.tf"
OUTPUTS_TF = OBSERVABILITY_MODULE / "outputs.tf"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _title_pattern(title: str) -> str:
    return rf'title\s*=\s*"{re.escape(title)}"'


def _title_offset(
    source: str,
    title: str,
) -> int:
    match = re.search(
        _title_pattern(title),
        source,
    )

    assert match is not None, (
        f"dashboard title not found: {title}"
    )

    return match.start()


@pytest.fixture(scope="module")
def main_tf() -> str:
    return _read(MAIN_TF)


@pytest.fixture(scope="module")
def dashboard_tf() -> str:
    return _read(DASHBOARD_TF)


@pytest.fixture(scope="module")
def outputs_tf() -> str:
    return _read(OUTPUTS_TF)


def test_dashboard_resource_is_owned_by_dashboard_tf(
    main_tf: str,
    dashboard_tf: str,
) -> None:
    resource_pattern = (
        r'resource\s+'
        r'"aws_cloudwatch_dashboard"\s+'
        r'"operations"'
    )

    assert re.search(
        resource_pattern,
        dashboard_tf,
    )

    assert not re.search(
        resource_pattern,
        main_tf,
    )


def test_dashboard_resource_address_is_stable(
    dashboard_tf: str,
) -> None:
    resource_pattern = (
        r'resource\s+'
        r'"aws_cloudwatch_dashboard"\s+'
        r'"operations"'
    )

    dashboard_name_pattern = (
        r'dashboard_name\s*=\s*'
        r'"\$\{local\.project_name\}'
        r'-\$\{local\.environment\}'
        r'-operations"'
    )

    assert re.search(
        resource_pattern,
        dashboard_tf,
    )

    assert re.search(
        dashboard_name_pattern,
        dashboard_tf,
    )


def test_dashboard_uses_composed_widget_lists(
    dashboard_tf: str,
) -> None:
    assert re.search(
        r"widgets\s*=\s*concat\s*\(",
        dashboard_tf,
    )


@pytest.mark.parametrize(
    "title",
    [
        "Risk Engine - Throughput",
        "Risk Engine - Reliability",
        "Alert Worker - Processing",
        "Alert Worker - Reliability",
        "SQS - ACK Semantics",
        "Idempotency / Replay Protection",
        "Operational Alarm Status",
        "SQS - Queue Health",
        "SQS - DLQ Health",
    ],
)
def test_dashboard_contains_required_operational_views(
    dashboard_tf: str,
    title: str,
) -> None:
    assert re.search(
        _title_pattern(title),
        dashboard_tf,
    )


@pytest.mark.parametrize(
    "alarm_reference",
    [
        "risk_processing_failures",
        "alert_processing_failures",
        "risk_processing_latency",
        "alert_processing_latency",
        "sqs_ack_failures",
    ],
)
def test_alarm_status_widget_contains_application_alarms(
    dashboard_tf: str,
    alarm_reference: str,
) -> None:
    pattern = (
        r"aws_cloudwatch_metric_alarm\s*"
        rf"\.{re.escape(alarm_reference)}\s*"
        r"\.arn"
    )

    assert re.search(
        pattern,
        dashboard_tf,
    )


def test_optional_queue_alarms_are_conditionally_composed(
    dashboard_tf: str,
) -> None:
    assert re.search(
        r"local\.alert_queue_enabled\s*\?\s*\[",
        dashboard_tf,
    )

    assert re.search(
        r"aws_cloudwatch_metric_alarm\s*"
        r"\.alert_queue_backlog\[0\]\s*"
        r"\.arn",
        dashboard_tf,
    )

    assert re.search(
        r"aws_cloudwatch_metric_alarm\s*"
        r"\.alert_queue_age\[0\]\s*"
        r"\.arn",
        dashboard_tf,
    )


def test_optional_dlq_alarm_is_conditionally_composed(
    dashboard_tf: str,
) -> None:
    assert re.search(
        r"local\.alert_dlq_enabled\s*\?\s*\[",
        dashboard_tf,
    )

    assert re.search(
        r"aws_cloudwatch_metric_alarm\s*"
        r"\.alert_dlq_messages\[0\]\s*"
        r"\.arn",
        dashboard_tf,
    )


@pytest.mark.parametrize(
    "threshold_variable",
    [
        "var.risk_processing_failure_threshold",
        "var.risk_latency_threshold_ms",
        "var.alert_processing_failure_threshold",
        "var.alert_latency_threshold_ms",
        "var.queue_backlog_threshold",
        "var.queue_age_threshold_seconds",
        "var.dlq_message_threshold",
    ],
)
def test_dashboard_visualizes_alarm_thresholds(
    dashboard_tf: str,
    threshold_variable: str,
) -> None:
    assert threshold_variable in dashboard_tf


def test_queue_health_uses_native_sqs_metrics(
    dashboard_tf: str,
) -> None:
    assert '"AWS/SQS"' in dashboard_tf

    assert (
        "ApproximateNumberOfMessagesVisible"
        in dashboard_tf
    )

    assert (
        "ApproximateAgeOfOldestMessage"
        in dashboard_tf
    )

    assert (
        "trimspace(var.alert_queue_name)"
        in dashboard_tf
    )

    assert (
        "trimspace(var.alert_dlq_name)"
        in dashboard_tf
    )


@pytest.mark.parametrize(
    "metric_name",
    [
        "SqsMessagesReceived",
        "SqsMessagesAcknowledged",
        "SqsMessagesNotAcknowledged",
        "SqsProcessingFailures",
    ],
)
def test_ack_semantics_remain_visible(
    dashboard_tf: str,
    metric_name: str,
) -> None:
    assert metric_name in dashboard_tf


def test_reliability_widgets_use_alarm_granularity(
    dashboard_tf: str,
) -> None:
    risk_start = _title_offset(
        dashboard_tf,
        "Risk Engine - Reliability",
    )

    alert_processing_start = _title_offset(
        dashboard_tf,
        "Alert Worker - Processing",
    )

    alert_reliability_start = _title_offset(
        dashboard_tf,
        "Alert Worker - Reliability",
    )

    sqs_start = _title_offset(
        dashboard_tf,
        "SQS - ACK Semantics",
    )

    risk_section = dashboard_tf[
        risk_start:alert_processing_start
    ]

    alert_section = dashboard_tf[
        alert_reliability_start:sqs_start
    ]

    assert re.search(
        r"period\s*=\s*60",
        risk_section,
    )

    assert re.search(
        r"period\s*=\s*60",
        alert_section,
    )


def test_reliability_widgets_keep_expected_statistics(
    dashboard_tf: str,
) -> None:
    risk_start = _title_offset(
        dashboard_tf,
        "Risk Engine - Reliability",
    )

    alert_processing_start = _title_offset(
        dashboard_tf,
        "Alert Worker - Processing",
    )

    alert_reliability_start = _title_offset(
        dashboard_tf,
        "Alert Worker - Reliability",
    )

    sqs_start = _title_offset(
        dashboard_tf,
        "SQS - ACK Semantics",
    )

    risk_section = dashboard_tf[
        risk_start:alert_processing_start
    ]

    alert_section = dashboard_tf[
        alert_reliability_start:sqs_start
    ]

    assert "RiskProcessingFailures" in risk_section
    assert "RiskProcessingLatency" in risk_section
    assert 'stat  = "Sum"' in risk_section
    assert 'stat  = "Average"' in risk_section

    assert "AlertProcessingFailures" in alert_section
    assert "AlertProcessingLatency" in alert_section
    assert 'stat  = "Sum"' in alert_section
    assert 'stat  = "Average"' in alert_section


def test_alarm_status_widget_uses_state_updated_sorting(
    dashboard_tf: str,
) -> None:
    alarm_start = _title_offset(
        dashboard_tf,
        "Operational Alarm Status",
    )

    queue_start = _title_offset(
        dashboard_tf,
        "SQS - Queue Health",
    )

    alarm_section = dashboard_tf[
        alarm_start:queue_start
    ]

    assert re.search(
        r'sortBy\s*=\s*"stateUpdatedTimestamp"',
        alarm_section,
    )


def test_queue_health_is_conditionally_rendered(
    dashboard_tf: str,
) -> None:
    queue_title = _title_offset(
        dashboard_tf,
        "SQS - Queue Health",
    )

    queue_condition = dashboard_tf.rfind(
        "local.alert_queue_enabled ? [",
        0,
        queue_title,
    )

    assert queue_condition != -1


def test_dlq_health_is_conditionally_rendered(
    dashboard_tf: str,
) -> None:
    dlq_title = _title_offset(
        dashboard_tf,
        "SQS - DLQ Health",
    )

    dlq_condition = dashboard_tf.rfind(
        "local.alert_dlq_enabled ? [",
        0,
        dlq_title,
    )

    assert dlq_condition != -1


def test_queue_health_contains_threshold_annotations(
    dashboard_tf: str,
) -> None:
    queue_start = _title_offset(
        dashboard_tf,
        "SQS - Queue Health",
    )

    dlq_start = _title_offset(
        dashboard_tf,
        "SQS - DLQ Health",
    )

    queue_section = dashboard_tf[
        queue_start:dlq_start
    ]

    assert (
        "var.queue_backlog_threshold"
        in queue_section
    )

    assert (
        "var.queue_age_threshold_seconds"
        in queue_section
    )

    assert re.search(
        r"annotations\s*=\s*\{",
        queue_section,
    )

    assert re.search(
        r"horizontal\s*=\s*\[",
        queue_section,
    )


def test_dlq_health_contains_threshold_annotation(
    dashboard_tf: str,
) -> None:
    dlq_start = _title_offset(
        dashboard_tf,
        "SQS - DLQ Health",
    )

    dlq_section = dashboard_tf[
        dlq_start:
    ]

    assert (
        "var.dlq_message_threshold"
        in dlq_section
    )

    assert re.search(
        r"annotations\s*=\s*\{",
        dlq_section,
    )


@pytest.mark.parametrize(
    "output_name",
    [
        "operations_dashboard_name",
        "operations_dashboard_arn",
    ],
)
def test_dashboard_outputs_are_exposed(
    outputs_tf: str,
    output_name: str,
) -> None:
    pattern = (
        rf'output\s+"{re.escape(output_name)}"'
    )

    assert re.search(
        pattern,
        outputs_tf,
    )


def test_dashboard_outputs_reference_stable_resource(
    outputs_tf: str,
) -> None:
    name_pattern = (
        r"aws_cloudwatch_dashboard\s*"
        r"\.operations\s*"
        r"\.dashboard_name"
    )

    arn_pattern = (
        r"aws_cloudwatch_dashboard\s*"
        r"\.operations\s*"
        r"\.dashboard_arn"
    )

    assert re.search(
        name_pattern,
        outputs_tf,
    )

    assert re.search(
        arn_pattern,
        outputs_tf,
    )