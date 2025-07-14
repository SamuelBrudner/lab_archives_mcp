# ======================================================================
# ECS Module Outputs
# ======================================================================
# This file defines the output variables for the ECS Terraform module,
# exposing key resource attributes and ARNs required for integration,
# referencing, and orchestration in the broader LabArchives MCP Server
# infrastructure.
# ======================================================================

# ECS Cluster Outputs
# ======================================================================

output "ecs_cluster_id" {
  description = "The ID of the ECS cluster."
  value       = aws_ecs_cluster.this.id
  
  # Expose cluster ID for service deployment and task scheduling
  # Used by parent modules for ECS service creation and management
}

output "ecs_cluster_arn" {
  description = "The ARN of the ECS cluster."
  value       = aws_ecs_cluster.this.arn
  
  # Required for IAM policies, CloudWatch monitoring, and cross-region references
  # Used by monitoring systems and CI/CD pipelines for cluster management
}

# ECS Service Outputs
# ======================================================================

output "ecs_service_name" {
  description = "The name of the ECS service."
  value       = aws_ecs_service.this.name
  
  # Service name used for deployment automation and monitoring integration
  # Required for service discovery and application load balancer configuration
}

output "ecs_service_arn" {
  description = "The ARN of the ECS service."
  value       = aws_ecs_service.this.arn
  
  # Service ARN used for scaling policies, CloudWatch alarms, and service mesh integration
  # Required for monitoring, logging, and automated deployment pipelines
}

# ECS Task Definition Outputs
# ======================================================================

output "ecs_task_definition_arn" {
  description = "The ARN of the ECS task definition."
  value       = aws_ecs_task_definition.this.arn
  
  # Task definition ARN used for deployments, rollbacks, and blue-green deployments
  # Required for CI/CD pipelines and automated deployment orchestration
}

# IAM Role Outputs
# ======================================================================

output "ecs_task_execution_role_arn" {
  description = "The ARN of the ECS task execution IAM role."
  value       = aws_iam_role.ecs_task_execution_role.arn
  
  # Task execution role ARN used for ECS task execution permissions
  # Required for pulling container images, writing logs, and accessing secrets
}

output "ecs_task_role_arn" {
  description = "The ARN of the ECS task IAM role."
  value       = aws_iam_role.ecs_task_role.arn
  
  # Task role ARN assigned to running tasks for application-level AWS API access
  # Used for accessing LabArchives API, S3 storage, and other AWS services
}

# Security Group Outputs
# ======================================================================

output "ecs_service_security_group_id" {
  description = "The ID of the security group attached to the ECS service."
  value       = aws_security_group.ecs_service.id
  
  # Security group ID used for network access control and firewall rules
  # Required for load balancer integration and inter-service communication
}

# Load Balancer Outputs
# ======================================================================

output "ecs_service_load_balancer_dns" {
  description = "The DNS name of the load balancer (if provisioned) in front of the ECS service."
  value       = aws_lb.ecs_service.dns_name
  
  # Load balancer DNS name used for service discovery and external access
  # Required for DNS configuration, SSL certificate management, and client connections
}

# ======================================================================
# Output Usage Notes
# ======================================================================
# These outputs enable the following integration patterns:
#
# 1. Parent Module Integration:
#    - Use cluster_id and service_name for resource references
#    - Use ARNs for IAM policy attachments and CloudWatch monitoring
#
# 2. CI/CD Pipeline Integration:
#    - Use task_definition_arn for automated deployments
#    - Use service_arn for deployment status monitoring
#
# 3. Monitoring and Alerting:
#    - Use cluster_arn and service_arn for CloudWatch metrics
#    - Use security_group_id for network monitoring
#
# 4. Load Balancer Integration:
#    - Use load_balancer_dns for DNS record creation
#    - Use security_group_id for traffic routing rules
#
# 5. Cross-Module Dependencies:
#    - Use role ARNs for IAM policy references
#    - Use resource IDs for dependency management
# ======================================================================