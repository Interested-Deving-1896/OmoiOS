# Phase 1 Agent Assignments - Quick Reference

**Status**: Ready for Assignment  
**Timeline**: Week 1-2  
**All streams can start immediately (Week 1)**

---

## Overview

This document provides detailed assignments for Phase 1 of the OmoiOS agent enhancement initiative. Each stream (A-D) represents an independent work track that can execute in parallel. The streams are designed to minimize conflicts while maximizing system capability improvements.

### Phase 1 Goals

1. **Task Dependencies & Blocking** - Enable complex task workflows with dependency graphs
2. **Error Handling & Retries** - Build resilient task execution with exponential backoff
3. **Agent Health & Heartbeat** - Implement comprehensive health monitoring
4. **Task Timeout & Cancellation** - Add execution boundaries and control mechanisms

### Coordination Strategy

All streams share a single database migration file but work on independent code areas:
- **Database**: Sequential migration updates (Agent A creates, others append)
- **Models**: Sequential field additions (dependencies → retry fields → timeout)
- **Services**: Independent method additions (minimal overlap)
- **Tests**: Completely independent test files

---

## 🎯 Agent A: Task Dependencies & Blocking

### Files to Modify
- `omoi_os/models/task.py` - Add `dependencies` field
- `omoi_os/services/task_queue.py` - Add dependency resolution
- `omoi_os/api/routes/tasks.py` - Add dependency endpoints
- `tests/test_task_dependencies.py` - **NEW FILE**

### Database Migration
```python
# Add to migration file (coordinate with other agents)
op.add_column('tasks', sa.Column('dependencies', sa.dialects.postgresql.JSONB, nullable=True))
op.create_index('idx_tasks_dependencies', 'tasks', ['dependencies'], postgresql_using='gin')
```

### Key Methods to Implement
```python
# TaskQueueService
def check_dependencies_complete(self, task_id: str) -> bool:
    """Check if all dependencies are completed"""
    
def get_blocked_tasks(self, task_id: str) -> list[Task]:
    """Get tasks blocked by this task"""
    
def get_next_task(self, phase_id: str) -> Task | None:
    """UPDATED: Filter out tasks with incomplete dependencies"""
    
def detect_circular_dependencies(self, task_id: str) -> list[str]:
    """Detect and return circular dependency chains"""
    
def get_dependency_graph(self, ticket_id: str) -> dict:
    """Return full dependency graph for visualization"""
```

### Dependency Graph Algorithm
```python
def _build_dependency_graph(self, tasks: list[Task]) -> dict:
    """Build adjacency list representation of task dependencies."""
    graph = {str(t.id): [] for t in tasks}
    for task in tasks:
        if task.dependencies:
            for dep_id in task.dependencies:
                graph[str(dep_id)].append(str(task.id))
    return graph

def _detect_cycle_dfs(
    self, 
    node: str, 
    graph: dict, 
    visited: set, 
    rec_stack: set
) -> bool:
    """DFS-based cycle detection."""
    visited.add(node)
    rec_stack.add(node)
    
    for neighbor in graph.get(node, []):
        if neighbor not in visited:
            if self._detect_cycle_dfs(neighbor, graph, visited, rec_stack):
                return True
        elif neighbor in rec_stack:
            return True
    
    rec_stack.remove(node)
    return False
```

### API Endpoints
```python
@router.get("/tasks/{task_id}/dependencies")
async def get_task_dependencies(task_id: str) -> list[TaskResponse]:
    """Get all tasks this task depends on."""

@router.get("/tasks/{task_id}/blocked")
async def get_blocked_tasks(task_id: str) -> list[TaskResponse]:
    """Get all tasks blocked by this task."""

@router.post("/tasks/{task_id}/dependencies")
async def add_dependency(
    task_id: str, 
    dependency_id: str
) -> TaskResponse:
    """Add a dependency to a task."""

@router.delete("/tasks/{task_id}/dependencies/{dependency_id}")
async def remove_dependency(task_id: str, dependency_id: str) -> TaskResponse:
    """Remove a dependency from a task."""

@router.get("/tickets/{ticket_id}/dependency-graph")
async def get_dependency_graph(ticket_id: str) -> DependencyGraphResponse:
    """Get full dependency graph for a ticket."""
```

