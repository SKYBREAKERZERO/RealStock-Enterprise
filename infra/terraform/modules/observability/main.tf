locals {
  project_name = lower(
    trimspace(var.project_name)
  )

  environment = lower(
    trimspace(var.environment)
  )

  common_tags = merge(
    {
      Project     = local.project_name
      Environment = local.environment
      ManagedBy   = "Terraform"
      Component   = "Observability"
    },
    var.tags
  )

  ops_topic_name = (
    "${local.project_name}-${local.environment}-ops-alerts"
  )

  alert_queue_enabled = (
    length(
      trimspace(var.alert_queue_name)
    ) > 0
  )

  alert_dlq_enabled = (
    length(
      trimspace(var.alert_dlq_name)
    ) > 0
  )
}


# ============================================================
# Operations SNS Topic
#
# This topic is intentionally separate from the application's
# business notification SNS topic.
#
# Business SNS:
#   risk.alert.detected -> user/business notification
#
# Operations SNS:
#   CloudWatch ALARM/OK -> operator notification
# ============================================================

resource "aws_sns_topic" "ops_alerts" {
  name = (
    local.ops_topic_name
  )

  kms_master_key_id = (
    var.ops_topic_kms_key_id
  )

  tags = merge(
    local.common_tags,
    {
      Name = (
        local.ops_topic_name
      )

      Purpose = "OperationalAlerting"
    }
  )
}


# ============================================================
# Risk Engine - Processing Failures
# ============================================================

resource "aws_cloudwatch_metric_alarm" "risk_processing_failures" {
  alarm_name = "${local.project_name}-${local.environment}-risk-engine-processing-failures-critical"

  alarm_description = <<-EOT
アラーム内容:
Risk Engine の処理失敗を検知しました。

影響範囲:
市場イベントがリスクイベントへ変換されず、
リスク通知が欠落する可能性があります。

処置手順:
1. Risk Engine の構造化ログを確認する。
2. Kinesis consumer の処理状態を確認する。
3. EventBridge API エラーを確認する。
4. correlation_id を利用して関連ログを追跡する。

担当:
Platform / SRE
EOT

  namespace = (
    var.metric_namespace
  )

  metric_name = (
    "RiskProcessingFailures"
  )

  dimensions = {
    Service = (
      var.risk_engine_service_name
    )

    Environment = (
      local.environment
    )
  }

  statistic = "Sum"
  period    = 60

  evaluation_periods  = 1
  datapoints_to_alarm = 1

  threshold = (
    var.risk_processing_failure_threshold
  )

  comparison_operator = (
    "GreaterThanOrEqualToThreshold"
  )

  treat_missing_data = (
    "notBreaching"
  )

  alarm_actions = [
    aws_sns_topic.ops_alerts.arn
  ]

  ok_actions = [
    aws_sns_topic.ops_alerts.arn
  ]

  tags = local.common_tags
}


# ============================================================
# Alert Worker - Processing Failures
# ============================================================

resource "aws_cloudwatch_metric_alarm" "alert_processing_failures" {
  alarm_name = "${local.project_name}-${local.environment}-alert-worker-processing-failures-critical"

  alarm_description = <<-EOT
アラーム内容:
Alert Worker の処理失敗を検知しました。

影響範囲:
リスク通知が SNS へ配信されず、
SQS メッセージが再試行される可能性があります。

処置手順:
1. Alert Worker の構造化ログを確認する。
2. DynamoDB idempotency 状態を確認する。
3. SNS publish error を確認する。
4. SQS retry / DLQ 状態を確認する。

担当:
Platform / SRE
EOT

  namespace = (
    var.metric_namespace
  )

  metric_name = (
    "AlertProcessingFailures"
  )

  dimensions = {
    Service = (
      var.alert_worker_service_name
    )

    Environment = (
      local.environment
    )
  }

  statistic = "Sum"
  period    = 60

  evaluation_periods  = 1
  datapoints_to_alarm = 1

  threshold = (
    var.alert_processing_failure_threshold
  )

  comparison_operator = (
    "GreaterThanOrEqualToThreshold"
  )

  treat_missing_data = (
    "notBreaching"
  )

  alarm_actions = [
    aws_sns_topic.ops_alerts.arn
  ]

  ok_actions = [
    aws_sns_topic.ops_alerts.arn
  ]

  tags = local.common_tags
}


# ============================================================
# Risk Engine - Processing Latency
#
# 3 of 5 periods must breach.
# ============================================================

