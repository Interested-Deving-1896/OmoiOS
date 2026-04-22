# Database Migration Troubleshooting

**Status**: Active | **Last Updated**: 2026-04-22 | **Applies To**: OmoiOS v1.0+

**Source Files**:
- `backend/alembic.ini` — Alembic configuration
- `backend/migrations/` — Migration scripts (74+ versions)
- `backend/migrations/env.py` — Migration environment setup
- `backend/omoi_os/models/` — SQLAlchemy model definitions

**Related Documentation**:
- **Architecture: Database Schema**
- [Database Issues](database-connections.md)
- [CONTRIBUTING.md](../../CONTRIBUTING.md) — Migration workflow

---

## Overview

OmoiOS uses Alembic for database schema migrations. The migration history spans 74+ versions covering the full schema evolution from initial models through agent orchestration, billing, and monitoring systems.

### Migration Workflow

```
Developer changes a model
    ↓
cd backend && uv run alembic revision -m "description"
    ↓ Alembic auto-generates migration script
backend/migrations/versions/NNN_description.py
    ↓
uv run alembic upgrade head
    ↓ Applied to database
```

### Key Commands

```bash
# Apply all pending migrations
just db-migrate
# equivalent to: cd backend && uv run alembic upgrade head

# Create a new migration
just db-revision "add user preferences table"
# equivalent to: cd backend && uv run alembic revision --autogenerate -m "..."

# Check current migration state
cd backend && uv run alembic current

# View migration history
just db-history
# equivalent to: cd backend && uv run alembic history --verbose

# Rollback one migration
just db-downgrade
# equivalent to: cd backend && uv run alembic downgrade -1
```

---

## Common Error Codes

| Error | Meaning | Typical Cause |
|-------|---------|---------------|
| `Can't locate revision` | Missing migration file | File deleted or not committed |
| `Multiple head revisions` | Branch conflict | Two migrations with same parent |
| `Target database is not up to date` | Pending migrations | Need to run `upgrade head` |
- `Column already exists` | Duplicate migration | Migration applied twice |
| `relation does not exist` | Missing table | Migration not applied |
| `alembic_version table not found` | Fresh database | First migration not run |
| `FAILED: Can't proceed with --autogenerate` | Model import error | Python import failure in env.py |

---

## Issue 1: Multiple Head Revisions (Branch Conflict)

### Symptoms
```
ERROR [alembic.util.messaging] Multiple head revisions are present for given argument 'head';
please specify a specific target revision, '<branchname>@head' to narrow to a specific head,
or 'heads' for all heads
```

### Root Cause Analysis

Two migration files both claim to be the "head" (latest) migration. This happens when two developers create migrations from the same base revision without merging first.

```
... → 003_agent_registry.py → 004_billing.py (HEAD A)
                            ↘ 004_monitoring.py (HEAD B)
```

### Diagnosis

```bash
cd backend

# Show all heads
uv run alembic heads

# Show the full branch graph
uv run alembic history --verbose | head -40

# Find the divergence point
uv run alembic branches
```

### Recovery Procedures

**Option 1: Merge the branches** (preferred for production):

```bash
cd backend

# Create a merge migration
uv run alembic merge heads -m "merge billing and monitoring branches"

# This creates a new migration that has both heads as parents
# Review the generated file — it should be empty (no schema changes)
cat migrations/versions/*merge*.py

# Apply the merge
uv run alembic upgrade head
```

**Option 2: Rebase one branch** (for development):

```bash
# Edit the conflicting migration file to point to the correct parent
# Change: down_revision = '003_agent_registry'
# To:     down_revision = '004_billing'

# Then upgrade
uv run alembic upgrade head
```

---

## Issue 2: Migration Fails Mid-Run

### Symptoms
```
sqlalchemy.exc.ProgrammingError: (psycopg2.errors.DuplicateColumn)
column "status" of relation "tasks" already exists
```
Or:
```
sqlalchemy.exc.ProgrammingError: (psycopg2.errors.UndefinedTable)
relation "agent_sessions" does not exist
```

### Root Cause Analysis

A migration script contains an operation that conflicts with the current database state. This happens when:
1. A migration was partially applied before a failure
2. Manual schema changes were made outside of Alembic
3. A migration was applied to a database that already had the change