### Success Criteria
- ✅ Tasks can have dependencies (list of task IDs)
- ✅ `get_next_task()` only returns tasks with completed dependencies
- ✅ Circular dependency detection prevents infinite loops
- ✅ Dependency graph API for visualization
- ✅ Tests pass with 80%+ coverage

---

## 🔄 Agent B: Error Handling & Retries

### Files to Modify
- `omoi_os/models/task.py` - Add `retry_count`, `max_retries` fields
- `omoi_os/worker.py` - Add retry logic
- `omoi_os/services/task_queue.py` - Add retry helper methods
- `tests/test_retry_logic.py` - **NEW FILE**

### Database Migration
```python
# Add to migration file (coordinate with other agents)
op.add_column('tasks', sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'))
op.add_column('tasks', sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'))
op.add_column('tasks', sa.Column('last_error', sa.Text(), nullable=True))
op.add_column('tasks', sa.Column('error_history', sa.dialects.postgresql.JSONB, default=list))
```

### Key Methods to Implement
```python
# TaskQueueService
def should_retry(self, task_id: str) -> bool:
    """Check if task should be retried based on retry_count < max_retries."""
    
def increment_retry(self, task_id: str, error: str) -> None:
    """Increment retry count, store error, reset status to pending."""
    
def get_retry_delay(self, retry_count: int) -> float:
    """Calculate exponential backoff delay with jitter."""
    base_delay = 2 ** retry_count  # 1s, 2s, 4s, 8s
    jitter = random.uniform(0, 0.5 * base_delay)
    return min(base_delay + jitter, 3600)  # Max 1 hour
    
def classify_error(self, error: str) -> ErrorClassification:
    """Classify error as retryable or permanent."""
    retryable_patterns = [
        "timeout", "connection", "503", "429", 
        "rate limit", "temporary"
    ]
    permanent_patterns = [
        "syntax error", "permission denied", "not found",
        "invalid", "unauthorized"
    ]

# Worker
def execute_task_with_retry(self, task: Task) -> None:
    """Execute task with exponential backoff retry logic."""
    
def _handle_task_failure(self, task: Task, error: Exception) -> None:
    """Handle task failure - retry or mark permanent."""
```

### Retry Logic Implementation
```python
async def execute_task_with_retry(self, task: Task) -> TaskResult:
    """Execute task with comprehensive retry logic."""
    max_retries = task.max_retries or 3
    
    for attempt in range(max_retries + 1):
        try:
            result = await self._execute_task(task)
            if result.success:
                return result
            
            # Task executed but returned failure
            if attempt < max_retries:
                delay = self._get_retry_delay(attempt)
                logger.warning(
                    f"Task {task.id} failed, retrying in {delay:.1f}s "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                await asyncio.sleep(delay)
            else:
                logger.error(f"Task {task.id} exhausted all retries")
                result.permanent_failure = True
                return result
                
        except Exception as e:
            error_str = str(e)
            classification = self._classify_error(error_str)
            
            if classification == ErrorClassification.RETRYABLE and attempt < max_retries:
                delay = self._get_retry_delay(attempt)
                logger.warning(
                    f"Task {task.id} error (retryable): {error_str}. "
                    f"Retrying in {delay:.1f}s"
                )
                await self._record_error(task.id, error_str, attempt)
                await asyncio.sleep(delay)
            else:
                logger.error(f"Task {task.id} permanent failure: {error_str}")
                return TaskResult(
                    success=False,
                    error=error_str,
                    permanent_failure=True
                )
    
    return TaskResult(success=False, error="Max retries exceeded")
```

### Error Classification
```python
class ErrorClassification(Enum):
    RETRYABLE = "retryable"      # Network, timeout, rate limit
    PERMANENT = "permanent"      # Syntax, auth, not found
    UNKNOWN = "unknown"          # Requires manual review

RETRYABLE_PATTERNS = [
    r"timeout",
    r"connection.*refused",
    r"503",
    r"502",
    r"429",
    r"rate.*limit",
    r"temporary.*failure",
    r"service.*unavailable",
]

PERMANENT_PATTERNS = [
    r"syntax.*error",
    r"permission.*denied",
    r"not.*found",
    r"invalid.*argument",
    r"unauthorized",
    r"authentication.*failed",
]
```

