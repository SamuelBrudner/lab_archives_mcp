# ======================================================================
# ECS Module Main Configuration
# ======================================================================
# This Terraform module provisions AWS ECS resources for deploying the
# LabArchives MCP Server as a containerized service, supporting scalable
# and secure deployment in a cloud environment with comprehensive
# infrastructure as code implementation.
# ======================================================================

# Data Sources
# ======================================================================

# Get current AWS region for resource placement and logging configuration
data "aws_region" "current" {}

# Get current AWS account ID for IAM role ARN construction
data "aws_caller_identity" "current" {}

# Local Values
# ======================================================================

locals {
  # Common tags for all resources
  common_tags = merge(var.tags, {
    Module      = "ecs"
    Service     = "labarchives-mcp-server"
    Environment = var.tags.Environment
  })

  # Container definitions for ECS task definition
  container_definitions = jsonencode([
    {
      name         = var.service_name
      image        = var.container_image
      cpu          = var.cpu
      memory       = var.memory
      essential    = true
      networkMode  = "awsvpc"
      
      # Port mappings for MCP protocol communication
      portMappings = [
        {
          containerPort = var.container_port
          hostPort      = var.container_port
          protocol      = "tcp"
        }
      ]
      
      # Environment variables for LabArchives MCP Server configuration
      environment = [
        for key, value in var.environment : {
          name  = key
          value = value
        }
      ]
      
      # CloudWatch logging configuration for audit and compliance
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = var.log_group_name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = var.service_name
        }
      }
      
      # Health check configuration for service reliability
      healthCheck = {
        command = [
          "CMD-SHELL",
          "curl -f http://localhost:${var.container_port}/health || exit 1"
        ]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
      
      # Stop timeout for graceful shutdown
      stopTimeout = 30
      
      # Resource limits for optimal performance
      memoryReservation = var.memory / 2
      
      # Security settings
      readonlyRootFilesystem = false
      privileged             = false
      user                   = "1000:1000"
      
      # Working directory
      workingDirectory = "/app"
    }
  ])
}

# CloudWatch Log Group
# ======================================================================

# CloudWatch log group for ECS container logs with retention and security
resource "aws_cloudwatch_log_group" "this" {
  name              = var.log_group_name
  retention_in_days = 30
  
  # Encryption at rest for compliance with SOC2, ISO 27001, HIPAA, GDPR
  kms_key_id = var.cloudwatch_kms_key_id
  
  tags = merge(local.common_tags, {
    Name        = "${var.service_name}-logs"
    Component   = "logging"
    DataClass   = "audit"
    Compliance  = "SOC2,ISO27001,HIPAA,GDPR"
  })
}

# IAM Roles and Policies
# ======================================================================

# ECS Task Execution Role - Required for pulling images and writing logs
resource "aws_iam_role" "ecs_task_execution_role" {
  name = "${var.service_name}-ecs-task-execution-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })
  
  tags = merge(local.common_tags, {
    Name      = "${var.service_name}-execution-role"
    Component = "iam"
    Purpose   = "ecs-task-execution"
  })
}

# Attach AWS managed policy for ECS task execution
resource "aws_iam_role_policy_attachment" "ecs_task_execution_policy" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Additional policy for CloudWatch logs and ECR access
resource "aws_iam_role_policy" "ecs_task_execution_additional" {
  name = "${var.service_name}-ecs-execution-additional"
  role = aws_iam_role.ecs_task_execution_role.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams"
        ]
        Resource = [
          aws_cloudwatch_log_group.this.arn,
          "${aws_cloudwatch_log_group.this.arn}:*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = "*"
      }
    ]
  })
}

# ECS Task Role - Runtime permissions for LabArchives MCP Server
resource "aws_iam_role" "ecs_task_role" {
  name = "${var.service_name}-ecs-task-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })
  
  tags = merge(local.common_tags, {
    Name      = "${var.service_name}-task-role"
    Component = "iam"
    Purpose   = "ecs-task-runtime"
  })
}

# Task role policy for LabArchives MCP Server operations
resource "aws_iam_role_policy" "ecs_task_policy" {
  name = "${var.service_name}-ecs-task-policy"
  role = aws_iam_role.ecs_task_role.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:${var.log_group_name}:*"
      },
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParametersByPath"
        ]
        Resource = "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:parameter/labarchives-mcp/*"
      }
    ]
  })
}

# Security Group
# ======================================================================

