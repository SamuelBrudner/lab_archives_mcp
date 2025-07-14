# ======================================================================
# LabArchives MCP Server Infrastructure Outputs
# ======================================================================
# This file defines Terraform output variables for the LabArchives MCP Server
# infrastructure, exposing key resource attributes such as service endpoints,
# ARNs, and connection details after provisioning. These outputs enable
# integration with CI/CD pipelines, monitoring systems, and operational
# handoff processes.
#
# Requirements Addressed:
# - Infrastructure Output Exposure (8.2 BUILD AND DISTRIBUTION REQUIREMENTS)
# - Deployment Automation Integration (8.2.2 Build Pipeline Configuration)
# - Operator Documentation and Handoff (8.2.8 Documentation and Support)
# ======================================================================

# ======================================================================
# ECS Service Infrastructure Outputs
# ======================================================================
# These outputs expose critical ECS service information for deployment
# automation, monitoring integration, and operational management.

output "ecs_service_arn" {
  description = "ARN of the ECS service running the LabArchives MCP Server"
  value       = module.ecs.ecs_service_arn
  
  # Used for:
  # - CloudWatch monitoring and alerting
  # - Auto-scaling policy configuration
  # - Service mesh integration
  # - CI/CD deployment status monitoring
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster hosting the MCP Server"
  value       = module.ecs.ecs_cluster_name
  
  # Used for:
  # - ECS CLI operations and debugging
  # - Service discovery configuration
  # - Cluster-level monitoring and metrics
  # - Resource tagging and cost allocation
}

output "ecs_service_name" {
  description = "Name of the ECS service for operational reference"
  value       = module.ecs.ecs_service_name
  
  # Used for:
  # - Deployment automation scripts
  # - Service discovery registration
  # - Application load balancer configuration
  # - Monitoring dashboard configuration
}

output "ecs_task_definition_arn" {
  description = "ARN of the ECS task definition for the MCP Server container"
  value       = module.ecs.ecs_task_definition_arn
  
  # Used for:
  # - Blue-green deployment orchestration
  # - Rollback operations and version management
  # - Container image security scanning
  # - Compliance audit trails
}

output "ecs_task_role_arn" {
  description = "IAM role ARN assigned to the ECS task for secure API access"
  value       = module.ecs.ecs_task_role_arn
  
  # Used for:
  # - IAM policy attachment and validation
  # - Security compliance auditing
  # - Cross-service authentication
  # - Least privilege access verification
}

# ======================================================================
# Service Endpoint Outputs
# ======================================================================
# Public-facing service endpoints for client connectivity and integration.

output "service_url" {
  description = "Public endpoint URL for the MCP Server (e.g., ALB, NLB, or API Gateway URL)"
  value       = module.ecs.service_url
  
  # Used for:
  # - Claude Desktop MCP client configuration
  # - Health check monitoring and uptime verification
  # - DNS record creation and management
  # - SSL certificate validation and renewal
  # - API gateway integration and routing
}

# ======================================================================
# Database Infrastructure Outputs
# ======================================================================
# RDS database connection details for audit logging and future enhancements.
# These outputs support future extensibility while maintaining security.

output "rds_endpoint" {
  description = "Endpoint of the RDS database (if provisioned for audit logging or future features)"
  value       = module.rds.rds_endpoint
  
  # Used for:
  # - Application database connection configuration
  # - Database migration and backup operations
  # - Performance monitoring and optimization
  # - Connection pooling and failover configuration
}

output "rds_db_name" {
  description = "Name of the RDS database"
  value       = module.rds.rds_db_name
  
  # Used for:
  # - Database schema initialization
  # - Application configuration management
  # - Backup and restore operations
  # - Multi-environment database isolation
}

output "rds_username" {
  description = "Username for the RDS database connection"
  value       = module.rds.rds_username
  sensitive   = true
  
  # Used for:
  # - Secure database authentication
  # - Connection string generation
  # - IAM database authentication setup
  # - Service account management
  #
  # Note: Marked as sensitive to prevent exposure in logs
}

# ======================================================================
# Operational Metadata Outputs
# ======================================================================
# Additional outputs for operational excellence and integration support.

output "deployment_timestamp" {
  description = "Timestamp of the infrastructure deployment for audit and tracking"
  value       = timestamp()
  
  # Used for:
  # - Deployment audit trails
  # - Change management tracking
  # - Rollback decision support
  # - Compliance documentation
}

output "infrastructure_tags" {
  description = "Common tags applied to all infrastructure resources"
  value = {
    Project     = "LabArchives-MCP-Server"
    Component   = "infrastructure"
    ManagedBy   = "terraform"
    Environment = var.environment
    Team        = var.team_name
    CostCenter  = var.cost_center
  }
  
  # Used for:
  # - Cost allocation and billing
  # - Resource governance and compliance
  # - Team ownership identification
  # - Environment-specific configuration
}

output "resource_summary" {
  description = "Summary of provisioned resources for documentation and handoff"
  value = {
    ecs_cluster   = module.ecs.ecs_cluster_name
    ecs_service   = module.ecs.ecs_service_name
    service_url   = module.ecs.service_url
    database_name = module.rds.rds_db_name
    region        = data.aws_region.current.name
    account_id    = data.aws_caller_identity.current.account_id
  }
  
  # Used for:
  # - Operator handoff documentation
  # - Infrastructure inventory management
  # - Disaster recovery planning
  # - Cross-region resource tracking
}