### Success Criteria
- ✅ Failed tasks automatically retry up to `max_retries`
- ✅ Exponential backoff (1s, 2s, 4s, 8s) with jitter
- ✅ Error classification (retryable vs permanent)
- ✅ Error history stored for debugging
- ✅ Permanent failures marked after max retries
- ✅ Tests pass with 80%+ coverage

---

## 💓 Agent C: Agent Health & Heartbeat

### Files to Modify
- `omoi_os/worker.py` - Add heartbeat emission
- `omoi_os/services/agent_health.py` - **NEW FILE**
- `omoi_os/api/routes/agents.py` - **NEW FILE** (health endpoints)
- `tests/test_agent_health.py` - **NEW FILE**

### Database Migration
- ✅ No changes needed (`last_heartbeat` already exists in Agent model)

### Key Methods to Implement
```python
# AgentHealthService (NEW)
class AgentHealthService:
    def emit_heartbeat(self, agent_id: str) -> None:
        """Update agent.last_heartbeat timestamp."""
        
    def check_agent_health(self, agent_id: str) -> HealthStatus:
        """Return comprehensive health status."""
        
    def detect_stale_agents(self, timeout_seconds: int = 90) -> list[Agent]:
        """Find agents that haven't heartbeated recently."""
        
    def get_health_statistics(self) -> HealthStats:
        """Get system-wide health metrics."""
        
    def restart_stale_agent(self, agent_id: str) -> bool:
        """Attempt to restart a stale agent."""

# Worker
def heartbeat_loop(agent_id: str):
    """Emit heartbeat every 30 seconds (background thread)."""
    
def _emit_heartbeat(self) -> None:
    """Send heartbeat to health service."""
```

### Heartbeat Protocol
```python
class HeartbeatProtocol:
    """Standard heartbeat protocol for all agents."""
    
    INTERVAL_SECONDS = 30
    STALE_THRESHOLD_SECONDS = 90
    CRITICAL_THRESHOLD_SECONDS = 300
    
    def __init__(self, agent_id: str, health_service: AgentHealthService):
        self.agent_id = agent_id
        self.health_service = health_service
        self._running = False
        self._task = None
    
    async def start(self):
        """Start heartbeat loop."""
        self._running = True
        self._task = asyncio.create_task(self._heartbeat_loop())
    
    async def stop(self):
        """Stop heartbeat loop."""
        self._running = False
        if self._task:
            self._task.cancel()
    
    async def _heartbeat_loop(self):
        """Emit heartbeat every INTERVAL_SECONDS."""
        while self._running:
            try:
                self.health_service.emit_heartbeat(self.agent_id)
                await asyncio.sleep(self.INTERVAL_SECONDS)
            except Exception as e:
                logger.error(f"Heartbeat failed: {e}")
                await asyncio.sleep(5)  # Retry quickly on error
```

### Health Status Model
```python
class HealthStatus(BaseModel):
    agent_id: str
    status: Literal["healthy", "stale", "critical", "unknown"]
    last_heartbeat: datetime
    seconds_since_heartbeat: float
    consecutive_misses: int
    
    @property
    def is_healthy(self) -> bool:
        return self.status == "healthy"

class HealthStats(BaseModel):
    total_agents: int
    healthy_count: int
    stale_count: int
    critical_count: int
    unknown_count: int
    average_heartbeat_age: float
```

### API Endpoints
```python
@router.get("/agents/{agent_id}/health")
async def get_agent_health(agent_id: str) -> HealthStatus:
    """Get health status for a specific agent."""

@router.get("/agents/health")
async def get_all_health() -> list[HealthStatus]:
    """Get health status for all agents."""

@router.get("/agents/health/stats")
async def get_health_statistics() -> HealthStats:
    """Get system-wide health statistics."""

@router.post("/agents/{agent_id}/heartbeat")
async def receive_heartbeat(agent_id: str, heartbeat: HeartbeatData):
    """Receive heartbeat from agent (internal use)."""
```

