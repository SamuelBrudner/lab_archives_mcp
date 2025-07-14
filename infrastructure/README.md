# LabArchives MCP Server Infrastructure

This directory contains all necessary scripts and configuration files for deploying the LabArchives MCP Server in various environments including local development, staging, and production/cloud environments.

## Overview

The LabArchives MCP Server is designed as a **single-process, stateless desktop application** that integrates LabArchives electronic lab notebook data with AI applications through the Model Context Protocol (MCP). This infrastructure setup provides flexible deployment options while maintaining the system's core architectural principles of simplicity, security, and ease of use.

### Key Infrastructure Characteristics

- **Single-Process Application**: No distributed microservices architecture required
- **Stateless Operation**: No persistent storage or database dependencies
- **Desktop-First Design**: Optimized for local Claude Desktop integration
- **Container-Ready**: Docker support for consistent deployment across environments
- **Cloud-Capable**: Terraform modules for ECS and RDS provisioning when needed

## Directory Structure

```
infrastructure/
├── docker/
│   ├── Dockerfile                 # Production Docker image
│   ├── docker-compose.yml         # Local development orchestration
│   ├── docker-compose.dev.yml     # Development environment
│   └── docker-compose.prod.yml    # Production environment
├── kubernetes/
│   ├── deployment.yaml            # Kubernetes deployment manifest
│   ├── service.yaml               # Service configuration
│   ├── ingress.yaml               # Ingress routing rules
│   ├── configmap.yaml             # Configuration management
│   └── secret.yaml                # Secret management template
├── terraform/
│   ├── modules/
│   │   ├── ecs/                   # ECS module for container orchestration
│   │   └── rds/                   # RDS module for future data needs
│   ├── environments/
│   │   ├── dev/                   # Development environment
│   │   ├── staging/               # Staging environment
│   │   └── prod/                  # Production environment
│   └── variables.tf               # Global variables
├── scripts/
│   ├── build.sh                   # Build automation script
│   ├── deploy.sh                  # Deployment automation
│   ├── health-check.sh            # Health monitoring script
│   └── cleanup.sh                 # Resource cleanup utility
└── monitoring/
    ├── prometheus/                # Prometheus configuration
    ├── grafana/                   # Grafana dashboards
    └── logs/                      # Log aggregation setup
```

## Docker and Docker Compose

### Building the Docker Image

The LabArchives MCP Server uses a multi-stage Docker build process based on `python:3.11-slim-bookworm` for optimal size and security.

```bash
# Build the production image
docker build -t labarchives-mcp:latest -f docker/Dockerfile .

# Build development image with debugging tools
docker build -t labarchives-mcp:dev -f docker/Dockerfile --target development .
```

### Docker Image Specifications

- **Base Image**: `python:3.11-slim-bookworm` (51MB download, 149MB uncompressed)
- **Runtime**: Python 3.11+ with latest bugfixes and security updates
- **Size**: Optimized for minimal footprint while maintaining functionality
- **Security**: Regular security updates through official Docker Python images

### Running with Docker Compose

#### Local Development Environment

```bash
# Start development environment
docker-compose -f docker-compose.dev.yml up --build

# Run with live code reloading
docker-compose -f docker-compose.dev.yml up --build --watch
```

#### Production Environment

```bash
# Start production environment
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose -f docker-compose.prod.yml logs -f labarchives-mcp
```

### Environment Variable Configuration

Create a `.env` file based on `.env.example`:

