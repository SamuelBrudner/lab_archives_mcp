# RDS Instance Endpoint Output
# Exposes the DNS endpoint of the RDS instance for application connectivity
output "rds_instance_endpoint" {
  description = "The DNS endpoint of the RDS instance, used by applications to connect to the database"
  value       = aws_db_instance.this.endpoint
  sensitive   = false
}

# RDS Instance Port Output
# Exposes the port number on which the RDS instance is listening
output "rds_instance_port" {
  description = "The port number on which the RDS instance is listening (typically 5432 for PostgreSQL, 3306 for MySQL, etc.)"
  value       = aws_db_instance.this.port
  sensitive   = false
}

# RDS Instance Database Name Output
# Exposes the name of the initial database created in the RDS instance
output "rds_instance_db_name" {
  description = "The name of the initial database created in the RDS instance"
  value       = aws_db_instance.this.db_name
  sensitive   = false
}

# RDS Instance Master Username Output
# Exposes the master username for the RDS instance (marked as sensitive for security)
output "rds_instance_username" {
  description = "The master username for the RDS instance, used for initial authentication"
  value       = aws_db_instance.this.username
  sensitive   = true
}

# RDS Instance Resource ID Output
# Exposes the unique resource identifier for the RDS instance
output "rds_instance_resource_id" {
  description = "The unique resource identifier for the RDS instance, useful for referencing in other modules or for monitoring"
  value       = aws_db_instance.this.resource_id
  sensitive   = false
}

# RDS Instance ARN Output
# Exposes the Amazon Resource Name (ARN) of the RDS instance
output "rds_instance_arn" {
  description = "The Amazon Resource Name (ARN) of the RDS instance, used for IAM policies and cross-service references"
  value       = aws_db_instance.this.arn
  sensitive   = false
}