### Success Criteria
- ✅ Agents emit heartbeats every 30 seconds
- ✅ Stale agents detected (no heartbeat for 90+ seconds)
- ✅ Critical agents flagged (no heartbeat for 300+ seconds)
- ✅ Health check API endpoint (`GET /api/v1/agents/{id}/health`)
- ✅ System-wide health statistics available
- ✅ Tests pass with 80%+ coverage

---

## ⏱️ Agent D: Task Timeout & Cancellation

### Files to Modify
- `omoi_os/models/task.py` - Add `timeout_seconds` field
- `omoi_os/api/main.py` - Add timeout detection in orchestrator
- `omoi_os/api/routes/tasks.py` - Add cancellation endpoint
- `omoi_os/worker.py` - Add timeout handling
- `tests/test_task_timeout.py` - **NEW FILE**

### Database Migration
```python
# Add to migration file (coordinate with other agents)
op.add_column('tasks', sa.Column('timeout_seconds', sa.Integer(), nullable=True))
op.add_column('tasks', sa.Column('started_at', sa.DateTime(timezone=True), nullable=True))
op.add_column('tasks', sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True))
op.add_column('tasks', sa.Column('cancellation_reason', sa.String(500), nullable=True))
```

### Key Methods to Implement
```python
# TaskQueueService
def check_task_timeout(self, task_id: str) -> bool:
    """Check if task has exceeded timeout."""
    
def cancel_task(self, task_id: str, reason: str) -> None:
    """Cancel a running task."""
    
def get_running_tasks(self) -> list[Task]:
    """Get all currently running tasks."""
    
def check_timeouts(self) -> list[Task]:
    """Check all running tasks for timeout, return timed out tasks."""

# Worker
def handle_task_timeout(self, task: Task) -> None:
    """Kill conversation, update status, cleanup resources."""
    
def handle_cancellation(self, task: Task) -> None:
    """Handle task cancellation request."""

# API
@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str, reason: str = "User requested"):
    """Cancel a running task."""
```

### Timeout Detection Loop
```python
class TimeoutMonitor:
    """Background monitor for task timeouts."""
    
    CHECK_INTERVAL_SECONDS = 10
    
    def __init__(self, task_queue: TaskQueueService):
        self.task_queue = task_queue
        self._running = False
    
    async def start(self):
        """Start timeout monitoring loop."""
        self._running = True
        while self._running:
            try:
                await self._check_timeouts()
                await asyncio.sleep(self.CHECK_INTERVAL_SECONDS)
            except Exception as e:
                logger.error(f"Timeout check failed: {e}")
    
    async def _check_timeouts(self):
        """Check all running tasks for timeout."""
        running_tasks = self.task_queue.get_running_tasks()
        
        for task in running_tasks:
            if not task.timeout_seconds or not task.started_at:
                continue
            
            elapsed = (utc_now() - task.started_at).total_seconds()
            
            if elapsed > task.timeout_seconds:
                logger.warning(
                    f"Task {task.id} timed out after {elapsed:.1f}s "
                    f"(limit: {task.timeout_seconds}s)"
                )
                await self._handle_timeout(task)
    
    async def _handle_timeout(self, task: Task):
        """Handle task timeout - cancel and cleanup."""
        await self.task_queue.cancel_task(
            task.id, 
            reason=f"Timeout after {task.timeout_seconds}s"
        )
```

### Cancellation Protocol
```python
class CancellationToken:
    """Token for cooperative task cancellation."""
    
    def __init__(self):
        self._cancelled = False
        self._reason: Optional[str] = None
    
    def cancel(self, reason: str = "Cancelled"):
        """Request cancellation."""
        self._cancelled = True
        self._reason = reason
    
    @property
    def is_cancelled(self) -> bool:
        return self._cancelled
    
    def check_cancelled(self):
        """Raise if cancelled."""
        if self._cancelled:
            raise TaskCancelledError(self._reason)

class TaskCancelledError(Exception):
    """Raised when task is cancelled."""
    pass
```

