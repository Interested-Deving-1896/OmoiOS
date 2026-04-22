# Sandbox Lifecycle Errors Troubleshooting Guide

**Status**: Active | **Last Updated**: 2025-04-22 | **Applies To**: OmoiOS v1.0+

**Source Files**:
- `backend/omoi_os/workers/orchestrator_worker.py` - Orchestrator loop and sandbox spawning
- `backend/omoi_os/services/sandbox_provider.py` - Sandbox provider protocol
- `backend/omoi_os/services/sandbox_factory.py` - Sandbox creation factory
- `backend/omoi_os/workers/sandbox_agent_worker.py` - Agent execution in sandboxes

**Related Documentation**:
- [Architecture: Execution System](../architecture/02-execution-system.md)
- [Sandbox Provisioning](sandbox-provisioning.md)
- [User Journey: Sandbox Troubleshooting](../user_journey/18_sandbox_troubleshooting.md)

---

## Overview

OmoiOS uses Daytona sandboxes for isolated agent execution. The sandbox lifecycle includes creation, setup, execution, and cleanup phases. Errors can occur at any stage, from API failures during creation to resource exhaustion and cleanup failures.

### Sandbox Lifecycle Flow

```
Orchestrator Loop → Spawn Decision → Daytona API Call → Sandbox Creating
       ↓                    ↓              ↓
   Task Found        Build Context    Wait for Ready
       ↓                    ↓              ↓
Assign Sandbox    Spawn Sandbox    Agent Execution
       ↓                    ↓              ↓
Update DB         Monitor Status   Cleanup/Terminate
```

---

## Common Errors Table

| Error Message | Cause | Fix |
|--------------|-------|-----|
| `sandbox_spawn_failed` with `daytona_spawner_failed` | Daytona API unavailable or misconfigured | Check `DAYTONA_API_KEY` and API endpoint |
| `task_sandbox_id_conflict` | Race condition - task already has different sandbox | Check for duplicate orchestrator instances |
| `validation_sandbox_spawn_failed` | Validation sandbox creation failed | Check concurrency limits and resource quotas |
| `daytona_spawner_failed` with connection error | Network timeout or Daytona service down | Verify network connectivity and service status |
| `task_already_has_sandbox` | Task found in pending queue but already has sandbox_id | Clear stale task state or check for stuck tasks |
| `no_github_token_in_user_attributes` | Missing GitHub token for repo operations | Configure GitHub OAuth or add token to user attributes |
| `project_missing_github_info` | Project missing `github_owner` or `github_repo` | Update project settings with repository info |
| `user_not_found_for_token` | User ID for token retrieval not found | Verify user exists and has proper authentication |
| `stale_tasks_cleaned` | Tasks stuck in 'assigned' status for too long | Adjust `STALE_TASK_THRESHOLD_MINUTES` or check worker health |
| `idle_sandboxes_terminated` | Sandboxes terminated due to inactivity | Adjust `IDLE_THRESHOLD_MINUTES` or check agent activity |

---

## Diagnostic Commands

### Check Daytona Configuration

```bash
# Verify Daytona API key is set
grep "DAYTONA_API_KEY" backend/.env

# Check sandbox execution mode
grep "SANDBOX_EXECUTION" backend/.env

# Verify orchestrator settings
grep "ORCHESTRATOR" backend/.env
```

### Monitor Sandbox Status

```bash
# Check orchestrator logs for spawn errors
tail -f backend/logs/worker.log | grep -E "sandbox_spawn|daytona|spawner"

# Check for stale tasks
cd backend && uv run python -c "
from omoi_os.config import get_app_settings
from omoi_os.services.database import DatabaseService
from omoi_os.models.task import Task

settings = get_app_settings()
db = DatabaseService(connection_string=settings.database.url)

with db.get_session() as session:
    stale = session.query(Task).filter(
        Task.status.in_(['assigned', 'claiming'])
    ).all()
    print(f'Stale tasks: {len(stale)}')
    for t in stale:
        print(f'  {t.id}: {t.status}, sandbox={t.sandbox_id}')
"

# Check active sandboxes
tail -f backend/logs/worker.log | grep "sandbox_spawned_successfully"
```