# Security group for ECS service with controlled network access
resource "aws_security_group" "ecs_service" {
  name        = "${var.service_name}-ecs-sg"
  description = "Security group for ${var.service_name} ECS service"
  vpc_id      = var.vpc_id
  
  # Ingress rules for MCP protocol communication
  ingress {
    description = "MCP Protocol Port"
    from_port   = var.container_port
    to_port     = var.container_port
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
  }
  
  # Health check port for load balancer
  ingress {
    description = "Health Check Port"
    from_port   = var.container_port
    to_port     = var.container_port
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"]
  }
  
  # Egress rules for external API access
  egress {
    description = "HTTPS for LabArchives API"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  egress {
    description = "HTTP for external dependencies"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  # DNS resolution
  egress {
    description = "DNS"
    from_port   = 53
    to_port     = 53
    protocol    = "udp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = merge(local.common_tags, {
    Name      = "${var.service_name}-sg"
    Component = "security"
    Purpose   = "ecs-network-access"
  })
}

# ECS Cluster
# ======================================================================

# ECS cluster for LabArchives MCP Server deployment
resource "aws_ecs_cluster" "this" {
  name = var.cluster_name
  
  # Container insights for monitoring and observability
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
  
  # Configuration for enhanced monitoring
  configuration {
    execute_command_configuration {
      kms_key_id = var.kms_key_id
      logging    = "OVERRIDE"
      
      log_configuration {
        cloud_watch_encryption_enabled = true
        cloud_watch_log_group_name     = aws_cloudwatch_log_group.this.name
        s3_bucket_name                 = var.s3_bucket_name
        s3_encryption_enabled          = true
        s3_key_prefix                  = "ecs-exec-logs/"
      }
    }
  }
  
  tags = merge(local.common_tags, {
    Name      = var.cluster_name
    Component = "compute"
    Purpose   = "mcp-server-cluster"
  })
}

# ECS Task Definition
# ======================================================================

# ECS task definition for LabArchives MCP Server container
resource "aws_ecs_task_definition" "this" {
  family                   = var.task_family
  network_mode             = "awsvpc"
  requires_compatibilities = [var.launch_type]
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn
  
  # Container definitions with security and compliance configurations
  container_definitions = local.container_definitions
  
  # Platform configuration for Fargate
  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
  
  # Volume configuration for temporary storage
  dynamic "volume" {
    for_each = var.enable_efs ? [1] : []
    content {
      name = "efs-storage"
      efs_volume_configuration {
        file_system_id          = var.efs_file_system_id
        root_directory          = "/opt/data"
        transit_encryption      = "ENABLED"
        transit_encryption_port = 2049
        authorization_config {
          access_point_id = var.efs_access_point_id
          iam             = "ENABLED"
        }
      }
    }
  }
  
  tags = merge(local.common_tags, {
    Name      = "${var.service_name}-task-definition"
    Component = "compute"
    Purpose   = "mcp-server-task"
  })
}

# Application Load Balancer
# ======================================================================

# Application Load Balancer for ECS service (if enabled)
resource "aws_lb" "ecs_service" {
  count              = var.enable_load_balancer ? 1 : 0
  name               = "${var.service_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.ecs_service.id]
  subnets            = var.subnets
  
  enable_deletion_protection = false
  
  access_logs {
    bucket  = var.alb_access_logs_bucket
    prefix  = "alb-logs"
    enabled = true
  }
  
  tags = merge(local.common_tags, {
    Name      = "${var.service_name}-alb"
    Component = "networking"
    Purpose   = "load-balancer"
  })
}

# Target Group for Load Balancer
resource "aws_lb_target_group" "ecs_service" {
  count       = var.enable_load_balancer ? 1 : 0
  name        = "${var.service_name}-tg"
  port        = var.container_port
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"
  
  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 2
    timeout             = 5
    interval            = 30
    path                = "/health"
    matcher             = "200"
    port                = "traffic-port"
    protocol            = "HTTP"
  }
  
  tags = merge(local.common_tags, {
    Name      = "${var.service_name}-tg"
    Component = "networking"
    Purpose   = "target-group"
  })
}

# Load Balancer Listener
resource "aws_lb_listener" "ecs_service" {
  count             = var.enable_load_balancer ? 1 : 0
  load_balancer_arn = aws_lb.ecs_service[0].arn
  port              = "80"
  protocol          = "HTTP"
  
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.ecs_service[0].arn
  }
  
  tags = merge(local.common_tags, {
    Name      = "${var.service_name}-listener"
    Component = "networking"
    Purpose   = "alb-listener"
  })
}

# ECS Service
# ======================================================================

