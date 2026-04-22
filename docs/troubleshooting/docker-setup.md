# Docker Setup Troubleshooting

**Status**: Active | **Last Updated**: 2026-04-22 | **Applies To**: OmoiOS v1.0+

**Source Files**:
- `docker-compose.yml` — Root-level full-stack orchestration
- `backend/docker-compose.yml` — Backend services (Postgres, Redis)
- `backend/Dockerfile.api` — API server image
- `backend/Dockerfile.worker` — Background worker image
- `backend/Dockerfile.cloud-agent` — Cloud agent image

**Related Documentation**:
- [CLAUDE.md](../../CLAUDE.md) — Monorepo structure and ports
- [CONTRIBUTING.md](../../CONTRIBUTING.md) — Local setup guide
- **Architecture: Execution System**

---

## Overview

OmoiOS uses Docker Compose to run infrastructure services (PostgreSQL, Redis) locally. The backend API and workers can run either natively (via `uv`) or inside Docker containers. All ports are offset by +10,000 to avoid conflicts with common local services.

### Port Reference

| Service | Port | Notes |
|---------|------|-------|
| PostgreSQL | 15432 | Offset from default 5432 |
| Redis | 16379 | Offset from default 6379 |
| Backend API | 18000 | Offset from default 8000 |
| Frontend | 3000 | Standard Next.js port |

### Service Topology

```
docker-compose.yml (root)
├── postgres:16          → localhost:15432
├── redis:7              → localhost:16379
├── backend-api          → localhost:18000
└── frontend             → localhost:3000

backend/docker-compose.yml (infra only)
├── postgres:16          → localhost:15432
└── redis:7              → localhost:16379
```

---

## Common Error Codes

| Error | Meaning | Typical Cause |
|-------|---------|---------------|
| `port is already allocated` | Port conflict | Another process using the port |
| `connection refused` | Service not running | Container not started |
| `no such file or directory` | Volume mount missing | Path doesn't exist on host |
| `permission denied` | File permission error | Docker socket or volume permissions |
| `network not found` | Docker network missing | Compose network not created |
| `OCI runtime exec failed` | Container exec error | Wrong command or missing binary |
| `health check failed` | Service unhealthy | Startup probe failing |

---

## Issue 1: Docker Not Running

### Symptoms
```
Cannot connect to the Docker daemon at unix:///var/run/docker.sock
Error response from daemon: dial unix /var/run/docker.sock: connect: no such file or directory
```

### Root Cause Analysis

Docker Desktop is not running, or the Docker daemon is stopped.

### Diagnosis

```bash
# Check Docker daemon status
docker info 2>&1 | head -5

# macOS — check Docker Desktop
pgrep -x "Docker Desktop" || echo "Docker Desktop not running"

# Linux — check systemd service
systemctl status docker
```

### Recovery Procedures

```bash
# macOS — start Docker Desktop
open -a Docker

# Wait for Docker to be ready
while ! docker info > /dev/null 2>&1; do
  echo "Waiting for Docker..."
  sleep 2
done
echo "Docker is ready"

# Linux — start Docker daemon
sudo systemctl start docker
sudo systemctl enable docker  # Auto-start on boot
```

---

## Issue 2: Port Already Allocated

### Symptoms
```
Error response from daemon: driver failed programming external connectivity on endpoint omoi_postgres:
Bind for 0.0.0.0:15432 failed: port is already allocated
```

### Root Cause Analysis

