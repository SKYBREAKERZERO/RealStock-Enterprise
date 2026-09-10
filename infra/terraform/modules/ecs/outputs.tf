output "cluster_id" {
  description = "ID of the ECS cluster."

  value = (
    aws_ecs_cluster.this.id
  )
}


output "cluster_arn" {
  description = "ARN of the ECS cluster."

  value = (
    aws_ecs_cluster.this.arn
  )
}


output "cluster_name" {
  description = "Name of the ECS cluster."

  value = (
    aws_ecs_cluster.this.name
  )
}


output "service_id" {
  description = "ID of the ECS service."

  value = (
    aws_ecs_service.this.id
  )
}


output "service_name" {
  description = "Name of the ECS service."

  value = (
    aws_ecs_service.this.name
  )
}


output "task_definition_arn" {
  description = "ARN of the ECS task definition revision."

  value = (
    aws_ecs_task_definition.this.arn
  )
}


output "task_definition_family" {
  description = "Family of the ECS task definition."

  value = (
    aws_ecs_task_definition.this.family
  )
}


output "log_group_name" {
  description = "CloudWatch Logs group used by the application container."

  value = (
    aws_cloudwatch_log_group.this.name
  )
}


output "container_name" {
  description = "Application container name."

  value = (
    local.container_name
  )
}


output "container_port" {
  description = "Application container port."

  value = (
    var.container_port
  )
}