resource "aws_cloudwatch_metric_alarm" "risk_processing_latency" {
  alarm_name = "${local.project_name}-${local.environment}-risk-engine-processing-latency-warning"

  alarm_description = <<-EOT
アラーム内容:
Risk Engine の処理レイテンシが継続的に高い状態です。

影響範囲:
リアルタイムリスク検知の遅延が発生する可能性があります。

処置手順:
1. RiskProcessingLatency の推移を確認する。
2. Kinesis backlog を確認する。
3. downstream AWS API latency を確認する。
4. CPU / memory / task saturation を確認する。

担当:
Platform / SRE
EOT

  namespace = (
    var.metric_namespace
  )

  metric_name = (
    "RiskProcessingLatency"
  )

  dimensions = {
    Service = (
      var.risk_engine_service_name
    )

    Environment = (
      local.environment
    )
  }

  statistic = "Average"
  period    = 60

  evaluation_periods  = 5
  datapoints_to_alarm = 3

  threshold = (
    var.risk_latency_threshold_ms
  )

  comparison_operator = (
    "GreaterThanThreshold"
  )

  treat_missing_data = (
    "notBreaching"
  )

  alarm_actions = [
    aws_sns_topic.ops_alerts.arn
  ]

  ok_actions = [
    aws_sns_topic.ops_alerts.arn
  ]

  tags = local.common_tags
}


# ============================================================
# Alert Worker - Processing Latency
# ============================================================

resource "aws_cloudwatch_metric_alarm" "alert_processing_latency" {
  alarm_name = "${local.project_name}-${local.environment}-alert-worker-processing-latency-warning"

  alarm_description = <<-EOT
アラーム内容:
Alert Worker の処理レイテンシが継続的に高い状態です。

影響範囲:
ユーザーへのリスク通知が遅延する可能性があります。

処置手順:
1. AlertProcessingLatency を確認する。
2. DynamoDB latency を確認する。
3. SNS publish latency を確認する。
4. SQS queue backlog を確認する。

担当:
Platform / SRE
EOT

  namespace = (
    var.metric_namespace
  )

  metric_name = (
    "AlertProcessingLatency"
  )

  dimensions = {
    Service = (
      var.alert_worker_service_name
    )

    Environment = (
      local.environment
    )
  }

  statistic = "Average"
  period    = 60

  evaluation_periods  = 5
  datapoints_to_alarm = 3

  threshold = (
    var.alert_latency_threshold_ms
  )

  comparison_operator = (
    "GreaterThanThreshold"
  )

  treat_missing_data = (
    "notBreaching"
  )

  alarm_actions = [
    aws_sns_topic.ops_alerts.arn
  ]

  ok_actions = [
    aws_sns_topic.ops_alerts.arn
  ]

  tags = local.common_tags
}


# ============================================================
# Alert Worker - SQS ACK Failure
#
# Metric identity:
#
# Service=alert-worker
# Environment=<environment>
# FailureStage=ACK
# ============================================================

resource "aws_cloudwatch_metric_alarm" "sqs_ack_failures" {
  alarm_name = "${local.project_name}-${local.environment}-alert-worker-ack-failures-critical"

  alarm_description = <<-EOT
アラーム内容:
Alert Worker の SQS ACK 失敗を検知しました。

影響範囲:
処理済みメッセージが再配信され、
重複処理が発生する可能性があります。

処置手順:
1. SqsProcessingFailures を確認する。
2. FailureStage=ACK のログを確認する。
3. SQS DeleteMessage API エラーを確認する。
4. DynamoDB idempotency 状態を確認する。

担当:
Platform / SRE
EOT

  namespace = (
    var.metric_namespace
  )

  metric_name = (
    "SqsProcessingFailures"
  )

  dimensions = {
    Service = (
      var.alert_worker_service_name
    )

    Environment = (
      local.environment
    )

    FailureStage = "ACK"
  }

  statistic = "Sum"
  period    = 60

  evaluation_periods  = 1
  datapoints_to_alarm = 1

  threshold = (
    var.ack_failure_threshold
  )

  comparison_operator = (
    "GreaterThanOrEqualToThreshold"
  )

  treat_missing_data = (
    "notBreaching"
  )

  alarm_actions = [
    aws_sns_topic.ops_alerts.arn
  ]

  ok_actions = [
    aws_sns_topic.ops_alerts.arn
  ]

  tags = local.common_tags
}


# ============================================================
# SQS Queue Backlog
# ============================================================

