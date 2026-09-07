# ============================================================
# CloudWatch Operations Dashboard
#
# SEARCH expressions are intentionally used for application
# metrics whose complete CloudWatch identity contains
# additional low-cardinality dimensions such as EventType,
# Severity, Market, FailureStage, Reason, or ProcessingStatus.
#
# Dashboard objectives:
#
# 1. Application throughput visibility
# 2. Application reliability visibility
# 3. SQS delivery / ACK semantics
# 4. Idempotency / replay protection visibility
# 5. Operational alarm state overview
# 6. SQS queue infrastructure health
# 7. DLQ health
# 8. Alarm threshold visualization
#
# Persistent dashboard ownership belongs to Terraform.
# ============================================================

resource "aws_cloudwatch_dashboard" "operations" {
  dashboard_name = "${local.project_name}-${local.environment}-operations"

  dashboard_body = jsonencode({
    start          = "-PT6H"
    periodOverride = "inherit"

    widgets = concat(
      [
        # ====================================================
        # Risk Engine - Throughput
        # ====================================================
        {
          type   = "metric"
          x      = 0
          y      = 0
          width  = 12
          height = 6

          properties = {
            title   = "Risk Engine - Throughput"
            view    = "timeSeries"
            stacked = false
            period  = 300

            metrics = [
              [
                {
                  expression = "SUM(SEARCH('{${var.metric_namespace}} MetricName=\"MarketEventsProcessed\" Service=\"${var.risk_engine_service_name}\" Environment=\"${local.environment}\"', 'Sum', 300))"
                  label      = "Market Events Processed"
                  id         = "r1"
                }
              ],
              [
                {
                  expression = "SUM(SEARCH('{${var.metric_namespace}} MetricName=\"RiskAlertsGenerated\" Service=\"${var.risk_engine_service_name}\" Environment=\"${local.environment}\"', 'Sum', 300))"
                  label      = "Risk Alerts Generated"
                  id         = "r2"
                }
              ],
              [
                {
                  expression = "SUM(SEARCH('{${var.metric_namespace}} MetricName=\"RiskEventsPublished\" Service=\"${var.risk_engine_service_name}\" Environment=\"${local.environment}\"', 'Sum', 300))"
                  label      = "Risk Events Published"
                  id         = "r3"
                }
              ]
            ]

            yAxis = {
              left = {
                min   = 0
                label = "Events / 5 min"
              }
            }
          }
        },

        # ====================================================
        # Risk Engine - Reliability
        #
        # Period intentionally matches CloudWatch alarms.
        # ====================================================
        {
          type   = "metric"
          x      = 12
          y      = 0
          width  = 12
          height = 6

          properties = {
            title   = "Risk Engine - Reliability"
            view    = "timeSeries"
            stacked = false
            period  = 60

            metrics = [
              [
                var.metric_namespace,
                "RiskProcessingFailures",
                "Service",
                var.risk_engine_service_name,
                "Environment",
                local.environment,
                {
                  stat  = "Sum"
                  label = "Processing Failures"
                }
              ],
              [
                var.metric_namespace,
                "RiskProcessingLatency",
                "Service",
                var.risk_engine_service_name,
                "Environment",
                local.environment,
                {
                  stat  = "Average"
                  label = "Processing Latency (ms)"
                  yAxis = "right"
                }
              ]
            ]

            annotations = {
              horizontal = [
                {
                  label = "Failure alarm threshold"
                  value = var.risk_processing_failure_threshold
                  yAxis = "left"
                  fill  = "above"
                },
                {
                  label = "Latency alarm threshold"
                  value = var.risk_latency_threshold_ms
                  yAxis = "right"
                  fill  = "above"
                }
              ]
            }

            yAxis = {
              left = {
                min   = 0
                label = "Failures / min"
              }

              right = {
                min   = 0
                label = "Milliseconds"
              }
            }
          }
        },

        # ====================================================
        # Alert Worker - Processing
        # ====================================================
        {
          type   = "metric"
          x      = 0
          y      = 6
          width  = 12
          height = 6

          properties = {
            title   = "Alert Worker - Processing"
            view    = "timeSeries"
            stacked = false
            period  = 300

            metrics = [
              [
                {
                  expression = "SUM(SEARCH('{${var.metric_namespace}} MetricName=\"AlertMessagesReceived\" Service=\"${var.alert_worker_service_name}\" Environment=\"${local.environment}\"', 'Sum', 300))"
                  label      = "Messages Received"
                  id         = "a1"
                }
              ],
              [
                {
                  expression = "SUM(SEARCH('{${var.metric_namespace}} MetricName=\"AlertNotificationsPublished\" Service=\"${var.alert_worker_service_name}\" Environment=\"${local.environment}\"', 'Sum', 300))"
                  label      = "Notifications Published"
                  id         = "a2"
                }
              ],
              [
                var.metric_namespace,
                "AlertProcessingCompleted",
                "Service",
                var.alert_worker_service_name,
                "Environment",
                local.environment,
                {
                  stat  = "Sum"
                  label = "Processing Completed"
                }
              ]
            ]

            yAxis = {
              left = {
                min   = 0
                label = "Events / 5 min"
              }
            }
          }
        },

        # ====================================================
        # Alert Worker - Reliability
        #
        # Period intentionally matches CloudWatch alarms.
        # ====================================================
        {
          type   = "metric"
          x      = 12
          y      = 6
          width  = 12
          height = 6

          properties = {
            title   = "Alert Worker - Reliability"
            view    = "timeSeries"
            stacked = false
            period  = 60

            metrics = [
              [
                var.metric_namespace,
                "AlertProcessingFailures",
                "Service",
                var.alert_worker_service_name,
                "Environment",
                local.environment,
                {
                  stat  = "Sum"
                  label = "Processing Failures"
                }
              ],
              [
                var.metric_namespace,
                "AlertProcessingLatency",
                "Service",
                var.alert_worker_service_name,
                "Environment",
                local.environment,
                {
                  stat  = "Average"
                  label = "Processing Latency (ms)"
                  yAxis = "right"
                }
              ]
            ]

            annotations = {
              horizontal = [
                {
                  label = "Failure alarm threshold"
                  value = var.alert_processing_failure_threshold
                  yAxis = "left"
                  fill  = "above"
                },
                {
                  label = "Latency alarm threshold"
                  value = var.alert_latency_threshold_ms
                  yAxis = "right"
                  fill  = "above"
                }
              ]
            }

            yAxis = {
              left = {
                min   = 0
                label = "Failures / min"
              }

              right = {
                min   = 0
                label = "Milliseconds"
              }
            }
          }
        },

        # ====================================================
        # SQS - ACK Semantics
        #
        # Application-level delivery semantics.
        #
        # NotAcknowledged is intentionally displayed but is
        # not treated as a generic failure alarm because
        # IN_PROGRESS can be a valid idempotency state.
        # ====================================================
        {
          type   = "metric"
          x      = 0
          y      = 12
          width  = 12
          height = 6

          properties = {
            title   = "SQS - ACK Semantics"
            view    = "timeSeries"
            stacked = false
            period  = 300

            metrics = [
              [
                {
                  expression = "SUM(SEARCH('{${var.metric_namespace}} MetricName=\"SqsMessagesReceived\" Service=\"${var.alert_worker_service_name}\" Environment=\"${local.environment}\"', 'Sum', 300))"
                  label      = "Received"
                  id         = "s1"
                }
              ],
              [
                {
                  expression = "SUM(SEARCH('{${var.metric_namespace}} MetricName=\"SqsMessagesAcknowledged\" Service=\"${var.alert_worker_service_name}\" Environment=\"${local.environment}\"', 'Sum', 300))"
                  label      = "Acknowledged"
                  id         = "s2"
                }
              ],
              [
                {
                  expression = "SUM(SEARCH('{${var.metric_namespace}} MetricName=\"SqsMessagesNotAcknowledged\" Service=\"${var.alert_worker_service_name}\" Environment=\"${local.environment}\"', 'Sum', 300))"
                  label      = "Not Acknowledged"
                  id         = "s3"
                }
              ],
              [
                {
                  expression = "SUM(SEARCH('{${var.metric_namespace}} MetricName=\"SqsProcessingFailures\" Service=\"${var.alert_worker_service_name}\" Environment=\"${local.environment}\"', 'Sum', 300))"
                  label      = "Processing Failures"
                  id         = "s4"
                }
              ]
            ]

            yAxis = {
              left = {
                min   = 0
                label = "Messages / 5 min"
              }
            }
          }
        },

        # ====================================================
        # Idempotency / Replay Protection
        # ====================================================
        {
          type   = "metric"
          x      = 12
          y      = 12
          width  = 12
          height = 6

          properties = {
            title   = "Idempotency / Replay Protection"
            view    = "timeSeries"
            stacked = false
            period  = 300
            stat    = "Sum"

            metrics = [
              [
                var.metric_namespace,
                "DuplicateAlertsSuppressed",
                "Service",
                var.alert_worker_service_name,
                "Environment",
                local.environment,
                {
                  label = "Duplicates Suppressed"
                }
              ],
              [
                var.metric_namespace,
                "AlertsInProgress",
                "Service",
                var.alert_worker_service_name,
                "Environment",
                local.environment,
                {
                  label = "Alerts In Progress"
                }
              ]
            ]

            yAxis = {
              left = {
                min   = 0
                label = "Events / 5 min"
              }
            }
          }
        }
      ],

      # ======================================================
      # Operational Alarm Status
      #
      # Always contains the five application alarms.
      #
      # Queue / DLQ alarms are appended only when their
      # corresponding Terraform resources are enabled.
      # ======================================================
      [
        {
          type   = "alarm"
          x      = 0
          y      = 18
          width  = 24
          height = 6

          properties = {
            title  = "Operational Alarm Status"
            sortBy = "stateUpdatedTimestamp"

            alarms = concat(
              [
                aws_cloudwatch_metric_alarm
                .risk_processing_failures
                .arn,

                aws_cloudwatch_metric_alarm
                .alert_processing_failures
                .arn,

                aws_cloudwatch_metric_alarm
                .risk_processing_latency
                .arn,

                aws_cloudwatch_metric_alarm
                .alert_processing_latency
                .arn,

                aws_cloudwatch_metric_alarm
                .sqs_ack_failures
                .arn
              ],

              local.alert_queue_enabled ? [
                aws_cloudwatch_metric_alarm
                .alert_queue_backlog[0]
                .arn,

                aws_cloudwatch_metric_alarm
                .alert_queue_age[0]
                .arn
              ] : [],

              local.alert_dlq_enabled ? [
                aws_cloudwatch_metric_alarm
                .alert_dlq_messages[0]
                .arn
              ] : []
            )
          }
        }
      ],

      # ======================================================
      # AWS/SQS Queue Health
      #
      # Infrastructure-level view.
      #
      # This is intentionally separate from application-level
      # SQS ACK semantics.
      # ======================================================
      local.alert_queue_enabled ? [
        {
          type   = "metric"
          x      = 0
          y      = 24
          width  = 12
          height = 6

          properties = {
            title   = "SQS - Queue Health"
            view    = "timeSeries"
            stacked = false
            period  = 60

            metrics = [
              [
                "AWS/SQS",
                "ApproximateNumberOfMessagesVisible",
                "QueueName",
                trimspace(var.alert_queue_name),
                {
                  stat  = "Maximum"
                  label = "Visible Messages"
                }
              ],
              [
                "AWS/SQS",
                "ApproximateAgeOfOldestMessage",
                "QueueName",
                trimspace(var.alert_queue_name),
                {
                  stat  = "Maximum"
                  label = "Oldest Message Age (s)"
                  yAxis = "right"
                }
              ]
            ]

            annotations = {
              horizontal = [
                {
                  label = "Backlog alarm threshold"
                  value = var.queue_backlog_threshold
                  yAxis = "left"
                  fill  = "above"
                },
                {
                  label = "Message age alarm threshold"
                  value = var.queue_age_threshold_seconds
                  yAxis = "right"
                  fill  = "above"
                }
              ]
            }

            yAxis = {
              left = {
                min   = 0
                label = "Messages"
              }

              right = {
                min   = 0
                label = "Seconds"
              }
            }
          }
        }
      ] : [],

      # ======================================================
      # AWS/SQS DLQ Health
      #
      # A non-zero DLQ generally means normal retry policy
      # could not recover one or more notification events.
      # ======================================================
      local.alert_dlq_enabled ? [
        {
          type   = "metric"
          x      = 12
          y      = 24
          width  = 12
          height = 6

          properties = {
            title   = "SQS - DLQ Health"
            view    = "timeSeries"
            stacked = false
            period  = 60
            stat    = "Maximum"

            metrics = [
              [
                "AWS/SQS",
                "ApproximateNumberOfMessagesVisible",
                "QueueName",
                trimspace(var.alert_dlq_name),
                {
                  label = "DLQ Visible Messages"
                }
              ]
            ]

            annotations = {
              horizontal = [
                {
                  label = "DLQ alarm threshold"
                  value = var.dlq_message_threshold
                  yAxis = "left"
                  fill  = "above"
                }
              ]
            }

            yAxis = {
              left = {
                min   = 0
                label = "Messages"
              }
            }
          }
        }
      ] : []
    )
  })
}