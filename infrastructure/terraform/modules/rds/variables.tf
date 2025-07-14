# =============================================================================
# RDS Module Variables
# =============================================================================
# This file defines input variables for the RDS (Relational Database Service) 
# Terraform module. It specifies all configurable parameters required to 
# provision and manage an RDS instance or cluster, enabling reusability and 
# parameterization across different environments and deployment scenarios.
#
# The RDS module supports future extensibility for the LabArchives MCP Server,
# which is primarily stateless but may require persistent storage for audit logs,
# caching, or future write-back features.
#
# Security and compliance considerations are built into these variables to 
# support SOC2, ISO 27001, HIPAA, and GDPR requirements.
# =============================================================================

# -----------------------------------------------------------------------------
# Database Engine Configuration
# -----------------------------------------------------------------------------

variable "engine" {
  description = "The database engine to use (e.g., 'postgres', 'mysql', 'mariadb', 'oracle-se2', 'sqlserver-ee'). For the LabArchives MCP Server, PostgreSQL is recommended for its JSON support and compliance features."
  type        = string
  default     = "postgres"

  validation {
    condition = contains([
      "postgres", "mysql", "mariadb", "oracle-se2", "oracle-ee", 
      "sqlserver-ee", "sqlserver-se", "sqlserver-ex", "sqlserver-web"
    ], var.engine)
    error_message = "Engine must be one of: postgres, mysql, mariadb, oracle-se2, oracle-ee, sqlserver-ee, sqlserver-se, sqlserver-ex, sqlserver-web."
  }
}

variable "engine_version" {
  description = "The version of the database engine. Use the latest supported version for security patches and features. For PostgreSQL, recommend 15.x or later."
  type        = string
  default     = "15.4"

  validation {
    condition     = can(regex("^[0-9]+\\.[0-9]+", var.engine_version))
    error_message = "Engine version must be in format 'major.minor' (e.g., '15.4')."
  }
}

# -----------------------------------------------------------------------------
# Instance Configuration
# -----------------------------------------------------------------------------

variable "instance_class" {
  description = "The instance type for the RDS instance (e.g., 'db.t3.micro', 'db.t3.small', 'db.r5.large'). For production workloads, use at least db.t3.small for better performance and stability."
  type        = string
  default     = "db.t3.micro"

  validation {
    condition = can(regex("^db\\.[a-z0-9]+\\.[a-z0-9]+$", var.instance_class))
    error_message = "Instance class must be a valid RDS instance type (e.g., 'db.t3.micro')."
  }
}

variable "allocated_storage" {
  description = "The amount of storage (in GB) to allocate for the RDS instance. Minimum 20GB for gp2, 100GB for gp3. Consider growth patterns and backup requirements."
  type        = number
  default     = 20

  validation {
    condition     = var.allocated_storage >= 20 && var.allocated_storage <= 65536
    error_message = "Allocated storage must be between 20 and 65536 GB."
  }
}

variable "storage_type" {
  description = "The type of storage to use ('standard', 'gp2', 'gp3', 'io1', 'io2'). gp3 is recommended for most workloads due to better performance and cost efficiency."
  type        = string
  default     = "gp3"

  validation {
    condition     = contains(["standard", "gp2", "gp3", "io1", "io2"], var.storage_type)
    error_message = "Storage type must be one of: standard, gp2, gp3, io1, io2."
  }
}

variable "max_allocated_storage" {
  description = "The upper limit to which Amazon RDS can automatically scale the storage of the DB instance. Set to 0 to disable storage autoscaling."
  type        = number
  default     = 100

  validation {
    condition     = var.max_allocated_storage == 0 || var.max_allocated_storage >= var.allocated_storage
    error_message = "Max allocated storage must be 0 (disabled) or greater than allocated storage."
  }
}

variable "storage_throughput" {
  description = "The storage throughput value for the DB instance (only for gp3 storage type). Valid values are 125-1000 MiB/s."
  type        = number
  default     = null

  validation {
    condition = var.storage_throughput == null || (var.storage_throughput >= 125 && var.storage_throughput <= 1000)
    error_message = "Storage throughput must be between 125 and 1000 MiB/s when specified."
  }
}