resource "aws_cloudwatch_metric_alarm" "alert_queue_backlog" {
  count = (
    local.alert_queue_enabled
    ? 1
    : 0
  )

  alarm_name = "${local.project_name}-${local.environment}-alert-worker-queue-backlog-warning"

  alarm_description = <<-EOT
アラーム内容:
Alert Worker SQS queue の backlog が増加しています。

影響範囲:
リスク通知処理が遅延する可能性があります。

処置手順:
1. ApproximateNumberOfMessagesVisible を確認する。
2. Alert Worker task health を確認する。
3. processing latency / failure を確認する。
4. 必要に応じて worker capacity を確認する。

担当:
Platform / SRE
EOT

  namespace = "AWS/SQS"

  metric_name = (
    "ApproximateNumberOfMessagesVisible"
  )

  dimensions = {
    QueueName = (
      trimspace(
        var.alert_queue_name
      )
    )
  }

  statistic = "Maximum"
  period    = 60

  evaluation_periods  = 3
  datapoints_to_alarm = 2

  threshold = (
    var.queue_backlog_threshold
  )

  comparison_operator = (
    "GreaterThanThreshold"
  )

  treat_missing_data = (
    "notBreaching"
  )

  alarm_actions = [
    aws_sns_topic.ops_alerts.arn
  ]

  ok_actions = [
    aws_sns_topic.ops_alerts.arn
  ]

  tags = local.common_tags
}


# ============================================================
# SQS Queue Oldest Message Age
# ============================================================

resource "aws_cloudwatch_metric_alarm" "alert_queue_age" {
  count = (
    local.alert_queue_enabled
    ? 1
    : 0
  )

  alarm_name = "${local.project_name}-${local.environment}-alert-worker-queue-age-critical"

  alarm_description = <<-EOT
アラーム内容:
Alert Worker SQS queue の最古メッセージ滞留時間が閾値を超えました。

影響範囲:
リスク通知が長時間遅延している可能性があります。

処置手順:
1. ApproximateAgeOfOldestMessage を確認する。
2. Worker failure / latency を確認する。
3. downstream SNS / DynamoDB の状態を確認する。
4. DLQ への redrive 状態を確認する。

担当:
Platform / SRE
EOT

  namespace = "AWS/SQS"

  metric_name = (
    "ApproximateAgeOfOldestMessage"
  )

  dimensions = {
    QueueName = (
      trimspace(
        var.alert_queue_name
      )
    )
  }

  statistic = "Maximum"
  period    = 60

  evaluation_periods  = 2
  datapoints_to_alarm = 2

  threshold = (
    var.queue_age_threshold_seconds
  )

  comparison_operator = (
    "GreaterThanThreshold"
  )

  treat_missing_data = (
    "notBreaching"
  )

  alarm_actions = [
    aws_sns_topic.ops_alerts.arn
  ]

  ok_actions = [
    aws_sns_topic.ops_alerts.arn
  ]

  tags = local.common_tags
}


# ============================================================
# Alert Worker DLQ
# ============================================================

resource "aws_cloudwatch_metric_alarm" "alert_dlq_messages" {
  count = (
    local.alert_dlq_enabled
    ? 1
    : 0
  )

  alarm_name = "${local.project_name}-${local.environment}-alert-worker-dlq-messages-critical"

  alarm_description = <<-EOT
アラーム内容:
Alert Worker DLQ にメッセージが存在します。

影響範囲:
通常の retry で回復できなかったリスク通知が存在します。

処置手順:
1. DLQ message count を確認する。
2. DLQ message payload と error logs を確認する。
3. 原因を修正してから replay を実施する。
4. replay 後に idempotency 状態を確認する。

担当:
Platform / SRE
EOT

  namespace = "AWS/SQS"

  metric_name = (
    "ApproximateNumberOfMessagesVisible"
  )

  dimensions = {
    QueueName = (
      trimspace(
        var.alert_dlq_name
      )
    )
  }

  statistic = "Maximum"
  period    = 60

  evaluation_periods  = 1
  datapoints_to_alarm = 1

  threshold = (
    var.dlq_message_threshold
  )

  comparison_operator = (
    "GreaterThanOrEqualToThreshold"
  )

  treat_missing_data = (
    "notBreaching"
  )

  alarm_actions = [
    aws_sns_topic.ops_alerts.arn
  ]

  ok_actions = [
    aws_sns_topic.ops_alerts.arn
  ]

  tags = local.common_tags
}
