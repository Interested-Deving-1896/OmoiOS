# Sandbox Spawner Service

> **Date**: 2025-07-20 | **Status**: Active | **Version**: 1.0 | **Owner**: Deep Docs Pipeline
> **Source**: Generated from codebase analysis | **Cross-links**: See Related Documents section

## Overview

The Sandbox Spawner Service is the bridge between the OmoiOS orchestrator and isolated agent execution environments. It manages the complete lifecycle of Daytona sandboxes—from provisioning and configuration to termination and cleanup. This service ensures that each agent task runs in an isolated, secure container with proper resource allocation, environment variables, and access credentials.

## Architecture

```mermaid
graph TB
    subgraph "OmoiOS Core"
        ORCH[Orchestrator Worker]
        PM[Phase Manager]
        EB[Event Bus]
        DB[(Database)]
    end

    subgraph "Sandbox Spawner"
        DS[DaytonaSpawnerService]
        SI[SandboxInfo Registry]
        DP[DaytonaProvider]
    end

    subgraph "Daytona Cloud"
        DAPI[Daytona API]
        SB1[Sandbox 1]
        SB2[Sandbox 2]
        SB3[Sandbox N]
    end

    subgraph "External Services"
        GH[GitHub API]
        ANTH[Anthropic API]
        MCP[MCP Server]
    end

    ORCH --> DS
    PM --> DS
    DS --> SI
    DS --> DP
    DP --> DAPI
    DAPI --> SB1
    DAPI --> SB2
    DAPI --> SB3
    SB1 --> GH
    SB1 --> ANTH
    SB1 --> MCP
    DS --> EB
    DS --> DB
```

## Key Components

### DaytonaSpawnerService

`backend/omoi_os/services/daytona_spawner.py:58-3600`

The main service class responsible for sandbox lifecycle management:

```python
class DaytonaSpawnerService:
    """Service for spawning and managing Daytona sandboxes.
    
    This service creates isolated execution environments for agents,
    passing the necessary configuration via environment variables.
    """
```

**Key Methods:**

| Method | Purpose | Lines |
|--------|---------|-------|
| `spawn_for_task()` | Create sandbox for a specific task | 139-856 |
| `spawn_for_phase()` | Create sandbox for spec phase workflow | 1004-1318 |
| `terminate_sandbox()` | Clean up and stop a sandbox | 3282-3389 |
| `_create_daytona_sandbox()` | Core Daytona SDK integration | 1320-1468 |
| `_start_worker_in_sandbox()` | Initialize agent worker | 1469-1929 |

### SandboxInfo

`backend/omoi_os/services/daytona_spawner.py:42-56`

Dataclass tracking sandbox state:

```python
@dataclass
class SandboxInfo:
    """Information about a spawned sandbox."""
    
    sandbox_id: str
    agent_id: str
    task_id: str
    phase_id: str
    status: str = "creating"  # creating, running, completed, failed, terminated
    created_at: datetime = field(default_factory=utc_now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    extra_data: Dict[str, Any] = field(default_factory=dict)
```

### DaytonaProvider

`backend/omoi_os/services/daytona_provider.py:8-60`

Adapter implementing the SandboxProvider interface:

```python
class DaytonaProvider:
    """SandboxProvider backed by Daytona Cloud."""
    
    def __init__(self, spawner):
        self._spawner = spawner
```

## Sandbox Provisioning Flow

```mermaid
sequenceDiagram
    participant ORCH as Orchestrator
    participant DS as DaytonaSpawner
    participant DB as Database
    participant DAPI as Daytona API
    participant SB as Sandbox
    participant GH as GitHub

    ORCH->>DS: spawn_for_task(task_id, agent_id, phase_id)
    DS->>DB: Validate task ownership
    DS->>DS: Generate sandbox_id
    DS->>DS: Build environment variables
    DS->>DB: Fetch GitHub credentials
    DS->>DB: Generate OmoiOS API token
    DS->>DAPI: CreateSandboxFromImage/Snapshot
    DAPI->>SB: Provision container
    DAPI-->>DS: sandbox reference
    DS->>SB: Install dependencies (uv/pip)
    DS->>SB: Install GitHub CLI
    DS->>SB: Upload Claude skills
    DS->>SB: Upload spec-sandbox subsystem
    DS->>GH: Clone repository
    DS->>SB: Checkout feature branch
    DS->>SB: Configure git credentials
    DS->>SB: Start worker process
    SB-->>DS: Worker running
    DS-->>ORCH: sandbox_id
```