variable "iops" {
  description = "The amount of provisioned IOPS. Required for io1 and io2 storage types. Valid values depend on storage type and allocated storage."
  type        = number
  default     = null

  validation {
    condition = var.iops == null || var.iops >= 100
    error_message = "IOPS must be at least 100 when specified."
  }
}

# -----------------------------------------------------------------------------
# Database Configuration
# -----------------------------------------------------------------------------

variable "db_name" {
  description = "The name of the initial database to create. Must be a valid database identifier. For the LabArchives MCP Server, consider names like 'labarchives_audit' or 'mcp_logs'."
  type        = string
  default     = "labarchives_mcp"

  validation {
    condition = can(regex("^[a-zA-Z][a-zA-Z0-9_]*$", var.db_name)) && length(var.db_name) <= 63
    error_message = "Database name must start with a letter, contain only alphanumeric characters and underscores, and be at most 63 characters long."
  }
}

variable "username" {
  description = "The master username for the database. Must be a valid database user identifier. Avoid using 'root', 'admin', or 'postgres' for security reasons."
  type        = string
  default     = "labarchives_admin"

  validation {
    condition = can(regex("^[a-zA-Z][a-zA-Z0-9_]*$", var.username)) && length(var.username) <= 63
    error_message = "Username must start with a letter, contain only alphanumeric characters and underscores, and be at most 63 characters long."
  }
}

variable "password" {
  description = "The master password for the database. Must be at least 8 characters long and contain a mix of uppercase, lowercase, numbers, and special characters. This should be marked as sensitive and passed through secure channels."
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.password) >= 8
    error_message = "Password must be at least 8 characters long."
  }
}

variable "manage_master_user_password" {
  description = "Whether to manage the master user password with AWS Secrets Manager. When enabled, AWS will generate and rotate the password automatically, improving security."
  type        = bool
  default     = true
}

variable "master_user_secret_kms_key_id" {
  description = "The Amazon Web Services KMS key identifier for encrypting the master user password secret. If not specified, the default KMS key for Secrets Manager is used."
  type        = string
  default     = null
}

# -----------------------------------------------------------------------------
# Network Configuration
# -----------------------------------------------------------------------------

variable "vpc_security_group_ids" {
  description = "List of VPC security group IDs to associate with the RDS instance. These security groups control network access to the database and should follow the principle of least privilege."
  type        = list(string)
  default     = []

  validation {
    condition     = length(var.vpc_security_group_ids) > 0
    error_message = "At least one VPC security group ID must be specified."
  }
}

variable "subnet_ids" {
  description = "List of subnet IDs for the RDS instance to create a DB subnet group. For high availability, provide subnets in different availability zones. Must be private subnets for security."
  type        = list(string)
  default     = []

  validation {
    condition     = length(var.subnet_ids) >= 2
    error_message = "At least two subnet IDs must be specified for multi-AZ deployment."
  }
}

variable "publicly_accessible" {
  description = "Whether the RDS instance should be publicly accessible. Set to false for production environments to maintain security. Database should only be accessible from within the VPC."
  type        = bool
  default     = false
}

variable "port" {
  description = "The port on which the database accepts connections. Default ports: PostgreSQL (5432), MySQL (3306), MariaDB (3306), Oracle (1521), SQL Server (1433)."
  type        = number
  default     = 5432

  validation {
    condition     = var.port >= 1024 && var.port <= 65535
    error_message = "Port must be between 1024 and 65535."
  }
}

# -----------------------------------------------------------------------------
# High Availability and Disaster Recovery
# -----------------------------------------------------------------------------

variable "multi_az" {
  description = "Whether to enable Multi-AZ deployment for high availability. Recommended for production environments to ensure automatic failover in case of AZ failure."
  type        = bool
  default     = true
}

variable "backup_retention_period" {
  description = "The number of days to retain backups for the RDS instance. Must be between 0 and 35 days. For compliance requirements, consider 7-35 days retention."
  type        = number
  default     = 7

  validation {
    condition     = var.backup_retention_period >= 0 && var.backup_retention_period <= 35
    error_message = "Backup retention period must be between 0 and 35 days."
  }
}

