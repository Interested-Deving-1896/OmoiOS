# Database Connections Troubleshooting Guide

**Status**: Active | **Last Updated**: 2025-04-22 | **Applies To**: OmoiOS v1.0+

**Source Files**:
- `backend/omoi_os/services/database.py` - Database service and connection management
- `backend/omoi_os/config.py` - Database settings configuration
- `backend/config/base.yaml` - Database connection parameters
- `backend/alembic.ini` - Migration configuration

**Related Documentation**:
- **Architecture: Database Schema**
- [Backend CLAUDE.md](../../backend/CLAUDE.md)
- [Detached Instance Fixes](detached_instance_fixes.md)

---

## Overview

OmoiOS uses **PostgreSQL 16** (Port: **15432**) as its primary data store with **SQLAlchemy 2.0** and **psycopg3** (asyncpg-compatible). The system implements connection pooling, automatic reconnection, and comprehensive timeout handling for production reliability.

### Connection Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   API Server    │────▶│  Connection Pool │────▶│   PostgreSQL    │
│  (FastAPI/ASGI) │     │  (SQLAlchemy 2)  │     │   (Port 15432)  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
        │                        │
        │              ┌─────────┴─────────┐
        │              │  Pool Settings:   │
        │              │  - pool_size: 5   │
        │              │  - max_overflow: 5│
        │              │  - pre_ping: true │
        │              └───────────────────┘
        │
   ┌────┴────┐
   │  Sync   │  (for migrations, admin)
   │  Async  │  (for API requests)
   └─────────┘
```

---

## Common Errors Table

| Error Message | Cause | Fix |
|--------------|-------|-----|
| `sqlalchemy.orm.exc.DetachedInstanceError: Parent instance <Model> is not bound to a Session` | Lazy-loaded attribute accessed after session closed | Use eager loading (`selectinload`) or refresh within session |
| `sqlalchemy.exc.TimeoutError: QueuePool limit of size 10 overflow 10 reached` | Connection pool exhausted | Increase pool size or close sessions properly |
| `asyncpg.exceptions.CannotConnectNowError: [Errno 61] Connection refused` | PostgreSQL not running or wrong port | Start Docker container or check port configuration |
| `sqlalchemy.exc.OperationalError: connection was closed in the middle of operation` | Network timeout or server killed connection | Enable `pool_pre_ping` and TCP keepalive |
| `asyncpg.exceptions._base.InterfaceError: cannot perform operation: another operation is in progress` | Concurrent operations on same session | Use one session per task, ensure proper `await` |
| `FATAL: remaining connection slots are reserved for non-replication superuser connections` | PostgreSQL max connections reached | Increase PostgreSQL `max_connections` or reduce pool size |
| `ERROR: column "metadata" does not exist` | Using reserved SQLAlchemy column name | Rename column to `change_metadata` or `item_metadata` |
| `asyncpg.exceptions.InvalidPasswordError: password authentication failed` | Wrong database credentials | Check `DATABASE_URL` in `.env` |
| `alembic.util.exc.CommandError: Can't locate revision identified by 'xxx'` | Migration out of sync | Run `just db-migrate` or check migration history |
| `sqlalchemy.exc.ProgrammingError: relation "users" does not exist` | Tables not created | Run migrations: `uv run alembic upgrade head` |

---

## Diagnostic Commands

### Check PostgreSQL Status

```bash
# Check if Postgres is running
docker ps | grep postgres

# Test connection from host
pg_isready -h localhost -p 15432 -U postgres

# View Postgres logs
docker logs omoi_os_postgres

# Check current active connections
just db-shell -c "SELECT count(*) FROM pg_stat_activity;"

# Check PostgreSQL max connections
just db-shell -c "SHOW max_connections;"
```

### Connection Pool Diagnostics