### Diagnosis

```bash
cd backend

# Check current migration state
uv run alembic current

# Check what the database actually has
psql postgresql://omoi_user:omoi_password@localhost:15432/omoi_db -c "\d tasks"
psql postgresql://omoi_user:omoi_password@localhost:15432/omoi_db -c "\dt"

# Compare with what Alembic thinks should be there
uv run alembic show <revision_id>
```

### Recovery Procedures

**If column already exists** — make the migration idempotent:

```python
# In the migration file, wrap in a check:
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('tasks')]

    if 'status' not in columns:
        op.add_column('tasks', sa.Column('status', sa.String(50)))
```

**If table doesn't exist** — check migration order:

```bash
# Verify the migration that creates the table runs first
uv run alembic history | grep "agent_sessions"

# If out of order, fix the down_revision in the failing migration
# to point to the migration that creates the dependency
```

**Mark a migration as applied without running it** (use with caution):

```bash
# Stamp the database at a specific revision without running migrations
uv run alembic stamp <revision_id>

# Then continue from there
uv run alembic upgrade head
```

---

## Issue 3: `alembic_version` Table Missing

### Symptoms
```
sqlalchemy.exc.ProgrammingError: (psycopg2.errors.UndefinedTable)
relation "alembic_version" does not exist
```

### Root Cause Analysis

The database is fresh (just created) and has never had Alembic migrations applied. The `alembic_version` table is created by the first migration.

### Recovery Procedures

```bash
# Simply run all migrations from scratch
just db-migrate

# If the database doesn't exist yet
just docker-up  # Start Postgres
just db-migrate  # Creates alembic_version and applies all migrations
```

---

## Issue 4: Model Import Errors During Autogenerate

### Symptoms
```
FAILED: Can't proceed with --autogenerate option; environment script
/path/to/migrations/env.py does not provide a MetaData object or
sqlalchemy.engine.Connection to the context.
```
Or:
```
ImportError: cannot import name 'SomeModel' from 'omoi_os.models'
```

### Root Cause Analysis

Alembic's `env.py` imports all models to detect schema changes. If a model file has a syntax error or import failure, autogenerate fails.

### Diagnosis

```bash
cd backend

# Test model imports directly
uv run python -c "from omoi_os.models import *; print('OK')"

# Check for specific import errors
uv run python -c "
import importlib
import pkgutil
import omoi_os.models as models_pkg

for importer, modname, ispkg in pkgutil.walk_packages(
    path=models_pkg.__path__,
    prefix=models_pkg.__name__ + '.',
    onerror=lambda x: print(f'Error: {x}')
):
    try:
        importlib.import_module(modname)
        print(f'OK: {modname}')
    except Exception as e:
        print(f'FAIL: {modname}: {e}')
"
```

### Recovery Procedures

```bash
# Fix the import error in the model file
# Common causes:
# 1. Using 'metadata' or 'registry' as column names (reserved by SQLAlchemy)
# 2. Circular imports between model files
# 3. Missing dependency in pyproject.toml

# After fixing, verify imports work
uv run python -c "from omoi_os.models import *; print('All models imported OK')"

# Then retry autogenerate
just db-revision "your migration description"
```

---

## Issue 5: Schema Drift (Database Out of Sync with Models)

### Symptoms
- `uv run alembic current` shows `head` but queries fail with `column does not exist`
- Manual schema changes were made directly in the database
- A migration was applied to one environment but not another

### Diagnosis

```bash
cd backend

# Generate a "diff" migration to see what's out of sync
uv run alembic revision --autogenerate -m "detect_drift"

# Review the generated file
cat migrations/versions/*detect_drift*.py

# If it's empty, schema is in sync
# If it has changes, those are the drifted columns/tables
```

### Recovery Procedures

**Option A: Apply the drift migration** (safest):

```bash
# Review the generated migration carefully
# Then apply it
uv run alembic upgrade head
```

**Option B: Stamp and move on** (if drift is intentional):

```bash
# Delete the drift migration file
rm migrations/versions/*detect_drift*.py

# Stamp the database at head (tells Alembic "we're current")
uv run alembic stamp head
```

