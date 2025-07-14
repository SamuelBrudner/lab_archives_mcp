# =============================================================================
# LabArchives MCP Server - Terraform Variables
# =============================================================================
# This file defines input variables for the Terraform configuration managing
# the infrastructure for the LabArchives MCP Server. It centralizes all
# configurable parameters required for provisioning and customizing cloud
# resources, enabling flexible, reusable, and environment-agnostic deployments.
# =============================================================================

# -----------------------------------------------------------------------------
# Project Configuration
# -----------------------------------------------------------------------------

variable "project_name" {
  description = "Project name for resource naming and tagging. Used as a prefix for all resources to ensure consistent naming conventions."
  type        = string
  
  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "Project name must contain only lowercase letters, numbers, and hyphens."
  }
}

variable "environment" {
  description = "Deployment environment (dev, staging, prod). Used for resource isolation and configuration management."
  type        = string
  
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be one of: dev, staging, prod."
  }
}

# -----------------------------------------------------------------------------
# AWS Configuration
# -----------------------------------------------------------------------------

variable "aws_region" {
  description = "AWS region for resource deployment. Determines the geographic location of all infrastructure resources."
  type        = string
  default     = "us-east-1"
  
  validation {
    condition     = can(regex("^[a-z]{2}-[a-z]+-[0-9]+$", var.aws_region))
    error_message = "AWS region must be in the format: us-east-1, eu-west-1, etc."
  }
}

# -----------------------------------------------------------------------------
# Networking Configuration
# -----------------------------------------------------------------------------

variable "vpc_id" {
  description = "VPC ID for networking resources. The Virtual Private Cloud where all resources will be deployed."
  type        = string
  
  validation {
    condition     = can(regex("^vpc-[a-z0-9]{8,17}$", var.vpc_id))
    error_message = "VPC ID must be in the format: vpc-xxxxxxxx."
  }
}

variable "subnet_ids" {
  description = "List of subnet IDs for ECS and RDS resources. Must be in different availability zones for high availability."
  type        = list(string)
  
  validation {
    condition     = length(var.subnet_ids) >= 2
    error_message = "At least 2 subnets must be provided for high availability."
  }
  
  validation {
    condition     = alltrue([for subnet in var.subnet_ids : can(regex("^subnet-[a-z0-9]{8,17}$", subnet))])
    error_message = "All subnet IDs must be in the format: subnet-xxxxxxxx."
  }
}

# -----------------------------------------------------------------------------
# ECS Configuration
# -----------------------------------------------------------------------------

variable "ecs_cluster_name" {
  description = "Name of the ECS cluster for container orchestration. The cluster where MCP server tasks will be deployed."
  type        = string
  
  validation {
    condition     = can(regex("^[a-zA-Z0-9-_]+$", var.ecs_cluster_name))
    error_message = "ECS cluster name must contain only alphanumeric characters, hyphens, and underscores."
  }
}

variable "ecs_task_cpu" {
  description = "CPU units for ECS tasks (256, 512, 1024, 2048, 4096). Determines the compute resources allocated to each task."
  type        = number
  default     = 256
  
  validation {
    condition     = contains([256, 512, 1024, 2048, 4096], var.ecs_task_cpu)
    error_message = "ECS task CPU must be one of: 256, 512, 1024, 2048, 4096."
  }
}

variable "ecs_task_memory" {
  description = "Memory in MiB for ECS tasks. Must be compatible with the selected CPU value according to AWS Fargate requirements."
  type        = number
  default     = 512
  
  validation {
    condition     = var.ecs_task_memory >= 512 && var.ecs_task_memory <= 30720
    error_message = "ECS task memory must be between 512 MiB and 30720 MiB."
  }
}

# -----------------------------------------------------------------------------
# RDS Configuration
# -----------------------------------------------------------------------------

variable "rds_instance_class" {
  description = "RDS instance type (e.g., db.t3.micro, db.t3.small). Determines the compute and memory resources for the database instance."
  type        = string
  default     = "db.t3.micro"
  
  validation {
    condition     = can(regex("^db\\.[a-z0-9]+\\.[a-z0-9]+$", var.rds_instance_class))
    error_message = "RDS instance class must be in the format: db.t3.micro, db.r5.large, etc."
  }
}

variable "rds_allocated_storage" {
  description = "Allocated storage in GB for the RDS instance. Minimum 20 GB, maximum 65536 GB."
  type        = number
  default     = 20
  
  validation {
    condition     = var.rds_allocated_storage >= 20 && var.rds_allocated_storage <= 65536
    error_message = "RDS allocated storage must be between 20 GB and 65536 GB."
  }
}

variable "rds_username" {
  description = "Master username for the RDS database. Must be 1-63 characters and start with a letter."
  type        = string
  sensitive   = true
  
  validation {
    condition     = can(regex("^[a-zA-Z][a-zA-Z0-9_]{0,62}$", var.rds_username))
    error_message = "RDS username must be 1-63 characters, start with a letter, and contain only letters, numbers, and underscores."
  }
}