### Check Resource Limits

```bash
# View current task queue status
cd backend && uv run python -c "
from omoi_os.services.task_queue import get_task_queue
tq = get_task_queue()
stats = tq.get_queue_stats()
print(f'Pending: {stats.get(\"pending\", 0)}')
print(f'Running: {stats.get(\"running\", 0)}')
print(f'Assigned: {stats.get(\"assigned\", 0)}')
"

# Check concurrency configuration
echo "MAX_CONCURRENT_TASKS_PER_PROJECT: ${MAX_CONCURRENT_TASKS_PER_PROJECT:-5}"
```

---

## Symptom 1: Sandbox Spawn Failures

**Error Message**: `sandbox_spawn_failed` with `error="Daytona API error: ..."`

**Root Cause**: The Daytona spawner cannot create sandboxes due to API errors, authentication issues, or resource limits.

### Diagnostic Steps

1. **Check Daytona Spawner Initialization**:
   ```python
   # In orchestrator_worker.py, check if spawner initialized
   logger.info("daytona_spawner_initialized", mode=mode)
   # If you see "daytona_spawner_failed", check the error
   ```

2. **Verify API Credentials**:
   ```bash
   # Check if DAYTONA_API_KEY is set
   python -c "import os; print('Key set:', bool(os.getenv('DAYTONA_API_KEY')))"
   ```

3. **Check Spawn Parameters**:
   ```python
   # Review spawn kwargs in _spawn_and_update()
   spawn_kwargs = {
       "task_id": ctx.task_id,
       "agent_id": agent_id,
       "phase_id": ctx.phase_id,
       "agent_type": ctx.agent_type,
       "extra_env": ctx.extra_env,
       "runtime": sandbox_runtime,  # Check this value
       "execution_mode": ctx.execution_mode,
   }
   ```

### Fix Procedure

1. **Verify Daytona API Access**:
   ```bash
   # Test Daytona API connectivity
   curl -H "Authorization: Bearer $DAYTONA_API_KEY" \
        https://api.daytona.io/v1/workspaces
   ```

2. **Check Environment Configuration**:
   ```yaml
   # backend/config/base.yaml
   daytona:
     api_key: ${DAYTONA_API_KEY}
     api_endpoint: https://api.daytona.io/v1
     sandbox_execution: true
   ```

3. **Enable Dry-Run Mode for Testing**:
   ```bash
   # Set dry-run to test without actual spawning
   export ORCHESTRATOR_DRY_RUN=true
   # Check logs for spawn decisions without actual creation
   ```

4. **Fallback to Legacy Mode**:
   ```python
   # If Daytona fails, system falls back to legacy mode
   logger.warning("falling_back_to_legacy_mode")
   # Set SANDBOX_EXECUTION=false to use legacy agent assignment
   ```

---

## Symptom 2: Sandbox ID Conflicts

**Error Message**: `task_sandbox_id_conflict` with `reason="Task already has a different sandbox_id"`

**Root Cause**: Race condition where a task is assigned to multiple sandboxes, or stale state from a previous run.

### Diagnostic Steps

1. **Check Task State**:
   ```python
   # Query task status and sandbox assignment
   with db.get_session() as session:
       task = session.get(Task, task_id)
       print(f"Task {task_id}:")
       print(f"  Status: {task.status}")
       print(f"  Sandbox ID: {task.sandbox_id}")
       print(f"  Assigned Agent: {task.assigned_agent_id}")
   ```

2. **Review Orchestrator Logs**:
   ```bash
   # Look for duplicate spawn attempts
   grep "task_already_has_sandbox" backend/logs/worker.log
   ```

3. **Check for Multiple Orchestrator Instances**:
   ```bash
   # Ensure only one orchestrator is running
   ps aux | grep orchestrator_worker
   ```

### Fix Procedure

