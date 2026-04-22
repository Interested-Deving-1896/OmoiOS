# Sandbox Agents Design Documentation

**Created**: 2025-12-12  
**Status**: Active Development  
**Purpose**: Comprehensive guide for running AI agents in isolated sandbox environments (Daytona) with full Git integration  
**Related**: **Architecture**, **AGENTS.md**, [Backend Guide](../../../backend/CLAUDE.md)

---

## Table of Contents

1. [Overview](#overview)
2. [Document Index](#document-index)
3. [Implementation Status](#implementation-status)
4. [Key Concepts](#key-concepts)
5. [Architecture Deep Dive](#architecture-deep-dive)
6. [Configuration](#configuration)
7. [Usage Examples](#usage-examples)
8. [Troubleshooting](#troubleshooting)
9. [Critical Issues](#critical-issues)
10. [Future Roadmap](#future-roadmap)

---

## Overview

The Sandbox Agents system enables OmoiOS to execute AI agents in isolated, ephemeral environments using [Daytona](https://www.daytona.io/) — a cloud sandbox technology. Each agent runs in its own container with:

- **Isolated filesystem** — No interference between parallel agents
- **Git integration** — Automatic branch creation and PR workflow
- **Resource limits** — Configurable CPU, memory, and disk constraints
- **Live preview** — Frontend tasks expose dev servers via secure URLs
- **Real-time communication** — WebSocket + HTTP callbacks for monitoring

### Why Sandboxes?

Traditional agent execution runs directly on host systems, creating risks:
- **Security**: Agents can access sensitive host files
- **Isolation**: Parallel agents conflict over shared resources
- **Reproducibility**: Host environment differences cause "works on my machine"
- **Cleanup**: Orphaned processes and file modifications persist

Daytona sandboxes solve these by providing:
- Fresh, reproducible environments per task
- Automatic cleanup on completion
- Network isolation with controlled egress
- Snapshot-based initialization for speed

---

## Document Index

| # | Document | Description | Status | Priority |
|---|----------|-------------|--------|----------|
| 01 | [Architecture](./01_architecture.md) | System design for real-time agent communication | 📋 Design | High |
| 02 | [Gap Analysis](./02_gap_analysis.md) | What we have vs. what we need | ✅ Validated | Critical |
| 03 | [Git Branch Workflow](./03_git_branch_workflow.md) | Branch management, PR workflow (Musubi) | 📋 Design | Medium |
| 04 | [Communication Patterns](./04_communication_patterns.md) | HTTP patterns, security, rate limiting | 📋 Design | High |
| 05 | [HTTP API Migration](./05_http_api_migration.md) | MCP→HTTP mapping, new routes | 📋 Design | High |
| 06 | [Implementation Checklist](./06_implementation_checklist.md) | ⭐ Test-driven implementation plan | 🆕 NEW | Critical |
| 07 | [Existing Systems Integration](./07_existing_systems_integration.md) | Guardian, Registry, Fault Tolerance | 🆕 NEW | High |
| 08 | [Frontend Integration](./08_frontend_integration.md) | UI components, WebSocket hooks | 🆕 NEW | Medium |
| 09 | [Rich Activity Feed Architecture](./09_rich_activity_feed_architecture.md) | ⭐ Future: Tool events, diffs, streaming | 🔮 POST-MVP | Low |
| 10 | [Development Workflow Guide](./10_development_workflow.md) | 🚀 Start Here: How to use these docs | 🆕 NEW | Critical |
| 11 | [Testing Workflows](./11_testing_workflows.md) | Testing patterns and validation | 📋 Design | High |
| 12 | [Improved Testing Guide](./12_improved_testing_guide.md) | Enhanced testing methodologies | 📋 Design | Medium |

### Reading Order

**For MVP (Quick Start)** — Get working in ~2 days:
1. **Development Workflow Guide** — How to use these docs practically
2. **Gap Analysis** — See what's already built (85% exists!)
3. **Implementation Checklist** — Phases 0-3.5 test code & implementation
4. **Architecture** — Reference as needed

**For Full Integration** — Production-ready system:
5. **Existing Systems Integration** — Guardian, Fault Tolerance integration
6. **Implementation Checklist** — Phases 4-7
7. **Git Workflow** — Branch/PR automation details
8. **Frontend Integration** — UI components and WebSocket hooks

---

## Implementation Status

### MVP Track (Phases 0-3.5) — Get Working Fast

| Phase | Effort | Description | Gate | Status |
|-------|--------|-------------|------|--------|
| Phase 0 | 1-2h | Validate existing infrastructure | Tests pass | ✅ Complete |
| Phase 1 | 2-3h | Sandbox event callback endpoint | Tests pass | ✅ Complete |
| Phase 2 | 4-6h | Message injection endpoints | Tests pass | ✅ Complete |
| Phase 3 | 4h | Worker script updates | Tests pass | ✅ Complete |
| Phase 3.5 | 3-4h | GitHub clone integration | MVP Complete | 🔄 In Progress |

**MVP Total**: 14-17 hours (~2 days)

### Full Integration Track (Phases 4-7) — Production Ready

| Phase | Effort | Description | Gate | Status |
|-------|--------|-------------|------|--------|
| Phase 4 | 4-6h | Database persistence | Tests pass | 📋 Planned |
| Phase 5 | 10-15h | Branch workflow service | Tests pass | 📋 Planned |
| Phase 6 | 6-8h | Guardian & systems integration | Tests pass | 📋 Planned |
| Phase 7 | 8-12h | Fault tolerance integration | Full Integration | 📋 Planned |

**Full Total**: 38-50 hours (~1 week)

---

## Key Concepts

### Daytona

[Daytona](https://www.daytona.io/) is the cloud sandbox technology powering agent isolation. Key features:

- **API-driven**: Create/destroy sandboxes via REST API
- **Snapshot support**: Pre-configured images for fast startup
- **Preview links**: Secure URLs for accessing dev servers
- **Resource controls**: CPU, memory, disk limits per sandbox

Configuration (from `config/base.yaml`):
```yaml
daytona:
  api_key: "${DAYTONA_API_KEY}"  # From .env
  api_url: "https://app.daytona.io/api"
  snapshot: "omoios-base-v1"       # Pre-built image
  sandbox_memory_gb: 4             # Max 8
  sandbox_cpu: 2                   # Max 4
  sandbox_disk_gb: 8               # Max 10
```

### BranchWorkflowService

Manages the ticket → branch → PR → merge lifecycle:

```python
# From backend/omoi_os/services/branch_workflow.py
class BranchWorkflowService:
    """Handles Git branch lifecycle for tickets."""
    
    async def start_work_on_ticket(
        self,
        ticket_id: str,
        ticket_title: str,
        repo_owner: str,
        repo_name: str,
        user_id: str,
        ticket_type: str = "feature",
    ) -> dict:
        """Create branch for ticket work."""
        
    async def create_pull_request(
        self,
        ticket_id: str,
        branch_name: str,
        repo_owner: str,
        repo_name: str,
        user_id: str,
    ) -> dict:
        """Create PR when work completes."""
```

Branch naming convention:
- Features: `feature/TKT-{id}-{slug}`
- Bugs: `fix/TKT-{id}-{slug}`
- Hotfixes: `hotfix/TKT-{id}-{slug}`

### HTTP over MCP

The system uses HTTP for task/status operations instead of MCP (Model Context Protocol) for reliability:

| Operation | Protocol | Why |
|-----------|----------|-----|
| Task assignment | HTTP | Simple, reliable, stateless |
| Status callbacks | HTTP | Fire-and-forget from sandbox |
| Message injection | HTTP | Sub-second latency |
| Tool execution | MCP | Rich context, streaming |

### Hook-Based Intervention

PreToolUse hooks enable sub-second message injection vs. polling:

```python
# Conceptual hook registration
hook_matcher = HookMatcher(
    tool_name="Write",
    predicate=lambda ctx: ctx.sandbox_id == target_sandbox
)

hook = HookInput(
    matcher=hook_matcher,
    callback=inject_message_callback,
)
```

This allows the Guardian to intervene mid-task without waiting for the next poll cycle.

---

## Architecture Deep Dive

### Sandbox Lifecycle State Machine

```
┌──────────┐     spawn()      ┌──────────┐    agent starts   ┌──────────┐
│ PENDING  │ ───────────────► │ CREATING │ ────────────────► │ RUNNING  │
└──────────┘                  └──────────┘                   └──────────┘
     │                             │                              │
     │                             │ creation fails               │
     │                             ▼                              │
     │                       ┌──────────┐                          │
     │                       │  FAILED  │ ◄──────────────────────────┤
     │                       └──────────┘   agent crashes/        │
     │                             ▲        timeout               │
     │                             │                              │
     │                             │                              ▼
     │                             │                        ┌──────────┐
     │                             │                        │COMPLETING│
     │                             │                        └──────────┘
     │                             │                              │
     │                             │                              │
     │                             │                              ▼
     │                             │                        ┌──────────┐
     └─────────────────────────────┴───────────────────────►│COMPLETED │
            manual cancel                                     └──────────┘
```

**State Transitions:**
- `PENDING → CREATING`: `DaytonaSpawnerService.spawn_sandbox()` called
- `CREATING → RUNNING`: Worker script starts, first heartbeat received
- `CREATING → FAILED`: Daytona API error or timeout
- `RUNNING → COMPLETING`: Task marked done, creating PR
- `RUNNING → FAILED`: Agent crash, Guardian timeout
- `COMPLETING → COMPLETED`: PR created successfully
- `COMPLETING → FAILED`: PR creation fails
- `* → COMPLETED`: Manual cancellation

### Service Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         SANDBOX AGENTS ARCHITECTURE                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐             │
│  │  Frontend    │     │   Backend    │     │   Daytona    │             │
│  │  (Next.js)   │◄───►│  (FastAPI)   │◄───►│  (Sandboxes) │             │
│  └──────────────┘     └──────────────┘     └──────────────┘             │
│         │                    │                    │                    │
│         │ WebSocket          │ HTTP/API           │ SSH/Exec           │
│         │ (Events)           │ (Daytona SDK)      │ (Agent Worker)     │
│         │                    │                    │                    │
│         ▼                    ▼                    ▼                    │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐             │
│  │ usePreview   │     │DaytonaSpawner│     │ClaudeSandbox │             │
│  │   Hook       │     │   Service    │     │   Worker     │             │
│  └──────────────┘     └──────────────┘     └──────────────┘             │
│                              │                    │                    │
│                              ▼                    ▼                    │
│                       ┌──────────────┐     ┌──────────────┐             │
│                       │PreviewManager│     │PreviewSetup  │             │
│                       │              │     │   Manager    │             │
│                       └──────────────┘     └──────────────┘             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Core Services

| Service | File | Responsibility |
|---------|------|----------------|
| `DaytonaSpawnerService` | `services/daytona_spawner.py` | Creates/destroys sandboxes, manages lifecycle |
| `PreviewManager` | `services/preview_manager.py` | Tracks preview sessions, publishes events |
| `BranchWorkflowService` | `services/branch_workflow.py` | Git branch/PR lifecycle |
| `ClaudeSandboxWorker` | `workers/claude_sandbox_worker.py` | Agent execution in sandbox |
| `IntelligentGuardian` | `services/intelligent_guardian.py` | Trajectory analysis, interventions |

---

## Configuration

### Environment Variables

Required in `.env`:
```bash
# Daytona
DAYTONA_API_KEY=your-daytona-api-key

# Anthropic (for Claude Agent SDK)
ANTHROPIC_API_KEY=sk-ant-...
# OR
CLAUDE_CODE_OAUTH_TOKEN=your-oauth-token

# GitHub (for PR creation)
GITHUB_TOKEN=ghp_...
```

### YAML Configuration

From `backend/config/base.yaml`:
```yaml
daytona:
  api_key: "${DAYTONA_API_KEY}"
  api_url: "https://app.daytona.io/api"
  snapshot: "omoios-base-v1"
  image: "nikolaik/python-nodejs:python3.12-nodejs22"
  sandbox_memory_gb: 4
  sandbox_cpu: 2
  sandbox_disk_gb: 8

worker:
  max_turns: 50
  max_budget_usd: 10.0
  heartbeat_interval: 30
  poll_interval: 0.5
```

### Sandbox Resource Limits

| Resource | Default | Max | Notes |
|----------|---------|-----|-------|
| Memory | 4 GB | 8 GB | Higher for large builds |
| CPU | 2 cores | 4 cores | More for compute-heavy tasks |
| Disk | 8 GB | 10 GB | For dependencies, build artifacts |

---

## Usage Examples

### Spawning a Sandbox for a Task

```python
from omoi_os.services.daytona_spawner import DaytonaSpawnerService
from omoi_os.services.database import DatabaseService
from omoi_os.services.event_bus import EventBusService

# Initialize services
db = DatabaseService(connection_string=settings.database.url)
event_bus = EventBusService(redis_url=settings.redis.url)

# Create spawner
spawner = DaytonaSpawnerService(
    db=db,
    event_bus=event_bus,
    mcp_server_url="http://localhost:18000/mcp/",
)

# Spawn sandbox for task
sandbox_id = await spawner.spawn_for_task(
    task_id="task-123",
    agent_id="agent-456",
    phase_id="PHASE_IMPLEMENTATION",
    runtime="claude",  # or "openhands"
    execution_mode="implementation",
    continuous_mode=True,  # Auto-iterate until complete
)

print(f"Sandbox created: {sandbox_id}")
```

### Creating a Preview Session

```python
from omoi_os.services.preview_manager import PreviewManager

manager = PreviewManager(db=db, event_bus=event_bus)

# Create preview (called by spawner for frontend tasks)
preview = await manager.create_preview(
    sandbox_id=sandbox_id,
    task_id="task-123",
    project_id="proj-456",
    port=3000,
    framework="vite",
)

# Later: mark as ready when dev server starts
await manager.mark_ready(
    preview_id=preview.id,
    preview_url="https://preview.daytona.io/...",
    preview_token="auth-token",
)
```

### Frontend: Using the Preview Hook

```typescript
// frontend/hooks/usePreview.ts
import { usePreview } from "@/hooks/usePreview";

function PreviewPanel({ sandboxId }: { sandboxId: string }) {
  const {
    preview,
    hasPreview,
    isReady,
    isPending,
    justBecameReady,
    stop,
    refresh,
  } = usePreview(sandboxId);

  // Auto-switch to preview tab when ready
  useEffect(() => {
    if (justBecameReady) {
      setActiveTab("preview");
    }
  }, [justBecameReady]);

  if (isPending) {
    return <LoadingSpinner message="Starting dev server..." />;
  }

  if (isReady && preview?.preview_url) {
    return (
      <iframe
        src={preview.preview_url}
        sandbox="allow-scripts allow-same-origin"
        title="Live Preview"
      />
    );
  }

  return null;
}
```

### Worker: Checking Git Status (Continuous Mode)

```python
# From claude_sandbox_worker.py
def check_git_status(cwd: str) -> dict:
    """Check git status for validation."""
    result = {
        "is_clean": False,
        "is_pushed": False,
        "has_pr": False,
        "branch_name": None,
        "errors": [],
        "tests_passed": False,
    }
    
    # Get current branch
    branch_result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if branch_result.returncode == 0:
        result["branch_name"] = branch_result.stdout.strip()
    
    # Check for uncommitted changes
    status_result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    result["is_clean"] = (
        status_result.returncode == 0 and not status_result.stdout.strip()
    )
    
    # Check for PR using gh CLI
    pr_result = subprocess.run(
        ["gh", "pr", "view", "--json", "number,title,state,url"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if pr_result.returncode == 0:
        result["has_pr"] = True
        pr_data = json.loads(pr_result.stdout)
        result["pr_url"] = pr_data.get("url")
    
    return result
```

---

## Troubleshooting

### Sandbox Creation Fails

**Symptom**: `RuntimeError: Failed to spawn sandbox`

**Checklist**:
1. Verify `DAYTONA_API_KEY` is set in `.env`
2. Check Daytona API status: `curl https://app.daytona.io/api/health`
3. Verify snapshot exists: `daytona snapshot list`
4. Check resource limits (memory/CPU within plan)

**Debug logging**:
```python
logger.info(
    "Creating Daytona sandbox",
    extra={
        "sandbox_id": sandbox_id,
        "task_id": task_id,
        "runtime": runtime,
        "env_vars_count": len(env_vars),
    },
)
```

### Preview URL Not Generated

**Symptom**: Preview session stuck in `PENDING` status

**Checklist**:
1. Verify task has `required_capabilities` with frontend indicators
2. Check `daytona_sandbox.get_preview_link()` returns valid URL
3. Ensure worker has `PREVIEW_ENABLED=true` env var
4. Verify PreviewSetupManager is running in worker

**Debug commands**:
```bash
# Check preview session status
uv run python -c "
from omoi_os.services.preview_manager import PreviewManager
from omoi_os.services.database import DatabaseService
from omoi_os.config import get_app_settings

db = DatabaseService(connection_string=get_app_settings().database.url)
manager = PreviewManager(db=db, event_bus=None)
preview = await manager.get_by_sandbox('sandbox-id')
print(preview.status, preview.preview_url)
"
```

### Worker Not Receiving Tasks

**Symptom**: Sandbox created but agent idle

**Checklist**:
1. Verify `MCP_SERVER_URL` is accessible from sandbox
2. Check worker logs: `docker logs <sandbox-container>`
3. Verify `TASK_DATA_BASE64` decoded correctly
4. Check heartbeat events reaching backend

### Git Operations Fail

**Symptom**: `git push` fails in sandbox

**Checklist**:
1. Verify `GITHUB_TOKEN` has `repo` scope
2. Check branch was created before sandbox spawn
3. Verify `BRANCH_NAME` env var passed to sandbox
4. Check `git remote -v` shows correct origin

---

## Critical Issues

| Issue | Status | Impact | Resolution |
|-------|--------|--------|------------|
| Missing `sandbox_id` on Task model | 📋 Documented | Guardian can't track sandbox agents | Fix in Phase 6 |
| Guardian can't intervene with sandbox agents | 📋 Documented | No mid-task steering | Hook-based injection in Phase 6 |
| Fault tolerance not sandbox-aware | 📋 Documented | Orphaned sandboxes on failures | Phase 7 integration |
| Polling-based intervention latency | ✅ Resolved | Sub-second injection designed | Hook-based in [04_communication_patterns.md](./04_communication_patterns.md) |
| SDK API correctness | ✅ Resolved | Fixed in [02_gap_analysis.md](./02_gap_analysis.md) | Gap #8 |

---

## Future Roadmap

### Post-MVP Enhancements

1. **Rich Activity Feed** — Tool events, file diffs, streaming output
2. **Multi-Region Sandboxes** — Deploy closer to user for lower latency
3. **Custom Snapshots** — User-defined base images with pre-installed tools
4. **Persistent Volumes** — Cache dependencies across sandbox restarts
5. **Collaborative Sessions** — Multiple users viewing same preview

### Integration Points

| System | Integration | Status |
|--------|-------------|--------|
| Guardian | Trajectory analysis, interventions | Phase 6 |
| Conductor | Duplicate detection, coherence | Phase 6 |
| Fault Tolerance | Auto-restart, health checks | Phase 7 |
| Billing | Per-sandbox cost tracking | Planned |
| Memory | Cross-session context | Planned |

---

## Related Documentation

- **Architecture Overview**
- [Daytona SDK Documentation](https://docs.daytona.io/)
- [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk)
- [Backend Service Guide](../../../backend/CLAUDE.md)
- [Frontend Integration](./08_frontend_integration.md)

---

<claude-mem-context>
# Recent Activity

<!-- This section is auto-generated by claude-mem. Edit content outside the tags. -->

### Mar 3, 2026

| ID | Time | T | Title | Read |
|----|------|---|-------|------|
| #6514 | 11:26 AM | 🔵 | Found unresolved merge conflict in documentation | ~160 |
| #6518 | 11:28 AM | ✅ | Committed dev stack fixes and Next.js memory optimizations | ~538 |
</claude-mem-context>
