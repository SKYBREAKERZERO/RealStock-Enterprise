output "cluster_id" {
  description = "Aurora cluster identifier."
  value       = aws_rds_cluster.this.id
}


output "cluster_arn" {
  description = "Aurora cluster ARN."
  value       = aws_rds_cluster.this.arn
}


output "cluster_resource_id" {
  description = "Aurora cluster resource ID."
  value       = aws_rds_cluster.this.cluster_resource_id
}


output "endpoint" {
  description = "Aurora writer endpoint."
  value       = aws_rds_cluster.this.endpoint
}


output "reader_endpoint" {
  description = "Aurora reader endpoint."
  value       = aws_rds_cluster.this.reader_endpoint
}


output "port" {
  description = "Aurora PostgreSQL port."
  value       = aws_rds_cluster.this.port
}


output "database_name" {
  description = "Initial Aurora database name."
  value       = var.database_name
}


output "security_group_id" {
  description = "Aurora security group ID."
  value       = aws_security_group.this.id
}


output "master_user_secret_arn" {
  description = "Secrets Manager ARN holding the AWS-managed Aurora master credentials."

  value = (
    aws_rds_cluster.this.master_user_secret[0].secret_arn
  )

  sensitive = true
}