1. **Clear Stale Sandbox References**:
   ```python
   # Reset task for re-spawning
   with db.get_session() as session:
       task = session.get(Task, task_id)
       if task.status == "pending":
           task.sandbox_id = None
           task.assigned_agent_id = None
           session.commit()
   ```

2. **Enable Stale Task Cleanup**:
   ```bash
   # Set environment variables for automatic cleanup
   export STALE_TASK_CLEANUP_ENABLED=true
   export STALE_TASK_THRESHOLD_MINUTES=3
   export STALE_CLAIMING_THRESHOLD_SECONDS=60
   ```

3. **Manual Task Reset**:
   ```bash
   # Force reset a stuck task
   cd backend && uv run python -c "
   from omoi_os.services.task_queue import get_task_queue
   tq = get_task_queue()
   tq.update_task_status('task-id-here', 'pending', error_message=None)
   tq.reset_task_sandbox('task-id-here')
   "
   ```

---

## Symptom 3: Timeout During Sandbox Setup

**Error Message**: `stale_tasks_cleaned` with tasks stuck in `assigned` status

**Root Cause**: Sandbox creation takes too long or agent never starts, leaving tasks in limbo.

### Diagnostic Steps

1. **Check Stale Task Thresholds**:
   ```bash
   # Current thresholds
   echo "STALE_TASK_THRESHOLD_MINUTES: ${STALE_TASK_THRESHOLD_MINUTES:-3}"
   echo "STALE_CLAIMING_THRESHOLD_SECONDS: ${STALE_CLAIMING_THRESHOLD_SECONDS:-60}"
   ```

2. **Review Stale Task Cleanup Logs**:
   ```bash
   # Monitor cleanup activity
   tail -f backend/logs/worker.log | grep -E "stale_tasks_cleaned|stale_claiming_tasks_reset"
   ```

3. **Check Sandbox Status**:
   ```python
   # If you have the sandbox_id, check its status
   from omoi_os.services.daytona_spawner import get_daytona_spawner
   spawner = get_daytona_spawner()
   status = await spawner.get_status(sandbox_id)
   print(f"Sandbox status: {status.status}")
   print(f"Error: {status.error}")
   ```

### Fix Procedure

1. **Adjust Timeout Thresholds**:
   ```bash
   # Increase thresholds for slower environments
   export STALE_TASK_THRESHOLD_MINUTES=10
   export STALE_CLAIMING_THRESHOLD_SECONDS=120
   ```

2. **Manual Cleanup**:
   ```python
   # Clean up specific stuck tasks
   from omoi_os.services.task_queue import get_task_queue
   tq = get_task_queue()
   
   # Clean stale claiming tasks
   cleaned = tq.cleanup_stale_claiming_tasks(stale_threshold_seconds=60)
   print(f"Reset {len(cleaned)} claiming tasks")
   
   # Clean stale assigned tasks
   cleaned = tq.cleanup_stale_assigned_tasks(stale_threshold_minutes=5)
   print(f"Marked {len(cleaned)} assigned tasks as failed")
   ```

3. **Verify Worker Health**:
   ```bash
   # Check if sandbox_agent_worker is running
   ps aux | grep sandbox_agent_worker
   
   # Check worker logs
   tail -f backend/logs/sandbox_worker.log
   ```

---

## Symptom 4: Sandbox Not Cleaning Up

**Error Message**: `idle_sandboxes_terminated` or sandboxes accumulating without termination

**Root Cause**: Idle detection not working or cleanup logic failing.

### Diagnostic Steps

1. **Check Idle Detection Configuration**:
   ```bash
   # Verify idle detection is enabled
   echo "IDLE_DETECTION_ENABLED: ${IDLE_DETECTION_ENABLED:-true}"
   echo "IDLE_THRESHOLD_MINUTES: ${IDLE_THRESHOLD_MINUTES:-10}"
   echo "IDLE_CHECK_INTERVAL_SECONDS: ${IDLE_CHECK_INTERVAL_SECONDS:-30}"
   ```

2. **Monitor Idle Sandbox Cleanup**:
   ```bash
   # Watch for idle sandbox termination
   tail -f backend/logs/worker.log | grep -E "idle_sandboxes_terminated|idle_monitor_initialized"
   ```

