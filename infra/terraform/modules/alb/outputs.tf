output "load_balancer_arn" {
  description = "ARN of the Application Load Balancer."

  value = (
    aws_lb.this.arn
  )
}


output "load_balancer_name" {
  description = "Name of the Application Load Balancer."

  value = (
    aws_lb.this.name
  )
}


output "dns_name" {
  description = "DNS name of the Application Load Balancer."

  value = (
    aws_lb.this.dns_name
  )
}


output "zone_id" {
  description = "Route 53 hosted-zone ID of the Application Load Balancer."

  value = (
    aws_lb.this.zone_id
  )
}


output "target_group_arn" {
  description = "ARN of the ECS application target group."

  value = (
    aws_lb_target_group.api.arn
  )
}


output "target_group_name" {
  description = "Name of the ECS application target group."

  value = (
    aws_lb_target_group.api.name
  )
}


output "https_listener_arn" {
  description = "ARN of the HTTPS listener."

  value = (
    aws_lb_listener.https.arn
  )
}


output "http_listener_arn" {
  description = "ARN of the optional HTTP redirect listener."

  value = (
    var.enable_http_redirect
    ? aws_lb_listener.http[0].arn
    : null
  )
}