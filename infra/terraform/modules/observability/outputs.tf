output "ops_alarm_topic_arn" {
  description = "ARN of the operational alarm SNS topic."

  value = (
    aws_sns_topic.ops_alerts.arn
  )
}


output "ops_alarm_topic_name" {
  description = "Name of the operational alarm SNS topic."

  value = (
    aws_sns_topic.ops_alerts.name
  )
}


output "application_alarm_names" {
  description = "Application-level CloudWatch alarm names."

  value = {
    risk_processing_failures = (
      aws_cloudwatch_metric_alarm
      .risk_processing_failures
      .alarm_name
    )

    alert_processing_failures = (
      aws_cloudwatch_metric_alarm
      .alert_processing_failures
      .alarm_name
    )

    risk_processing_latency = (
      aws_cloudwatch_metric_alarm
      .risk_processing_latency
      .alarm_name
    )

    alert_processing_latency = (
      aws_cloudwatch_metric_alarm
      .alert_processing_latency
      .alarm_name
    )

    sqs_ack_failures = (
      aws_cloudwatch_metric_alarm
      .sqs_ack_failures
      .alarm_name
    )
  }
}


output "alert_queue_backlog_alarm_name" {
  description = "Queue backlog alarm name when enabled."

  value = try(
    aws_cloudwatch_metric_alarm
    .alert_queue_backlog[0]
    .alarm_name,
    null
  )
}


output "alert_queue_age_alarm_name" {
  description = "Queue age alarm name when enabled."

  value = try(
    aws_cloudwatch_metric_alarm
    .alert_queue_age[0]
    .alarm_name,
    null
  )
}


output "alert_dlq_alarm_name" {
  description = "DLQ alarm name when enabled."

  value = try(
    aws_cloudwatch_metric_alarm
    .alert_dlq_messages[0]
    .alarm_name,
    null
  )
}

output "operations_dashboard_name" {
  description = "Name of the RealStock CloudWatch operations dashboard."

  value = (
    aws_cloudwatch_dashboard
    .operations
    .dashboard_name
  )
}


output "operations_dashboard_arn" {
  description = "ARN of the RealStock CloudWatch operations dashboard."

  value = (
    aws_cloudwatch_dashboard
    .operations
    .dashboard_arn
  )
}