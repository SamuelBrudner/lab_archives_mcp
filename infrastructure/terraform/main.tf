# ======================================================================
# LabArchives MCP Server - Main Terraform Configuration
# ======================================================================
# This is the root Terraform module for provisioning infrastructure
# resources required for the LabArchives MCP Server cloud deployment.
# It orchestrates the creation of ECS and RDS resources through child
# modules, supporting optional cloud or enterprise deployment scenarios.
#
# Key Features:
# - Stateless, horizontally scalable ECS deployment
# - Optional RDS for audit logging and enterprise features
# - Comprehensive security and compliance configurations
# - Network isolation with VPC and security groups
# - Automated monitoring and alerting
# - SOC2, ISO 27001, HIPAA, and GDPR compliance support
# ======================================================================

terraform {
  required_version = ">= 1.3.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0.0"
    }
    random = {
      source  = "hashicorp/random"
      version = ">= 3.0.0"
    }
  }
}

# ======================================================================
# Provider Configuration
# ======================================================================

# Primary AWS provider configuration
provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile

  # Default tags applied to all resources
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
      Component   = "labarchives-mcp-server"
      Owner       = "platform-team"
      CostCenter  = "engineering"
    }
  }
}

# Random provider for generating unique identifiers
provider "random" {}

# ======================================================================
# Data Sources
# ======================================================================

# Get current AWS account ID for resource naming and IAM policies
data "aws_caller_identity" "current" {}

# Get current AWS region for resource configuration
data "aws_region" "current" {}

# Get available availability zones for multi-AZ deployment
data "aws_availability_zones" "available" {
  state = "available"
}

# ======================================================================
# Local Values
# ======================================================================

locals {
  # Resource naming convention
  project_name = var.project_name
  environment  = var.environment
  
  # Common tags for all resources
  common_tags = {
    Project          = local.project_name
    Environment      = local.environment
    ManagedBy        = "terraform"
    Component        = "labarchives-mcp-server"
    Owner            = "platform-team"
    CostCenter       = "engineering"
    DataClass        = "internal"
    Compliance       = "SOC2,ISO27001,HIPAA,GDPR"
    BackupRequired   = "true"
    MonitoringLevel  = "standard"
    CreatedBy        = data.aws_caller_identity.current.user_id
    CreatedDate      = formatdate("YYYY-MM-DD", timestamp())
  }
  
  # ECS service configuration
  ecs_service_name = "${local.project_name}-${local.environment}"
  ecs_cluster_name = "${local.project_name}-${local.environment}-cluster"
  
  # Container configuration
  container_port = 8080
  container_image = var.container_image
  
  # Environment variables for the MCP server container
  container_environment = {
    # LabArchives API configuration
    LABARCHIVES_API_BASE = var.labarchives_api_base
    LABARCHIVES_REGION   = var.labarchives_region
    
    # MCP Server configuration
    MCP_SERVER_NAME      = "labarchives-mcp-server"
    MCP_SERVER_VERSION   = "1.0.0"
    MCP_LOG_LEVEL        = var.log_level
    MCP_AUDIT_ENABLED    = var.audit_enabled ? "true" : "false"
    
    # Environment metadata
    ENVIRONMENT          = local.environment
    PROJECT_NAME         = local.project_name
    AWS_REGION           = data.aws_region.current.name
    AWS_ACCOUNT_ID       = data.aws_caller_identity.current.account_id
    
    # Database configuration (if RDS is enabled)
    DB_ENABLED           = var.db_enabled ? "true" : "false"
    DB_HOST              = var.db_enabled ? module.rds[0].rds_instance_endpoint : ""
    DB_PORT              = var.db_enabled ? tostring(module.rds[0].rds_instance_port) : ""
    DB_NAME              = var.db_enabled ? module.rds[0].rds_instance_db_name : ""
    DB_USER              = var.db_enabled ? module.rds[0].rds_instance_username : ""
    
    # Security and compliance
    SECURITY_MODE        = "strict"
    COMPLIANCE_MODE      = "enabled"
    AUDIT_RETENTION_DAYS = "2555" # 7 years for compliance
  }
  
  # VPC and subnet configuration
  vpc_id = var.vpc_id
  subnet_ids = var.subnet_ids
  
  # Security group configuration
  allowed_cidr_blocks = var.allowed_cidr_blocks
  
  # Database configuration
  db_subnet_ids = var.db_enabled ? var.subnet_ids : []
  
  # Monitoring configuration
  enable_monitoring = true
  enable_logging = true
  
  # Auto-scaling configuration
  min_capacity = 1
  max_capacity = var.desired_count * 2
  
  # Load balancer configuration
  enable_load_balancer = var.enable_load_balancer
  
  # CloudWatch log group names
  ecs_log_group = "/aws/ecs/${local.ecs_service_name}"
  
  # SNS topic for alerts
  sns_topic_name = "${local.project_name}-${local.environment}-alerts"
}

