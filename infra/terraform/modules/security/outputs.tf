output "alb_security_group_id" {
  description = "Security group ID attached to the public ALB."

  value = (
    aws_security_group.alb.id
  )
}


output "alb_security_group_arn" {
  description = "ARN of the public ALB security group."

  value = (
    aws_security_group.alb.arn
  )
}


output "ecs_security_group_id" {
  description = "Security group ID attached to ECS application tasks."

  value = (
    aws_security_group.ecs.id
  )
}


output "ecs_security_group_arn" {
  description = "ARN of the ECS application security group."

  value = (
    aws_security_group.ecs.arn
  )
}