# ECS Cluster Configuration
variable "cluster_name" {
  description = "Name of the ECS cluster to create or use for the LabArchives MCP Server deployment"
  type        = string
  
  validation {
    condition     = can(regex("^[a-zA-Z0-9\\-_]+$", var.cluster_name))
    error_message = "Cluster name must contain only alphanumeric characters, hyphens, and underscores."
  }
}

# ECS Service Configuration
variable "service_name" {
  description = "Name of the ECS service to create for the LabArchives MCP Server"
  type        = string
  
  validation {
    condition     = can(regex("^[a-zA-Z0-9\\-_]+$", var.service_name))
    error_message = "Service name must contain only alphanumeric characters, hyphens, and underscores."
  }
}

# ECS Task Definition Configuration
variable "task_family" {
  description = "Family name for the ECS task definition used by the LabArchives MCP Server"
  type        = string
  
  validation {
    condition     = can(regex("^[a-zA-Z0-9\\-_]+$", var.task_family))
    error_message = "Task family name must contain only alphanumeric characters, hyphens, and underscores."
  }
}

# Container Configuration
variable "container_image" {
  description = "Docker image URI for the LabArchives MCP Server container (e.g., from Docker Hub or ECR)"
  type        = string
  
  validation {
    condition     = can(regex("^[a-zA-Z0-9\\-_./]+:[a-zA-Z0-9\\-_.]+$", var.container_image))
    error_message = "Container image must be in the format repository:tag or registry/repository:tag."
  }
}

variable "container_port" {
  description = "Port on which the LabArchives MCP Server container listens for MCP protocol connections"
  type        = number
  default     = 8080
  
  validation {
    condition     = var.container_port >= 1024 && var.container_port <= 65535
    error_message = "Container port must be between 1024 and 65535."
  }
}

# Service Scaling Configuration
variable "desired_count" {
  description = "Number of ECS service tasks to run for the LabArchives MCP Server (typically 1 for single-user model)"
  type        = number
  default     = 1
  
  validation {
    condition     = var.desired_count >= 0 && var.desired_count <= 10
    error_message = "Desired count must be between 0 and 10."
  }
}

# Resource Allocation Configuration
variable "cpu" {
  description = "CPU units to allocate to the ECS task (256 = 0.25 vCPU, 512 = 0.5 vCPU, 1024 = 1 vCPU)"
  type        = number
  default     = 256
  
  validation {
    condition     = contains([256, 512, 1024, 2048, 4096], var.cpu)
    error_message = "CPU must be one of: 256, 512, 1024, 2048, 4096."
  }
}

variable "memory" {
  description = "Memory (in MiB) to allocate to the ECS task for the LabArchives MCP Server"
  type        = number
  default     = 512
  
  validation {
    condition     = var.memory >= 128 && var.memory <= 8192
    error_message = "Memory must be between 128 and 8192 MiB."
  }
}

# Environment Configuration
variable "environment" {
  description = "Map of environment variables to inject into the LabArchives MCP Server container (e.g., LABARCHIVES_AKID, LABARCHIVES_SECRET, LABARCHIVES_API_BASE)"
  type        = map(string)
  default     = {}
  
  validation {
    condition = alltrue([
      for key, value in var.environment : can(regex("^[A-Z_][A-Z0-9_]*$", key))
    ])
    error_message = "Environment variable names must start with a letter or underscore and contain only uppercase letters, numbers, and underscores."
  }
}

# Network Configuration
variable "subnets" {
  description = "List of subnet IDs for ECS service placement (should be private subnets for security)"
  type        = list(string)
  
  validation {
    condition     = length(var.subnets) >= 1
    error_message = "At least one subnet must be specified."
  }
  
  validation {
    condition = alltrue([
      for subnet in var.subnets : can(regex("^subnet-[a-z0-9]{8,17}$", subnet))
    ])
    error_message = "All subnet IDs must be valid AWS subnet IDs (format: subnet-xxxxxxxxx)."
  }
}

variable "security_groups" {
  description = "List of security group IDs to associate with the ECS service for network access control"
  type        = list(string)
  
  validation {
    condition     = length(var.security_groups) >= 1
    error_message = "At least one security group must be specified."
  }
  
  validation {
    condition = alltrue([
      for sg in var.security_groups : can(regex("^sg-[a-z0-9]{8,17}$", sg))
    ])
    error_message = "All security group IDs must be valid AWS security group IDs (format: sg-xxxxxxxxx)."
  }
}