# ======================================================================
# Random Resources
# ======================================================================

# Generate random suffix for unique resource naming
resource "random_string" "suffix" {
  length  = 8
  special = false
  upper   = false
}

# ======================================================================
# VPC and Networking Resources
# ======================================================================

# Create VPC if not provided
resource "aws_vpc" "this" {
  count = var.vpc_id == "" ? 1 : 0
  
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
  
  tags = merge(local.common_tags, {
    Name = "${local.project_name}-${local.environment}-vpc"
    Type = "vpc"
  })
}

# Create private subnets if not provided
resource "aws_subnet" "private" {
  count = var.vpc_id == "" ? 2 : 0
  
  vpc_id            = aws_vpc.this[0].id
  cidr_block        = "10.0.${count.index + 1}.0/24"
  availability_zone = data.aws_availability_zones.available.names[count.index]
  
  tags = merge(local.common_tags, {
    Name = "${local.project_name}-${local.environment}-private-subnet-${count.index + 1}"
    Type = "private-subnet"
  })
}

# Create public subnets for load balancer
resource "aws_subnet" "public" {
  count = var.vpc_id == "" && var.enable_load_balancer ? 2 : 0
  
  vpc_id                  = aws_vpc.this[0].id
  cidr_block              = "10.0.${count.index + 10}.0/24"
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true
  
  tags = merge(local.common_tags, {
    Name = "${local.project_name}-${local.environment}-public-subnet-${count.index + 1}"
    Type = "public-subnet"
  })
}

# Create internet gateway
resource "aws_internet_gateway" "this" {
  count = var.vpc_id == "" ? 1 : 0
  
  vpc_id = aws_vpc.this[0].id
  
  tags = merge(local.common_tags, {
    Name = "${local.project_name}-${local.environment}-igw"
    Type = "internet-gateway"
  })
}

# Create NAT gateway for private subnet internet access
resource "aws_eip" "nat" {
  count = var.vpc_id == "" ? 1 : 0
  
  domain = "vpc"
  depends_on = [aws_internet_gateway.this]
  
  tags = merge(local.common_tags, {
    Name = "${local.project_name}-${local.environment}-nat-eip"
    Type = "elastic-ip"
  })
}

resource "aws_nat_gateway" "this" {
  count = var.vpc_id == "" ? 1 : 0
  
  allocation_id = aws_eip.nat[0].id
  subnet_id     = aws_subnet.public[0].id
  
  tags = merge(local.common_tags, {
    Name = "${local.project_name}-${local.environment}-nat-gw"
    Type = "nat-gateway"
  })
  
  depends_on = [aws_internet_gateway.this]
}

# Route tables
resource "aws_route_table" "public" {
  count = var.vpc_id == "" ? 1 : 0
  
  vpc_id = aws_vpc.this[0].id
  
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this[0].id
  }
  
  tags = merge(local.common_tags, {
    Name = "${local.project_name}-${local.environment}-public-rt"
    Type = "route-table"
  })
}