```bash
# Check pool status via Python
cd backend && uv run python -c "
from omoi_os.config import get_app_settings
from omoi_os.services.database import DatabaseService

settings = get_app_settings()
db = DatabaseService(connection_string=settings.database.url)

# Check sync engine pool
print(f'Pool size: {db.engine.pool.size()}')
print(f'Checked in: {db.engine.pool.checkedin()}')
print(f'Checked out: {db.engine.pool.checkedout()}')
"

# Monitor connection usage
just db-shell -c "
SELECT state, count(*) 
FROM pg_stat_activity 
WHERE datname = 'omoi_os' 
GROUP BY state;
"
```

### Migration Diagnostics

```bash
# View migration history
uv run alembic history

# Check current revision
uv run alembic current

# Verify migration status
uv run alembic heads

# Check for pending migrations
uv run alembic check
```

---

## Symptom 1: DetachedInstanceError

**Error Message**: `sqlalchemy.orm.exc.DetachedInstanceError: Parent instance <Model> is not bound to a Session; lazy load operation of attribute 'attribute' cannot proceed`

**Root Cause**: This occurs when an async service tries to access a lazy-loaded relationship after the session that loaded the object has been closed. In OmoiOS, this is common when accessing `User.organizations` or related attributes after the request context ends.

### Diagnostic Steps

1. **Identify the failing access pattern**:
   ```python
   # Problematic pattern
   async with db.get_async_session() as session:
       user = await session.execute(select(User).where(User.id == user_id))
       user_obj = user.scalar_one()
   # Session closes here
   print(user_obj.organizations)  # ERROR: DetachedInstanceError
   ```

2. **Check SQLAlchemy session lifecycle**:
   Review `backend/omoi_os/api/dependencies.py` for session management.

3. **Verify eager loading strategy**:
   Check if relationships are being lazy-loaded outside the session context.

### Fix Procedure

1. **Eager Loading** (Recommended):
   Use `selectinload` or `joinedload` in the repository/service layer.
   ```python
   from sqlalchemy.orm import selectinload
   
   # backend/omoi_os/services/user_service.py
   stmt = select(User).where(User.id == user_id).options(
       selectinload(User.organizations),
       selectinload(User.settings)
   )
   result = await session.execute(stmt)
   user = result.scalar_one()
   # Now user.organizations is loaded and accessible
   ```

2. **Explicit Refresh**:
   Refresh the attribute while the session is still active.
   ```python
   async with db.get_async_session() as session:
       user = await session.execute(select(User).where(User.id == user_id))
       user_obj = user.scalar_one()
       await session.refresh(user_obj, ["organizations"])
       # Now safe to access user_obj.organizations
   ```

3. **Extract ID Early**:
   Extract the user ID before the session closes.
   ```python
   async with db.get_async_session() as session:
       user = await session.execute(select(User).where(User.id == user_id))
       user_obj = user.scalar_one()
       user_id = user_obj.id  # Extract before session closes
   
   # Use user_id for subsequent operations instead of user_obj.id
   ```

---

## Symptom 2: QueuePool Limit Reached

**Error Message**: `sqlalchemy.exc.TimeoutError: QueuePool limit of size 10 overflow 10 reached, connection timed out, timeout 30.0`

**Root Cause**: The database connection pool is exhausted. This happens when:
1. Sessions are not being closed (missing `await session.close()`)
2. Long-running transactions are holding connections (e.g., blocking LLM calls inside a DB transaction)
3. The `POOL_SIZE` in `config/base.yaml` is too low for the current traffic

### Diagnostic Steps

1. **Check active connections**:
   ```bash
   just db-shell -c "
   SELECT count(*), state 
   FROM pg_stat_activity 
   WHERE datname = 'omoi_os' 
   GROUP BY state;
   "
   ```

2. **Identify long-running queries**:
   ```bash
   just db-shell -c "
   SELECT pid, state, query_start, now() - query_start as duration, query
   FROM pg_stat_activity
   WHERE state = 'active' AND now() - query_start > interval '10 seconds';
   "
   ```

3. **Check application logs**:
   ```bash
   tail -f backend/logs/api.log | grep -i "pool\|timeout"
   ```

### Fix Procedure

1. **Close Sessions Properly**:
   Ensure `async with get_session() as session:` is used correctly.
   ```python
   # Correct usage
   async with db.get_async_session() as session:
       result = await session.execute(select(User))
       users = result.scalars().all()
       # Session automatically closes on exit
   ```

