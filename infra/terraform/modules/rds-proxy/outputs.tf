output "proxy_name" {
  description = "RDS Proxy name."
  value       = aws_db_proxy.this.name
}

output "proxy_arn" {
  description = "RDS Proxy ARN."
  value       = aws_db_proxy.this.arn
}
output "endpoint" {
  description = "RDS Proxy endpoint used by application clients."
  value       = aws_db_proxy.this.endpoint
}

output "security_group_id" {
  description = "RDS Proxy security group ID."
  value       = aws_security_group.this.id
}


output "iam_role_arn" {
  description = "IAM role used by RDS Proxy to read database credentials."
  value       = aws_iam_role.this.arn
}