```bash
# LabArchives API Configuration
LABARCHIVES_AKID=your_access_key_id
LABARCHIVES_SECRET=your_access_password_or_token
LABARCHIVES_USER=your_username_for_token_auth
LABARCHIVES_API_BASE=https://api.labarchives.com/api

# Regional API Configuration (Australia example)
# LABARCHIVES_API_BASE=https://auapi.labarchives.com/api

# Scope Configuration
LABARCHIVES_NOTEBOOK_ID=optional_notebook_restriction
LABARCHIVES_NOTEBOOK_NAME=optional_notebook_name_filter

# Logging Configuration
LABARCHIVES_LOG_LEVEL=INFO
LABARCHIVES_LOG_FILE=/app/logs/labarchives_mcp.log
LABARCHIVES_VERBOSE=false

# Server Configuration
MCP_SERVER_NAME=labarchives-mcp-server
MCP_SERVER_VERSION=0.1.0
```

### Volume Mounting for Persistent Logs

```yaml
# docker-compose.yml example
volumes:
  - ./logs:/app/logs
  - ./config:/app/config:ro
```

## Kubernetes Deployment

### Prerequisites

- Kubernetes cluster (1.24+)
- kubectl configured with cluster access
- Appropriate RBAC permissions for deployment

### Deployment Steps

1. **Create Namespace** (optional):
```bash
kubectl create namespace labarchives-mcp
```

2. **Configure Secrets**:
```bash
# Create secret from environment variables
kubectl create secret generic labarchives-credentials \
  --from-literal=LABARCHIVES_AKID=your_key \
  --from-literal=LABARCHIVES_SECRET=your_secret \
  --namespace=labarchives-mcp
```

3. **Deploy Application**:
```bash
# Apply all manifests
kubectl apply -f kubernetes/ --namespace=labarchives-mcp

# Or deploy individually
kubectl apply -f kubernetes/configmap.yaml
kubectl apply -f kubernetes/secret.yaml
kubectl apply -f kubernetes/deployment.yaml
kubectl apply -f kubernetes/service.yaml
kubectl apply -f kubernetes/ingress.yaml
```

### Kubernetes Configuration Customization

#### Resource Requests and Limits

```yaml
# deployment.yaml
resources:
  requests:
    memory: "64Mi"
    cpu: "250m"
  limits:
    memory: "128Mi"
    cpu: "500m"
```

#### Environment Variables

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: labarchives-config
data:
  LABARCHIVES_API_BASE: "https://api.labarchives.com/api"
  LABARCHIVES_LOG_LEVEL: "INFO"
  MCP_SERVER_NAME: "labarchives-mcp-server"
```

#### Health Check Configuration

```yaml
# deployment.yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5
```

### Scaling and High Availability

Since the MCP server is designed for single-user sessions, scaling involves replica management rather than horizontal scaling:

```bash
# Scale deployment
kubectl scale deployment labarchives-mcp-server --replicas=3

# Configure horizontal pod autoscaling
kubectl autoscale deployment labarchives-mcp-server --cpu-percent=70 --min=2 --max=10
```

## Terraform Cloud Provisioning

### AWS ECS Deployment

The Terraform configuration provides modules for deploying to AWS ECS with supporting infrastructure.

#### ECS Module Configuration

```bash
# Navigate to terraform directory
cd terraform/environments/prod

# Initialize Terraform
terraform init

# Plan deployment
terraform plan -var-file="terraform.tfvars"

# Apply infrastructure
terraform apply -auto-approve
```

#### ECS Module Variables

```hcl
# terraform.tfvars
aws_region = "us-west-2"
environment = "production"
cluster_name = "labarchives-mcp-cluster"

# Container configuration
container_image = "labarchives/mcp-server:latest"
container_port = 8000
desired_capacity = 2
max_capacity = 10
min_capacity = 1

# Network configuration
vpc_id = "vpc-12345678"
subnet_ids = ["subnet-12345678", "subnet-87654321"]
security_group_ids = ["sg-12345678"]

# Load balancer configuration
certificate_arn = "arn:aws:acm:us-west-2:123456789012:certificate/12345678-1234-1234-1234-123456789012"
domain_name = "mcp.example.com"
```

### RDS Module (Future Enhancement)

For future stateful requirements, an RDS module is provided:

```hcl
module "rds" {
  source = "../../modules/rds"
  