2. **Move I/O Out of Transactions**:
   Never perform LLM calls or sandbox operations inside a database transaction block.
   ```python
   # WRONG: Holding connection during LLM call
   async with db.get_async_session() as session:
       task = await session.get(Task, task_id)
       result = await llm.complete(task.prompt)  # DON'T DO THIS
       task.result = result
       await session.commit()
   
   # CORRECT: Separate I/O from transaction
   task = await get_task(task_id)  # Quick DB operation
   result = await llm.complete(task.prompt)  # I/O outside transaction
   await update_task_result(task_id, result)  # Quick DB operation
   ```

3. **Increase Pool Size**:
   Adjust `backend/config/base.yaml`:
   ```yaml
   database:
     pool_size: 20          # Increase from 5
     max_overflow: 10         # Increase from 5
     pool_timeout: 30
     pool_recycle: 1800
     pool_pre_ping: true
   ```

4. **Set Connection Limits**:
   Ensure PostgreSQL `max_connections` > application pool total:
   ```bash
   # PostgreSQL max_connections should be > (pool_size + max_overflow) * num_app_instances
   # Example: (20 + 10) * 4 instances = 120 connections needed
   just db-shell -c "ALTER SYSTEM SET max_connections = 200;"
   ```

---

## Symptom 3: Connection Refused

**Error Message**: `asyncpg.exceptions.CannotConnectNowError: [Errno 61] Connection refused`

**Root Cause**: The backend cannot reach the Postgres port (15432).
1. Docker container is down
2. Wrong port specified in `.env` (default is 15432, not 5432)
3. Postgres is in "recovery mode" or starting up

### Diagnostic Steps

1. **Check Docker container status**:
   ```bash
   docker ps | grep postgres
   docker-compose ps
   ```

2. **Verify port accessibility**:
   ```bash
   pg_isready -h localhost -p 15432 -U postgres
   nc -zv localhost 15432
   ```

3. **Check environment configuration**:
   ```bash
   grep DATABASE_URL backend/.env
   ```

### Fix Procedure

1. **Restart Infrastructure**:
   ```bash
   just docker-up           # Start/restart Postgres + Redis
   just dev-infra-restart   # Full infrastructure restart
   ```

2. **Check .env Configuration**:
   Ensure `DATABASE_URL` uses the correct port:
   ```bash
   # backend/.env
   DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:15432/omoi_os
   ```

3. **Wait for Health Check**:
   ```bash
   # Check container health status
   docker inspect omoi_os_postgres --format='{{.State.Health.Status}}'
   
   # Wait and retry
   sleep 5 && pg_isready -h localhost -p 15432
   ```

4. **Check Docker Logs**:
   ```bash
   docker logs omoi_os_postgres --tail 50
   ```

---

## Symptom 4: Connection Closed Unexpectedly

**Error Message**: `sqlalchemy.exc.OperationalError: (asyncpg.exceptions.ConnectionDoesNotExistError) connection was closed in the middle of operation`

**Root Cause**: Usually a network timeout or the Postgres server killed the backend's process due to inactivity or resource limits.

### Diagnostic Steps

1. **Check PostgreSQL logs for terminations**:
   ```bash
   docker logs omoi_os_postgres 2>&1 | grep -i "terminate\|kill\|timeout"
   ```

2. **Verify connection settings**:
   ```bash
   just db-shell -c "SHOW statement_timeout;"
   just db-shell -c "SHOW tcp_keepalives_idle;"
   ```

3. **Check application timeout configuration**:
   ```yaml
   # backend/config/base.yaml
   database:
     command_timeout: 30
     connect_timeout: 10
   ```

### Fix Procedure

1. **Enable Pool Pre-Ping**:
   Ensure `pool_pre_ping=True` is set in `DatabaseService` (already default):
   ```python
   self.async_engine = create_async_engine(
       async_url,
       pool_pre_ping=True,  # Verify connection before use
       # ... other settings
   )
   ```