## Configuration

### Resource Allocation

`backend/omoi_os/services/daytona_spawner.py:81-134`

```python
def __init__(
    self,
    sandbox_memory_gb: int = 4,      # Max: 8 GiB
    sandbox_cpu: int = 2,             # Max: 4 cores
    sandbox_disk_gb: int = 8,        # Max: 10 GiB
    auto_cleanup: bool = True,
    ...
):
```

Resource limits are enforced to prevent runaway resource consumption:

| Resource | Default | Maximum | Purpose |
|----------|---------|---------|---------|
| Memory | 4 GiB | 8 GiB | Prevents OOM kills |
| CPU | 2 cores | 4 cores | Parallel processing |
| Disk | 8 GiB | 10 GiB | Workspace storage |

### Environment Variables

`backend/omoi_os/services/daytona_spawner.py:282-710`

The spawner constructs a comprehensive environment for each sandbox:

**Core Identity:**
```python
env_vars = {
    "AGENT_ID": agent_id,
    "TASK_ID": task_id,
    "EXECUTION_MODE": execution_mode,
    "PHASE_ID": phase_id,
    "SANDBOX_ID": sandbox_id,
    "IS_SANDBOX": "1",  # Signals secure sandbox context
}
```

**API Configuration:**
```python
env_vars.update({
    "MCP_SERVER_URL": self.mcp_server_url,
    "CALLBACK_URL": base_url,
    "OMOIOS_API_URL": base_url,
    "OMOIOS_API_KEY": sandbox_token,  # JWT for API auth
})
```

**Git Integration:**
```python
env_vars.update({
    "GITHUB_REPO": github_repo,
    "GITHUB_TOKEN": github_token,
    "GITHUB_USERNAME": github_creds.username,
    "BRANCH_NAME": branch_name,
    "WORKSPACE_PATH": "/workspace",
})
```

**LLM Credentials:**
```python
# Prefer OAuth token for Claude Agent SDK
if creds.oauth_token:
    env_vars["CLAUDE_CODE_OAUTH_TOKEN"] = creds.oauth_token
elif creds.api_key:
    env_vars["ANTHROPIC_API_KEY"] = creds.api_key

# Model configuration
env_vars.update({
    "MODEL": creds.model,
    "ANTHROPIC_MODEL": creds.model,
    "ANTHROPIC_DEFAULT_SONNET_MODEL": creds.default_sonnet_model,
})
```

## Execution Modes

`backend/omoi_os/services/daytona_spawner.py:147-152`

The spawner supports three execution modes that determine skill loading and behavior:

| Mode | Purpose | Skills Loaded | Continuous |
|------|---------|---------------|------------|
| `exploration` | Feature definition, spec creation | spec-driven-dev | Auto-enabled |
| `implementation` | Code execution, PR creation | git-workflow, code-review | Auto-enabled |
| `validation` | Testing, verification | code-review, test-writer | Auto-enabled |

## Lifecycle Management

### Creation

`backend/omoi_os/services/daytona_spawner.py:1320-1468`

```python
async def _create_daytona_sandbox(
    self,
    sandbox_id: str,
    env_vars: Dict[str, str],
    labels: Dict[str, str],
    runtime: str = "openhands",
    execution_mode: str = "implementation",
    continuous_mode: bool = False,
) -> None:
```

