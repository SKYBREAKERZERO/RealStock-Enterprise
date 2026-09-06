variable "project_name" {
  description = "Project name used in resource names."
  type        = string
  default     = "realstock"

  validation {
    condition = (
      length(
        trimspace(
          var.project_name
        )
      ) > 0
    )

    error_message = "project_name must not be empty."
  }
}


variable "environment" {
  description = "Deployment environment."
  type        = string

  validation {
    condition = (
      length(
        trimspace(
          var.environment
        )
      ) > 0
    )

    error_message = "environment must not be empty."
  }
}


variable "metric_namespace" {
  description = "CloudWatch namespace for application metrics."
  type        = string
  default     = "RealStock/Applications"

  validation {
    condition = (
      length(
        trimspace(
          var.metric_namespace
        )
      ) > 0
    )

    error_message = "metric_namespace must not be empty."
  }
}


variable "risk_engine_service_name" {
  description = "Service dimension value used by Risk Engine metrics."
  type        = string
  default     = "risk-engine"

  validation {
    condition = (
      length(
        trimspace(
          var.risk_engine_service_name
        )
      ) > 0
    )

    error_message = "risk_engine_service_name must not be empty."
  }
}


variable "alert_worker_service_name" {
  description = "Service dimension value used by Alert Worker metrics."
  type        = string
  default     = "alert-worker"

  validation {
    condition = (
      length(
        trimspace(
          var.alert_worker_service_name
        )
      ) > 0
    )

    error_message = "alert_worker_service_name must not be empty."
  }
}


variable "ops_topic_kms_key_id" {
  description = "Optional KMS key ID or ARN for the operations SNS topic."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition = (
      var.ops_topic_kms_key_id == null
      || length(
        trimspace(
          var.ops_topic_kms_key_id
        )
      ) > 0
    )

    error_message = "ops_topic_kms_key_id must be null or non-empty."
  }
}


variable "risk_processing_failure_threshold" {
  description = "Risk processing failure alarm threshold."
  type        = number
  default     = 5

  validation {
    condition = (
      var.risk_processing_failure_threshold >= 0
    )

    error_message = "risk_processing_failure_threshold must be non-negative."
  }
}


variable "alert_processing_failure_threshold" {
  description = "Alert Worker processing failure alarm threshold."
  type        = number
  default     = 5

  validation {
    condition = (
      var.alert_processing_failure_threshold >= 0
    )

    error_message = "alert_processing_failure_threshold must be non-negative."
  }
}


variable "risk_latency_threshold_ms" {
  description = "Risk Engine processing latency threshold in milliseconds."
  type        = number
  default     = 1000

  validation {
    condition = (
      var.risk_latency_threshold_ms > 0
    )

    error_message = "risk_latency_threshold_ms must be positive."
  }
}


variable "alert_latency_threshold_ms" {
  description = "Alert Worker processing latency threshold in milliseconds."
  type        = number
  default     = 2000

  validation {
    condition = (
      var.alert_latency_threshold_ms > 0
    )

    error_message = "alert_latency_threshold_ms must be positive."
  }
}


variable "ack_failure_threshold" {
  description = "SQS ACK failure count that triggers the alarm."
  type        = number
  default     = 1

  validation {
    condition = (
      var.ack_failure_threshold > 0
    )

    error_message = "ack_failure_threshold must be positive."
  }
}


variable "alert_queue_name" {
  description = "Alert Worker SQS queue name. Empty disables queue alarms."
  type        = string
  default     = ""
}


variable "alert_dlq_name" {
  description = "Alert Worker DLQ name. Empty disables DLQ alarms."
  type        = string
  default     = ""
}


variable "queue_backlog_threshold" {
  description = "Visible SQS message backlog threshold."
  type        = number
  default     = 100

  validation {
    condition = (
      var.queue_backlog_threshold >= 0
    )

    error_message = "queue_backlog_threshold must be non-negative."
  }
}


variable "queue_age_threshold_seconds" {
  description = "Maximum acceptable age of the oldest SQS message."
  type        = number
  default     = 300

  validation {
    condition = (
      var.queue_age_threshold_seconds > 0
    )

    error_message = "queue_age_threshold_seconds must be positive."
  }
}


variable "dlq_message_threshold" {
  description = "Visible DLQ message threshold."
  type        = number
  default     = 1

  validation {
    condition = (
      var.dlq_message_threshold > 0
    )

    error_message = "dlq_message_threshold must be positive."
  }
}


variable "tags" {
  description = "Additional resource tags."
  type        = map(string)
  default     = {}
}