# Sandbox Agent Timeouts Troubleshooting Guide

**Last Updated**: 2026-04-22  
**Applies To**: OmoiOS Orchestrator Worker v1.0+  
**Related Services**: `OrchestratorWorker`, `DaytonaSpawner`, `TaskQueueService`

---

## Overview

This guide covers troubleshooting for sandbox agent timeouts, stale task detection, and orchestrator loop failures in OmoiOS. The orchestrator worker manages the lifecycle of agent sandboxes, task assignment, and cleanup. Failures can occur during sandbox spawning, task execution, heartbeat monitoring, or idle sandbox detection.

---

## Common Error Scenarios

### 1. Sandbox Spawn Timeout

**Error Message**:
```
sandbox_spawn_failed: Daytona API timeout
Error spawning sandbox: Connection timeout after 30s
orchestrator_loop_error: Sandbox spawn failed
```

**Root Causes**:
- Daytona API rate limiting
- Network connectivity issues to Daytona
- Docker image pull taking too long
- Resource quota exceeded (max concurrent sandboxes)
- Invalid Daytona API key

**Diagnosis Steps**:

1. Check Daytona configuration:
```python
from omoi_os.config import get_app_settings

settings = get_app_settings()
print(f"Sandbox execution enabled: {settings.daytona.sandbox_execution}")
print(f"Daytona API key configured: {bool(settings.daytona.api_key)}")
print(f"Daytona target: {settings.daytona.target}")
```

2. Verify Daytona spawner initialization:
```python
from omoi_os.services.daytona_spawner import get_daytona_spawner
from omoi_os.services.database import DatabaseService
from omoi_os.services.event_bus import EventBusService

db = DatabaseService(connection_string=settings.database.url)
event_bus = EventBusService(redis_url=settings.redis.url)

try:
    spawner = get_daytona_spawner(db=db, event_bus=event_bus)
    print("Daytona spawner initialized successfully")
except Exception as e:
    print(f"Daytona spawner failed: {e}")
```

3. Check orchestrator mode:
```python
import os

sandbox_execution = settings.daytona.sandbox_execution
dry_run = settings.orchestrator.dry_run or os.getenv("ORCHESTRATOR_DRY_RUN", "").lower() in ("true", "1", "yes")
mode = "dry_run" if dry_run else ("sandbox" if sandbox_execution else "legacy")
print(f"Orchestrator mode: {mode}")
```

4. Verify concurrency limits:
```python
import os

max_concurrent = int(os.getenv("MAX_CONCURRENT_TASKS_PER_PROJECT", "5"))
print(f"Max concurrent tasks per project: {max_concurrent}")

# Check current active sandboxes
from omoi_os.models.task import Task
from sqlalchemy import select, func

result = session.execute(
    select(func.count()).select_from(Task).where(
        Task.status.in_(["assigned", "running"]),
        Task.sandbox_id.isnot(None)
    )
)
active_count = result.scalar()
print(f"Active sandboxes: {active_count}")
```

**Fix**:
```python
# In backend/.env or .env.local
DAYTONA_API_KEY=your-daytona-api-key
DAYTONA_TARGET=us
DAYTONA_SANDBOX_EXECUTION=true

# Increase timeout for slow networks
DAYTONA_SPAWN_TIMEOUT_SECONDS=60

# Adjust concurrency if hitting limits
MAX_CONCURRENT_TASKS_PER_PROJECT=3
```

Handle spawn failures gracefully:
```python
async def spawn_with_retry(task, max_retries=3):
    for attempt in range(max_retries):
        try:
            sandbox_id = await daytona_spawner.spawn_for_task(
                task_id=task.id,
                agent_id=agent_id,
                phase_id=task.phase_id,
                agent_type="worker",
                extra_env=env_vars,
                runtime="claude"
            )
            return sandbox_id
        except TimeoutError:
            logger.warning(f"Spawn attempt {attempt + 1} timed out")
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
    
    # All retries failed
    queue.update_task_status(
        task.id,
        "failed",
        error_message="Sandbox spawn failed after retries"
    )
    raise RuntimeError("Failed to spawn sandbox")
```

---

### 2. Stale Task Detection and Cleanup

**Error Message**:
```
stale_tasks_cleaned: count=5, task_ids=['abc123', 'def456']
task_sandbox_id_conflict: existing_sandbox_id=sb_..., new_sandbox_id=sb_...
Task stuck in 'assigned' status for > 3 minutes
```