variable "backup_window" {
  description = "The daily time range (in UTC) during which automated backups are created. Format: 'HH:MM-HH:MM' (e.g., '03:00-04:00'). Should be during low-activity periods."
  type        = string
  default     = "03:00-04:00"

  validation {
    condition = can(regex("^([01][0-9]|2[0-3]):[0-5][0-9]-([01][0-9]|2[0-3]):[0-5][0-9]$", var.backup_window))
    error_message = "Backup window must be in format 'HH:MM-HH:MM' with valid 24-hour times."
  }
}

variable "maintenance_window" {
  description = "The weekly time range (in UTC) during which system maintenance can occur. Format: 'Day:HH:MM-Day:HH:MM' (e.g., 'sun:03:00-sun:04:00'). Should be during low-activity periods."
  type        = string
  default     = "sun:03:00-sun:04:00"

  validation {
    condition = can(regex("^(sun|mon|tue|wed|thu|fri|sat):[0-2][0-9]:[0-5][0-9]-(sun|mon|tue|wed|thu|fri|sat):[0-2][0-9]:[0-5][0-9]$", var.maintenance_window))
    error_message = "Maintenance window must be in format 'day:HH:MM-day:HH:MM' with valid days and times."
  }
}

variable "copy_tags_to_snapshot" {
  description = "Whether to copy all instance tags to snapshots. Recommended for consistent tagging and cost allocation across resources."
  type        = bool
  default     = true
}

variable "skip_final_snapshot" {
  description = "Whether to skip the final snapshot when the DB instance is deleted. Set to false for production to ensure data is preserved."
  type        = bool
  default     = false
}

variable "final_snapshot_identifier" {
  description = "The name of the final snapshot when the DB instance is deleted. If not specified, a default name will be generated."
  type        = string
  default     = null
}

# -----------------------------------------------------------------------------
# Security and Encryption
# -----------------------------------------------------------------------------

variable "storage_encrypted" {
  description = "Whether to enable storage encryption for the RDS instance. Required for compliance with SOC2, ISO 27001, HIPAA, and GDPR. Always set to true for production."
  type        = bool
  default     = true
}

variable "kms_key_id" {
  description = "The ARN of the KMS key to use for encryption (if storage_encrypted is true). If not specified, the default AWS managed key for RDS is used."
  type        = string
  default     = null

  validation {
    condition = var.kms_key_id == null || can(regex("^arn:aws:kms:[a-z0-9-]+:[0-9]+:key/[a-f0-9-]+$", var.kms_key_id))
    error_message = "KMS key ID must be a valid KMS key ARN when specified."
  }
}

variable "deletion_protection" {
  description = "Whether to enable deletion protection for the RDS instance. Recommended for production environments to prevent accidental deletion."
  type        = bool
  default     = true
}

variable "iam_database_authentication_enabled" {
  description = "Whether to enable IAM database authentication. Provides additional security by allowing IAM users and roles to connect to the database."
  type        = bool
  default     = false
}

variable "ca_cert_identifier" {
  description = "The identifier of the CA certificate for the DB instance. Use 'rds-ca-2019' or newer for enhanced security."
  type        = string
  default     = "rds-ca-2019"
}

# -----------------------------------------------------------------------------
# Parameter and Option Groups
# -----------------------------------------------------------------------------

variable "parameter_group_name" {
  description = "The name of the DB parameter group to associate with the RDS instance. Create custom parameter groups for specific configuration requirements."
  type        = string
  default     = null
}

variable "parameter_group_family" {
  description = "The family of the parameter group (e.g., 'postgres15', 'mysql8.0'). Required when creating a custom parameter group."
  type        = string
  default     = "postgres15"
}

variable "option_group_name" {
  description = "The name of the DB option group to associate with the RDS instance. Used for engine-specific features and plugins."
  type        = string
  default     = null
}

variable "db_parameters" {
  description = "A list of DB parameters to apply to the parameter group. Each parameter should have 'name' and 'value' attributes."
  type = list(object({
    name  = string
    value = string
  }))
  default = []
}

# -----------------------------------------------------------------------------
# Monitoring and Performance
# -----------------------------------------------------------------------------

variable "monitoring_interval" {
  description = "The interval for collecting enhanced monitoring metrics (0, 1, 5, 10, 15, 30, 60 seconds). Set to 0 to disable enhanced monitoring."
  type        = number
  default     = 60

  validation {
    condition     = contains([0, 1, 5, 10, 15, 30, 60], var.monitoring_interval)
    error_message = "Monitoring interval must be one of: 0, 1, 5, 10, 15, 30, 60."
  }
}

