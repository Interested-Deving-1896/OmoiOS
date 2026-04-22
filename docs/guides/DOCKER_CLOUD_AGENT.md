# Cloud Agent Dockerfile Usage

**Created**: 2025-01-10  
**Updated**: 2025-04-22  
**Status**: Active  
**Purpose**: Comprehensive guide for deploying and managing OmoiOS cloud agents using Docker

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Features](#features)
4. [Building the Image](#building-the-image)
5. [Configuration](#configuration)
6. [Deployment Steps](#deployment-steps)
7. [Running the Container](#running-the-container)
8. [Connecting to Services](#connecting-to-services)
9. [Using Python/UV Inside the Container](#using-pythonuv-inside-the-container)
10. [Mounting Your Project](#mounting-your-project)
11. [Environment Variables](#environment-variables)
12. [Health Checks](#health-checks)
13. [Security Considerations](#security-considerations)
14. [Troubleshooting](#troubleshooting)
15. [Deployment Diagram](#deployment-diagram)
16. [Related Documentation](#related-documentation)

---

## Overview

The Cloud Agent Dockerfile creates a single container that runs both **PostgreSQL 18** (with PGVector extension) and **Redis**, configured for use in Cursor Cloud Agents and other cloud development environments. This container provides a complete, isolated development environment for OmoiOS without requiring multiple services or complex orchestration.

### Use Cases

- **Cloud Development Environments**: Cursor Cloud Agents, GitHub Codespaces, Gitpod
- **CI/CD Pipelines**: Isolated test environments
- **Local Development**: Single-command setup for new developers
- **Demo/Prototype Environments**: Quick deployment for demonstrations
- **Testing**: Consistent, reproducible test environments

---

## Architecture

### Container Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    OmoiOS Cloud Agent                        │
│                      (Single Container)                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────┐    ┌─────────────────────┐       │
│  │   PostgreSQL 18     │    │      Redis 7        │       │
│  │   + PGVector        │    │                     │       │
│  │                     │    │                     │       │
│  │  Port: 15432        │    │  Port: 16379        │       │
│  │  User: postgres     │    │  Auth: None         │       │
│  │  Pass: postgres     │    │  DB: 0              │       │
│  │  DB: app_db         │    │                     │       │
│  └─────────────────────┘    └─────────────────────┘       │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Supervisor (Process Manager)            │   │
│  │         Manages PostgreSQL and Redis processes       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              UV Package Manager                    │   │
│  │         Fast Python package installation           │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Service Ports

| Service | Container Port | Host Port (Default) | Purpose |
|---------|---------------|---------------------|---------|
| PostgreSQL | 5432 | 15432 | Primary database with pgvector |
| Redis | 6379 | 16379 | Cache, pub/sub, task queue |

### Base Image

The Dockerfile uses a multi-stage build based on `nikolaik/python-nodejs:python3.12-nodejs22`:

- **Python 3.12**: For OmoiOS backend
- **Node.js 22**: For frontend development
- **UV**: Fast Python package manager
- **Supervisor**: Process management

---

## Features

### Core Services

- **PostgreSQL 18** with PGVector extension
  - Pre-configured with `app_db` database
  - pgvector extension enabled for AI/ML features
  - Custom port 15432 to avoid conflicts
  
- **Redis** server
  - Default configuration
  - Custom port 16379 to avoid conflicts
  - Persistence enabled

- **UV package manager**
  - For fast Python dependency management
  - Pre-installed and configured

### Port Configuration

Ports are configured to match `.env.local` defaults:
- PostgreSQL: `15432` (default 5432 + 10000 offset)
- Redis: `16379` (default 6379 + 10000 offset)

This offset pattern prevents conflicts with locally installed PostgreSQL/Redis instances.

### Health Checks

The container includes built-in health checks:
- PostgreSQL connectivity check
- Redis connectivity check
- Supervisor process status

---

## Building the Image

### Basic Build

```bash
docker build -f Dockerfile.cloud-agent -t omoi-cloud-agent .
```

### Build with Custom Tag

```bash
docker build -f Dockerfile.cloud-agent -t omoi-cloud-agent:v1.0.0 .
```

### Build for Multiple Platforms

```bash
# Enable buildx
docker buildx create --use

# Build for AMD64 and ARM64
docker buildx build \
  -f Dockerfile.cloud-agent \
  -t omoi-cloud-agent:latest \
  --platform linux/amd64,linux/arm64 \
  --push
```

### Build Arguments

```bash
docker build \
  -f Dockerfile.cloud-agent \
  -t omoi-cloud-agent \
  --build-arg PYTHON_VERSION=3.12 \
  --build-arg NODE_VERSION=22 \
  --build-arg POSTGRES_VERSION=18 \
  .
```

### Dockerfile Reference

```dockerfile
# backend/Dockerfile.cloud-agent

FROM nikolaik/python-nodejs:python3.12-nodejs22

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-18 \
    postgresql-contrib-18 \
    postgresql-18-pgvector \
    redis-server \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Configure PostgreSQL
RUN service postgresql start && \
    su - postgres -c "psql -c \"CREATE USER root WITH SUPERUSER PASSWORD 'postgres';\"" && \
    su - postgres -c "psql -c \"CREATE DATABASE app_db;\"" && \
    su - postgres -c "psql -c \"GRANT ALL PRIVILEGES ON DATABASE app_db TO root;\"" && \
    su - postgres -c "psql -d app_db -c \"CREATE EXTENSION IF NOT EXISTS vector;\""

# Configure Redis
RUN sed -i 's/^bind 127.0.0.1 ::1/bind 0.0.0.0/' /etc/redis/redis.conf && \
    sed -i 's/^port 6379/port 16379/' /etc/redis/redis.conf

# Configure PostgreSQL port
RUN echo "port = 15432" >> /etc/postgresql/18/main/postgresql.conf && \
    echo "listen_addresses = '*'" >> /etc/postgresql/18/main/postgresql.conf

# Install UV
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Supervisor configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

EXPOSE 15432 16379

CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
```

---

## Configuration

### Environment Variables

The container uses these defaults (matching `.env.local`):

| Variable | Default Value | Description |
|----------|---------------|-------------|
| `POSTGRES_USER` | `postgres` | PostgreSQL superuser |
| `POSTGRES_PASSWORD` | `postgres` | PostgreSQL password |
| `POSTGRES_DB` | `app_db` | Default database |
| `POSTGRES_PORT` | `15432` | PostgreSQL port |
| `REDIS_PORT` | `16379` | Redis port |
| `PGDATA` | `/var/lib/postgresql/data` | PostgreSQL data directory |

### Custom Configuration

Override defaults at runtime:

```bash
docker run -d \
  -p 15432:15432 \
  -p 16379:16379 \
  -e POSTGRES_PASSWORD=custom_password \
  -e POSTGRES_DB=my_app \
  --name omoi-services \
  omoi-cloud-agent
```

### Volume Mounts

Persist data across container restarts:

```bash
docker run -d \
  -p 15432:15432 \
  -p 16379:16379 \
  -v omoi_postgres_data:/var/lib/postgresql/data \
  -v omoi_redis_data:/var/lib/redis \
  --name omoi-services \
  omoi-cloud-agent
```

---

## Deployment Steps

### 1. Prerequisites

Ensure Docker is installed and running:

```bash
docker --version
# Docker version 24.0.0 or higher recommended
```

### 2. Build or Pull Image

**Option A: Build locally**
```bash
cd /path/to/omoi_os
# Use the .cursor directory version for cloud agents
docker build -f .cursor/Dockerfile.cloud-agent -t omoi-cloud-agent .
```

**Option B: Pull from registry (if available)**
```bash
docker pull ghcr.io/kivo360/omoi-cloud-agent:latest
```

### 3. Create Network (Optional)

For multi-container setups:

```bash
docker network create omoi-network
```

### 4. Run Container

**Basic deployment:**
```bash
docker run -d \
  -p 15432:15432 \
  -p 16379:16379 \
  --name omoi-services \
  omoi-cloud-agent
```

**With volume persistence:**
```bash
docker run -d \
  -p 15432:15432 \
  -p 16379:16379 \
  -v omoi_postgres_data:/var/lib/postgresql/data \
  -v omoi_redis_data:/var/lib/redis \
  --name omoi-services \
  omoi-cloud-agent
```

**With project mount:**
```bash
docker run -d \
  -p 15432:15432 \
  -p 16379:16379 \
  -v $(pwd):/app \
  -v omoi_postgres_data:/var/lib/postgresql/data \
  --name omoi-services \
  omoi-cloud-agent
```

### 5. Verify Deployment

```bash
# Check container status
docker ps

# Should show:
# CONTAINER ID   IMAGE              STATUS         PORTS
# xxxxxxxx       omoi-cloud-agent   Up 2 minutes   0.0.0.0:15432->15432/tcp, 0.0.0.0:16379->16379/tcp

# Check health
docker exec omoi-services supervisorctl status

# Expected output:
# postgresql                       RUNNING   pid 123, uptime 0:02:15
# redis-server                     RUNNING   pid 124, uptime 0:02:15
```

### 6. Initialize Database

```bash
# Enter container
docker exec -it omoi-services bash

# Run migrations
cd /app/backend
uv run alembic upgrade head
```

---

## Running the Container

### Docker Run Options

```bash
docker run -d \
  -p 15432:15432 \
  -p 16379:16379 \
  --name omoi-services \
  --restart unless-stopped \
  --memory=2g \
  --cpus=2 \
  -e POSTGRES_PASSWORD=secure_password \
  -v omoi_data:/var/lib/postgresql/data \
  omoi-cloud-agent
```

### Docker Compose

```yaml
# docker-compose.cloud-agent.yml

version: '3.8'

services:
  omoi-services:
    build:
      context: .
      dockerfile: .cursor/Dockerfile.cloud-agent
    container_name: omoi-services
    ports:
      - "15432:15432"
      - "16379:16379"
    environment:
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-postgres}
      - POSTGRES_DB=${POSTGRES_DB:-app_db}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - redis_data:/var/lib/redis
      - .:/app:cached
    healthcheck:
      test: ["CMD", "supervisorctl", "status", "postgresql"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

Run with Docker Compose:

```bash
docker-compose -f docker-compose.cloud-agent.yml up -d
```

### Kubernetes Deployment

```yaml
# k8s/cloud-agent-deployment.yaml

apiVersion: apps/v1
kind: Deployment
metadata:
  name: omoi-cloud-agent
  labels:
    app: omoi-cloud-agent
spec:
  replicas: 1
  selector:
    matchLabels:
      app: omoi-cloud-agent
  template:
    metadata:
      labels:
        app: omoi-cloud-agent
    spec:
      containers:
      - name: omoi-services
        image: omoi-cloud-agent:latest
        ports:
        - containerPort: 15432
          name: postgres
        - containerPort: 16379
          name: redis
        env:
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: omoi-secrets
              key: postgres-password
        volumeMounts:
        - name: postgres-storage
          mountPath: /var/lib/postgresql/data
        - name: redis-storage
          mountPath: /var/lib/redis
        livenessProbe:
          exec:
            command:
            - supervisorctl
            - status
            - postgresql
          initialDelaySeconds: 30
          periodSeconds: 10
      volumes:
      - name: postgres-storage
        persistentVolumeClaim:
          claimName: postgres-pvc
      - name: redis-storage
        persistentVolumeClaim:
          claimName: redis-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: omoi-services
spec:
  selector:
    app: omoi-cloud-agent
  ports:
  - name: postgres
    port: 15432
    targetPort: 15432
  - name: redis
    port: 16379
    targetPort: 16379
```

---

## Connecting to Services

### PostgreSQL

**Connection string:**
```
postgresql://postgres:postgres@localhost:15432/app_db
```

**Using psql:**
```bash
psql -h localhost -p 15432 -U postgres -d app_db
```

**Using Docker exec:**
```bash
docker exec -it omoi-services psql -h localhost -p 15432 -U postgres -d app_db
```

**Python connection:**
```python
import psycopg

conn = psycopg.connect(
    host="localhost",
    port=15432,
    user="postgres",
    password="postgres",
    dbname="app_db"
)
```

### Redis

**Connection string:**
```
redis://localhost:16379
```

**Using redis-cli:**
```bash
redis-cli -p 16379
```

**Using Docker exec:**
```bash
docker exec -it omoi-services redis-cli -p 16379
```

**Python connection:**
```python
import redis

r = redis.Redis(
    host='localhost',
    port=16379,
    decode_responses=True
)
```

---

## Using Python/UV Inside the Container

### 1. Enter the Container

```bash
docker exec -it omoi-services bash
```

### 2. Navigate to Project Directory

```bash
cd /app
```

### 3. Set Up Environment

```bash
# Sync dependencies
uv sync

# Or install specific packages
uv pip install pytest httpx
```

### 4. Run Python Commands

```bash
# Run the API server
uv run python -m omoi_os.api.main

# Run tests
uv run pytest

# Run migrations
uv run alembic upgrade head
```

### 5. Execute One-Off Commands

```bash
# Run without entering container
docker exec omoi-services uv run python -c "print('Hello from container')"

# Run tests
docker exec omoi-services bash -c "cd /app/backend && uv run pytest"
```

---

## Mounting Your Project

### Basic Mount

Mount current directory to `/app`:

```bash
docker run -d \
  -p 15432:15432 \
  -p 16379:16379 \
  -v $(pwd):/app \
  --name omoi-services \
  omoi-cloud-agent
```

### Mount with Cache

For better performance on macOS:

```bash
docker run -d \
  -p 15432:15432 \
  -p 16379:16379 \
  -v $(pwd):/app:cached \
  -v omoi_postgres_data:/var/lib/postgresql/data \
  --name omoi-services \
  omoi-cloud-agent
```

### Mount Specific Directories

```bash
docker run -d \
  -p 15432:15432 \
  -p 16379:16379 \
  -v $(pwd)/backend:/app/backend \
  -v $(pwd)/frontend:/app/frontend \
  -v omoi_postgres_data:/var/lib/postgresql/data \
  --name omoi-services \
  omoi-cloud-agent
```

### Read-Only Mount

For safe development:

```bash
docker run -d \
  -p 15432:15432 \
  -p 16379:16379 \
  -v $(pwd):/app:ro \
  -v omoi_postgres_data:/var/lib/postgresql/data \
  --name omoi-services \
  omoi-cloud-agent
```

---

## Environment Variables

### Complete Environment Variable Reference

| Variable | Default | Description | Required |
|----------|---------|-------------|----------|
| `POSTGRES_USER` | `postgres` | PostgreSQL username | No |
| `POSTGRES_PASSWORD` | `postgres` | PostgreSQL password | No |
| `POSTGRES_DB` | `app_db` | Default database name | No |
| `POSTGRES_PORT` | `15432` | PostgreSQL port | No |
| `REDIS_PORT` | `16379` | Redis port | No |
| `PGDATA` | `/var/lib/postgresql/data` | PostgreSQL data directory | No |
| `SUPERVISOR_LOG_LEVEL` | `info` | Supervisor logging level | No |

### Production Environment Variables

For production deployments, override defaults:

```bash
docker run -d \
  -p 15432:15432 \
  -p 16379:16379 \
  -e POSTGRES_USER=omoios_prod \
  -e POSTGRES_PASSWORD=$(openssl rand -base64 32) \
  -e POSTGRES_DB=omoios_production \
  -v omoi_prod_data:/var/lib/postgresql/data \
  --name omoi-services \
  omoi-cloud-agent
```

### Development Environment Variables

For development, use defaults:

```bash
docker run -d \
  -p 15432:15432 \
  -p 16379:16379 \
  -v $(pwd):/app \
  -v omoi_dev_data:/var/lib/postgresql/data \
  --name omoi-services \
  omoi-cloud-agent
```

---

## Health Checks

### Built-in Health Checks

The container includes health checks for both services:

```bash
# Check container health
docker ps
# Should show "healthy" status

# Check detailed health
docker inspect --format='{{.State.Health.Status}}' omoi-services
```

### Manual Health Verification

**PostgreSQL health check:**
```bash
docker exec omoi-services pg_isready -h localhost -p 15432 -U postgres
# Output: localhost:15432 - accepting connections
```

**Redis health check:**
```bash
docker exec omoi-services redis-cli -p 16379 ping
# Output: PONG
```

**Supervisor status:**
```bash
docker exec omoi-services supervisorctl status
# Output:
# postgresql                       RUNNING   pid 123, uptime 0:05:30
# redis-server                     RUNNING   pid 124, uptime 0:05:30
```

### Custom Health Checks

Add to your application:

```python
# health_check.py

import psycopg
import redis
import sys

def check_postgres():
    try:
        conn = psycopg.connect(
            host="localhost",
            port=15432,
            user="postgres",
            password="postgres",
            dbname="app_db"
        )
        conn.close()
        return True
    except Exception as e:
        print(f"PostgreSQL check failed: {e}")
        return False

def check_redis():
    try:
        r = redis.Redis(host='localhost', port=16379)
        r.ping()
        return True
    except Exception as e:
        print(f"Redis check failed: {e}")
        return False

if __name__ == "__main__":
    postgres_ok = check_postgres()
    redis_ok = check_redis()
    
    if postgres_ok and redis_ok:
        print("All services healthy")
        sys.exit(0)
    else:
        print("Some services unhealthy")
        sys.exit(1)
```

---

## Security Considerations

### Default Credentials

**⚠️ WARNING**: Default credentials are for development only!

- PostgreSQL: `postgres/postgres`
- Redis: No authentication

### Production Security

1. **Change default passwords:**
```bash
docker run -d \
  -e POSTGRES_PASSWORD=$(openssl rand -base64 32) \
  -e POSTGRES_USER=customuser \
  ...
```

2. **Use secrets management:**
```bash
# Create secret
echo "my_secure_password" | docker secret create postgres_password -

# Use in swarm
docker service create \
  --secret postgres_password \
  -e POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password \
  omoi-cloud-agent
```

3. **Network isolation:**
```bash
docker network create --internal omoi-internal
docker run --network omoi-internal ...
```

4. **Read-only root filesystem:**
```bash
docker run --read-only \
  --tmpfs /tmp \
  --tmpfs /var/run/postgresql \
  ...
```

### Security Scanning

```bash
# Scan image for vulnerabilities
docker scan omoi-cloud-agent

# Or use Trivy
trivy image omoi-cloud-agent
```

---

## Troubleshooting

### View Logs

**All logs:**
```bash
docker logs omoi-services
```

**PostgreSQL logs:**
```bash
docker exec omoi-services tail -f /var/log/supervisor/postgresql.out.log
```

**Redis logs:**
```bash
docker exec omoi-services tail -f /var/log/supervisor/redis.out.log
```

**Supervisor logs:**
```bash
docker exec omoi-services tail -f /var/log/supervisor/supervisord.log
```

### Check Service Status

```bash
docker exec omoi-services supervisorctl status
```

### Restart Services

```bash
# Restart PostgreSQL
docker exec omoi-services supervisorctl restart postgresql

# Restart Redis
docker exec omoi-services supervisorctl restart redis

# Restart all
docker restart omoi-services
```

### Common Issues

#### 1. Port Already in Use

```
Error: Ports are not available: exposing port TCP 0.0.0.0:15432 -> 0.0.0.0:0: listen tcp 0.0.0.0:15432: bind: address already in use
```

**Solution:**
```bash
# Find process using port
lsof -i :15432

# Kill process or use different port
docker run -d -p 25432:15432 ...  # Use different host port
```

#### 2. Permission Denied on Volume

```
Error: initdb: could not create directory "/var/lib/postgresql/data": Permission denied
```

**Solution:**
```bash
# Use named volume instead of bind mount
docker run -d -v postgres_data:/var/lib/postgresql/data ...

# Or fix permissions
docker run -d --user $(id -u):$(id -g) ...
```

#### 3. Container Exits Immediately

```bash
# Check logs
docker logs omoi-services

# Check if ports are available
docker run --rm -p 15432:15432 -p 16379:16379 omoi-cloud-agent echo "Ports available"

# Run interactively to debug
docker run -it --rm omoi-cloud-agent bash
```

#### 4. Database Connection Failed

```bash
# Verify PostgreSQL is running
docker exec omoi-services pg_isready -h localhost -p 15432

# Check PostgreSQL logs
docker exec omoi-services cat /var/log/postgresql/postgresql-18-main.log

# Reset database
docker exec omoi-services su - postgres -c "psql -c 'DROP DATABASE IF EXISTS app_db;'"
docker exec omoi-services su - postgres -c "psql -c 'CREATE DATABASE app_db;'"
```

#### 5. Redis Connection Failed

```bash
# Verify Redis is running
docker exec omoi-services redis-cli -p 16379 ping

# Check Redis logs
docker exec omoi-services cat /var/log/redis/redis-server.log

# Restart Redis
docker exec omoi-services supervisorctl restart redis
```

### Debug Mode

Run container with debug output:

```bash
docker run -it --rm \
  -p 15432:15432 \
  -p 16379:16379 \
  omoi-cloud-agent bash

# Inside container, start services manually
/usr/lib/postgresql/18/bin/pg_ctl start -D /var/lib/postgresql/data
redis-server /etc/redis/redis.conf
```

---

## Deployment Diagram

```mermaid
graph TB
    subgraph "Host Machine"
        A[Developer/CI] --> B[Docker Engine]
        C[OmoiOS Backend] --> B
        D[OmoiOS Frontend] --> B
    end
    
    subgraph "OmoiOS Cloud Agent Container"
        B --> E[Supervisor]
        
        E --> F[PostgreSQL 18]
        E --> G[Redis 7]
        
        F --> H[(PostgreSQL Data)]
        G --> I[(Redis Data)]
        
        F --> J[PGVector Extension]
        
        subgraph "Ports"
            K[15432<br/>PostgreSQL]
            L[16379<br/>Redis]
        end
        
        F --> K
        G --> L
    end
    
    subgraph "External Services"
        M[Daytona Sandboxes]
        N[GitHub API]
        O[LLM Providers]
    end
    
    C --> M
    C --> N
    C --> O
    
    style A fill:#e1f5ff
    style B fill:#e1f5ff
    style C fill:#e1f5ff
    style D fill:#e1f5ff
    style E fill:#ffe1e1
    style F fill:#e1ffe1
    style G fill:#e1ffe1
    style H fill:#fff9e1
    style I fill:#fff9e1
    style J fill:#f0e1ff
    style K fill:#ffe1e1
    style L fill:#ffe1e1
    style M fill:#e1f5ff
    style N fill:#e1f5ff
    style O fill:#e1f5ff
```

### Data Flow

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant Container as Cloud Agent Container
    participant PG as PostgreSQL
    participant RD as Redis
    participant App as OmoiOS App
    
    Dev->>Container: docker run
    Container->>PG: Start PostgreSQL
    Container->>RD: Start Redis
    PG-->>Container: Ready on 15432
    RD-->>Container: Ready on 16379
    Container-->>Dev: Container healthy
    
    Dev->>App: Start application
    App->>PG: Connect to postgres://localhost:15432
    App->>RD: Connect to redis://localhost:16379
    PG-->>App: Database operations
    RD-->>App: Cache/Queue operations
```

---

## Related Documentation

- OmoiOS Installation Guide - Full installation instructions
- [OmoiOS Backend Guide](../../backend/CLAUDE.md) - Backend development guide
- [OmoiOS Architecture](../../ARCHITECTURE.md) - System architecture overview
- [Docker Documentation](https://docs.docker.com/) - Official Docker docs
- [PostgreSQL Documentation](https://www.postgresql.org/docs/) - PostgreSQL reference
- [Redis Documentation](https://redis.io/documentation) - Redis reference
- [Supervisor Documentation](http://supervisord.org/) - Process management

---

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2025-01-10 | Initial Dockerfile and documentation | @kivo360 |
| 2025-04-22 | Expanded with architecture, deployment steps, security, troubleshooting, and diagrams | Documentation Team |

---

**Last Updated**: 2025-04-22  
**Document Owner**: DevOps Team  
**Review Cycle**: Monthly