  environment = var.environment
  vpc_id = var.vpc_id
  subnet_ids = var.private_subnet_ids
  
  # Database configuration
  engine = "postgres"
  engine_version = "14.9"
  instance_class = "db.t3.micro"
  allocated_storage = 20
  
  # Security
  backup_retention_period = 7
  backup_window = "03:00-04:00"
  maintenance_window = "sun:04:00-sun:05:00"
}
```

### Multi-Environment Management

```bash
# Development environment
cd terraform/environments/dev
terraform workspace select dev
terraform apply -var-file="dev.tfvars"

# Staging environment
cd terraform/environments/staging
terraform workspace select staging
terraform apply -var-file="staging.tfvars"

# Production environment
cd terraform/environments/prod
terraform workspace select prod
terraform apply -var-file="prod.tfvars"
```

## Environment Variables and Secrets

### Required Environment Variables

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `LABARCHIVES_AKID` | LabArchives API Access Key ID | `AKID123456789` | Yes |
| `LABARCHIVES_SECRET` | API Password or Authentication Token | `your_password_or_token` | Yes |
| `LABARCHIVES_USER` | Username for token authentication | `user@institution.edu` | For token auth |
| `LABARCHIVES_API_BASE` | API base URL (regional) | `https://api.labarchives.com/api` | No |

### Optional Configuration Variables

| Variable | Description | Default | Options |
|----------|-------------|---------|---------|
| `LABARCHIVES_NOTEBOOK_ID` | Restrict to specific notebook | None | Notebook ID |
| `LABARCHIVES_NOTEBOOK_NAME` | Restrict to notebook by name | None | Notebook name |
| `LABARCHIVES_LOG_LEVEL` | Logging verbosity | `INFO` | `DEBUG`, `INFO`, `WARN`, `ERROR` |
| `LABARCHIVES_LOG_FILE` | Log file path | `labarchives_mcp.log` | File path |
| `LABARCHIVES_VERBOSE` | Enable verbose logging | `false` | `true`, `false` |

### Secrets Management

#### Docker Compose Secrets

```yaml
# docker-compose.yml
secrets:
  labarchives_credentials:
    file: ./secrets/credentials.txt
  api_token:
    external: true
```

#### Kubernetes Secrets

```bash
# Create secret from file
kubectl create secret generic labarchives-credentials \
  --from-file=.env.production

# Create secret from literals
kubectl create secret generic labarchives-api \
  --from-literal=LABARCHIVES_AKID=your_key \
  --from-literal=LABARCHIVES_SECRET=your_secret
```

#### AWS Secrets Manager Integration

```hcl
# terraform/modules/ecs/secrets.tf
resource "aws_secretsmanager_secret" "labarchives_credentials" {
  name = "${var.environment}-labarchives-credentials"
  
  tags = {
    Environment = var.environment
    Application = "labarchives-mcp"
  }
}

resource "aws_secretsmanager_secret_version" "labarchives_credentials" {
  secret_id = aws_secretsmanager_secret.labarchives_credentials.id
  secret_string = jsonencode({
    LABARCHIVES_AKID = var.labarchives_akid
    LABARCHIVES_SECRET = var.labarchives_secret
  })
}
```

## Operational Guidance

### Health Monitoring

The MCP server provides several health check endpoints:

```bash
# Basic health check
curl http://localhost:8000/health

# Readiness probe
curl http://localhost:8000/health/ready

# Liveness probe
curl http://localhost:8000/health/live
```

### Performance Monitoring

#### Resource Usage Monitoring

```bash
# Monitor container resource usage
docker stats labarchives-mcp

# Kubernetes resource monitoring
kubectl top pods -n labarchives-mcp
kubectl describe pod <pod-name> -n labarchives-mcp
```

#### Log Analysis