# ECS service for running and managing LabArchives MCP Server tasks
resource "aws_ecs_service" "this" {
  name            = var.service_name
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.this.arn
  desired_count   = var.desired_count
  launch_type     = var.launch_type
  platform_version = var.platform_version
  
  # Network configuration for Fargate
  network_configuration {
    subnets          = var.subnets
    security_groups  = [aws_security_group.ecs_service.id]
    assign_public_ip = var.assign_public_ip
  }
  
  # Load balancer configuration (if enabled)
  dynamic "load_balancer" {
    for_each = var.enable_load_balancer ? [1] : []
    content {
      target_group_arn = aws_lb_target_group.ecs_service[0].arn
      container_name   = var.service_name
      container_port   = var.container_port
    }
  }
  
  # Deployment configuration for rolling updates
  deployment_configuration {
    maximum_percent         = var.deployment_maximum_percent
    minimum_healthy_percent = var.deployment_minimum_healthy_percent
    
    deployment_circuit_breaker {
      enable   = true
      rollback = true
    }
  }
  
  # Service discovery configuration (if enabled)
  dynamic "service_registries" {
    for_each = var.enable_service_discovery ? [1] : []
    content {
      registry_arn = aws_service_discovery_service.this[0].arn
      port         = var.container_port
    }
  }
  
  # Health check grace period
  health_check_grace_period_seconds = var.health_check_grace_period_seconds
  
  # Enable execute command for debugging
  enable_execute_command = true
  
  # Force new deployment on changes
  force_new_deployment = true
  
  # Wait for steady state during deployment
  wait_for_steady_state = true
  
  tags = merge(local.common_tags, {
    Name      = var.service_name
    Component = "compute"
    Purpose   = "mcp-server-service"
  })
  
  depends_on = [
    aws_iam_role_policy_attachment.ecs_task_execution_policy,
    aws_iam_role_policy.ecs_task_execution_additional,
    aws_iam_role_policy.ecs_task_policy,
    aws_cloudwatch_log_group.this
  ]
}

# Service Discovery
# ======================================================================

# Service discovery service (if enabled)
resource "aws_service_discovery_service" "this" {
  count = var.enable_service_discovery ? 1 : 0
  name  = var.service_name
  
  dns_config {
    namespace_id = var.service_discovery_namespace_id
    
    dns_records {
      ttl  = 10
      type = "A"
    }
    
    routing_policy = "MULTIVALUE"
  }
  
  health_check_grace_period_seconds = var.health_check_grace_period_seconds
  
  tags = merge(local.common_tags, {
    Name      = "${var.service_name}-discovery"
    Component = "networking"
    Purpose   = "service-discovery"
  })
}

# Auto Scaling
# ======================================================================

# Auto Scaling Target (if enabled)
resource "aws_appautoscaling_target" "ecs_service" {
  count              = var.enable_autoscaling ? 1 : 0
  max_capacity       = var.max_capacity
  min_capacity       = var.min_capacity
  resource_id        = "service/${aws_ecs_cluster.this.name}/${aws_ecs_service.this.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
  
  tags = merge(local.common_tags, {
    Name      = "${var.service_name}-autoscaling-target"
    Component = "scaling"
    Purpose   = "autoscaling"
  })
}

# Auto Scaling Policy - Scale Up
resource "aws_appautoscaling_policy" "ecs_service_scale_up" {
  count              = var.enable_autoscaling ? 1 : 0
  name               = "${var.service_name}-scale-up"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ecs_service[0].resource_id
  scalable_dimension = aws_appautoscaling_target.ecs_service[0].scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs_service[0].service_namespace
  
  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value = 70.0
  }
}

# Auto Scaling Policy - Scale Down
resource "aws_appautoscaling_policy" "ecs_service_scale_down" {
  count              = var.enable_autoscaling ? 1 : 0
  name               = "${var.service_name}-scale-down"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ecs_service[0].resource_id
  scalable_dimension = aws_appautoscaling_target.ecs_service[0].scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs_service[0].service_namespace
  
  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageMemoryUtilization"
    }
    target_value = 80.0
  }
}

# ======================================================================
# Security and Compliance Features
# ======================================================================

# CloudWatch Alarms for monitoring
resource "aws_cloudwatch_metric_alarm" "ecs_service_cpu" {
  alarm_name          = "${var.service_name}-cpu-utilization"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors ECS service CPU utilization"
  alarm_actions       = [var.sns_topic_arn]
  
  dimensions = {
    ServiceName = aws_ecs_service.this.name
    ClusterName = aws_ecs_cluster.this.name
  }
  
  tags = merge(local.common_tags, {
    Name      = "${var.service_name}-cpu-alarm"
    Component = "monitoring"
    Purpose   = "cpu-monitoring"
  })
}

# CloudWatch Alarms for memory monitoring
resource "aws_cloudwatch_metric_alarm" "ecs_service_memory" {
  alarm_name          = "${var.service_name}-memory-utilization"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = "300"
  statistic           = "Average"
  threshold           = "85"
  alarm_description   = "This metric monitors ECS service memory utilization"
  alarm_actions       = [var.sns_topic_arn]
  
  dimensions = {
    ServiceName = aws_ecs_service.this.name
    ClusterName = aws_ecs_cluster.this.name
  }
  
  tags = merge(local.common_tags, {
    Name      = "${var.service_name}-memory-alarm"
    Component = "monitoring"
    Purpose   = "memory-monitoring"
  })
}

# ======================================================================
# End of ECS Module Main Configuration
# ======================================================================