**Creation Steps:**
1. Initialize Daytona SDK with API credentials
2. Configure resource allocation (CPU, memory, disk)
3. Attempt creation from snapshot (fallback to image)
4. Store sandbox reference in registry
5. Start worker process with environment

### Termination

`backend/omoi_os/services/daytona_spawner.py:3282-3389`

```python
async def terminate_sandbox(self, sandbox_id: str) -> bool:
    """Terminate a running sandbox.
    
    Handles two cases:
    1. Sandbox in memory: Use cached Daytona reference
    2. Sandbox not in memory: Use direct Daytona API
    """
```

**Termination Flow:**
1. Check in-memory registry for sandbox info
2. If cached, use stored Daytona reference to stop
3. If not cached, query Daytona API directly
4. Handle "not found" gracefully (already terminated)
5. Publish `sandbox.terminated` event

### Auto-Cleanup

`backend/omoi_os/services/daytona_spawner.py:3406-3428`

```python
def mark_completed(self, sandbox_id: str, result: Optional[Dict] = None) -> None:
    """Mark a sandbox as completed (called when task finishes)."""
    info = self._sandboxes.get(sandbox_id)
    if info:
        info.status = "completed"
        if self.auto_cleanup:
            asyncio.create_task(self.terminate_sandbox(sandbox_id))
```

## Error Recovery

### Snapshot Fallback

`backend/omoi_os/services/daytona_spawner.py:1368-1409`

```python
# Create sandbox from snapshot if provided, otherwise use image
if self.sandbox_snapshot:
    try:
        params = CreateSandboxFromSnapshotParams(
            snapshot=self.sandbox_snapshot,
            ephemeral=True,
            resources=resources,
        )
        sandbox = daytona.create(params=params, timeout=120)
    except Exception as snapshot_error:
        # Snapshot may be inactive/expired/unavailable
        logger.warning(f"Snapshot creation failed: {snapshot_error}")
        # Fall back to image-based creation
```

### Worker Startup Failures

`backend/omoi_os/services/daytona_spawner.py:1445-1468`

Worker startup errors are explicitly raised (not silently swallowed):

```python
try:
    await self._start_worker_in_sandbox(sandbox, env_vars, runtime)
    logger.info(f"Worker started successfully in sandbox {sandbox.id}")
except Exception as e:
    # Log worker startup errors clearly
    logger.error(f"Failed to start worker in sandbox {sandbox.id}: {e}")
    # Re-raise so caller knows something went wrong
    raise RuntimeError(f"Worker startup failed: {e}") from e
```

### Mock Sandbox (Development)

`backend/omoi_os/services/daytona_spawner.py:3261-3281`

For local development without Daytona access:

```python
async def _create_mock_sandbox(
    self,
    sandbox_id: str,
    env_vars: Dict[str, str],
) -> None:
    """Create a mock sandbox for local testing without Daytona."""
    logger.info(f"Creating mock sandbox {sandbox_id}")
    # Log environment for manual worker execution
```

## GitHub Integration

### Branch Creation

`backend/omoi_os/services/daytona_spawner.py:608-661`

```python
# Create GitHub branch BEFORE sandbox creation
branch_workflow = BranchWorkflowService(github_service)
result = await branch_workflow.start_work_on_ticket(
    ticket_id=ticket_id,
    ticket_title=ticket_title,
    repo_owner=repo_owner,
    repo_name=repo_name,
    user_id=user_id,
    ticket_type=ticket_type,
)
```

### Repository Cloning

`backend/omoi_os/services/daytona_spawner.py:1652-1859`

```python
# Use Daytona SDK's native git.clone() with authentication
clone_kwargs = {
    "url": repo_url,
    "path": workspace_path,
    "username": "x-access-token",
    "password": github_token,
    "branch": branch_name,  # Clone specific branch
}
sandbox.git.clone(**clone_kwargs)
```

### Git Configuration

`backend/kevinhill/Coding/Experiments/senior-sandbox/omoi_os/backend/omoi_os/services/daytona_spawner.py:1815-1844`

