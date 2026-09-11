output "vpc_id" {
  description = "ID of the VPC."

  value = (
    aws_vpc.this.id
  )
}


output "vpc_arn" {
  description = "ARN of the VPC."

  value = (
    aws_vpc.this.arn
  )
}


output "vpc_cidr_block" {
  description = "IPv4 CIDR block of the VPC."

  value = (
    aws_vpc.this.cidr_block
  )
}


output "internet_gateway_id" {
  description = "ID of the VPC Internet Gateway."

  value = (
    aws_internet_gateway.this.id
  )
}


output "availability_zones" {
  description = "Availability Zones used by this VPC."

  value = (
    var.availability_zones
  )
}


output "public_subnet_ids" {
  description = "Public subnet IDs ordered by Availability Zone input."

  value = [
    for index in range(length(var.availability_zones)) :
    aws_subnet.public[tostring(index)].id
  ]
}


output "private_app_subnet_ids" {
  description = "Private application subnet IDs ordered by Availability Zone input."

  value = [
    for index in range(length(var.availability_zones)) :
    aws_subnet.private_app[tostring(index)].id
  ]
}


output "private_data_subnet_ids" {
  description = "Private data subnet IDs ordered by Availability Zone input."

  value = [
    for index in range(length(var.availability_zones)) :
    aws_subnet.private_data[tostring(index)].id
  ]
}


output "public_route_table_id" {
  description = "Shared public subnet route table ID."

  value = (
    aws_route_table.public.id
  )
}


output "private_app_route_table_ids" {
  description = "Private application route table IDs."

  value = [
    for index in range(length(var.availability_zones)) :
    aws_route_table.private_app[tostring(index)].id
  ]
}


output "private_data_route_table_ids" {
  description = "Private data route table IDs."

  value = [
    for index in range(length(var.availability_zones)) :
    aws_route_table.private_data[tostring(index)].id
  ]
}


output "nat_gateway_ids" {
  description = "NAT Gateway IDs created by the configured NAT topology."

  value = [
    for key in sort(keys(aws_nat_gateway.this)) :
    aws_nat_gateway.this[key].id
  ]
}


output "nat_gateway_public_ips" {
  description = "Public Elastic IP addresses assigned to NAT Gateways."

  value = [
    for key in sort(keys(aws_eip.nat)) :
    aws_eip.nat[key].public_ip
  ]
}