variable "rds_password" {
  description = "Master password for the RDS database. Must be 8-128 characters and contain at least one uppercase letter, one lowercase letter, and one number."
  type        = string
  sensitive   = true
  
  validation {
    condition     = length(var.rds_password) >= 8 && length(var.rds_password) <= 128
    error_message = "RDS password must be between 8 and 128 characters."
  }
}

variable "rds_db_name" {
  description = "Database name for the RDS instance. Must be 1-64 characters and contain only letters, numbers, and underscores."
  type        = string
  
  validation {
    condition     = can(regex("^[a-zA-Z][a-zA-Z0-9_]{0,63}$", var.rds_db_name))
    error_message = "RDS database name must be 1-64 characters, start with a letter, and contain only letters, numbers, and underscores."
  }
}

# -----------------------------------------------------------------------------
# Container Configuration
# -----------------------------------------------------------------------------

variable "container_image" {
  description = "Docker image URI for the MCP server container. Can be from ECR, Docker Hub, or other registries."
  type        = string
  
  validation {
    condition     = can(regex("^[a-zA-Z0-9./:-]+$", var.container_image))
    error_message = "Container image must be a valid Docker image URI."
  }
}

variable "container_port" {
  description = "Port on which the MCP server container listens for incoming connections."
  type        = number
  default     = 8080
  
  validation {
    condition     = var.container_port >= 1 && var.container_port <= 65535
    error_message = "Container port must be between 1 and 65535."
  }
}

# -----------------------------------------------------------------------------
# Logging Configuration
# -----------------------------------------------------------------------------

variable "log_retention_days" {
  description = "Number of days to retain CloudWatch logs. Valid values: 1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653."
  type        = number
  default     = 7
  
  validation {
    condition     = contains([1, 3, 5, 7, 14, 30, 60, 90, 120, 150, 180, 365, 400, 545, 731, 1827, 3653], var.log_retention_days)
    error_message = "Log retention days must be one of the valid CloudWatch log retention values."
  }
}

# -----------------------------------------------------------------------------
# Security Configuration
# -----------------------------------------------------------------------------

variable "enable_public_access" {
  description = "Enable public access to the MCP server. When false, the server is only accessible from within the VPC."
  type        = bool
  default     = false
}

# -----------------------------------------------------------------------------
# Tagging Configuration
# -----------------------------------------------------------------------------

variable "additional_tags" {
  description = "Additional resource tags for cost allocation and management. These tags will be applied to all resources."
  type        = map(string)
  default     = {}
  
  validation {
    condition = alltrue([
      for tag_key, tag_value in var.additional_tags : 
      can(regex("^[a-zA-Z0-9._:/=+\\-@]+$", tag_key)) && 
      can(regex("^[a-zA-Z0-9._:/=+\\-@\\s]+$", tag_value)) &&
      length(tag_key) <= 128 &&
      length(tag_value) <= 256
    ])
    error_message = "Tag keys and values must follow AWS tagging conventions (max 128 chars for keys, 256 for values)."
  }
}

# -----------------------------------------------------------------------------
# Advanced Configuration
# -----------------------------------------------------------------------------

variable "enable_ssl" {
  description = "Enable SSL/TLS encryption for the MCP server. Requires ACM certificate ARN if enabled."
  type        = bool
  default     = true
}

variable "ssl_certificate_arn" {
  description = "ARN of the SSL certificate from AWS Certificate Manager. Required if enable_ssl is true."
  type        = string
  default     = ""
  
  validation {
    condition = var.ssl_certificate_arn == "" || can(regex("^arn:aws:acm:[a-z0-9-]+:[0-9]{12}:certificate/[a-f0-9-]+$", var.ssl_certificate_arn))
    error_message = "SSL certificate ARN must be a valid ACM certificate ARN or empty string."
  }
}

variable "backup_retention_period" {
  description = "Number of days to retain automated RDS backups. Set to 0 to disable automated backups."
  type        = number
  default     = 7
  
  validation {
    condition     = var.backup_retention_period >= 0 && var.backup_retention_period <= 35
    error_message = "Backup retention period must be between 0 and 35 days."
  }
}

variable "enable_multi_az" {
  description = "Enable Multi-AZ deployment for RDS instance for high availability and automated failover."
  type        = bool
  default     = false
}

variable "enable_performance_insights" {
  description = "Enable Performance Insights for RDS instance monitoring and performance analysis."
  type        = bool
  default     = false
}