2. **Adjust PostgreSQL Keepalive**:
   ```bash
   just db-shell -c "
   ALTER SYSTEM SET tcp_keepalives_idle = 60;
   ALTER SYSTEM SET tcp_keepalives_interval = 10;
   ALTER SYSTEM SET tcp_keepalives_count = 6;
   SELECT pg_reload_conf();
   "
   ```

3. **Increase Statement Timeout** (if needed):
   ```yaml
   database:
     command_timeout: 60  # Increase for long-running queries
   ```

4. **Handle Gracefully in Code**:
   The `DatabaseService.get_async_session()` already handles these errors:
   ```python
   except (OperationalError, DisconnectionError) as e:
       logger.error("Database connection error: %s", error_msg)
       if session is not None:
           try:
               await session.rollback()
           except Exception:
               pass  # Connection may already be dead
       raise
   ```

---

## Symptom 5: Concurrent Operation Error

**Error Message**: `asyncpg.exceptions._base.InterfaceError: cannot perform operation: another operation is in progress`

**Root Cause**: Concurrent operations are being attempted on the same `AsyncSession` or `AsyncConnection`. Since asyncpg is not thread-safe and doesn't allow concurrent commands on a single connection, this happens when multiple tasks share a session.

### Diagnostic Steps

1. **Check for missing await**:
   ```bash
   cd backend && grep -r "session\." --include="*.py" | grep -v "await" | head -20
   ```

2. **Identify shared session patterns**:
   Look for sessions passed to background tasks or shared across async boundaries.

3. **Review task spawning**:
   ```python
   # Problematic: Sharing session across tasks
   async with db.get_async_session() as session:
       task1 = asyncio.create_task(operation1(session))
       task2 = asyncio.create_task(operation2(session))  # ERROR!
   ```

### Fix Procedure

1. **One Session Per Task**:
   Ensure each background task/request creates its own session:
   ```python
   # Correct: Each task gets its own session
   async def background_task(user_id: UUID):
       async with db.get_async_session() as session:
           user = await session.get(User, user_id)
           # ... operations
   ```

2. **Await Everything**:
   Check for missing `await` keywords on database calls:
   ```python
   # WRONG
   result = session.execute(select(User))  # Missing await!
   
   # CORRECT
   result = await session.execute(select(User))
   ```

3. **Use Proper Async Patterns**:
   ```python
   # For parallel operations, use separate sessions
   async def get_users_parallel(user_ids: list[UUID]):
       async def fetch_one(user_id: UUID):
           async with db.get_async_session() as session:
               return await session.get(User, user_id)
       
       return await asyncio.gather(*[fetch_one(uid) for uid in user_ids])
   ```

---

## Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|---------------|
| `DATABASE_URL` | Yes | `postgresql+psycopg://postgres:postgres@localhost:15432/omoi_os` | Full connection string |
| `DATABASE_POOL_SIZE` | No | `5` | Max persistent connections |
| `DATABASE_MAX_OVERFLOW` | No | `5` | Additional connections above pool_size |
| `DATABASE_POOL_TIMEOUT` | No | `30` | Seconds to wait for connection |
| `DATABASE_POOL_RECYCLE` | No | `1800` | Recycle connections after N seconds |
| `DATABASE_POOL_PRE_PING` | No | `true` | Verify connection before use |
| `DATABASE_COMMAND_TIMEOUT` | No | `30` | Max time for SQL statements |
| `DATABASE_CONNECT_TIMEOUT` | No | `10` | Max time to establish connection |

### YAML Configuration (base.yaml)

```yaml
database:
  url: postgresql+psycopg://postgres:postgres@localhost:15432/omoi_os
  # Connection pool settings
  pool_size: 5              # Max persistent connections
  max_overflow: 5           # Additional connections above pool_size
  pool_timeout: 30          # Seconds to wait for connection from pool
  pool_recycle: 1800        # Recycle connections after 30 min
  pool_pre_ping: true       # Verify connection is alive before use
  pool_use_lifo: true       # Use LIFO for connection reuse
  # Statement/command timeouts (in seconds)
  command_timeout: 30       # Max time for a single SQL statement
  connect_timeout: 10       # Max time to establish a new connection
```