variable "assign_public_ip" {
  description = "Whether to assign a public IP to the ECS task (required for Fargate in public subnets, false for private subnets with NAT)"
  type        = bool
  default     = false
}

# Logging Configuration
variable "log_group_name" {
  description = "Name of the CloudWatch log group for LabArchives MCP Server container logs"
  type        = string
  
  validation {
    condition     = can(regex("^[a-zA-Z0-9\\-_/\\.]+$", var.log_group_name))
    error_message = "Log group name must contain only alphanumeric characters, hyphens, underscores, forward slashes, and periods."
  }
}

# IAM Role Configuration
variable "execution_role_arn" {
  description = "ARN of the IAM role for ECS task execution (required for pulling images and writing logs)"
  type        = string
  
  validation {
    condition     = can(regex("^arn:aws:iam::[0-9]{12}:role/.+$", var.execution_role_arn))
    error_message = "Execution role ARN must be a valid AWS IAM role ARN."
  }
}

variable "task_role_arn" {
  description = "ARN of the IAM role for the ECS task (grants permissions for the LabArchives MCP Server to access AWS services)"
  type        = string
  
  validation {
    condition     = can(regex("^arn:aws:iam::[0-9]{12}:role/.+$", var.task_role_arn))
    error_message = "Task role ARN must be a valid AWS IAM role ARN."
  }
}

# Optional: Platform Configuration
variable "platform_version" {
  description = "Platform version for Fargate tasks (LATEST, 1.4.0, etc.)"
  type        = string
  default     = "LATEST"
}

variable "launch_type" {
  description = "Launch type for the ECS service (FARGATE or EC2)"
  type        = string
  default     = "FARGATE"
  
  validation {
    condition     = contains(["FARGATE", "EC2"], var.launch_type)
    error_message = "Launch type must be either FARGATE or EC2."
  }
}

# Optional: Health Check Configuration
variable "health_check_grace_period_seconds" {
  description = "Seconds to ignore failing health checks after a task starts"
  type        = number
  default     = 300
  
  validation {
    condition     = var.health_check_grace_period_seconds >= 0 && var.health_check_grace_period_seconds <= 2147483647
    error_message = "Health check grace period must be a non-negative integer."
  }
}

# Optional: Service Discovery Configuration
variable "enable_service_discovery" {
  description = "Whether to enable service discovery for the ECS service"
  type        = bool
  default     = false
}

variable "service_discovery_namespace_id" {
  description = "ID of the service discovery namespace (required if enable_service_discovery is true)"
  type        = string
  default     = ""
}

# Optional: Load Balancer Configuration
variable "enable_load_balancer" {
  description = "Whether to attach the service to a load balancer"
  type        = bool
  default     = false
}

variable "target_group_arn" {
  description = "ARN of the target group for load balancer integration (required if enable_load_balancer is true)"
  type        = string
  default     = ""
}

# Optional: Auto Scaling Configuration
variable "enable_autoscaling" {
  description = "Whether to enable auto scaling for the ECS service"
  type        = bool
  default     = false
}

variable "min_capacity" {
  description = "Minimum number of tasks for auto scaling"
  type        = number
  default     = 1
}

variable "max_capacity" {
  description = "Maximum number of tasks for auto scaling"
  type        = number
  default     = 3
}

# Optional: Deployment Configuration
variable "deployment_minimum_healthy_percent" {
  description = "Minimum healthy percent during deployment"
  type        = number
  default     = 50
  
  validation {
    condition     = var.deployment_minimum_healthy_percent >= 0 && var.deployment_minimum_healthy_percent <= 100
    error_message = "Deployment minimum healthy percent must be between 0 and 100."
  }
}

variable "deployment_maximum_percent" {
  description = "Maximum percent during deployment"
  type        = number
  default     = 200
  
  validation {
    condition     = var.deployment_maximum_percent >= 100 && var.deployment_maximum_percent <= 200
    error_message = "Deployment maximum percent must be between 100 and 200."
  }
}

# Optional: Tags Configuration
variable "tags" {
  description = "Map of tags to apply to all ECS resources"
  type        = map(string)
  default = {
    Project     = "LabArchives-MCP-Server"
    Environment = "development"
    ManagedBy   = "terraform"
  }
}