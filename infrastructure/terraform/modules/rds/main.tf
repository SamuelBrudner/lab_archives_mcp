# =============================================================================
# RDS Module - Main Configuration
# =============================================================================
# This Terraform module provisions Amazon RDS (Relational Database Service) 
# instances with comprehensive security, compliance, and operational features.
# 
# The module supports:
# - Single RDS instances with multi-AZ deployment
# - Automated backup and maintenance windows
# - Encryption at rest and in transit
# - AWS Secrets Manager integration for credentials
# - Performance Insights and enhanced monitoring
# - Compliance features for SOC2, ISO 27001, HIPAA, and GDPR
# - Custom parameter and option groups
# - Comprehensive tagging and resource management
#
# Provider version: hashicorp/aws >= 5.0.0
# =============================================================================

terraform {
  required_version = ">= 1.0"
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

# -----------------------------------------------------------------------------
# Local Variables and Data Sources
# -----------------------------------------------------------------------------

locals {
  # Common resource naming convention
  resource_prefix = "${var.project_name}-${var.environment}"
  
  # Merged tags for consistent resource tagging
  common_tags = merge(
    var.tags,
    var.compliance_tags,
    {
      Name           = "${local.resource_prefix}-rds"
      Environment    = var.environment
      Project        = var.project_name
      Team           = var.team_name
      CostCenter     = var.cost_center
      ManagedBy      = "terraform"
      ModuleVersion  = var.module_version
      CreatedDate    = formatdate("YYYY-MM-DD", timestamp())
    }
  )

  # Database engine port mapping
  default_ports = {
    postgres    = 5432
    mysql       = 3306
    mariadb     = 3306
    oracle-se2  = 1521
    oracle-ee   = 1521
    sqlserver-ee = 1433
    sqlserver-se = 1433
    sqlserver-ex = 1433
    sqlserver-web = 1433
  }

  # Use provided port or default based on engine
  db_port = var.port != null ? var.port : lookup(local.default_ports, var.engine, 5432)

  # Enhanced monitoring IAM role ARN
  enhanced_monitoring_role_arn = var.monitoring_interval > 0 ? (
    var.monitoring_role_arn != null ? var.monitoring_role_arn : aws_iam_role.enhanced_monitoring[0].arn
  ) : null

  # Determine if we need to create a parameter group
  create_parameter_group = length(var.db_parameters) > 0 || var.parameter_group_name == null

  # Final snapshot identifier with fallback
  final_snapshot_identifier = var.final_snapshot_identifier != null ? var.final_snapshot_identifier : "${local.resource_prefix}-final-snapshot-${formatdate("YYYY-MM-DD-hhmm", timestamp())}"
}

# Data source for current AWS region
data "aws_region" "current" {}

# Data source for current AWS caller identity
data "aws_caller_identity" "current" {}

# Data source for availability zones
data "aws_availability_zones" "available" {
  state = "available"
}

# -----------------------------------------------------------------------------
# Random Password Generation
# -----------------------------------------------------------------------------

# Generate a random password if password is not provided and auto-management is disabled
resource "random_password" "master_password" {
  count = var.password == null && !var.manage_master_user_password ? 1 : 0

  length      = 16
  min_upper   = 2
  min_lower   = 2
  min_numeric = 2
  min_special = 2
  special     = true
  
  # Exclude characters that might cause issues in connection strings
  override_special = "!#$%&*()-_=+[]{}<>?"
  
  keepers = {
    # Force password regeneration if the username changes
    username = var.username
  }
}

# -----------------------------------------------------------------------------
# Enhanced Monitoring IAM Role
# -----------------------------------------------------------------------------

# IAM role for enhanced monitoring (created only if monitoring is enabled and no role is provided)
resource "aws_iam_role" "enhanced_monitoring" {
  count = var.monitoring_interval > 0 && var.monitoring_role_arn == null ? 1 : 0

  name = "${local.resource_prefix}-rds-enhanced-monitoring"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name = "${local.resource_prefix}-rds-enhanced-monitoring"
    Type = "iam-role"
  })
}