**Option C: Full reset** (development only — destroys data):

```bash
# Drop and recreate the database
psql postgresql://postgres:postgres@localhost:15432/postgres -c "DROP DATABASE omoi_db;"
psql postgresql://postgres:postgres@localhost:15432/postgres -c "CREATE DATABASE omoi_db;"

# Apply all migrations from scratch
just db-migrate
```

---

## Issue 6: Migration Conflicts After Git Merge

### Symptoms
After merging a feature branch, `just db-migrate` fails with:
```
ERROR: Multiple head revisions are present
```
Or two migration files have the same revision number prefix.

### Root Cause Analysis

Two developers created migrations independently. Both migrations have the same `down_revision` (the revision they branched from), creating a fork in the migration history.

### Recovery Procedures

```bash
cd backend

# Step 1: Identify the conflict
uv run alembic heads
# Shows: abc123 (head), def456 (head)

# Step 2: Create a merge migration
uv run alembic merge abc123 def456 -m "merge feature branches"

# Step 3: Review the merge migration (should be empty)
cat migrations/versions/*merge*.py

# Step 4: Apply
uv run alembic upgrade head

# Step 5: Commit the merge migration
git add migrations/versions/*merge*.py
git commit -m "fix: merge alembic migration branches"
```

---

## Issue 7: Slow Migrations on Large Tables

### Symptoms
- Migration runs for 10+ minutes
- Database locks causing API timeouts during migration
- `ALTER TABLE` operations blocking reads/writes

### Root Cause Analysis

PostgreSQL `ALTER TABLE` operations acquire an `ACCESS EXCLUSIVE` lock that blocks all reads and writes. On large tables (millions of rows), this can take minutes.

### Recovery Procedures

**Use `ADD COLUMN` with a default** (fast in PostgreSQL 11+):

```python
# Fast — PostgreSQL 11+ stores default in catalog, no table rewrite
op.add_column('tasks', sa.Column(
    'priority',
    sa.Integer(),
    server_default='0',
    nullable=False
))
```

**Create indexes concurrently** (no table lock):

```python
# In migration — use raw SQL for CONCURRENTLY
op.execute(
    "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tasks_status ON tasks(status)"
)
```

**Add NOT NULL constraints in two phases**:

```python
def upgrade():
    # Phase 1: Add nullable column
    op.add_column('tasks', sa.Column('agent_id', sa.String(255), nullable=True))

    # Phase 2: Backfill data
    op.execute("UPDATE tasks SET agent_id = 'unknown' WHERE agent_id IS NULL")

    # Phase 3: Add NOT NULL constraint (fast since no nulls exist)
    op.alter_column('tasks', 'agent_id', nullable=False)
```

---

## Zero-Downtime Migration Checklist

For production deployments, follow this checklist:

```
□ Migration is backward-compatible (old code works with new schema)
□ No column renames (use add + copy + drop in separate deployments)
□ No NOT NULL without defaults on existing tables
□ Indexes created with CONCURRENTLY
□ Large table changes tested on a copy first
□ Rollback migration (downgrade) is written and tested
□ Migration tested on staging with production data volume
□ Deployment window communicated to team
```

---

## Useful Alembic Commands Reference

```bash
cd backend

# Show current revision
uv run alembic current

# Show full history
uv run alembic history --verbose

# Show pending migrations
uv run alembic history -r current:head

# Apply specific revision
uv run alembic upgrade <revision_id>

# Rollback to specific revision
uv run alembic downgrade <revision_id>

# Rollback one step
uv run alembic downgrade -1

# Rollback all migrations
uv run alembic downgrade base

# Show SQL without applying
uv run alembic upgrade head --sql

# Stamp without running
uv run alembic stamp head

# Show branches
uv run alembic branches

# Merge branches
uv run alembic merge <rev1> <rev2> -m "merge description"
```

---

## Related Documentation

- [Database Issues](database-connections.md) — PostgreSQL connection problems
- **Architecture: Database Schema** — Schema design
- [CONTRIBUTING.md](../../CONTRIBUTING.md) — Migration workflow for contributors
- [SQLAlchemy DetachedInstanceError Fixes](detached_instance_fixes.md) — ORM session issues