**Root Causes**:
- Agent crashed after claiming task but before sending heartbeat
- Sandbox terminated unexpectedly
- Network partition between agent and orchestrator
- Task claimed but sandbox spawn failed silently
- Database inconsistency (task status vs reality)

**Diagnosis Steps**:

1. Check stale task configuration:
```python
import os

stale_cleanup_enabled = os.getenv("STALE_TASK_CLEANUP_ENABLED", "true").lower() in ("true", "1", "yes")
stale_threshold_minutes = int(os.getenv("STALE_TASK_THRESHOLD_MINUTES", "3"))
stale_claiming_threshold_seconds = int(os.getenv("STALE_CLAIMING_THRESHOLD_SECONDS", "60"))
check_interval = int(os.getenv("STALE_TASK_CHECK_INTERVAL_SECONDS", "15"))

print(f"Stale cleanup enabled: {stale_cleanup_enabled}")
print(f"Stale threshold: {stale_threshold_minutes} minutes")
print(f"Claiming threshold: {stale_claiming_threshold_seconds} seconds")
print(f"Check interval: {check_interval} seconds")
```

2. Find stuck tasks:
```python
from omoi_os.models.task import Task
from omoi_os.utils.datetime import utc_now
from datetime import timedelta
from sqlalchemy import select

stale_threshold = utc_now() - timedelta(minutes=3)

result = session.execute(
    select(Task).where(
        Task.status.in_(["assigned", "claiming"]),
        Task.updated_at < stale_threshold
    )
)
stale_tasks = result.scalars().all()

for task in stale_tasks:
    print(f"Task {task.id}: status={task.status}, updated_at={task.updated_at}")
    print(f"  sandbox_id={task.sandbox_id}, agent_id={task.assigned_agent_id}")
```

3. Check task event history:
```python
# Review Redis events for task
from omoi_os.services.event_bus import EventBusService

event_bus = EventBusService(redis_url=settings.redis.url)
# Events to look for:
# - TASK_ASSIGNED
# - SANDBOX_SPAWNED
# - agent.started (from sandbox)
# - agent.heartbeat
```

**Fix**:
```python
# Manual cleanup of stuck tasks
from omoi_os.services.task_queue import TaskQueueService

queue = TaskQueueService(db, event_bus=event_bus)

# Reset claiming tasks (quick fix)
claiming_cleaned = queue.cleanup_stale_claiming_tasks(
    stale_threshold_seconds=60
)
print(f"Reset {len(claiming_cleaned)} claiming tasks to pending")

# Mark assigned tasks as failed
assigned_cleaned = queue.cleanup_stale_assigned_tasks(
    stale_threshold_minutes=3,
    dry_run=False
)
print(f"Marked {len(assigned_cleaned)} assigned tasks as failed")

# For each cleaned task, clear sandbox_id
for task_info in assigned_cleaned:
    task = session.get(Task, task_info["task_id"])
    if task:
        task.sandbox_id = None
        task.assigned_agent_id = None
        session.commit()
```

---

### 3. Idle Sandbox Detection

**Error Message**:
```
idle_sandboxes_terminated: count=2, sandbox_ids=['sb_...', 'sb_...']
idle_sandbox_check_error: database connection lost
Sandbox has no work events for > 10 minutes
```

**Root Causes**:
- Agent finished work but didn't terminate properly
- Agent stuck in infinite loop
- Heartbeat working but no progress events
- Task completed but sandbox not cleaned up
- Idle detection threshold too aggressive

**Diagnosis Steps**:

1. Check idle detection configuration:
```python
import os

idle_detection_enabled = os.getenv("IDLE_DETECTION_ENABLED", "true").lower() in ("true", "1", "yes")
idle_threshold_minutes = int(os.getenv("IDLE_THRESHOLD_MINUTES", "10"))
check_interval = int(os.getenv("IDLE_CHECK_INTERVAL_SECONDS", "30"))

print(f"Idle detection enabled: {idle_detection_enabled}")
print(f"Idle threshold: {idle_threshold_minutes} minutes")
print(f"Check interval: {check_interval} seconds")
```

2. Monitor sandbox activity:
```python
from omoi_os.services.idle_sandbox_monitor import IdleSandboxMonitor
from omoi_os.services.daytona_spawner import get_daytona_spawner

daytona_spawner = get_daytona_spawner(db=db, event_bus=event_bus)
idle_monitor = IdleSandboxMonitor(
    db=db,
    daytona_spawner=daytona_spawner,
    event_bus=event_bus,
    idle_threshold=timedelta(minutes=10)
)

# Check for idle sandboxes
terminated = await idle_monitor.check_and_terminate_idle_sandboxes()
print(f"Terminated {len(terminated)} idle sandboxes")
```