resource "aws_route_table" "private" {
  count = var.vpc_id == "" ? 1 : 0
  
  vpc_id = aws_vpc.this[0].id
  
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.this[0].id
  }
  
  tags = merge(local.common_tags, {
    Name = "${local.project_name}-${local.environment}-private-rt"
    Type = "route-table"
  })
}

# Route table associations
resource "aws_route_table_association" "public" {
  count = var.vpc_id == "" && var.enable_load_balancer ? 2 : 0
  
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public[0].id
}

resource "aws_route_table_association" "private" {
  count = var.vpc_id == "" ? 2 : 0
  
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[0].id
}

# ======================================================================
# Security Groups
# ======================================================================

# Security group for ECS service
resource "aws_security_group" "ecs" {
  name        = "${local.project_name}-${local.environment}-ecs-sg"
  description = "Security group for LabArchives MCP Server ECS service"
  vpc_id      = local.vpc_id != "" ? local.vpc_id : aws_vpc.this[0].id
  
  # Ingress rules for MCP protocol
  ingress {
    description = "MCP Protocol Port"
    from_port   = local.container_port
    to_port     = local.container_port
    protocol    = "tcp"
    cidr_blocks = local.allowed_cidr_blocks
  }
  
  # Health check access
  ingress {
    description = "Health Check"
    from_port   = local.container_port
    to_port     = local.container_port
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"]
  }
  
  # Egress rules for external API access
  egress {
    description = "HTTPS to LabArchives API"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  egress {
    description = "HTTP for health checks"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  egress {
    description = "DNS"
    from_port   = 53
    to_port     = 53
    protocol    = "udp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  # Database access (if enabled)
  dynamic "egress" {
    for_each = var.db_enabled ? [1] : []
    content {
      description     = "Database access"
      from_port       = 5432
      to_port         = 5432
      protocol        = "tcp"
      security_groups = [aws_security_group.rds[0].id]
    }
  }
  
  tags = merge(local.common_tags, {
    Name = "${local.project_name}-${local.environment}-ecs-sg"
    Type = "security-group"
  })
}

# Security group for RDS (if enabled)
resource "aws_security_group" "rds" {
  count = var.db_enabled ? 1 : 0
  
  name        = "${local.project_name}-${local.environment}-rds-sg"
  description = "Security group for LabArchives MCP Server RDS instance"
  vpc_id      = local.vpc_id != "" ? local.vpc_id : aws_vpc.this[0].id
  
  # Ingress from ECS service
  ingress {
    description     = "Database access from ECS"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs.id]
  }
  
  tags = merge(local.common_tags, {
    Name = "${local.project_name}-${local.environment}-rds-sg"
    Type = "security-group"
  })
}

# ======================================================================
# CloudWatch Resources
# ======================================================================

# SNS topic for alerts
resource "aws_sns_topic" "alerts" {
  name = local.sns_topic_name
  
  tags = merge(local.common_tags, {
    Name = local.sns_topic_name
    Type = "sns-topic"
  })
}

# CloudWatch log group for ECS
resource "aws_cloudwatch_log_group" "ecs" {
  name              = local.ecs_log_group
  retention_in_days = 30
  
  tags = merge(local.common_tags, {
    Name = local.ecs_log_group
    Type = "cloudwatch-log-group"
  })
}

# ======================================================================
# KMS Resources for Encryption
# ======================================================================

# KMS key for encryption at rest
resource "aws_kms_key" "main" {
  description             = "KMS key for LabArchives MCP Server encryption"
  deletion_window_in_days = 7
  
  tags = merge(local.common_tags, {
    Name = "${local.project_name}-${local.environment}-kms-key"
    Type = "kms-key"
  })
}

# KMS key alias
resource "aws_kms_alias" "main" {
  name          = "alias/${local.project_name}-${local.environment}"
  target_key_id = aws_kms_key.main.key_id
}

# ======================================================================
# ECS Module
# ======================================================================

# ECS module for container orchestration
module "ecs" {
  source = "./modules/ecs"
  
  # Cluster configuration
  cluster_name = local.ecs_cluster_name
  service_name = local.ecs_service_name
  task_family  = "${local.ecs_service_name}-task"
  
  # Container configuration
  container_image = local.container_image
  container_port  = local.container_port
  
  # Resource allocation
  cpu           = 256
  memory        = 512
  desired_count = var.desired_count
  
  # Environment variables
  environment = local.container_environment
  
  # Network configuration
  vpc_id             = local.vpc_id != "" ? local.vpc_id : aws_vpc.this[0].id
  subnets           = length(local.subnet_ids) > 0 ? local.subnet_ids : aws_subnet.private[*].id
  security_groups   = [aws_security_group.ecs.id]
  assign_public_ip  = false
  
  # Logging configuration
  log_group_name = aws_cloudwatch_log_group.ecs.name
  
  # Load balancer configuration
  enable_load_balancer = local.enable_load_balancer
  
  # Auto-scaling configuration
  enable_autoscaling = true
  min_capacity      = local.min_capacity
  max_capacity      = local.max_capacity
  
  # Monitoring configuration
  enable_monitoring = local.enable_monitoring
  sns_topic_arn    = aws_sns_topic.alerts.arn
  
  # Security configuration
  cloudwatch_kms_key_id = aws_kms_key.main.arn
  kms_key_id           = aws_kms_key.main.arn
  
  # Service discovery
  enable_service_discovery = false
  
  # Health check configuration
  health_check_grace_period_seconds = 300
  
  # Deployment configuration
  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent        = 200
  
  # Platform configuration
  launch_type      = "FARGATE"
  platform_version = "LATEST"
  
  # Optional EFS configuration
  enable_efs = false
  
  # Load balancer configuration
  allowed_cidr_blocks = local.allowed_cidr_blocks
  
  # S3 bucket for ALB logs (if load balancer is enabled)
  s3_bucket_name = var.enable_load_balancer ? "${local.project_name}-${local.environment}-alb-logs-${random_string.suffix.result}" : ""
  alb_access_logs_bucket = var.enable_load_balancer ? "${local.project_name}-${local.environment}-alb-logs-${random_string.suffix.result}" : ""
  
  # Tags
  tags = local.common_tags
  
  depends_on = [
    aws_cloudwatch_log_group.ecs,
    aws_security_group.ecs,
    aws_kms_key.main
  ]
}

# ======================================================================
# RDS Module (Optional)
# ======================================================================

# RDS module for optional database services
module "rds" {
  count = var.db_enabled ? 1 : 0
  
  source = "./modules/rds"
  
  # Database engine configuration
  engine         = "postgres"
  engine_version = "15.4"
  instance_class = "db.t3.micro"
  
  # Database configuration
  db_name  = "labarchives_mcp"
  username = "labarchives_admin"
  password = var.db_password
  
  # Storage configuration
  allocated_storage     = 20
  max_allocated_storage = 100
  storage_type         = "gp3"
  storage_encrypted    = true
  kms_key_id          = aws_kms_key.main.arn
  
  # Network configuration
  vpc_security_group_ids = [aws_security_group.rds[0].id]
  subnet_ids            = length(local.subnet_ids) > 0 ? local.subnet_ids : aws_subnet.private[*].id
  publicly_accessible   = false
  port                  = 5432
  
  # High availability configuration
  multi_az                = var.environment == "production" ? true : false
  backup_retention_period = 7
  backup_window          = "03:00-04:00"
  maintenance_window     = "sun:03:00-sun:04:00"
  
  # Security configuration
  deletion_protection                = var.environment == "production" ? true : false
  iam_database_authentication_enabled = true
  
  # Monitoring configuration
  monitoring_interval                = 60
  performance_insights_enabled       = true
  performance_insights_retention_period = 7
  enabled_cloudwatch_logs_exports    = ["postgresql"]
  
  # Backup and snapshot configuration
  skip_final_snapshot = var.environment == "production" ? false : true
  copy_tags_to_snapshot = true
  
  # Parameter group configuration
  parameter_group_family = "postgres15"
  db_parameters = [
    {
      name  = "log_statement"
      value = "all"
    },
    {
      name  = "log_min_duration_statement"
      value = "1000"
    }
  ]
  
  # Auto-scaling configuration
  auto_minor_version_upgrade = true
  apply_immediately         = false
  allow_major_version_upgrade = false
  
  # Environment configuration
  environment    = local.environment
  project_name   = local.project_name
  team_name      = "platform-team"
  cost_center    = "engineering"
  
  # Notification configuration
  notification_topic_arn = aws_sns_topic.alerts.arn
  
  # Compliance configuration
  compliance_tags = {
    DataClassification = "internal"
    RetentionPolicy   = "7-years"
    Compliance        = "SOC2,ISO27001,HIPAA,GDPR"
  }
  
  # Tags
  tags = local.common_tags
  
  depends_on = [
    aws_security_group.rds,
    aws_kms_key.main
  ]
}

# ======================================================================
# Outputs
# ======================================================================

# ECS Service URL
output "ecs_service_url" {
  description = "Public URL or endpoint of the ECS service running the LabArchives MCP Server"
  value       = var.enable_load_balancer ? "http://${module.ecs.ecs_service_load_balancer_dns}" : "Internal service - no public endpoint"
}

# VPC ID
output "vpc_id" {
  description = "VPC ID used for the deployment"
  value       = local.vpc_id != "" ? local.vpc_id : aws_vpc.this[0].id
}

# Database endpoint (if enabled)
output "db_instance_endpoint" {
  description = "Endpoint of the RDS database instance (if enabled)"
  value       = var.db_enabled ? module.rds[0].rds_instance_endpoint : null
  sensitive   = true
}

# ECS Cluster Information
output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = module.ecs.ecs_cluster_name
}

output "ecs_service_name" {
  description = "Name of the ECS service"
  value       = module.ecs.ecs_service_name
}

# Security Group IDs
output "security_group_ids" {
  description = "Security group IDs for the deployment"
  value = {
    ecs = aws_security_group.ecs.id
    rds = var.db_enabled ? aws_security_group.rds[0].id : null
  }
}

# KMS Key Information
output "kms_key_id" {
  description = "KMS key ID used for encryption"
  value       = aws_kms_key.main.id
}

output "kms_key_arn" {
  description = "KMS key ARN used for encryption"
  value       = aws_kms_key.main.arn
}

# Monitoring Information
output "cloudwatch_log_group" {
  description = "CloudWatch log group for ECS service"
  value       = aws_cloudwatch_log_group.ecs.name
}

output "sns_topic_arn" {
  description = "SNS topic ARN for alerts"
  value       = aws_sns_topic.alerts.arn
}

# Network Information
output "subnet_ids" {
  description = "Subnet IDs used for the deployment"
  value       = length(local.subnet_ids) > 0 ? local.subnet_ids : aws_subnet.private[*].id
}

# Database Information (if enabled)
output "db_connection_info" {
  description = "Database connection information (if enabled)"
  value = var.db_enabled ? {
    endpoint = module.rds[0].rds_instance_endpoint
    port     = module.rds[0].rds_instance_port
    database = module.rds[0].rds_instance_db_name
    username = module.rds[0].rds_instance_username
  } : null
  sensitive = true
}

# Deployment Information
output "deployment_info" {
  description = "Deployment information and metadata"
  value = {
    project_name     = local.project_name
    environment      = local.environment
    aws_region       = data.aws_region.current.name
    aws_account_id   = data.aws_caller_identity.current.account_id
    deployment_time  = timestamp()
    terraform_version = "1.3.0"
    module_version   = "1.0.0"
  }
}