3. **Check Sandbox Activity**:
   ```python
   # List active sandboxes and their last activity
   from omoi_os.services.daytona_spawner import get_daytona_spawner
   spawner = get_daytona_spawner()
   active = await spawner.list_active()
   for sb in active:
       print(f"{sb.sandbox_id}: {sb.status}, started: {sb.started_at}")
   ```

### Fix Procedure

1. **Enable/Configure Idle Detection**:
   ```bash
   # Ensure idle detection is enabled
   export IDLE_DETECTION_ENABLED=true
   export IDLE_THRESHOLD_MINUTES=10
   export IDLE_CHECK_INTERVAL_SECONDS=30
   ```

2. **Manual Sandbox Termination**:
   ```python
   # Force terminate a specific sandbox
   from omoi_os.services.daytona_spawner import get_daytona_spawner
   spawner = get_daytona_spawner()
   await spawner.terminate_sandbox(sandbox_id)
   ```

3. **Bulk Cleanup**:
   ```bash
   # Terminate all idle sandboxes
   cd backend && uv run python -c "
   from omoi_os.services.daytona_spawner import get_daytona_spawner
   from omoi_os.services.database import get_db_service
   import asyncio
   
   async def cleanup():
       db = get_db_service()
       spawner = get_daytona_spawner(db=db)
       active = await spawner.list_active()
       for sb in active:
           if sb.status == 'idle':
               await spawner.terminate_sandbox(sb.sandbox_id)
               print(f'Terminated: {sb.sandbox_id}')
   
   asyncio.run(cleanup())
   "
   ```

---

## Symptom 5: Resource Exhaustion

**Error Message**: `429 Too Many Requests` from Daytona API or `max_concurrent_per_project` reached

**Root Cause**: Too many sandboxes running concurrently, hitting API rate limits or resource quotas.

### Diagnostic Steps

1. **Check Current Concurrency**:
   ```bash
   # View current sandbox count
   cd backend && uv run python -c "
   from omoi_os.services.daytona_spawner import get_daytona_spawner
   from omoi_os.services.database import get_db_service
   import asyncio
   
   async def count():
       db = get_db_service()
       spawner = get_daytona_spawner(db=db)
       active = await spawner.list_active()
       print(f'Active sandboxes: {len(active)}')
   
   asyncio.run(count())
   "
   ```

2. **Review Concurrency Limits**:
   ```bash
   # Check configured limits
   echo "MAX_CONCURRENT_TASKS_PER_PROJECT: ${MAX_CONCURRENT_TASKS_PER_PROJECT:-5}"
   ```

3. **Monitor Queue Depth**:
   ```bash
   # Check if tasks are backing up
   tail -f backend/logs/worker.log | grep "no_pending_tasks\|task_found"
   ```

### Fix Procedure

1. **Reduce Concurrency Limits**:
   ```bash
   # Lower concurrent tasks per project
   export MAX_CONCURRENT_TASKS_PER_PROJECT=3
   ```

2. **Implement Backpressure**:
   ```python
   # The orchestrator already implements concurrency limits
   # Check get_next_task_with_concurrency_limit() in task_queue
   task = queue.get_next_task_with_concurrency_limit(
       max_concurrent_per_project=max_concurrent_per_project,
       phase_id=None,
   )
   ```

3. **Scale Infrastructure**:
   - Contact Daytona support to increase rate limits
   - Consider upgrading to higher tier plan
   - Implement request throttling in spawner

---

## Symptom 6: GitHub Token Missing for Sandbox

**Error Message**: `no_github_token_in_user_attributes` or `project_missing_github_info`

**Root Cause**: Sandbox needs GitHub token to clone repos, but user or project lacks configuration.

### Diagnostic Steps

1. **Check User Attributes**:
   ```python
   # Verify user has GitHub token
   with db.get_session() as session:
       user = session.get(User, user_id)
       attrs = user.attributes or {}
       has_token = bool(attrs.get("github_access_token"))
       print(f"User {user_id} has GitHub token: {has_token}")
       print(f"Available attrs: {list(attrs.keys())}")
   ```