3. Review agent heartbeats:
```python
from omoi_os.models.agent import Agent
from sqlalchemy import select

result = session.execute(
    select(Agent).where(
        Agent.status == "RUNNING",
        Agent.last_heartbeat < utc_now() - timedelta(minutes=5)
    )
)
stale_agents = result.scalars().all()

for agent in stale_agents:
    print(f"Agent {agent.id}: last_heartbeat={agent.last_heartbeat}")
    print(f"  health_status={agent.health_status}")
```

**Fix**:
```python
# Adjust idle detection thresholds
# In backend/.env:
IDLE_DETECTION_ENABLED=true
IDLE_THRESHOLD_MINUTES=30  # Increase for long-running tasks
IDLE_CHECK_INTERVAL_SECONDS=60

# Or disable for specific task types
# Modify orchestrator_worker.py idle_sandbox_check_loop()
if task.task_type in ["long_running_analysis", "large_repo_clone"]:
    logger.info(f"Skipping idle check for long-running task {task.id}")
    continue
```

---

### 4. Orchestrator Loop Hang

**Error Message**:
```
orchestrator_loop_error: database connection error
poll_started but no task_found logged
heartbeat stopped at cycle 1234
```

**Root Causes**:
- Database connection pool exhausted
- Redis connection lost
- Blocking I/O in async loop
- Signal handling issues
- Memory leak causing slowdown

**Diagnosis Steps**:

1. Check orchestrator stats:
```python
# Global stats dict in orchestrator_worker.py
stats = {
    "poll_count": 0,
    "tasks_processed": 0,
    "tasks_failed": 0,
    "events_received": 0,
    "start_time": 0.0,
}

# Calculate rates
uptime = time.time() - stats["start_time"]
poll_rate = stats["poll_count"] / uptime if uptime > 0 else 0
print(f"Poll rate: {poll_rate:.2f} polls/second")
print(f"Tasks processed: {stats['tasks_processed']}")
print(f"Tasks failed: {stats['tasks_failed']}")
print(f"Failure rate: {stats['tasks_failed'] / max(stats['tasks_processed'], 1):.2%}")
```

2. Monitor heartbeat:
```python
# Heartbeat logs every 30 seconds
# Look for gaps in heartbeat logs
# Last heartbeat: heartbeat_num=1234, uptime_seconds=36000
# If gap > 60 seconds, orchestrator may be stuck
```

3. Check for blocking operations:
```python
# Enable asyncio debug mode
import asyncio
asyncio.get_event_loop().set_debug(True)

# Look for warnings about slow callbacks
# WARNING: Executing <Task ...> took 10.234 seconds
```

**Fix**:
```python
# Restart orchestrator gracefully
import signal
import asyncio

async def restart_orchestrator():
    # Signal shutdown
    shutdown_event.set()
    
    # Wait for cleanup
    await asyncio.sleep(5)
    
    # Reinitialize services
    await init_services()
    
    # Restart loops
    await asyncio.gather(
        heartbeat_task(),
        orchestrator_loop(),
        idle_sandbox_check_loop(),
        stale_task_cleanup_loop(),
    )

# Or use systemd/docker restart
# systemctl restart omoios-orchestrator
# docker-compose restart orchestrator
```

---

### 5. Task Validation Failed Loop

**Error Message**:
```
TASK_VALIDATION_FAILED: task_id=..., iteration=3
validation_failed_handling: task_id=..., iteration=3, feedback_preview=...
task_reset_for_revision: new_status=pending, iteration=3
```

**Root Causes**:
- Implementation doesn't meet requirements
- Validation criteria too strict
- Infinite loop between implementer and validator
- Task requirements unclear
- Sandbox environment issues causing false failures

**Diagnosis Steps**:

1. Check validation iteration count:
```python
from omoi_os.models.task import Task

task = session.get(Task, task_id)
print(f"Current iteration: {task.validation_iteration}")
print(f"Max iterations: {task.max_validation_iterations}")
print(f"Status: {task.status}")
print(f"Result: {task.result}")  # Contains revision_feedback
```

2. Review validation feedback:
```python
if task.result:
    feedback = task.result.get("revision_feedback", "")
    recommendations = task.result.get("revision_recommendations", [])
    print(f"Feedback: {feedback[:200]}...")
    print(f"Recommendations: {recommendations}")
```

3. Check for infinite loop:
```python
# If iteration > 5, likely stuck in loop
if task.validation_iteration > 5:
    print("WARNING: Task may be stuck in validation loop")
    # Consider manual intervention
```