```bash
# View application logs
docker logs labarchives-mcp -f

# Kubernetes logs
kubectl logs -f deployment/labarchives-mcp-server -n labarchives-mcp

# Search for specific events
kubectl logs -f deployment/labarchives-mcp-server | grep "ERROR\|WARN"
```

### Troubleshooting Common Issues

#### Authentication Failures

```bash
# Check credentials configuration
echo $LABARCHIVES_AKID
echo $LABARCHIVES_SECRET

# Test API connectivity
curl -X GET "https://api.labarchives.com/api/users/user_info?akid=${LABARCHIVES_AKID}&sig=test&ts=$(date +%s)"
```

#### Connection Issues

```bash
# Check network connectivity
ping api.labarchives.com
nslookup api.labarchives.com

# Test port accessibility
telnet api.labarchives.com 443
```

#### Memory Issues

```bash
# Monitor memory usage
docker stats --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# Check for memory leaks
kubectl top pods --sort-by=memory
```

### Log Management

#### Log Rotation

```bash
# Configure log rotation
cat > /etc/logrotate.d/labarchives-mcp << EOF
/app/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 app app
}
EOF
```

#### Log Aggregation

```yaml
# docker-compose.yml with log driver
services:
  labarchives-mcp:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### Scaling Considerations

#### Vertical Scaling

```bash
# Update resource limits
kubectl patch deployment labarchives-mcp-server -p '{"spec":{"template":{"spec":{"containers":[{"name":"labarchives-mcp","resources":{"limits":{"memory":"256Mi","cpu":"1000m"}}}]}}}}'
```

#### Horizontal Scaling

```bash
# Scale replicas for multiple user sessions
kubectl scale deployment labarchives-mcp-server --replicas=5

# Configure autoscaling
kubectl autoscale deployment labarchives-mcp-server --cpu-percent=70 --min=2 --max=10
```

## CI/CD Pipeline Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/deploy.yml
name: Deploy LabArchives MCP Server

on:
  push:
    branches: [ main ]
  release:
    types: [ published ]

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    
    - name: Build Docker image
      run: |
        docker build -t labarchives-mcp:${{ github.sha }} .
        docker tag labarchives-mcp:${{ github.sha }} labarchives-mcp:latest
    
    - name: Deploy to staging
      if: github.ref == 'refs/heads/main'
      run: |
        docker-compose -f docker-compose.staging.yml up -d
    
    - name: Deploy to production
      if: github.event_name == 'release'
      run: |
        docker-compose -f docker-compose.prod.yml up -d
```

### Deployment Automation

```bash
# scripts/deploy.sh
#!/bin/bash
set -e

ENVIRONMENT=${1:-dev}
VERSION=${2:-latest}

echo "Deploying LabArchives MCP Server to $ENVIRONMENT..."

case $ENVIRONMENT in
  dev)
    docker-compose -f docker-compose.dev.yml up -d
    ;;
  staging)
    docker-compose -f docker-compose.staging.yml up -d
    ;;
  prod)
    docker-compose -f docker-compose.prod.yml up -d
    ;;
  *)
    echo "Unknown environment: $ENVIRONMENT"
    exit 1
    ;;
esac

echo "Deployment completed successfully!"
```

## Security Best Practices

### Container Security

```dockerfile
# Dockerfile security practices
FROM python:3.11-slim-bookworm

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Install dependencies as root
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Start application
CMD ["python", "-m", "labarchives_mcp.cli"]
```

### Network Security

```yaml
# kubernetes/network-policy.yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: labarchives-mcp-network-policy
spec:
  podSelector:
    matchLabels:
      app: labarchives-mcp
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: mcp-clients
    ports:
    - protocol: TCP
      port: 8000
  egress:
  - to: []
    ports:
    - protocol: TCP
      port: 443  # HTTPS to LabArchives API
```

## Monitoring and Observability

### Prometheus Configuration

```yaml
# monitoring/prometheus/prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'labarchives-mcp'
    static_configs:
      - targets: ['labarchives-mcp:8000']
    metrics_path: /metrics
    scrape_interval: 5s
```

### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "LabArchives MCP Server",
    "panels": [
      {
        "title": "Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
            "legendFormat": "95th percentile"
          }
        ]
      },
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total[1m])",
            "legendFormat": "Requests per second"
          }
        ]
      }
    ]
  }
}
```

### Log Aggregation with ELK Stack

```yaml
# docker-compose.monitoring.yml
version: '3.8'
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.12.0
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
  
  logstash:
    image: docker.elastic.co/logstash/logstash:8.12.0
    volumes:
      - ./monitoring/logstash/pipeline:/usr/share/logstash/pipeline
  
  kibana:
    image: docker.elastic.co/kibana/kibana:8.12.0
    ports:
      - "5601:5601"
    depends_on:
      - elasticsearch
```

## Backup and Recovery

### Configuration Backup

```bash
# scripts/backup.sh
#!/bin/bash
BACKUP_DIR="/backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup configuration
cp .env "$BACKUP_DIR/"
cp -r kubernetes/ "$BACKUP_DIR/"
cp -r terraform/ "$BACKUP_DIR/"

# Backup logs
cp -r logs/ "$BACKUP_DIR/"

# Create archive
tar -czf "$BACKUP_DIR.tar.gz" "$BACKUP_DIR"
rm -rf "$BACKUP_DIR"

echo "Backup completed: $BACKUP_DIR.tar.gz"
```

### Disaster Recovery

```bash
# scripts/recovery.sh
#!/bin/bash
BACKUP_FILE=$1

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file.tar.gz>"
    exit 1
fi

# Extract backup
tar -xzf "$BACKUP_FILE"
BACKUP_DIR=$(basename "$BACKUP_FILE" .tar.gz)

# Restore configuration
cp "$BACKUP_DIR/.env" .
cp -r "$BACKUP_DIR/kubernetes/" .
cp -r "$BACKUP_DIR/terraform/" .

# Redeploy
./scripts/deploy.sh prod

echo "Recovery completed successfully!"
```

## Further Documentation and Support

### Additional Resources

- **Main Project README**: [../README.md](../README.md)
- **API Documentation**: [../docs/api.md](../docs/api.md)
- **Configuration Guide**: [../docs/configuration.md](../docs/configuration.md)
- **Troubleshooting Guide**: [../docs/troubleshooting.md](../docs/troubleshooting.md)

### Official Documentation

- **LabArchives API Documentation**: [https://api.labarchives.com/docs](https://api.labarchives.com/docs)
- **Model Context Protocol Specification**: [https://spec.modelcontextprotocol.io](https://spec.modelcontextprotocol.io)
- **FastMCP Framework**: [https://github.com/jlowin/fastmcp](https://github.com/jlowin/fastmcp)

### Support Channels

- **GitHub Issues**: [Report bugs and request features](https://github.com/org/labarchives-mcp-server/issues)
- **GitHub Discussions**: [Community Q&A and usage help](https://github.com/org/labarchives-mcp-server/discussions)
- **Documentation**: [Comprehensive setup and usage guides](https://docs.labarchives-mcp.org)

### Community Resources

- **MCP Server Catalog**: [Discover other MCP servers](https://mcp.so)
- **Claude Desktop Integration**: [Official Claude Desktop documentation](https://claude.ai/docs)
- **Docker Hub**: [Official container images](https://hub.docker.com/r/labarchives/mcp-server)

---

## Quick Start Commands

```bash
# Local development with Docker
docker-compose up --build

# Kubernetes deployment
kubectl apply -f kubernetes/

# Terraform cloud deployment
cd terraform/environments/prod && terraform apply

# Health check
curl http://localhost:8000/health

# View logs
docker logs labarchives-mcp -f
```

This infrastructure setup provides a robust, scalable, and secure foundation for deploying the LabArchives MCP Server across various environments while maintaining the system's core principles of simplicity and reliability.