2. **Check Project Configuration**:
   ```python
   # Verify project has GitHub info
   with db.get_session() as session:
       project = session.get(Project, project_id)
       print(f"GitHub owner: {project.github_owner}")
       print(f"GitHub repo: {project.github_repo}")
       print(f"GitHub connected: {project.github_connected}")
   ```

3. **Review Token Extraction Logs**:
   ```bash
   # Check for token extraction warnings
   grep -E "no_github_token|project_missing_github|user_not_found_for_token" backend/logs/worker.log
   ```

### Fix Procedure

1. **Configure GitHub OAuth**:
   ```bash
   # Ensure GitHub OAuth is configured
   export GITHUB_CLIENT_ID=your_client_id
   export GITHUB_CLIENT_SECRET=your_client_secret
   ```

2. **Manual Token Addition**:
   ```python
   # Add token to user attributes
   with db.get_session() as session:
       user = session.get(User, user_id)
       if not user.attributes:
           user.attributes = {}
       user.attributes["github_access_token"] = "ghp_xxxxxxxx"
       session.commit()
   ```

3. **Update Project Settings**:
   ```python
   # Connect project to GitHub repo
   with db.get_session() as session:
       project = session.get(Project, project_id)
       project.github_owner = "owner-name"
       project.github_repo = "repo-name"
       project.github_connected = True
       session.commit()
   ```

---

## Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DAYTONA_API_KEY` | Yes (for sandbox mode) | None | Daytona API authentication |
| `SANDBOX_EXECUTION` | No | `true` | Enable Daytona sandbox mode |
| `SANDBOX_RUNTIME` | No | `claude` | Default runtime for sandboxes |
| `ORCHESTRATOR_ENABLED` | No | `true` | Enable orchestrator worker |
| `ORCHESTRATOR_DRY_RUN` | No | `false` | Test mode without actual spawning |
| `MAX_CONCURRENT_TASKS_PER_PROJECT` | No | `5` | Max parallel sandboxes per project |
| `STALE_TASK_CLEANUP_ENABLED` | No | `true` | Enable stale task detection |
| `STALE_TASK_THRESHOLD_MINUTES` | No | `3` | Minutes before task considered stale |
| `STALE_CLAIMING_THRESHOLD_SECONDS` | No | `60` | Seconds before claiming task reset |
| `IDLE_DETECTION_ENABLED` | No | `true` | Enable idle sandbox detection |
| `IDLE_THRESHOLD_MINUTES` | No | `10` | Minutes of inactivity before termination |
| `IDLE_CHECK_INTERVAL_SECONDS` | No | `30` | Seconds between idle checks |

### Sandbox States

| State | Description | Action |
|-------|-------------|--------|
| `creating` | Sandbox is being provisioned | Wait for transition to running |
| `running` | Sandbox is active and executing | Normal operation |
| `completed` | Task finished successfully | Cleanup scheduled |
| `failed` | Sandbox or task failed | Review logs, may retry |
| `terminated` | Sandbox was stopped | Normal end of lifecycle |
| `idle` | No activity detected | Will be auto-terminated |

---

## Step-by-Step Recovery Procedures

### Procedure 1: Reset Stuck Sandbox

1. **Identify the stuck task**:
   ```bash
   cd backend && uv run python -c "
   from omoi_os.services.database import get_db_service
   from omoi_os.models.task import Task
   
   db = get_db_service()
   with db.get_session() as session:
       tasks = session.query(Task).filter(
           Task.status.in_(['assigned', 'claiming'])
       ).all()
       for t in tasks:
           print(f'{t.id}: {t.status}, sandbox={t.sandbox_id}')
   "
   ```

2. **Reset the task**:
   ```python
   from omoi_os.services.task_queue import get_task_queue
   tq = get_task_queue()
   
   # Reset to pending
   tq.update_task_status(task_id, 'pending')
   # Clear sandbox reference
   tq.reset_task_sandbox(task_id)
   ```