### Default Timeout Values
```python
DEFAULT_TIMEOUTS = {
    "exploration": 300,      # 5 minutes for exploration
    "implementation": 3600,  # 1 hour for implementation
    "validation": 600,     # 10 minutes for validation
    "analysis": 300,       # 5 minutes for analysis
}

MAX_TIMEOUT_SECONDS = 86400  # 24 hours maximum
```

### Success Criteria
- ✅ Tasks can have timeout (seconds)
- ✅ Orchestrator detects timeouts automatically
- ✅ Tasks can be cancelled via API
- ✅ Worker handles timeout (kills conversation gracefully)
- ✅ Cancellation reason tracked
- ✅ Tests pass with 80%+ coverage

---

## 🔄 Coordination Points

### 1. Database Migration File
**Action**: Agent A creates migration file, others add to it
```bash
# Agent A runs:
alembic revision -m "phase_1_enhancements"

# File created: migrations/versions/002_phase_1_enhancements.py
# All agents add their schema changes to this file
```

### 2. Task Model Coordination
**Strategy**: Sequential merges
1. Agent A merges `dependencies` field
2. Agent B merges `retry_count`, `max_retries` fields  
3. Agent D merges `timeout_seconds` field

**OR**: Use feature branches, merge in order

### 3. TaskQueueService Coordination
**Strategy**: Each agent adds new methods (minimal overlap)
- Agent A: Modifies `get_next_task()`, adds dependency methods
- Agent B: Adds retry helper methods
- Agent D: Adds timeout/cancellation methods

### 4. Shared Constants
Add to `omoi_os/constants.py`:
```python
# Phase 1 shared constants
DEFAULT_MAX_RETRIES = 3
DEFAULT_TIMEOUT_SECONDS = 3600
HEARTBEAT_INTERVAL_SECONDS = 30
STALE_AGENT_THRESHOLD_SECONDS = 90
```

---

## 📋 Daily Checklist

### Morning Sync (15 min)
- [ ] Share progress from previous day
- [ ] Identify any conflicts early
- [ ] Coordinate database migration changes
- [ ] Review test failures

### Evening Sync (15 min)
- [ ] Review merges
- [ ] Resolve conflicts
- [ ] Run full test suite
- [ ] Plan next day

---

## ✅ Definition of Done

Each agent's work is done when:
1. ✅ All code implemented
2. ✅ All tests written and passing
3. ✅ Database migration created/updated
4. ✅ Code reviewed
5. ✅ Merged to main branch
6. ✅ Integration tests pass

---

## 🚀 Getting Started

### For Each Agent:
1. Create feature branch: `git checkout -b feature/phase1-{stream-letter}`
2. Read the detailed stream description above
3. Start with database migration (coordinate with others)
4. Implement model changes
5. Implement service logic
6. Write tests
7. Submit for review

### Example Branch Names:
- `feature/phase1-a-dependencies`
- `feature/phase1-b-retries`
- `feature/phase1-c-heartbeat`
- `feature/phase1-d-timeout`

---

## 📞 Communication

- **Slack/Channel**: #phase1-coordination
- **Daily Standup**: 9:00 AM
- **Conflict Resolution**: Tag @tech-lead
- **Questions**: Ask in channel, don't block

---

## Testing Strategy

### Unit Tests (Each Agent)
```python
# Agent A
test_dependency_resolution()
test_circular_detection()
test_graph_generation()

# Agent B
test_retry_logic()
test_backoff_calculation()
test_error_classification()

# Agent C
test_heartbeat_emission()
test_stale_detection()
test_health_statistics()

# Agent D
test_timeout_detection()
test_cancellation()
test_cleanup()
```

### Integration Tests (Combined)
```python
test_full_task_lifecycle()  # Create → Dependencies → Execute → Retry → Complete
test_error_recovery()       # Failure → Retry → Success
test_timeout_and_retry()    # Timeout → Retry → Success
test_health_monitoring()    # Heartbeat → Stale → Restart
```

---

**Ready to assign agents!** 🎉
