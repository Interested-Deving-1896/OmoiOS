# Database Issues Troubleshooting Guide

**Created**: 2025-04-22  
**Updated**: 2025-04-22  
**Status**: Active  
**Purpose**: Comprehensive guide to diagnosing and fixing PostgreSQL database issues in OmoiOS

---

## Table of Contents

1. [Quick Diagnostics](#quick-diagnostics)
2. [PostgreSQL Connection Refused](#postgresql-connection-refused)
3. [Migration Failures (Alembic)](#migration-failures-alembic)
4. [Query Timeouts](#query-timeouts)
5. [pgvector Extension Issues](#pgvector-extension-issues)
6. [Connection Pool Exhaustion](#connection-pool-exhaustion)
7. [Deadlocks](#deadlocks)
8. [Stale Read Replicas](#stale-read-replicas)
9. [Prevention Strategies](#prevention-strategies)
10. [Related Documentation](#related-documentation)

---

## Quick Diagnostics

```bash
# Check if PostgreSQL is running
just status

# Test database connection
uv run python -c "
from omoi_os.config import get_app_settings
from omoi_os.services.database import DatabaseService
settings = get_app_settings()
db = DatabaseService(connection_string=settings.database.url)
with db.get_session() as session:
    result = session.execute('SELECT 1')
    print('Connection successful:', result.scalar())
"

# Check PostgreSQL logs
docker compose logs postgres

# Verify connection string
echo $DATABASE_URL
# Expected: postgresql+psycopg://postgres:postgres@localhost:15432/omoi_os
```

---

## PostgreSQL Connection Refused

### Symptom

```
sqlalchemy.exc.OperationalError: (psycopg.OperationalError) connection to server at "localhost", port 15432 failed: Connection refused
	Is the server running on that host and accepting TCP/IP connections?
```

### Root Causes

| Cause | Description |
|-------|-------------|
| Docker not running | PostgreSQL container is not started |
| Port conflict | Another service is using port 15432 |
| Wrong host | Using `localhost` instead of `postgres` in Docker |
| Firewall blocking | Local firewall preventing connections |
| Container crashed | PostgreSQL container exited unexpectedly |

### Step-by-Step Fix

#### Step 1: Verify Docker Container Status

```bash
# Check if postgres container is running
docker ps | grep omoios_postgres

# If not running, start it
just docker-up
# or
docker compose up -d postgres
```

#### Step 2: Check Port Availability

```bash
# Check if port 15432 is in use
lsof -i :15432
# or
netstat -tuln | grep 15432

# Kill process if needed
just kill-port 15432
```

#### Step 3: Verify Connection String

```bash
# For local development (outside Docker)
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:15432/omoi_os

# For Docker containers (internal networking)
DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/app_db
```

#### Step 4: Check Container Logs

```bash
# View PostgreSQL logs
docker compose logs postgres

# Check for startup errors
docker compose logs postgres | grep -i error
```

#### Step 5: Restart PostgreSQL

```bash
# Restart the container
docker compose restart postgres

# Wait for health check
sleep 5
docker compose ps postgres
```

### Prevention

- Use `just docker-up` to ensure all services start together
- Configure Docker Compose health checks (already in `docker-compose.yml`)
- Set up monitoring for container restarts

---

## Migration Failures (Alembic)

### Symptom

```
alembic.util.exc.CommandError: Can't locate revision identified by 'abc123'

# OR

sqlalchemy.exc.ProgrammingError: (psycopg.errors.DuplicateTable) relation "users" already exists

# OR

alembic.util.exc.CommandError: Multiple heads found
```

### Root Causes

| Cause | Description |
|-------|-------------|
| Multiple heads | Two developers created migrations simultaneously |
| Missing revision | Database has a revision that doesn't exist in code |
| Duplicate objects | Migration tries to create existing tables/columns |
| Dependency conflict | Migration depends on a revision that was deleted |
| Manual DB changes | Schema was modified outside Alembic |

### Step-by-Step Fix

#### Fix 1: Multiple Heads

```bash
cd backend

# View current heads
uv run alembic heads

# Merge the heads
uv run alembic merge <head1> <head2> -m "merge_heads"

# Apply the merge
uv run alembic upgrade head
```

#### Fix 2: Missing Revision

```bash
# Check current database revision
uv run alembic current

# View all revisions
uv run alembic history

# If revision is missing, stamp to a known good revision
uv run alembic stamp <known_good_revision>

# Then upgrade
uv run alembic upgrade head
```

#### Fix 3: Duplicate Objects (Idempotent Migrations)

Edit the failing migration to use `IF NOT EXISTS`:

```python
# In migration file
from alembic import op
import sqlalchemy as sa

def upgrade():
    # Use checkfirst=True for create_table
    op.create_table(
        'new_table',
        sa.Column('id', sa.Integer(), nullable=False),
        # ... other columns
        sa.PrimaryKeyConstraint('id'),
        # This makes it idempotent
        if_not_exists=True
    )
```

#### Fix 4: Full Reset (Development Only)

```bash
# ⚠️ WARNING: This deletes all data!
cd backend

# Drop and recreate database
docker compose exec postgres psql -U postgres -c "DROP DATABASE app_db;"
docker compose exec postgres psql -U postgres -c "CREATE DATABASE app_db;"

# Recreate tables
uv run alembic upgrade head
```

### Prevention

- Always run `uv run alembic upgrade head` before starting development
- Coordinate with team before creating migrations
- Use `just db-migrate` command which includes checks
- Never manually modify the database schema outside migrations

---

## Query Timeouts

### Symptom

```
sqlalchemy.exc.TimeoutError: QueuePool limit of size 5 overflow 5 reached, connection timed out, timeout 30.00

# OR

sqlalchemy.exc.OperationalError: (psycopg.errors.QueryCanceled) canceling statement due to statement timeout
```

### Root Causes

| Cause | Description |
|-------|-------------|
| Long-running queries | Queries exceeding `command_timeout` (30s default) |
| Missing indexes | Full table scans on large tables |
| Connection pool exhaustion | All connections in use |
| N+1 queries | Inefficient ORM usage causing multiple queries |
| Lock contention | Queries waiting for locks |

### Step-by-Step Fix

#### Step 1: Identify Slow Queries

```python
# Enable SQL logging temporarily
import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# Or in config
# backend/config/base.yaml
database:
  echo: true  # Log all SQL
```

#### Step 2: Add Missing Indexes

```python
# In a new migration
from alembic import op

def upgrade():
    # Add index for frequently queried columns
    op.create_index(
        'ix_tasks_status_created',
        'tasks',
        ['status', 'created_at'],
        if_not_exists=True
    )
```

#### Step 3: Optimize N+1 Queries

```python
# ❌ BAD: N+1 queries
for task in session.query(Task).all():
    print(task.ticket.title)  # Queries ticket for each task

# ✅ GOOD: Eager loading
from sqlalchemy.orm import joinedload

tasks = (
    session.query(Task)
    .options(joinedload(Task.ticket))
    .all()
)
```

#### Step 4: Increase Pool Size (if needed)

```yaml
# backend/config/base.yaml
database:
  pool_size: 10              # Increase from 5
  max_overflow: 10           # Increase from 5
  pool_timeout: 60           # Increase from 30
  command_timeout: 60          # Increase from 30
```

#### Step 5: Kill Long-Running Queries

```bash
# Connect to PostgreSQL
docker compose exec postgres psql -U postgres -d app_db

# View active queries
SELECT pid, state, query_start, query 
FROM pg_stat_activity 
WHERE state = 'active' 
AND query_start < NOW() - INTERVAL '30 seconds';

# Kill a specific query
SELECT pg_terminate_backend(<pid>);
```

### Prevention

- Use `joinedload()` for relationships accessed in loops
- Add indexes for frequently filtered columns
- Set appropriate `command_timeout` values
- Monitor slow query logs

---

## pgvector Extension Issues

### Symptom

```
sqlalchemy.exc.ProgrammingError: (psycopg.errors.UndefinedFile) could not open extension control file "/usr/share/postgresql/16/extension/vector.control": No such file or directory

# OR

sqlalchemy.exc.ProgrammingError: (psycopg.errors.UndefinedObject) type "vector" does not exist
```

### Root Causes

| Cause | Description |
|-------|-------------|
| Wrong PostgreSQL image | Using standard postgres instead of pgvector image |
| Extension not created | pgvector extension not installed in database |
| Version mismatch | pgvector version incompatible with PostgreSQL |

### Step-by-Step Fix

#### Step 1: Verify Docker Image

```yaml
# docker-compose.yml
services:
  postgres:
    image: pgvector/pgvector:pg16  # ✅ Correct
    # NOT: postgres:16  # ❌ Missing pgvector
```

#### Step 2: Create Extension

```bash
# Connect to database
docker compose exec postgres psql -U postgres -d app_db

# Create extension
CREATE EXTENSION IF NOT EXISTS vector;

# Verify
SELECT * FROM pg_extension WHERE extname = 'vector';
```

#### Step 3: Recreate Container (if needed)

```bash
# Remove old container and volume
docker compose down postgres
docker volume rm senior_sandbox_postgres_data

# Recreate with correct image
docker compose up -d postgres

# Wait for health check
sleep 10

# Create extension
docker compose exec postgres psql -U postgres -d app_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### Prevention

- Always use `pgvector/pgvector:pg16` image
- Include extension creation in init scripts
- Test embedding features after database setup

---

## Connection Pool Exhaustion

### Symptom

```
sqlalchemy.exc.TimeoutError: QueuePool limit of size 5 overflow 5 reached, connection timed out, timeout 30.00

# Backend logs show:
# "Database connection error: connection already closed"
```

### Root Causes

| Cause | Description |
|-------|-------------|
| Leaked connections | Sessions not properly closed |
| Too many concurrent requests | Load exceeding pool capacity |
| Long-running transactions | Connections held for extended periods |
| No pool_pre_ping | Stale connections not detected |

### Step-by-Step Fix

#### Step 1: Check Current Connections

```bash
# Connect to PostgreSQL
docker compose exec postgres psql -U postgres -d app_db

# View active connections
SELECT 
    pid,
    usename,
    application_name,
    state,
    query_start,
    query
FROM pg_stat_activity
WHERE datname = 'app_db';

# Count by state
SELECT state, COUNT(*) 
FROM pg_stat_activity 
WHERE datname = 'app_db' 
GROUP BY state;
```

#### Step 2: Enable Pool Pre-Ping

```yaml
# backend/config/base.yaml
database:
  pool_pre_ping: true  # Verify connection before use
  pool_recycle: 1800   # Recycle connections after 30 min
```

#### Step 3: Kill Idle Connections

```sql
-- Kill idle connections (run in psql)
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'app_db'
AND state = 'idle'
AND state_change < NOW() - INTERVAL '5 minutes';
```

#### Step 4: Increase Pool Size

```yaml
# backend/config/base.yaml
database:
  pool_size: 10        # Increase from 5
  max_overflow: 10     # Increase from 5
  pool_timeout: 60     # Increase from 30
```

#### Step 5: Fix Connection Leaks

```python
# ❌ BAD: Connection not closed
def bad_function():
    session = db.SessionLocal()
    result = session.query(User).all()
    return result  # Session never closed!

# ✅ GOOD: Use context manager
def good_function():
    with db.get_session() as session:
        result = session.query(User).all()
        return result

# ✅ GOOD: Async pattern
async def async_good_function():
    async with db.get_async_session() as session:
        result = await session.execute(select(User))
        return result.scalars().all()
```

### Prevention

- Always use context managers (`with db.get_session()`)
- Enable `pool_pre_ping: true` in config
- Set appropriate `pool_recycle` time
- Monitor connection counts in production

---

## Deadlocks

### Symptom

```
sqlalchemy.exc.OperationalError: (psycopg.errors.DeadlockDetected) deadlock detected
DETAIL:  Process 123 waits for ShareLock on transaction 456; blocked by process 789.
```

### Root Causes

| Cause | Description |
|-------|-------------|
| Circular dependencies | Two transactions waiting for each other's locks |
| Long transactions | Holding locks while doing other work |
| Inconsistent lock order | Different code paths lock tables in different orders |
| Missing indexes | Table scans causing broader locks |

### Step-by-Step Fix

#### Step 1: Identify Deadlock Details

```bash
# Check PostgreSQL logs
docker compose logs postgres | grep -i deadlock

# View recent deadlocks in database
docker compose exec postgres psql -U postgres -d app_db -c "
SELECT 
    blocked_locks.pid AS blocked_pid,
    blocked_activity.usename AS blocked_user,
    blocking_locks.pid AS blocking_pid,
    blocking_activity.usename AS blocking_user,
    blocked_activity.query AS blocked_statement,
    blocking_activity.query AS blocking_statement
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.relation = blocked_locks.relation
    AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;
"
```

#### Step 2: Fix Transaction Order

```python
# ❌ BAD: Inconsistent ordering
def update_task_a():
    with db.get_session() as session:
        task = session.query(Task).get(1)
        ticket = session.query(Ticket).get(1)  # Different order!
        # ...

def update_task_b():
    with db.get_session() as session:
        ticket = session.query(Ticket).get(1)  # Different order!
        task = session.query(Task).get(1)
        # ...

# ✅ GOOD: Consistent ordering
def update_task():
    with db.get_session() as session:
        # Always lock in same order: Ticket first, then Task
        ticket = session.query(Ticket).get(1)
        task = session.query(Task).get(1)
        # ...
```

#### Step 3: Use Row-Level Locking

```python
from sqlalchemy import select
from sqlalchemy.orm import selectinload

# Use FOR UPDATE to lock rows explicitly
async with db.get_async_session() as session:
    result = await session.execute(
        select(Task)
        .where(Task.id == task_id)
        .with_for_update()  # Lock the row
    )
    task = result.scalar_one()
    # Modify and commit
    task.status = "completed"
    await session.commit()
```

#### Step 4: Keep Transactions Short

```python
# ❌ BAD: Long transaction with external calls
def bad_process():
    with db.get_session() as session:
        task = session.query(Task).get(1)
        # External API call while holding lock!
        result = call_external_api()
        task.result = result
        session.commit()

# ✅ GOOD: Short transaction
def good_process():
    # External call first
    result = call_external_api()
    
    # Then quick database update
    with db.get_session() as session:
        task = session.query(Task).get(1)
        task.result = result
        session.commit()
```

### Prevention

- Always access tables in the same order
- Keep transactions as short as possible
- Use `with_for_update()` for concurrent modifications
- Add indexes to reduce lock contention

---

## Stale Read Replicas

### Symptom

```
# Application reads old data after write
# Or sees inconsistent state across queries
```

### Root Causes

| Cause | Description |
|-------|-------------|
| Replication lag | Read replica behind primary |
| Session stickiness | Read after write hitting different replica |
| Caching issues | Application cache not invalidated |

### Step-by-Step Fix

#### Step 1: Check Replication Lag

```sql
-- On primary
SELECT 
    client_addr,
    state,
    sent_lsn,
    write_lsn,
    flush_lsn,
    replay_lsn,
    write_lag,
    flush_lag,
    replay_lag
FROM pg_stat_replication;

-- On replica
SELECT 
    extract(epoch from (now() - backend_start)) as lag_seconds
FROM pg_stat_activity 
WHERE application_name = 'walreceiver';
```

#### Step 2: Force Primary Read (if needed)

```python
# For critical read-after-write operations
# Use the primary database for reads
async with db.get_async_session() as session:
    # Hint: Use primary for this query
    result = await session.execute(
        select(Task).where(Task.id == task_id)
    )
    task = result.scalar_one()
```

#### Step 3: Implement Retry Logic

```python
import asyncio
from sqlalchemy import select

async def read_with_retry(task_id, max_retries=3):
    for attempt in range(max_retries):
        async with db.get_async_session() as session:
            result = await session.execute(
                select(Task).where(Task.id == task_id)
            )
            task = result.scalar_one_or_none()
            
            if task and task.updated_at > datetime.utcnow() - timedelta(seconds=5):
                return task
        
        # Wait for replication
        await asyncio.sleep(0.1 * (2 ** attempt))  # Exponential backoff
    
    return task
```

### Prevention

- Use session stickiness for read-after-write patterns
- Monitor replication lag metrics
- Implement retry logic for consistency-sensitive operations

---

## Prevention Strategies

### 1. Database Configuration Checklist

```yaml
# backend/config/base.yaml
database:
  # Connection pool
  pool_size: 5
  max_overflow: 5
  pool_timeout: 30
  pool_recycle: 1800
  pool_pre_ping: true
  pool_use_lifo: true
  
  # Timeouts
  command_timeout: 30
  connect_timeout: 10
```

### 2. Monitoring Queries

```bash
# Add to monitoring script
#!/bin/bash

# Check connection count
docker compose exec postgres psql -U postgres -d app_db -c "
SELECT count(*) as active_connections 
FROM pg_stat_activity 
WHERE state = 'active';
"

# Check for long-running queries
docker compose exec postgres psql -U postgres -d app_db -c "
SELECT pid, query_start, query 
FROM pg_stat_activity 
WHERE state = 'active' 
AND query_start < NOW() - INTERVAL '1 minute';
"

# Check for locks
docker compose exec postgres psql -U postgres -d app_db -c "
SELECT 
    l.locktype,
    l.relation::regclass,
    l.mode,
    l.granted,
    a.query
FROM pg_locks l
JOIN pg_stat_activity a ON l.pid = a.pid
WHERE NOT l.granted;
"
```

### 3. Code Review Checklist

- [ ] Use context managers for all database sessions
- [ ] Use `joinedload()` for relationships in loops
- [ ] Keep transactions short
- [ ] Use consistent table access ordering
- [ ] Add indexes for frequently filtered columns
- [ ] Handle `OperationalError` with retry logic

### 4. Migration Best Practices

```bash
# Before creating migrations
cd backend

# Check current state
uv run alembic current

# Create migration
uv run alembic revision -m "description"

# Test migration (up and down)
uv run alembic upgrade +1
uv run alembic downgrade -1
uv run alembic upgrade head
```

---

## Related Documentation

- [SQLAlchemy DetachedInstanceError Fixes](./detached_instance_fixes.md)
- [Migration Issues](./migration-issues.md)
- [Backend CLAUDE.md](../../backend/CLAUDE.md)
- [Database Service](../../backend/omoi_os/services/database.py)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/16/index.html)
- [Alembic Documentation](https://alembic.sqlalchemy.org/)

---

**Last Updated**: 2025-04-22  
**Document Owner**: Backend Team  
**Review Cycle**: Quarterly