variable "monitoring_role_arn" {
  description = "The ARN of the IAM role that permits RDS to send enhanced monitoring metrics to CloudWatch Logs. Required when monitoring_interval > 0."
  type        = string
  default     = null
}

variable "performance_insights_enabled" {
  description = "Whether to enable Performance Insights for the RDS instance. Provides detailed performance monitoring and analysis."
  type        = bool
  default     = true
}

variable "performance_insights_retention_period" {
  description = "The amount of time to retain Performance Insights data (7 days for free tier, 731 days for paid). Valid values: 7, 731."
  type        = number
  default     = 7

  validation {
    condition     = contains([7, 731], var.performance_insights_retention_period)
    error_message = "Performance Insights retention period must be 7 or 731 days."
  }
}

variable "performance_insights_kms_key_id" {
  description = "The ARN of the KMS key to use for encrypting Performance Insights data. If not specified, the default AWS managed key is used."
  type        = string
  default     = null
}

variable "enabled_cloudwatch_logs_exports" {
  description = "List of log types to enable for exporting to CloudWatch Logs. Valid values depend on the engine (e.g., ['postgresql'] for PostgreSQL)."
  type        = list(string)
  default     = []
}

# -----------------------------------------------------------------------------
# Auto Scaling Configuration
# -----------------------------------------------------------------------------

variable "auto_minor_version_upgrade" {
  description = "Whether to enable automatic minor version upgrades during maintenance windows. Recommended for security patches."
  type        = bool
  default     = true
}

variable "apply_immediately" {
  description = "Whether to apply changes immediately or during the next maintenance window. Use with caution for production environments."
  type        = bool
  default     = false
}

variable "allow_major_version_upgrade" {
  description = "Whether to allow major version upgrades. Should be carefully planned for production environments."
  type        = bool
  default     = false
}

# -----------------------------------------------------------------------------
# Tagging and Metadata
# -----------------------------------------------------------------------------

variable "tags" {
  description = "A map of tags to assign to the RDS resources. Include environment, project, owner, and compliance tags for proper resource management."
  type        = map(string)
  default = {
    Environment = "development"
    Project     = "labarchives-mcp-server"
    Terraform   = "true"
    Component   = "database"
  }
}

variable "db_instance_tags" {
  description = "Additional tags to apply only to the DB instance. These are merged with the general tags."
  type        = map(string)
  default     = {}
}

variable "db_subnet_group_tags" {
  description = "Additional tags to apply to the DB subnet group. These are merged with the general tags."
  type        = map(string)
  default     = {}
}

# -----------------------------------------------------------------------------
# Replica Configuration (for Read Replicas)
# -----------------------------------------------------------------------------

variable "replicate_source_db" {
  description = "The identifier of the source database to replicate. Used when creating read replicas."
  type        = string
  default     = null
}

variable "replica_mode" {
  description = "The replica mode for the RDS instance. Valid values: 'open-read-only', 'mounted'."
  type        = string
  default     = null

  validation {
    condition = var.replica_mode == null || contains(["open-read-only", "mounted"], var.replica_mode)
    error_message = "Replica mode must be 'open-read-only' or 'mounted' when specified."
  }
}

# -----------------------------------------------------------------------------
# Snapshot Configuration
# -----------------------------------------------------------------------------

variable "snapshot_identifier" {
  description = "The identifier of the snapshot to restore from when creating the RDS instance."
  type        = string
  default     = null
}

variable "restore_to_point_in_time" {
  description = "Configuration for point-in-time recovery. Should include source_db_instance_identifier and restore_time."
  type = object({
    source_db_instance_identifier = string
    restore_time                  = string
  })
  default = null
}

# -----------------------------------------------------------------------------
# Blue/Green Deployment
# -----------------------------------------------------------------------------

variable "blue_green_update" {
  description = "Configuration for blue/green deployments. Enables zero-downtime updates for supported engine versions."
  type = object({
    enabled = bool
  })
  default = null
}

# -----------------------------------------------------------------------------
# Custom Endpoints (for Aurora clusters)
# -----------------------------------------------------------------------------