**Fix**:
```python
# Implement max iteration limit
MAX_VALIDATION_ITERATIONS = 3

async def handle_validation_failed(event_data):
    task_id = event_data.get("entity_id")
    payload = event_data.get("payload", {})
    iteration = payload.get("iteration", 0)
    
    if iteration >= MAX_VALIDATION_ITERATIONS:
        # Mark as failed after max retries
        queue.update_task_status(
            task_id,
            "failed",
            error_message=f"Validation failed after {MAX_VALIDATION_ITERATIONS} attempts"
        )
        return
    
    # Otherwise reset for another attempt
    # ... existing reset logic
```

---

## Prevention

### 1. Health Checks

```python
# Implement health check endpoint
async def health_check():
    checks = {
        "database": await check_database(),
        "redis": await check_redis(),
        "daytona": await check_daytona(),
        "orchestrator_loop": check_orchestrator_running(),
    }
    
    all_healthy = all(checks.values())
    return {
        "status": "healthy" if all_healthy else "unhealthy",
        "checks": checks,
        "stats": stats
    }
```

### 2. Resource Limits

```python
# Set appropriate resource limits
# In docker-compose.yml or k8s manifests:
# memory: 2G
# cpu: 2
# max_concurrent_tasks: 5 per project
```

### 3. Monitoring and Alerting

```python
# Alert on:
# - High task failure rate (> 20%)
# - Stale tasks accumulating
# - Orchestrator heartbeat gaps
# - Daytona spawn failures
# - Idle sandbox accumulation
```

### 4. Graceful Degradation

```python
# If Daytona fails, fall back to legacy mode
if sandbox_execution and daytona_spawner is None:
    logger.warning("falling_back_to_legacy_mode")
    sandbox_execution = False
    mode = "legacy"
```

### 5. Task Timeouts

```python
# Set appropriate timeouts per task type
TASK_TIMEOUTS = {
    "explore_codebase": 300,  # 5 minutes
    "implement_feature": 1800,  # 30 minutes
    "run_tests": 600,  # 10 minutes
    "validate": 300,  # 5 minutes
}
```

---

## Related Documentation

- [Orchestrator Worker](../../backend/omoi_os/workers/orchestrator_worker.py)
- [Daytona Spawner](../../backend/omoi_os/services/daytona_spawner.py)
- [Task Queue Service](../../backend/omoi_os/services/task_queue.py)
- [Architecture - Execution System](../../docs/architecture/02-execution-system.md)
- [Sandbox Provisioning Guide](./sandbox-provisioning.md)

---

## Quick Reference: Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `ORCHESTRATOR_ENABLED` | `true` | Enable/disable orchestrator |
| `ORCHESTRATOR_DRY_RUN` | `false` | Run without spawning sandboxes |
| `MAX_CONCURRENT_TASKS_PER_PROJECT` | `5` | Concurrency limit |
| `STALE_TASK_CLEANUP_ENABLED` | `true` | Enable stale task cleanup |
| `STALE_TASK_THRESHOLD_MINUTES` | `3` | Mark assigned tasks stale after |
| `STALE_CLAIMING_THRESHOLD_SECONDS` | `60` | Reset claiming tasks after |
| `IDLE_DETECTION_ENABLED` | `true` | Enable idle sandbox detection |
| `IDLE_THRESHOLD_MINUTES` | `10` | Terminate idle sandboxes after |
| `DAYTONA_SANDBOX_EXECUTION` | `false` | Enable Daytona sandbox mode |
| `SANDBOX_RUNTIME` | `claude` | Default sandbox runtime |

---

## Quick Reference: Key Functions

| Function | Purpose | Location |
|----------|---------|----------|
| `orchestrator_loop()` | Main orchestration loop | `orchestrator_worker.py:881` |
| `stale_task_cleanup_loop()` | Clean up stuck tasks | `orchestrator_worker.py:1222` |
| `idle_sandbox_check_loop()` | Terminate idle sandboxes | `orchestrator_worker.py:1309` |
| `heartbeat_task()` | Log worker health | `orchestrator_worker.py:740` |
| `_spawn_sandbox_for_task()` | Spawn Daytona sandbox | `orchestrator_worker.py:682` |
| `handle_validation_failed()` | Reset failed validation tasks | `orchestrator_worker.py:781` |
| `cleanup_stale_assigned_tasks()` | Mark stuck tasks failed | `task_queue.py` |
| `cleanup_stale_claiming_tasks()` | Reset claiming tasks | `task_queue.py` |