### Alembic Configuration (alembic.ini)

```ini
[alembic]
script_location = migrations
sqlalchemy.url = postgresql+psycopg://postgres:postgres@localhost:15432/app_db

[loggers]
keys = root,sqlalchemy,alembic

[logger_sqlalchemy]
level = WARN
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
qualname = alembic
```

---

## Step-by-Step Recovery Procedures

### Procedure 1: Reset Connection Pool

1. **Identify stuck connections**:
   ```bash
   just db-shell -c "
   SELECT pid, state, query_start, query
   FROM pg_stat_activity
   WHERE state = 'idle in transaction';
   "
   ```

2. **Terminate stuck connections**:
   ```bash
   just db-shell -c "
   SELECT pg_terminate_backend(pid)
   FROM pg_stat_activity
   WHERE state = 'idle in transaction' AND pid <> pg_backend_pid();
   "
   ```

3. **Restart application**:
   ```bash
   just dev-backend-restart
   ```

### Procedure 2: Fix Migration Issues

1. **Check current state**:
   ```bash
   uv run alembic current
   uv run alembic history
   ```

2. **If migration is stuck**:
   ```bash
   # Stamp to specific version (use with caution!)
   uv run alembic stamp <revision_id>
   
   # Or downgrade and re-apply
   uv run alembic downgrade -1
   uv run alembic upgrade head
   ```

3. **For fresh database**:
   ```bash
   # WARNING: Destroys all data!
   just db-shell -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
   uv run alembic upgrade head
   ```

### Procedure 3: Performance Tuning

1. **Analyze slow queries**:
   ```bash
   just db-shell -c "
   SELECT query, mean_exec_time, calls
   FROM pg_stat_statements
   ORDER BY mean_exec_time DESC
   LIMIT 10;
   "
   ```

2. **Check for missing indexes**:
   ```bash
   just db-shell -c "
   SELECT schemaname, tablename, attname as column
   FROM pg_stats
   WHERE schemaname = 'public'
   AND tablename IN ('users', 'tasks', 'tickets')
   ORDER BY tablename;
   "
   ```

3. **Update statistics**:
   ```bash
   just db-shell -c "ANALYZE;"
   ```

---

## Prevention Strategies

- **Use the Repository Pattern**: Centralize all DB access in `backend/omoi_os/services/repositories/` to ensure consistent loading strategies.

- **Migration Safety**: Always run `just db-migrate` before `just dev-all`.

- **Health Checks**: Monitor `/api/v1/health` which checks DB connectivity every 30s via the `HealthCheck` service.

- **Connection Monitoring**: Set up alerts for:
  - Pool exhaustion (>80% connections in use)
  - Long-running queries (>30 seconds)
  - Connection errors (>10 per minute)

- **SQLAlchemy Best Practices**:
  - Always use `async with` for sessions
  - Never share sessions across tasks
  - Use eager loading for relationships
  - Keep transactions short

---

## Exact Error Patterns Reference

| Error | Pattern | Resolution |
|-------|---------|------------|
| `FATAL: remaining connection slots are reserved` | Too many connections | Increase PostgreSQL `max_connections` |
| `ERROR: column "metadata" does not exist` | Reserved word usage | Rename to `change_metadata` |
| `asyncpg.exceptions.InvalidPasswordError` | Wrong credentials | Check `DATABASE_URL` |
| `alembic.util.exc.CommandError: Can't locate revision` | Migration conflict | Run `just db-migrate` |
| `sqlalchemy.exc.ProgrammingError: relation does not exist` | Missing tables | Run migrations |
| `sqlalchemy.exc.IntegrityError: duplicate key value` | Unique constraint violation | Check for existing records |
| `asyncpg.exceptions.UniqueViolationError` | Duplicate entry | Handle in application code |

---

*End of Database Connections Troubleshooting Guide*

*This guide covers PostgreSQL connection management, SQLAlchemy 2.0 patterns, and production-ready database operations in OmoiOS.*
