# LabArchives MCP Server - Terraform Providers Configuration
# This file specifies the external cloud and infrastructure providers and their versions
# for provisioning and managing infrastructure resources for the LabArchives MCP Server deployment.

# Terraform version and provider requirements
terraform {
  required_version = ">= 1.4.0"
  
  required_providers {
    # AWS Provider - Primary cloud provider for infrastructure resources
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0.0, < 6.0.0"
    }
    
    # Random Provider - Generate random values for resource names, passwords, and secrets
    random = {
      source  = "hashicorp/random"
      version = ">= 3.5.1"
    }
    
    # Null Provider - Execute provisioners and local-exec/remote-exec scripts
    null = {
      source  = "hashicorp/null"
      version = ">= 3.2.1"
    }
  }
}

# AWS Provider Configuration
# Configures the AWS provider with region and profile specified via variables
# and applies default tags to all AWS resources for environment and project identification
provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile
  
  # Default tags applied to all AWS resources for consistent resource management
  default_tags {
    tags = {
      Environment = var.environment
      Project     = "labarchives-mcp-server"
    }
  }
}

# Random Provider Configuration
# No explicit configuration required - used for generating random values
# such as random suffixes for S3 buckets, database passwords, and resource identifiers
provider "random" {
  # No configuration parameters required
}

# Null Provider Configuration  
# No explicit configuration required - used for running provisioners
# and local-exec/remote-exec scripts as part of infrastructure orchestration
provider "null" {
  # No configuration parameters required
}