variable "custom_endpoints" {
  description = "List of custom endpoints for Aurora clusters. Each endpoint should specify type and static_members."
  type = list(object({
    identifier       = string
    type            = string
    static_members  = list(string)
    excluded_members = list(string)
  }))
  default = []
}

# -----------------------------------------------------------------------------
# Environment-specific Overrides
# -----------------------------------------------------------------------------

variable "environment" {
  description = "The deployment environment (development, staging, production). Used to apply environment-specific configurations."
  type        = string
  default     = "development"

  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "Environment must be one of: development, staging, production."
  }
}

variable "project_name" {
  description = "The name of the project. Used for resource naming and tagging consistency."
  type        = string
  default     = "labarchives-mcp-server"

  validation {
    condition     = can(regex("^[a-zA-Z][a-zA-Z0-9-_]*$", var.project_name))
    error_message = "Project name must start with a letter and contain only alphanumeric characters, hyphens, and underscores."
  }
}

variable "team_name" {
  description = "The name of the team responsible for this resource. Used for cost allocation and support contact."
  type        = string
  default     = "platform-team"
}

variable "cost_center" {
  description = "The cost center for billing and cost allocation. Used for financial tracking and reporting."
  type        = string
  default     = "engineering"
}

# -----------------------------------------------------------------------------
# Compliance and Governance
# -----------------------------------------------------------------------------

variable "compliance_tags" {
  description = "Additional tags required for compliance and governance. Include data classification, retention policies, and regulatory requirements."
  type        = map(string)
  default = {
    DataClassification = "internal"
    RetentionPolicy   = "7-years"
    Compliance        = "SOC2,ISO27001,GDPR"
  }
}

variable "data_classification" {
  description = "The data classification level for the database content (public, internal, confidential, restricted)."
  type        = string
  default     = "internal"

  validation {
    condition     = contains(["public", "internal", "confidential", "restricted"], var.data_classification)
    error_message = "Data classification must be one of: public, internal, confidential, restricted."
  }
}

variable "backup_compliance_required" {
  description = "Whether backup compliance is required for this database. Enforces stricter backup and retention policies."
  type        = bool
  default     = true
}

# -----------------------------------------------------------------------------
# Notification Configuration
# -----------------------------------------------------------------------------

variable "notification_topic_arn" {
  description = "The ARN of the SNS topic for RDS event notifications. Used for alerting on database events."
  type        = string
  default     = null
}

variable "event_categories" {
  description = "List of RDS event categories to subscribe to for notifications."
  type        = list(string)
  default     = ["availability", "backup", "configuration change", "failover", "failure", "maintenance", "security"]
}

# -----------------------------------------------------------------------------
# Advanced Configuration
# -----------------------------------------------------------------------------

variable "character_set_name" {
  description = "The character set name for the database (Oracle and SQL Server only)."
  type        = string
  default     = null
}

variable "nchar_character_set_name" {
  description = "The national character set name for the database (Oracle only)."
  type        = string
  default     = null
}

variable "timezone" {
  description = "The timezone for the database (SQL Server only)."
  type        = string
  default     = null
}

variable "license_model" {
  description = "The license model for the database (Oracle and SQL Server). Valid values: 'bring-your-own-license', 'license-included'."
  type        = string
  default     = null

  validation {
    condition = var.license_model == null || contains(["bring-your-own-license", "license-included"], var.license_model)
    error_message = "License model must be 'bring-your-own-license' or 'license-included' when specified."
  }
}

variable "domain" {
  description = "The Active Directory domain for the database (SQL Server only)."
  type        = string
  default     = null
}

variable "domain_iam_role_name" {
  description = "The name of the IAM role for Active Directory authentication (SQL Server only)."
  type        = string
  default     = null
}

# -----------------------------------------------------------------------------
# Module Metadata
# -----------------------------------------------------------------------------

variable "module_version" {
  description = "The version of this RDS module for tracking and compatibility."
  type        = string
  default     = "1.0.0"
}

variable "terraform_version" {
  description = "The minimum Terraform version required for this module."
  type        = string
  default     = "1.0"
}

variable "aws_provider_version" {
  description = "The minimum AWS provider version required for this module."
  type        = string
  default     = "5.0"
}