```python
# Configure git for pushing
sandbox.process.exec(
    "git config --global credential.helper 'cache --timeout=86400'"
)

# Set remote URL with embedded token
authenticated_url = f"https://x-access-token:{github_token}@github.com/{github_repo}.git"
sandbox.process.exec(
    f"cd {workspace_path} && git remote set-url origin {shlex.quote(authenticated_url)}"
)

# Configure git user
sandbox.process.exec(
    'git config --global user.email "41898282+github-actions[bot]@users.noreply.github.com"'
)
```

## Skills and Subsystem Upload

### Claude Skills

`backend/omoi_os/services/daytona_spawner.py:1548-1591`

```python
if runtime == "claude":
    # Create skills directory
    sandbox.process.exec("mkdir -p /root/.claude/skills")
    
    # Upload settings for bypassPermissions mode
    settings_content = '{"permissions": {"allow": [], "deny": []}}'
    sandbox.fs.upload_file(settings_content.encode(), "/root/.claude/settings.local.json")
    
    # Get skills based on execution mode
    skills = get_skills_for_upload(mode=execution_mode)
    for skill_path, content in skills.items():
        sandbox.fs.upload_file(content.encode("utf-8"), skill_path)
```

### Spec-Sandbox Subsystem

`backend/omoi_os/services/daytona_spawner.py:1592-1642`

```python
# Upload spec-sandbox subsystem for spec-driven development
spec_sandbox_files = get_spec_sandbox_files(install_path="/tmp/spec_sandbox_pkg")
for sandbox_path, content in spec_sandbox_files.items():
    sandbox.fs.upload_file(content.encode("utf-8"), sandbox_path)

# Add to PYTHONPATH
env_vars["PYTHONPATH"] = "/tmp/spec_sandbox_pkg"
```

## Event Publishing

The spawner publishes events via the EventBus for real-time monitoring:

| Event | Trigger | Payload |
|-------|---------|---------|
| `sandbox.spawned` | Sandbox created | sandbox_id, task_id, agent_id |
| `sandbox.failed` | Creation failed | error, task_id |
| `sandbox.terminated` | Sandbox stopped | task_id, sandbox_id |

## Related Documents

- [Phase Manager](./phase_manager.md) - Orchestrates phase transitions that trigger sandbox spawning
- [Event Bus](./event_bus.md) - Real-time event distribution for sandbox lifecycle
- `backend/omoi_os/services/daytona_provider.py` - Provider adapter interface
- `backend/omoi_os/workers/claude_sandbox_worker.py` - Worker that runs inside sandboxes
- `docs/architecture/02-execution-system.md` - Execution system deep-dive

## API Reference

### spawn_for_task

```python
async def spawn_for_task(
    self,
    task_id: str,
    agent_id: str,
    phase_id: str,
    agent_type: Optional[str] = None,
    extra_env: Optional[Dict[str, str]] = None,
    labels: Optional[Dict[str, str]] = None,
    runtime: str = "openhands",  # "openhands" or "claude"
    execution_mode: str = "implementation",
    continuous_mode: Optional[bool] = None,
    task_requirements: Optional["TaskRequirements"] = None,
    require_spec_skill: bool = False,
    project_id: Optional[str] = None,
    omoios_api_key: Optional[str] = None,
) -> str:
    """Spawn a Daytona sandbox for executing a task.
    
    Returns:
        Sandbox ID string
        
    Raises:
        RuntimeError: If sandbox creation fails
        OwnershipConflictError: If task ownership validation fails
    """
```

### terminate_sandbox

```python
async def terminate_sandbox(self, sandbox_id: str) -> bool:
    """Terminate a running sandbox.
    
    Handles both cached and direct API termination.
    Gracefully handles already-terminated sandboxes.
    
    Returns:
        True if terminated successfully
    """
```

### get_sandbox_info

```python
def get_sandbox_info(self, sandbox_id: str) -> Optional[SandboxInfo]:
    """Get information about a sandbox from the in-memory registry."""
```