# Attach the enhanced monitoring policy to the role
resource "aws_iam_role_policy_attachment" "enhanced_monitoring" {
  count = var.monitoring_interval > 0 && var.monitoring_role_arn == null ? 1 : 0

  role       = aws_iam_role.enhanced_monitoring[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}

# -----------------------------------------------------------------------------
# DB Subnet Group
# -----------------------------------------------------------------------------

# Create DB subnet group for RDS placement
resource "aws_db_subnet_group" "this" {
  name       = "${local.resource_prefix}-rds-subnet-group"
  subnet_ids = var.subnet_ids

  tags = merge(
    local.common_tags,
    var.db_subnet_group_tags,
    {
      Name = "${local.resource_prefix}-rds-subnet-group"
      Type = "db-subnet-group"
    }
  )

  lifecycle {
    create_before_destroy = true
  }
}

# -----------------------------------------------------------------------------
# DB Parameter Group
# -----------------------------------------------------------------------------

# Create custom DB parameter group if parameters are provided
resource "aws_db_parameter_group" "this" {
  count = local.create_parameter_group ? 1 : 0

  name   = "${local.resource_prefix}-rds-parameter-group"
  family = var.parameter_group_family

  dynamic "parameter" {
    for_each = var.db_parameters
    content {
      name  = parameter.value.name
      value = parameter.value.value
    }
  }

  tags = merge(local.common_tags, {
    Name = "${local.resource_prefix}-rds-parameter-group"
    Type = "db-parameter-group"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# -----------------------------------------------------------------------------
# AWS Secrets Manager Integration
# -----------------------------------------------------------------------------

# Create AWS Secrets Manager secret for RDS credentials (when not using managed master user password)
resource "aws_secretsmanager_secret" "rds_credentials" {
  count = !var.manage_master_user_password ? 1 : 0

  name        = "${local.resource_prefix}-rds-credentials"
  description = "RDS credentials for ${var.project_name} ${var.environment} environment"
  
  kms_key_id = var.master_user_secret_kms_key_id

  tags = merge(local.common_tags, {
    Name = "${local.resource_prefix}-rds-credentials"
    Type = "secrets-manager-secret"
  })

  # Ensure secrets are properly cleaned up
  force_overwrite_replica_secret = true
}

# Store the credential values in the secret
resource "aws_secretsmanager_secret_version" "rds_credentials" {
  count = !var.manage_master_user_password ? 1 : 0

  secret_id = aws_secretsmanager_secret.rds_credentials[0].id
  secret_string = jsonencode({
    username = var.username
    password = var.password != null ? var.password : random_password.master_password[0].result
    engine   = var.engine
    host     = aws_db_instance.this.endpoint
    port     = aws_db_instance.this.port
    dbname   = aws_db_instance.this.db_name
  })

  depends_on = [aws_db_instance.this]
}

# -----------------------------------------------------------------------------
# RDS Event Subscription
# -----------------------------------------------------------------------------

# Create RDS event subscription for monitoring
resource "aws_db_event_subscription" "this" {
  count = var.notification_topic_arn != null ? 1 : 0

  name      = "${local.resource_prefix}-rds-events"
  sns_topic = var.notification_topic_arn

  source_type = "db-instance"
  source_ids  = [aws_db_instance.this.identifier]

  event_categories = var.event_categories

  tags = merge(local.common_tags, {
    Name = "${local.resource_prefix}-rds-events"
    Type = "db-event-subscription"
  })
}

# -----------------------------------------------------------------------------
# Main RDS Instance
# -----------------------------------------------------------------------------

# Create the main RDS instance
resource "aws_db_instance" "this" {
  # Basic instance configuration
  identifier     = "${local.resource_prefix}-rds"
  engine         = var.engine
  engine_version = var.engine_version
  instance_class = var.instance_class

  # Database configuration
  db_name  = var.db_name
  username = var.username
  password = var.manage_master_user_password ? null : (
    var.password != null ? var.password : random_password.master_password[0].result
  )
  
  # Managed master user password configuration
  manage_master_user_password   = var.manage_master_user_password
  master_user_secret_kms_key_id = var.manage_master_user_password ? var.master_user_secret_kms_key_id : null

  # Storage configuration
  allocated_storage      = var.allocated_storage
  max_allocated_storage  = var.max_allocated_storage > 0 ? var.max_allocated_storage : null
  storage_type          = var.storage_type
  storage_encrypted     = var.storage_encrypted
  kms_key_id           = var.storage_encrypted ? var.kms_key_id : null
  iops                 = var.iops
  storage_throughput   = var.storage_type == "gp3" ? var.storage_throughput : null

  # Network configuration
  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = var.vpc_security_group_ids
  publicly_accessible    = var.publicly_accessible
  port                   = local.db_port

  # High availability and backup configuration
  multi_az                = var.multi_az
  backup_retention_period = var.backup_retention_period
  backup_window          = var.backup_window
  maintenance_window     = var.maintenance_window
  copy_tags_to_snapshot  = var.copy_tags_to_snapshot

  # Snapshot configuration
  skip_final_snapshot       = var.skip_final_snapshot
  final_snapshot_identifier = var.skip_final_snapshot ? null : local.final_snapshot_identifier
  snapshot_identifier       = var.snapshot_identifier

  # Point-in-time recovery configuration
  dynamic "restore_to_point_in_time" {
    for_each = var.restore_to_point_in_time != null ? [var.restore_to_point_in_time] : []
    content {
      source_db_instance_identifier = restore_to_point_in_time.value.source_db_instance_identifier
      restore_time                  = restore_to_point_in_time.value.restore_time
    }
  }

  # Security configuration
  deletion_protection                = var.deletion_protection
  iam_database_authentication_enabled = var.iam_database_authentication_enabled
  ca_cert_identifier                 = var.ca_cert_identifier

  # Parameter and option groups
  parameter_group_name = local.create_parameter_group ? aws_db_parameter_group.this[0].name : var.parameter_group_name
  option_group_name    = var.option_group_name

  # Monitoring configuration
  monitoring_interval = var.monitoring_interval
  monitoring_role_arn = local.enhanced_monitoring_role_arn

  # Performance Insights configuration
  performance_insights_enabled          = var.performance_insights_enabled
  performance_insights_retention_period = var.performance_insights_enabled ? var.performance_insights_retention_period : null
  performance_insights_kms_key_id       = var.performance_insights_enabled ? var.performance_insights_kms_key_id : null

  # CloudWatch logs configuration
  enabled_cloudwatch_logs_exports = var.enabled_cloudwatch_logs_exports

  # Upgrade configuration
  auto_minor_version_upgrade = var.auto_minor_version_upgrade
  allow_major_version_upgrade = var.allow_major_version_upgrade
  apply_immediately          = var.apply_immediately

  # Replica configuration
  replicate_source_db = var.replicate_source_db
  replica_mode       = var.replica_mode

  # Blue/Green deployment configuration
  dynamic "blue_green_update" {
    for_each = var.blue_green_update != null ? [var.blue_green_update] : []
    content {
      enabled = blue_green_update.value.enabled
    }
  }

  # Engine-specific configuration
  character_set_name       = var.character_set_name
  nchar_character_set_name = var.nchar_character_set_name
  timezone                = var.timezone
  license_model           = var.license_model
  domain                  = var.domain
  domain_iam_role_name    = var.domain_iam_role_name

  # Tagging
  tags = merge(
    local.common_tags,
    var.db_instance_tags,
    {
      Name = "${local.resource_prefix}-rds"
      Type = "rds-instance"
    }
  )

  # Lifecycle management
  lifecycle {
    ignore_changes = [
      password,
      latest_restorable_time,
      status,
      availability_zone,
      endpoint,
      hosted_zone_id,
      resource_id,
      replicas,
      backup_window,
      maintenance_window
    ]
    prevent_destroy = true
  }

  # Dependencies
  depends_on = [
    aws_db_subnet_group.this,
    aws_iam_role_policy_attachment.enhanced_monitoring
  ]
}

# -----------------------------------------------------------------------------
# CloudWatch Alarms for Monitoring
# -----------------------------------------------------------------------------

# CPU utilization alarm
resource "aws_cloudwatch_metric_alarm" "cpu_utilization" {
  alarm_name          = "${local.resource_prefix}-rds-cpu-utilization"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors RDS CPU utilization"
  alarm_actions       = var.notification_topic_arn != null ? [var.notification_topic_arn] : []

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.this.identifier
  }

  tags = merge(local.common_tags, {
    Name = "${local.resource_prefix}-rds-cpu-utilization"
    Type = "cloudwatch-alarm"
  })
}

# Database connection alarm
resource "aws_cloudwatch_metric_alarm" "database_connections" {
  alarm_name          = "${local.resource_prefix}-rds-database-connections"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "50"
  alarm_description   = "This metric monitors RDS database connections"
  alarm_actions       = var.notification_topic_arn != null ? [var.notification_topic_arn] : []

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.this.identifier
  }

  tags = merge(local.common_tags, {
    Name = "${local.resource_prefix}-rds-database-connections"
    Type = "cloudwatch-alarm"
  })
}

# Free storage space alarm
resource "aws_cloudwatch_metric_alarm" "free_storage_space" {
  alarm_name          = "${local.resource_prefix}-rds-free-storage-space"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "2000000000" # 2GB in bytes
  alarm_description   = "This metric monitors RDS free storage space"
  alarm_actions       = var.notification_topic_arn != null ? [var.notification_topic_arn] : []

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.this.identifier
  }

  tags = merge(local.common_tags, {
    Name = "${local.resource_prefix}-rds-free-storage-space"
    Type = "cloudwatch-alarm"
  })
}

# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------

# RDS Instance Endpoint
output "rds_endpoint" {
  description = "The connection endpoint for the RDS instance"
  value       = aws_db_instance.this.endpoint
  sensitive   = false
}

# RDS Instance Port
output "rds_port" {
  description = "The port on which the RDS instance is listening"
  value       = aws_db_instance.this.port
  sensitive   = false
}

# RDS Instance Address
output "rds_address" {
  description = "The DNS address of the RDS instance"
  value       = aws_db_instance.this.address
  sensitive   = false
}

# RDS Instance Database Name
output "rds_db_name" {
  description = "The name of the database"
  value       = aws_db_instance.this.db_name
  sensitive   = false
}

# RDS Instance Username
output "rds_username" {
  description = "The master username for the database"
  value       = aws_db_instance.this.username
  sensitive   = true
}

# RDS Instance Resource ID
output "rds_resource_id" {
  description = "The RDS resource ID of the instance"
  value       = aws_db_instance.this.resource_id
  sensitive   = false
}

# RDS Instance ARN
output "rds_arn" {
  description = "The ARN of the RDS instance"
  value       = aws_db_instance.this.arn
  sensitive   = false
}

# RDS Instance Identifier
output "rds_identifier" {
  description = "The identifier of the RDS instance"
  value       = aws_db_instance.this.identifier
  sensitive   = false
}

# DB Subnet Group Name
output "db_subnet_group_name" {
  description = "The name of the DB subnet group"
  value       = aws_db_subnet_group.this.name
  sensitive   = false
}

# DB Subnet Group ARN
output "db_subnet_group_arn" {
  description = "The ARN of the DB subnet group"
  value       = aws_db_subnet_group.this.arn
  sensitive   = false
}

# Parameter Group Name
output "parameter_group_name" {
  description = "The name of the DB parameter group"
  value       = local.create_parameter_group ? aws_db_parameter_group.this[0].name : var.parameter_group_name
  sensitive   = false
}

# Secrets Manager Secret ARN
output "rds_credentials_secret_arn" {
  description = "The ARN of the AWS Secrets Manager secret containing the RDS credentials"
  value       = !var.manage_master_user_password ? aws_secretsmanager_secret.rds_credentials[0].arn : null
  sensitive   = false
}

# Master User Secret ARN (for managed passwords)
output "master_user_secret_arn" {
  description = "The ARN of the master user secret when using managed master user password"
  value       = var.manage_master_user_password ? aws_db_instance.this.master_user_secret[0].secret_arn : null
  sensitive   = false
}

# Enhanced Monitoring Role ARN
output "enhanced_monitoring_role_arn" {
  description = "The ARN of the enhanced monitoring IAM role"
  value       = local.enhanced_monitoring_role_arn
  sensitive   = false
}

# CloudWatch Alarm ARNs
output "cloudwatch_alarm_arns" {
  description = "ARNs of the CloudWatch alarms created for RDS monitoring"
  value = {
    cpu_utilization      = aws_cloudwatch_metric_alarm.cpu_utilization.arn
    database_connections = aws_cloudwatch_metric_alarm.database_connections.arn
    free_storage_space   = aws_cloudwatch_metric_alarm.free_storage_space.arn
  }
  sensitive = false
}

# Connection information output (for convenience)
output "connection_info" {
  description = "Database connection information"
  value = {
    endpoint = aws_db_instance.this.endpoint
    port     = aws_db_instance.this.port
    database = aws_db_instance.this.db_name
    username = aws_db_instance.this.username
  }
  sensitive = true
}