Another process (or a previous Docker container that wasn't cleaned up) is already bound to the port.

### Diagnosis

```bash
# Find what's using the port
lsof -i :15432
lsof -i :16379
lsof -i :18000

# Check for existing Docker containers using the port
docker ps -a | grep -E "15432|16379|18000"
```

### Recovery Procedures

```bash
# Kill the conflicting process
just kill-port 15432
just kill-port 16379

# Or kill by PID
kill -9 <PID>

# Remove stopped containers that might hold the port
docker rm $(docker ps -aq --filter status=exited)

# Restart Docker services
just docker-up
```

---

## Issue 3: Container Fails to Start (Health Check)

### Symptoms
```
omoi_postgres is unhealthy
dependency failed to start: container omoi_postgres is unhealthy
```

### Root Cause Analysis

The PostgreSQL or Redis container started but its health check probe is failing. Common causes:
- Insufficient startup time (container still initializing)
- Corrupted data volume
- Insufficient disk space

### Diagnosis

```bash
# Check container status and health
docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# View container logs
docker logs omoi_postgres --tail 50
docker logs omoi_redis --tail 50

# Inspect health check details
docker inspect omoi_postgres | python3 -c "
import json, sys
data = json.load(sys.stdin)
health = data[0].get('State', {}).get('Health', {})
print(json.dumps(health, indent=2))
"

# Check disk space
df -h /var/lib/docker
```

### Recovery Procedures

```bash
# Restart just the unhealthy container
docker restart omoi_postgres

# If data is corrupted, remove the volume and recreate
docker-compose down -v  # WARNING: destroys all data
just docker-up

# Re-run migrations after recreating
just db-migrate

# If disk space is the issue
docker system prune -f  # Remove unused images/containers
docker volume prune -f  # Remove unused volumes (careful!)
```

---

## Issue 4: Database Connection Refused from Backend

### Symptoms
```
sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) could not connect to server:
Connection refused
    Is the server running on host "localhost" and accepting TCP/IP connections on port 15432?
```

### Root Cause Analysis

The backend is trying to connect to PostgreSQL but either:
1. The Docker container is not running
2. The `DATABASE_URL` in `.env` points to the wrong host/port
3. The backend is running inside Docker and using `localhost` instead of the service name

### Diagnosis

```bash
# Check if Postgres container is running
docker ps | grep postgres

# Test connection directly
psql postgresql://omoi_user:omoi_password@localhost:15432/omoi_db -c "SELECT 1"

# Check DATABASE_URL in .env
grep DATABASE_URL backend/.env

# If backend is in Docker, check if it uses service name
grep DATABASE_URL backend/docker-compose.yml
```

### Recovery Procedures

```bash
# Start infrastructure
just docker-up

# Verify connection
psql postgresql://omoi_user:omoi_password@localhost:15432/omoi_db -c "\l"

# Fix .env if wrong port
# For native backend (outside Docker):
DATABASE_URL=postgresql+asyncpg://omoi_user:omoi_password@localhost:15432/omoi_db

# For backend inside Docker (use service name):
DATABASE_URL=postgresql+asyncpg://omoi_user:omoi_password@postgres:5432/omoi_db
```

---

## Issue 5: Volume Mount Errors

### Symptoms
```
Error response from daemon: invalid mount config for type "bind":
bind source path does not exist: /Users/username/project/backend/data
```

### Root Cause Analysis

A bind mount in `docker-compose.yml` references a host path that doesn't exist.

### Diagnosis

```bash
# Check what volumes are configured
grep -A3 "volumes:" docker-compose.yml backend/docker-compose.yml

# Check if the host paths exist
ls -la backend/data 2>/dev/null || echo "Path missing"
```

### Recovery Procedures

```bash
# Create missing directories
mkdir -p backend/data
mkdir -p backend/logs

# Or remove the bind mount from docker-compose.yml if not needed
# Change:
#   volumes:
#     - ./backend/data:/app/data
# To a named volume:
#   volumes:
#     - backend_data:/app/data
```

---

## Issue 6: Docker Compose Network Conflicts

### Symptoms
```
ERROR: Pool overlaps with other one on this address space
Creating network "omoi_default" with the default driver
Error response from daemon: Pool overlaps with other one on this address space
```

### Root Cause Analysis

Docker's default subnet (`172.17.0.0/16`) conflicts with an existing network on the host (VPN, corporate network, or another Docker project).

### Diagnosis

```bash
# List all Docker networks
docker network ls

# Check subnet assignments
docker network inspect bridge | python3 -c "
import json, sys
data = json.load(sys.stdin)
for net in data:
    print(net['Name'], net.get('IPAM', {}).get('Config', []))
"

# Check for VPN interfaces
ifconfig | grep -E "utun|tun|vpn" | head -10
```

### Recovery Procedures

```bash
# Option 1: Specify a custom subnet in docker-compose.yml
# Add to the bottom of docker-compose.yml:
networks:
  default:
    driver: bridge
    ipam:
      config:
        - subnet: 192.168.200.0/24

# Option 2: Remove conflicting Docker networks
docker network prune -f

# Option 3: Disconnect VPN temporarily during Docker startup
```

---

## Issue 7: Container Out of Memory (OOM Kill)

### Symptoms
```
Exited (137)  # 137 = 128 + 9 (SIGKILL)
```
Or in logs:
```
Killed
Out of memory: Kill process <PID>
```

### Root Cause Analysis

The container exceeded its memory limit and was killed by the OOM killer. PostgreSQL and the backend API are the most common culprits.

### Diagnosis

```bash
# Check container exit codes
docker ps -a --format "table {{.Names}}\t{{.Status}}"

# Check system memory
free -h  # Linux
vm_stat | head -10  # macOS

# Check Docker stats
docker stats --no-stream
```

### Recovery Procedures

```bash
# Increase memory limits in docker-compose.yml
services:
  postgres:
    mem_limit: 1g
    memswap_limit: 2g

  backend-api:
    mem_limit: 2g
    memswap_limit: 4g

# Or remove limits entirely for development
# (remove mem_limit lines)

# Restart after config change
docker-compose down
just docker-up
```

---

## Issue 8: Slow Container Startup on macOS

### Symptoms
- `just docker-up` takes 60+ seconds
- Health checks time out during startup
- `docker stats` shows high CPU on `com.docker.hyperkit`

### Root Cause Analysis

Docker Desktop on macOS uses a Linux VM (HyperKit or Apple Virtualization Framework). File system operations through the VM are slow, especially for volume mounts with many small files.

### Recovery Procedures

```bash
# Use Docker Desktop's VirtioFS for faster file sharing
# Docker Desktop → Settings → General → "Use VirtioFS"

# Reduce bind mounts — use named volumes instead
# In docker-compose.yml, replace:
#   - ./backend:/app
# With:
#   - backend_code:/app
# And sync code via docker cp or rebuild

# Allocate more resources to Docker Desktop
# Docker Desktop → Settings → Resources
# Recommended: 4 CPUs, 8GB RAM, 60GB disk

# Use the "just watch" command which uses Docker with hot-reload
just watch
```

---

## Full Reset Procedure

When nothing else works, perform a complete Docker reset:

```bash
# Step 1: Stop all OmoiOS containers
just stop-all
# or
docker-compose down

# Step 2: Remove OmoiOS containers and volumes
docker-compose down -v --remove-orphans

# Step 3: Remove OmoiOS images (forces rebuild)
docker images | grep omoi | awk '{print $3}' | xargs docker rmi -f

# Step 4: Clean up Docker system
docker system prune -f

# Step 5: Restart infrastructure
just docker-up

# Step 6: Wait for health checks
sleep 10
docker ps

# Step 7: Re-run migrations
just db-migrate

# Step 8: Start the application
just dev-all
```

---

## Docker Compose Reference

### Key Commands

```bash
# Start infrastructure only (Postgres + Redis)
cd backend && docker-compose up -d

# Start full stack
docker-compose up -d  # from repo root

# View logs
docker-compose logs -f postgres
docker-compose logs -f redis
docker-compose logs -f backend-api

# Restart a single service
docker-compose restart postgres

# Execute commands inside a container
docker exec -it omoi_postgres psql -U omoi_user -d omoi_db

# Check container resource usage
docker stats

# List volumes
docker volume ls | grep omoi
```

### Environment Variables for Docker

```bash
# backend/.env — used by native backend
DATABASE_URL=postgresql+asyncpg://omoi_user:omoi_password@localhost:15432/omoi_db
REDIS_URL=redis://localhost:16379/0

# When backend runs inside Docker (use service names)
DATABASE_URL=postgresql+asyncpg://omoi_user:omoi_password@postgres:5432/omoi_db
REDIS_URL=redis://redis:6379/0
```

---

## Related Documentation

- [Database Issues](database-connections.md) — PostgreSQL-specific problems
- [Redis Issues](redis-issues.md) — Redis-specific problems
- [CONTRIBUTING.md](../../CONTRIBUTING.md) — Full local setup guide
- [CLAUDE.md](../../CLAUDE.md) — Port configuration reference
