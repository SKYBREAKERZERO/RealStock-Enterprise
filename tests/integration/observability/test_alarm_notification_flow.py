from __future__ import annotations

import json
import time
from typing import Any
from uuid import uuid4

import pytest

from libs.aws import (
    get_cloudwatch_client,
    get_sns_client,
    get_sqs_client,
)
from libs.observability import (
    AlarmComparisonOperator,
    AlarmDefinition,
    CloudWatchAlarmManager,
    MetricUnit,
)

pytestmark = pytest.mark.integration


def wait_for_alarm(
    *,
    cloudwatch: Any,
    alarm_name: str,
) -> dict[str, Any]:
    for _ in range(20):
        response = cloudwatch.describe_alarms(
            AlarmNames=[
                alarm_name
            ]
        )

        alarms = response.get(
            "MetricAlarms",
            [],
        )

        if alarms:
            return alarms[0]

        time.sleep(
            0.25
        )

    raise AssertionError(
        "CloudWatch alarm was not created"
    )


def wait_for_sqs_message(
    *,
    sqs: Any,
    queue_url: str,
) -> dict[str, Any]:
    for _ in range(20):
        response = sqs.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=1,
        )

        messages = response.get(
            "Messages",
            [],
        )

        if messages:
            return messages[0]

    raise AssertionError(
        "SNS alarm notification was not "
        "delivered to SQS"
    )


def test_cloudwatch_alarm_delivers_notification_through_sns() -> None:
    cloudwatch = (
        get_cloudwatch_client()
    )

    sns = get_sns_client()
    sqs = get_sqs_client()

    suffix = uuid4().hex[:8]

    topic_name = (
        f"realstock-test-ops-{suffix}"
    )

    queue_name = (
        f"realstock-test-alarm-{suffix}"
    )

    alarm_name = (
        f"realstock-test-risk-failure-"
        f"{suffix}"
    )

    namespace = (
        f"RealStock/Integration/{suffix}"
    )

    topic_arn: str | None = None
    queue_url: str | None = None
    subscription_arn: str | None = None

    manager = CloudWatchAlarmManager(
        client=cloudwatch
    )

    try:
        # --------------------------------------------------
        # Operations SNS topic
        # --------------------------------------------------

        topic_response = sns.create_topic(
            Name=topic_name
        )

        topic_arn = topic_response[
            "TopicArn"
        ]

        # --------------------------------------------------
        # SQS verification endpoint
        # --------------------------------------------------

        queue_response = sqs.create_queue(
            QueueName=queue_name
        )

        queue_url = queue_response[
            "QueueUrl"
        ]

        attributes = (
            sqs.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=[
                    "QueueArn"
                ],
            )
        )

        queue_arn = attributes[
            "Attributes"
        ][
            "QueueArn"
        ]

        queue_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": (
                        "AllowOperationsSns"
                    ),
                    "Effect": "Allow",
                    "Principal": {
                        "Service": (
                            "sns.amazonaws.com"
                        )
                    },
                    "Action": (
                        "sqs:SendMessage"
                    ),
                    "Resource": queue_arn,
                    "Condition": {
                        "ArnEquals": {
                            "aws:SourceArn": (
                                topic_arn
                            )
                        }
                    },
                }
            ],
        }

        sqs.set_queue_attributes(
            QueueUrl=queue_url,
            Attributes={
                "Policy": json.dumps(
                    queue_policy
                )
            },
        )

        # --------------------------------------------------
        # SNS -> SQS subscription
        # --------------------------------------------------

        subscription_response = (
            sns.subscribe(
                TopicArn=topic_arn,
                Protocol="sqs",
                Endpoint=queue_arn,
                Attributes={
                    "RawMessageDelivery":
                        "false"
                },
                ReturnSubscriptionArn=True,
            )
        )

        subscription_arn = (
            subscription_response.get(
                "SubscriptionArn"
            )
        )

        # --------------------------------------------------
        # CloudWatch Alarm -> SNS action
        # --------------------------------------------------

        alarm = AlarmDefinition(
            name=alarm_name,
            metric_name=(
                "RiskProcessingFailures"
            ),
            namespace=namespace,
            threshold=1,
            comparison_operator=(
                AlarmComparisonOperator
                .GREATER_THAN_OR_EQUAL
            ),
            period_seconds=60,
            evaluation_periods=1,
            datapoints_to_alarm=1,
            unit=MetricUnit.COUNT,
            dimensions={
                "Service":
                    "risk-engine",
                "Environment":
                    "integration",
            },
            alarm_actions=(
                topic_arn,
            ),
            description=(
                "Day 12 alarm notification "
                "integration test"
            ),
        )

        manager.put_alarm(
            alarm
        )

        created_alarm = wait_for_alarm(
            cloudwatch=cloudwatch,
            alarm_name=alarm_name,
        )

        assert (
            created_alarm[
                "AlarmName"
            ]
            == alarm_name
        )

        assert (
            created_alarm[
                "AlarmActions"
            ]
            == [
                topic_arn
            ]
        )

        # --------------------------------------------------
        # Force a deterministic ALARM transition.
        #
        # This validates:
        #
        # CloudWatch alarm state change
        #       -> SNS action
        #       -> SQS delivery
        #
        # The separate CloudWatch metrics integration test
        # already validates PutMetricData delivery.
        # --------------------------------------------------

        cloudwatch.set_alarm_state(
            AlarmName=alarm_name,
            StateValue="ALARM",
            StateReason=(
                "Day 12 integration test"
            ),
        )

        message = wait_for_sqs_message(
            sqs=sqs,
            queue_url=queue_url,
        )

        body = json.loads(
            message["Body"]
        )

        assert (
            body["Type"]
            == "Notification"
        )

        assert (
            body["TopicArn"]
            == topic_arn
        )

        alarm_notification = (
            json.loads(
                body["Message"]
            )
        )

        assert (
            alarm_notification[
                "AlarmName"
            ]
            == alarm_name
        )

        assert (
            alarm_notification[
                "NewStateValue"
            ]
            == "ALARM"
        )

        sqs.delete_message(
            QueueUrl=queue_url,
            ReceiptHandle=(
                message[
                    "ReceiptHandle"
                ]
            ),
        )

    finally:
        try:
            manager.delete_alarm(
                alarm_name
            )
        except Exception:
            pass

        if (
            subscription_arn
            and subscription_arn
            != "pending confirmation"
        ):
            try:
                sns.unsubscribe(
                    SubscriptionArn=(
                        subscription_arn
                    )
                )
            except Exception:
                pass

        if topic_arn:
            try:
                sns.delete_topic(
                    TopicArn=topic_arn
                )
            except Exception:
                pass

        if queue_url:
            try:
                sqs.delete_queue(
                    QueueUrl=queue_url
                )
            except Exception:
                pass