variable "performance_insights_retention_period" {
  description = "Number of days to retain Performance Insights data. Valid values: 7, 31, 62, 93, 124, 155, 186, 217, 248, 279, 310, 341, 372, 403, 434, 465, 496, 527, 558, 589, 620, 651, 682, 713, 731."
  type        = number
  default     = 7
  
  validation {
    condition = !var.enable_performance_insights || contains([7, 31, 62, 93, 124, 155, 186, 217, 248, 279, 310, 341, 372, 403, 434, 465, 496, 527, 558, 589, 620, 651, 682, 713, 731], var.performance_insights_retention_period)
    error_message = "Performance Insights retention period must be one of the valid values."
  }
}

variable "monitoring_interval" {
  description = "The interval for collecting enhanced monitoring metrics. Valid values: 0, 1, 5, 10, 15, 30, 60."
  type        = number
  default     = 0
  
  validation {
    condition     = contains([0, 1, 5, 10, 15, 30, 60], var.monitoring_interval)
    error_message = "Monitoring interval must be one of: 0, 1, 5, 10, 15, 30, 60."
  }
}

variable "auto_minor_version_upgrade" {
  description = "Enable automatic minor version upgrades for the RDS instance during maintenance windows."
  type        = bool
  default     = true
}

variable "storage_encrypted" {
  description = "Enable encryption at rest for the RDS instance using AWS KMS."
  type        = bool
  default     = true
}

variable "kms_key_id" {
  description = "ARN of the AWS KMS key for RDS encryption. If not specified, the default AWS managed key will be used."
  type        = string
  default     = ""
  
  validation {
    condition = var.kms_key_id == "" || can(regex("^arn:aws:kms:[a-z0-9-]+:[0-9]{12}:key/[a-f0-9-]+$", var.kms_key_id))
    error_message = "KMS key ID must be a valid KMS key ARN or empty string."
  }
}

variable "deletion_protection" {
  description = "Enable deletion protection for the RDS instance to prevent accidental deletion."
  type        = bool
  default     = true
}

variable "skip_final_snapshot" {
  description = "Skip creating a final snapshot when the RDS instance is deleted. Not recommended for production."
  type        = bool
  default     = false
}

variable "final_snapshot_identifier" {
  description = "Name of the final snapshot created when the RDS instance is deleted. Auto-generated if not specified."
  type        = string
  default     = ""
}

variable "health_check_grace_period" {
  description = "Grace period in seconds for ECS service health checks before considering a task unhealthy."
  type        = number
  default     = 60
  
  validation {
    condition     = var.health_check_grace_period >= 0 && var.health_check_grace_period <= 2147483647
    error_message = "Health check grace period must be a valid positive integer."
  }
}

variable "desired_count" {
  description = "Desired number of ECS tasks to run simultaneously for the MCP server service."
  type        = number
  default     = 1
  
  validation {
    condition     = var.desired_count >= 0 && var.desired_count <= 100
    error_message = "Desired count must be between 0 and 100."
  }
}

variable "enable_auto_scaling" {
  description = "Enable auto scaling for the ECS service based on CPU and memory utilization."
  type        = bool
  default     = false
}

variable "min_capacity" {
  description = "Minimum number of ECS tasks for auto scaling. Only used if enable_auto_scaling is true."
  type        = number
  default     = 1
  
  validation {
    condition     = var.min_capacity >= 0 && var.min_capacity <= 100
    error_message = "Minimum capacity must be between 0 and 100."
  }
}

variable "max_capacity" {
  description = "Maximum number of ECS tasks for auto scaling. Only used if enable_auto_scaling is true."
  type        = number
  default     = 10
  
  validation {
    condition     = var.max_capacity >= 1 && var.max_capacity <= 100
    error_message = "Maximum capacity must be between 1 and 100."
  }
}

variable "target_cpu_utilization" {
  description = "Target CPU utilization percentage for auto scaling. Only used if enable_auto_scaling is true."
  type        = number
  default     = 70
  
  validation {
    condition     = var.target_cpu_utilization >= 1 && var.target_cpu_utilization <= 100
    error_message = "Target CPU utilization must be between 1 and 100."
  }
}

variable "target_memory_utilization" {
  description = "Target memory utilization percentage for auto scaling. Only used if enable_auto_scaling is true."
  type        = number
  default     = 80
  
  validation {
    condition     = var.target_memory_utilization >= 1 && var.target_memory_utilization <= 100
    error_message = "Target memory utilization must be between 1 and 100."
  }
}

# -----------------------------------------------------------------------------
# Local Values for Computed Tags
# -----------------------------------------------------------------------------

locals {
  # Common tags applied to all resources
  common_tags = merge(
    {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
      Service     = "labarchives-mcp-server"
      CreatedBy   = "terraform"
      CreatedAt   = timestamp()
    },
    var.additional_tags
  )
  
  # Resource naming prefix
  name_prefix = "${var.project_name}-${var.environment}"
  
  # SSL validation
  ssl_enabled = var.enable_ssl && var.ssl_certificate_arn != ""
}