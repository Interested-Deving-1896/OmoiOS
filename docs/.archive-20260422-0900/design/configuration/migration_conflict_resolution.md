# Migration Conflict Resolution

**Created**: 2025-12-12  
**Status**: Active  
**Purpose**: Comprehensive guide for resolving Alembic migration conflicts, preventing future conflicts, and maintaining clean migration history  
**Related**: [Database Schema](../../architecture/11-database-schema.md), [Backend Guide](../../../backend/CLAUDE.md)

---

## Table of Contents

1. [Overview](#overview)
2. [Understanding Migration Conflicts](#understanding-migration-conflicts)
3. [Conflict Types](#conflict-types)
4. [Resolution Strategies](#resolution-strategies)
5. [Step-by-Step Resolution](#step-by-step-resolution)
6. [Prevention Best Practices](#prevention-best-practices)
7. [Code Examples](#code-examples)
8. [Troubleshooting](#troubleshooting)
9. [Related Files](#related-files)

---

## Overview

Database migration conflicts occur when multiple developers create migrations simultaneously, resulting in divergent migration histories. Alembic uses a linear revision chain (`down_revision` pointers), and conflicts arise when two migrations claim the same parent.

### The Problem

When two migration files both claim revision `003_*` with the same parent:

```
003_agent_registry_expansion.py — Revision: "003_agent_registry", Parent: "002_phase1"
003_phase_workflow.py           — Revision: "003_phase_workflow", Parent: "002_phase1"
```

This creates a **branching migration tree**, which Alembic cannot resolve automatically. The migration history becomes:

```
001_initial → 002_phase1 → [003_agent_registry]
                         ↘ [003_phase_workflow]  ← CONFLICT!
```

### Impact

- **Production deployments fail** — Alembic raises `CommandError` on upgrade
- **CI/CD pipelines break** — Automated migrations fail
- **Developer friction** — Team members blocked until resolved
- **Data integrity risks** — Manual fixes can corrupt migration state

---

## Understanding Migration Conflicts

### How Alembic Tracks History

Alembic uses a **directed graph** where each migration points to its parent:

```python
# migration_file.py
revision: str = "003_example"        # Unique identifier
down_revision: str = "002_parent"    # Parent in the chain
branch_labels: Optional[str] = None   # For named branches
depends_on: Optional[str] = None     # Cross-branch dependencies
```

The `alembic_version` table in your database stores the current revision:

```sql
SELECT * FROM alembic_version;
-- version_num
-- ------------
-- 002_phase1
```

### Conflict Scenarios

#### Scenario 1: Simultaneous Development

Two developers branch from `main` (at revision `002_phase1`):

```
Developer A: Creates 003_agent_registry (parent: 002_phase1)
Developer B: Creates 003_phase_workflow (parent: 002_phase1)

Both merge to main → CONFLICT!
```

#### Scenario 2: Long-Running Branches

```
main: 001 → 002 → 003 → 004
                    ↑
feature-branch:     003_feature (parent: 002)

When feature-branch merges, 003_feature conflicts with 003, 004
```

#### Scenario 3: Cherry-Pick Conflicts

Cherry-picking a migration from another branch can create duplicate revisions or orphaned chains.

---

## Conflict Types

### Type 1: Revision Collision (Same Parent)

**Symptom**: Two migrations with same `down_revision`

```python
# File 1: 003_agent_registry.py
revision = "003_agent_registry"
down_revision = "002_phase1"

# File 2: 003_phase_workflow.py
revision = "003_phase_workflow"
down_revision = "002_phase1"  # SAME PARENT!
```

**Detection**:
```bash
uv run alembic history
# CommandError: Multiple heads found
```

### Type 2: Duplicate Revisions

**Symptom**: Same `revision` ID in multiple files

```python
# File 1 and File 2 both have:
revision = "003_duplicate"
```

**Detection**:
```bash
uv run alembic check
# FAILED: Duplicate revision ID found
```

### Type 3: Orphaned Migrations

**Symptom**: Migration with no path from base

```python
# 004_orphan.py
revision = "004_orphan"
down_revision = "003_nonexistent"  # Parent doesn't exist!
```

**Detection**:
```bash
uv run alembic history --verbose
# Shows disconnected nodes
```

### Type 4: Cross-Branch Dependencies

**Symptom**: `depends_on` references migration in unmerged branch

```python
revision = "005_cross"
down_revision = "004_main"
depends_on = "004_other_branch"  # May not exist in all environments
```

---

## Resolution Strategies

### Strategy 1: Linear Chain (Recommended)

Make the second migration depend on the first, creating a linear history:

```python
# In migrations/versions/003_phase_workflow.py
revision: str = "003_phase_workflow"
down_revision: Union[str, None] = "003_agent_registry"  # Changed from 002_phase1
```

**Result**:
```
001_initial → 002_phase1 → 003_agent_registry → 003_phase_workflow
```

**When to use**:
- Migrations are orthogonal (different tables/columns)
- No conflicting schema changes
- Team prefers linear history

**Pros**:
- Simple to understand
- Works with all Alembic commands
- No merge migrations needed

**Cons**:
- Loses some parallelism information
- Must determine dependency order

### Strategy 2: Branch Labels

Keep both as independent branches with labels:

```python
# In migrations/versions/003_agent_registry_expansion.py
revision: str = "003_agent_registry"
down_revision: Union[str, None] = "002_phase1"
branch_labels: Union[str, Sequence[str], None] = ("registry",)

# In migrations/versions/003_phase_workflow.py
revision: str = "003_phase_workflow"
down_revision: Union[str, None] = "002_phase1"
branch_labels: Union[str, Sequence[str], None] = ("workflow",)
```

Then create a merge migration:

```bash
uv run alembic merge -m "merge_registry_and_workflow" \
    003_agent_registry 003_phase_workflow
```

**Result**:
```
001_initial → 002_phase1 → [003_agent_registry]
                         ↘ [003_phase_workflow] ↘
                                                  004_merge
```

**When to use**:
- Migrations truly independent
- Need to track parallel development
- Long-running feature branches

**Pros**:
- Preserves parallel development history
- Clear branch/merge semantics

**Cons**:
- More complex
- Requires merge migration
- Some tools don't handle branches well

### Strategy 3: Revision Renumbering

Rename one migration to fit in sequence:

```bash
# Rename file
git mv 003_phase_workflow.py 004_phase_workflow.py

# Update revision and parent
# In 004_phase_workflow.py:
revision = "004_phase_workflow"
down_revision = "003_agent_registry"
```

**When to use**:
- Early in development (no production data)
- Simple sequential ordering obvious

**Pros**:
- Clean linear history
- Simple to implement

**Cons**:
- Breaks existing deployments
- Must coordinate with team

---

## Step-by-Step Resolution

### Step 1: Identify the Conflict

```bash
# Check current migration status
uv run alembic history --verbose

# Check for multiple heads
uv run alembic heads

# Show current database revision
uv run alembic current
```

### Step 2: Analyze the Migrations

```bash
# List all migration files
ls -la backend/migrations/versions/

# Check revision IDs
grep -h "revision = " backend/migrations/versions/*.py

# Check down_revision pointers
grep -h "down_revision" backend/migrations/versions/*.py
```

### Step 3: Choose Resolution Strategy

**Decision matrix**:

| Condition | Recommended Strategy |
|-----------|---------------------|
| Both migrations touch same table | Linear chain (Strategy 1) |
| Migrations are orthogonal | Linear chain or Branch labels |
| Already deployed to production | Branch labels + merge |
| Early development, no prod data | Revision renumbering |

### Step 4: Implement the Fix

#### For Linear Chain (Strategy 1):

```python
# In 003_phase_workflow.py, line 17:
# BEFORE:
down_revision: Union[str, None] = "002_phase1"

# AFTER:
down_revision: Union[str, None] = "003_agent_registry"
```

Verify:
```bash
uv run alembic history
# Should show: 001 → 002 → 003_agent → 003_phase
```

#### For Branch Labels (Strategy 2):

```python
# In 003_agent_registry.py:
revision = "003_agent_registry"
down_revision = "002_phase1"
branch_labels = ("registry",)

# In 003_phase_workflow.py:
revision = "003_phase_workflow"
down_revision = "002_phase1"
branch_labels = ("workflow",)
```

Create merge:
```bash
uv run alembic merge -m "merge_branches" \
    003_agent_registry 003_phase_workflow
```

### Step 5: Verify the Fix

```bash
# 1. Check history is linear (or properly branched)
uv run alembic history

# 2. Run upgrade on fresh database
uv run alembic downgrade base
uv run alembic upgrade head

# 3. Verify schema is correct
uv run python -c "
from omoi_os.services.database import DatabaseService
from omoi_os.config import get_app_settings
db = DatabaseService(connection_string=get_app_settings().database.url)
with db.get_session() as session:
    result = session.execute('SELECT version_num FROM alembic_version')
    print('Current revision:', result.scalar())
"

# 4. Run tests
just test
```

### Step 6: Commit and Notify

```bash
# Stage changes
git add backend/migrations/versions/

# Commit with clear message
git commit -m "fix: resolve migration conflict between agent_registry and phase_workflow

- Changed 003_phase_workflow down_revision to 003_agent_registry
- Creates linear migration chain: 001 → 002 → 003_agent → 003_phase
- Verified with alembic upgrade head on fresh database

Fixes: #<issue_number>"

# Push and notify team
git push origin fix/migration-conflict
```

---

## Prevention Best Practices
n
### 1. Pre-Migration Checklist

Before creating a new migration:

```bash
# 1. Pull latest main
git checkout main
git pull origin main

# 2. Check current head
uv run alembic heads

# 3. Create migration (will use correct parent)
uv run alembic revision -m "add user preferences"

# 4. Verify parent is correct
grep down_revision backend/migrations/versions/$(uv run alembic heads -v | tail -1).py
```

### 2. CI/CD Protection

Add to your CI pipeline (`.github/workflows/ci.yml`):

```yaml
- name: Check Migrations
  run: |
    # Check for multiple heads
    uv run alembic heads | grep -q "Multiple heads" && exit 1
    
    # Check migration chain integrity
    uv run alembic check
    
    # Test upgrade on fresh database
    uv run alembic downgrade base
    uv run alembic upgrade head
```

### 3. Team Workflow

**Rule**: Always pull main before creating migrations

```bash
# Recommended workflow
git checkout main
git pull origin main
uv run alembic upgrade head  # Ensure local DB is current
git checkout -b feature/my-feature

# ... make code changes ...

# Create migration AFTER pulling latest
uv run alembic revision -m "add new table"
git add .
git commit -m "feat: add new table"
```

### 4. Migration Naming Convention

Use descriptive names to avoid confusion:

```
✅ 003_add_user_preferences_table.py
✅ 004_create_task_indexes.py
❌ 003_migration.py
❌ 004_fix_stuff.py
```

### 5. Regular Migration Audits

```bash
# Weekly check for issues
uv run alembic history --verbose > /tmp/migration_history.txt
uv run alembic heads > /tmp/migration_heads.txt

# Check for:
# - Multiple heads
# - Duplicate revisions
# - Orphaned migrations
```

---

## Code Examples

### Example 1: Detecting Conflicts Programmatically

```python
# scripts/check_migrations.py
from pathlib import Path
import re
from typing import Dict, List, Set

def check_migration_conflicts():
    """Check for migration conflicts before they cause issues."""
    versions_dir = Path("backend/migrations/versions")
    
    revisions: Dict[str, Path] = {}
    down_revisions: Dict[str, str] = {}
    
    for migration_file in versions_dir.glob("*.py"):
        content = migration_file.read_text()
        
        # Extract revision
        rev_match = re.search(r'revision\s*=\s*["\']([^"\']+)["\']', content)
        if rev_match:
            revision = rev_match.group(1)
            if revision in revisions:
                print(f"❌ DUPLICATE: {revision} in {migration_file} and {revisions[revision]}")
            revisions[revision] = migration_file
        
        # Extract down_revision
        down_match = re.search(r'down_revision\s*=\s*["\']([^"\']+)["\']', content)
        if down_match:
            down_revisions[revision] = down_match.group(1)
    
    # Check for multiple heads
    all_parents = set(down_revisions.values())
    all_revisions = set(revisions.keys())
    heads = all_revisions - all_parents
    
    if len(heads) > 1:
        print(f"❌ MULTIPLE HEADS: {heads}")
        print("   Run: uv run alembic merge to resolve")
    else:
        print(f"✅ Single head: {heads}")
    
    return len(heads) <= 1

if __name__ == "__main__":
    import sys
    sys.exit(0 if check_migration_conflicts() else 1)
```

### Example 2: Automated Merge Migration

```python
# scripts/merge_migrations.py
import subprocess
import sys

def create_merge_migration():
    """Automatically create merge migration when multiple heads detected."""
    # Get current heads
    result = subprocess.run(
        ["uv", "run", "alembic", "heads"],
        capture_output=True,
        text=True,
    )
    
    heads = [line.strip() for line in result.stdout.split("\n") if line.strip()]
    
    if len(heads) <= 1:
        print("✅ No merge needed, single head")
        return 0
    
    print(f"Found {len(heads)} heads: {heads}")
    
    # Create merge migration
    cmd = ["uv", "run", "alembic", "merge", "-m", "auto_merge"] + heads
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Created merge migration")
        return 0
    else:
        print(f"❌ Failed: {result.stderr}")
        return 1

if __name__ == "__main__":
    sys.exit(create_merge_migration())
```

### Example 3: Safe Migration Creation

```python
# backend/omoi_os/services/migration_helper.py
from pathlib import Path
import subprocess
from typing import Optional

class MigrationHelper:
    """Helper for safe migration creation."""
    
    def __init__(self, migrations_dir: str = "backend/migrations/versions"):
        self.migrations_dir = Path(migrations_dir)
    
    def ensure_linear_history(self) -> bool:
        """Check that migration history is linear."""
        result = subprocess.run(
            ["uv", "run", "alembic", "heads"],
            capture_output=True,
            text=True,
        )
        heads = [h for h in result.stdout.strip().split("\n") if h]
        return len(heads) == 1
    
    def create_migration(
        self,
        message: str,
        autogenerate: bool = False,
    ) -> Optional[Path]:
        """Create migration with safety checks."""
        # 1. Check for linear history
        if not self.ensure_linear_history():
            raise RuntimeError(
                "Multiple migration heads detected. "
                "Resolve conflicts before creating new migration."
            )
        
        # 2. Create migration
        cmd = ["uv", "run", "alembic", "revision", "-m", message]
        if autogenerate:
            cmd.append("--autogenerate")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise RuntimeError(f"Migration creation failed: {result.stderr}")
        
        # 3. Extract filename from output
        # Output: "Generating /path/to/migrations/versions/003_xxx.py ... done"
        import re
        match = re.search(r'Generating (.+?) \.\.\. done', result.stdout)
        if match:
            return Path(match.group(1))
        
        return None
```

---

## Troubleshooting

### Issue: "Multiple heads found"

**Error**:
```
CommandError: Multiple heads found
```

**Solution**:
```bash
# See all heads
uv run alembic heads

# Option 1: Merge them
uv run alembic merge -m "merge_heads" head1 head2

# Option 2: Linearize (if one should depend on other)
# Edit the later migration's down_revision
```

### Issue: "Revision ID already exists"

**Error**:
```
CommandError: Revision ID '003_duplicate' already exists
```

**Solution**:
```bash
# Find duplicate revisions
grep -r "revision = '003_duplicate'" backend/migrations/versions/

# Rename one file and its revision
mv 003_duplicate.py 004_duplicate.py
# Edit file: change revision = "003_duplicate" to "004_duplicate"
# Edit file: change down_revision to point to 003_other
```

### Issue: "Can't locate revision"

**Error**:
```
CommandError: Can't locate revision identified by '003_missing'
```

**Solution**:
```bash
# Database is ahead of migrations or migration file deleted

# Option 1: If migration was deleted but applied
uv run alembic stamp 002_previous  # Mark DB at previous revision

# Option 2: If database is wrong
uv run alembic downgrade 002_previous  # Rollback
```

### Issue: Migration works locally but fails in CI

**Causes**:
1. Different Alembic versions
2. Missing migration files in git
3. Database state differences

**Solution**:
```bash
# In CI, always test on fresh database
uv run alembic downgrade base
uv run alembic upgrade head

# Verify all files committed
git ls-files backend/migrations/versions/

# Check Alembic version
uv run alembic --version
```

---

## Related Files

| File | Purpose |
|------|---------|
| `backend/alembic.ini` | Alembic configuration |
| `backend/migrations/env.py` | Migration environment setup |
| `backend/migrations/script.py.mako` | Migration template |
| `backend/omoi_os/models/base.py` | SQLAlchemy base model |
| `backend/omoi_os/services/database.py` | Database service |

### Key Configuration

From `backend/alembic.ini`:
```ini
[alembic]
script_location = migrations
prepend_sys_path = .
version_path_separator = os

# Logging
[loggers]
keys = root,sqlalchemy,alembic
```

---

## Recommended Action

**Use Option 1 (Linear Chain)** for simplicity since:
1. Agent registry changes are orthogonal to phase workflow
2. No conflicting table/column modifications
3. Linear history is easier to reason about

### Steps:

1. Update `003_phase_workflow.py` line 17:
   ```python
   down_revision: Union[str, None] = "003_agent_registry"
   ```

2. Verify migration chain:
   ```bash
   uv run alembic history
   ```

3. Test on fresh database:
   ```bash
   uv run alembic upgrade head
   ```

---

## Current Workaround

Tests pass because the test database is dropped/recreated each run, so Alembic never sees the conflict. However, production deployments or incremental migrations will fail.

**Status**: Safe for testing, **unsafe for production** until resolved.

---

<claude-mem-context>
# Recent Activity

<!-- This section is auto-generated by claude-mem. Edit content outside the tags. -->

*No recent activity*
</claude-mem-context>