3. **Terminate orphaned sandbox** (if exists):
   ```python
   from omoi_os.services.daytona_spawner import get_daytona_spawner
   spawner = get_daytona_spawner()
   await spawner.terminate_sandbox(sandbox_id)
   ```

### Procedure 2: Full Sandbox Cleanup

1. **List all active sandboxes**:
   ```bash
   cd backend && uv run python -c "
   import asyncio
   from omoi_os.services.daytona_spawner import get_daytona_spawner
   from omoi_os.services.database import get_db_service
   
   async def list_all():
       db = get_db_service()
       spawner = get_daytona_spawner(db=db)
       active = await spawner.list_active()
       for sb in active:
           print(f'{sb.sandbox_id}: {sb.status}')
   
   asyncio.run(list_all())
   "
   ```

2. **Terminate all sandboxes**:
   ```python
   for sb in active:
       await spawner.terminate_sandbox(sb.sandbox_id)
   ```

3. **Reset all stuck tasks**:
   ```python
   with db.get_session() as session:
       stuck = session.query(Task).filter(
           Task.status.in_(['assigned', 'claiming', 'running'])
       ).all()
       for task in stuck:
           task.status = 'pending'
           task.sandbox_id = None
           task.assigned_agent_id = None
       session.commit()
   ```

---

## Prevention Strategies

1. **Monitor Orchestrator Health**:
   - Watch for `heartbeat` logs every 30 seconds
   - Alert on missing heartbeats
   - Monitor `tasks_failed` counter

2. **Set Appropriate Timeouts**:
   - Adjust `STALE_TASK_THRESHOLD_MINUTES` based on average task duration
   - Set `IDLE_THRESHOLD_MINUTES` based on expected agent think time

3. **Resource Limits**:
   - Keep `MAX_CONCURRENT_TASKS_PER_PROJECT` reasonable (3-5)
   - Monitor Daytona API rate limits
   - Implement exponential backoff for retries

4. **GitHub Token Management**:
   - Validate tokens before spawning
   - Implement token refresh for long-running tasks
   - Alert on missing tokens early

---

## Troubleshooting Flowchart

```
Sandbox spawn failed?
├── Check DAYTONA_API_KEY → Must be valid and set
├── Check SANDBOX_EXECUTION → Should be "true"
├── Check network connectivity → Can reach Daytona API
└── Check rate limits → May need to wait or increase quota

Task stuck in assigned?
├── Check STALE_TASK_CLEANUP_ENABLED → Should be "true"
├── Check worker logs → Look for agent.started events
├── Verify sandbox status → May need manual termination
└── Reset task to pending → Clear sandbox_id and retry

Sandbox not cleaning up?
├── Check IDLE_DETECTION_ENABLED → Should be "true"
├── Check IDLE_THRESHOLD_MINUTES → May be too high
├── Verify idle_monitor_initialized → Check logs
└── Manual cleanup → Terminate sandboxes and reset tasks

GitHub clone failing in sandbox?
├── Check user attributes → Must have github_access_token
├── Check project settings → Must have github_owner/repo
├── Verify token permissions → Needs repo access
└── Check token expiration → May need refresh
```

---

## Common Diagnostic Commands

```bash
# Check orchestrator heartbeat
tail -f backend/logs/worker.log | grep "heartbeat"

# Monitor sandbox spawn events
tail -f backend/logs/worker.log | grep -E "sandbox_spawn|spawning_sandbox"

# Check for errors
tail -f backend/logs/worker.log | grep -E "ERROR|error|failed"

# View stale task cleanup
tail -f backend/logs/worker.log | grep -E "stale_tasks|stale_claiming"

# Check idle sandbox monitoring
tail -f backend/logs/worker.log | grep -E "idle_sandbox|idle_monitor"

# Test Daytona connectivity
curl -H "Authorization: Bearer $DAYTONA_API_KEY" \
     https://api.daytona.io/v1/workspaces
```

---

*End of Sandbox Lifecycle Errors Troubleshooting Guide*

*This guide covers Daytona sandbox creation, monitoring, cleanup, and resource management in OmoiOS.*