# ======================================================================
# Security and Compliance Outputs
# ======================================================================
# Security-focused outputs for compliance validation and audit support.

output "security_configuration" {
  description = "Security configuration summary for compliance reporting"
  value = {
    encryption_at_rest_enabled = var.rds_encryption_enabled
    encryption_in_transit     = var.enable_ssl_termination
    vpc_isolation_enabled     = var.enable_vpc_isolation
    iam_authentication       = var.enable_iam_db_authentication
    security_groups          = var.security_group_ids
  }
  
  # Used for:
  # - SOC2, ISO 27001, HIPAA compliance validation
  # - Security audit preparations
  # - Vulnerability assessment reporting
  # - Penetration testing scope definition
}

output "backup_configuration" {
  description = "Backup and disaster recovery configuration for compliance"
  value = {
    rds_backup_enabled         = var.rds_backup_retention_period > 0
    rds_backup_retention_days  = var.rds_backup_retention_period
    rds_multi_az_enabled       = var.rds_multi_az
    point_in_time_recovery     = var.rds_backup_retention_period > 0
  }
  
  # Used for:
  # - Disaster recovery planning
  # - RTO/RPO compliance verification
  # - Backup policy validation
  # - Business continuity planning
}

# ======================================================================
# Monitoring and Observability Outputs
# ======================================================================
# CloudWatch and monitoring configuration for operational excellence.

output "monitoring_endpoints" {
  description = "Monitoring and observability endpoints for dashboards and alerts"
  value = {
    cloudwatch_log_group     = "/aws/ecs/${module.ecs.ecs_service_name}"
    ecs_service_metrics      = "AWS/ECS"
    rds_performance_insights = module.rds.rds_endpoint
    container_insights       = module.ecs.ecs_cluster_name
  }
  
  # Used for:
  # - CloudWatch dashboard configuration
  # - Automated alerting setup
  # - Performance monitoring integration
  # - Log aggregation and analysis
}

# ======================================================================
# Integration Support Outputs
# ======================================================================
# Outputs specifically designed for CI/CD and automation integration.

output "ci_cd_integration" {
  description = "CI/CD integration endpoints and identifiers for automation"
  value = {
    ecs_service_arn      = module.ecs.ecs_service_arn
    task_definition_arn  = module.ecs.ecs_task_definition_arn
    cluster_name         = module.ecs.ecs_cluster_name
    service_name         = module.ecs.ecs_service_name
    deployment_endpoint  = module.ecs.service_url
  }
  
  # Used for:
  # - GitHub Actions deployment workflows
  # - Jenkins pipeline configuration
  # - Automated testing and validation
  # - Blue-green deployment orchestration
}

output "api_integration" {
  description = "API endpoints and configuration for external integrations"
  value = {
    mcp_server_url       = module.ecs.service_url
    health_check_path    = "/health"
    api_version          = "v1"
    supported_transports = ["stdio", "http"]
    protocol_version     = "2024-11-05"
  }
  
  # Used for:
  # - Claude Desktop MCP client setup
  # - API gateway configuration
  # - Load balancer health checks
  # - Service mesh integration
}

# ======================================================================
# Cost Optimization Outputs
# ======================================================================
# Cost-related outputs for financial tracking and optimization.

output "cost_allocation" {
  description = "Cost allocation tags and resource identifiers for billing"
  value = {
    cost_center    = var.cost_center
    project_code   = "labarchives-mcp-server"
    environment    = var.environment
    resource_owner = var.team_name
    billing_tags   = var.billing_tags
  }
  
  # Used for:
  # - AWS Cost Explorer filtering
  # - Chargeback and showback reporting
  # - Budget alert configuration
  # - Cost optimization recommendations
}

# ======================================================================
# Documentation and Support Outputs
# ======================================================================
# Human-readable outputs for documentation and operator handoff.

output "deployment_guide" {
  description = "Quick reference guide for operators and documentation"
  value = {
    service_url           = module.ecs.service_url
    cluster_name          = module.ecs.ecs_cluster_name
    service_name          = module.ecs.ecs_service_name
    database_endpoint     = module.rds.rds_endpoint
    log_group            = "/aws/ecs/${module.ecs.ecs_service_name}"
    region               = data.aws_region.current.name
    deployment_timestamp = timestamp()
  }
  
  # Used for:
  # - Operator runbooks and documentation
  # - Support ticket information
  # - Infrastructure as Code documentation
  # - Team onboarding materials
}

# ======================================================================
# Data Sources for Output Values
# ======================================================================
# Required data sources for regional and account information.

data "aws_region" "current" {}

data "aws_caller_identity" "current" {}

# ======================================================================
# Output Usage Examples
# ======================================================================
# The following examples demonstrate how to use these outputs in downstream
# modules, CI/CD pipelines, and operational workflows:
#
# 1. Claude Desktop Configuration:
#    Use `service_url` output to configure MCP client endpoints
#
# 2. Monitoring Setup:
#    Use `monitoring_endpoints` for CloudWatch dashboard creation
#
# 3. CI/CD Integration:
#    Reference `ci_cd_integration` outputs in GitHub Actions workflows
#
# 4. Database Connections:
#    Use `rds_endpoint`, `rds_db_name`, and `rds_username` for app config
#
# 5. Security Auditing:
#    Reference `security_configuration` for compliance reporting
#
# 6. Cost Management:
#    Use `cost_allocation` outputs for billing and chargeback
#
# 7. Operational Handoff:
#    Provide `deployment_guide` output to operations teams
# ======================================================================