# OmoiOS Backend API Reference

**Version:** 1.0  
**Total Route Files:** 39  
**Total Endpoints:** 300+  
**Generated:** April 2026

---

## Table of Contents

1. [Authentication & Users](#1-authentication--users)
2. [Projects & Specs](#2-projects--specs)
3. [Task Management](#3-task-management)
4. [Agents & Monitoring](#4-agents--monitoring)
5. [GitHub Integration](#5-github-integration)
6. [Billing & Usage](#6-billing--usage)
7. [Memory & Learning](#7-memory--learning)
8. [System & Utilities](#8-system--utilities)

---

## 1. Authentication & Users

### Files Overview

| File | Lines | Description |
|------|-------|-------------|
| `auth.py` | 835 | Authentication, registration, tokens, API keys |
| `oauth.py` | 591 | OAuth provider management (GitHub, Google, GitLab) |
| `organizations.py` | 632 | Organization CRUD, membership, roles |
| `onboarding.py` | 487 | User onboarding flows and progress tracking |

### 1.1 Authentication (`auth.py`)

**Base Path:** `/api/v1/auth`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| POST | `/register` | `UserResponse` | Register new user with email/password |
| POST | `/login` | `TokenResponse` | Authenticate user, return JWT tokens |
| POST | `/logout` | `dict` | Logout user, revoke tokens |
| POST | `/refresh` | `TokenResponse` | Refresh access token using refresh token |
| POST | `/verify-email` | `dict` | Verify email with token |
| POST | `/resend-verification` | `dict` | Resend verification email |
| POST | `/forgot-password` | `dict` | Request password reset |
| POST | `/reset-password` | `dict` | Reset password with token |
| POST | `/change-password` | `dict` | Change password (authenticated) |
| GET | `/me` | `UserResponse` | Get current user profile |
| PATCH | `/me` | `UserResponse` | Update user profile |
| DELETE | `/me` | `dict` | Delete user account |
| POST | `/api-keys` | `APIKeyResponse` | Create new API key |
| GET | `/api-keys` | `List[APIKeyResponse]` | List user's API keys |
| DELETE | `/api-keys/{key_id}` | `dict` | Revoke API key |
| POST | `/waitlist` | `WaitlistResponse` | Join waitlist |

#### Key Pydantic Models

```python
class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    is_verified: bool
    created_at: datetime

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class APIKeyResponse(BaseModel):
    id: str
    name: str
    key_preview: str  # Last 4 characters
    created_at: datetime
    last_used_at: Optional[datetime]
```

### 1.2 OAuth (`oauth.py`)

**Base Path:** `/api/v1/oauth`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| GET | `/providers` | `List[OAuthProviderResponse]` | List configured OAuth providers |
| GET | `/github/authorize` | `OAuthAuthorizeResponse` | Get GitHub OAuth URL |
| POST | `/github/callback` | `TokenResponse` | Handle GitHub OAuth callback |
| GET | `/google/authorize` | `OAuthAuthorizeResponse` | Get Google OAuth URL |
| POST | `/google/callback` | `TokenResponse` | Handle Google OAuth callback |
| GET | `/gitlab/authorize` | `OAuthAuthorizeResponse` | Get GitLab OAuth URL |
| POST | `/gitlab/callback` | `TokenResponse` | Handle GitLab OAuth callback |
| POST | `/connect/{provider}` | `dict` | Connect OAuth to existing account |
| DELETE | `/disconnect/{provider}` | `dict` | Disconnect OAuth provider |

#### Key Pydantic Models

```python
class OAuthProviderResponse(BaseModel):
    id: str
    name: str
    icon_url: str
    connected: bool

class OAuthAuthorizeResponse(BaseModel):
    authorization_url: str
    state: str
```

### 1.3 Organizations (`organizations.py`)

**Base Path:** `/api/v1/organizations`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| GET | `/` | `List[OrganizationResponse]` | List user's organizations |
| POST | `/` | `OrganizationResponse` | Create new organization |
| GET | `/{org_id}` | `OrganizationResponse` | Get organization details |
| PATCH | `/{org_id}` | `OrganizationResponse` | Update organization |
| DELETE | `/{org_id}` | `dict` | Delete organization |
| GET | `/{org_id}/members` | `List[MemberResponse]` | List organization members |
| POST | `/{org_id}/members` | `MemberResponse` | Invite member to organization |
| DELETE | `/{org_id}/members/{user_id}` | `dict` | Remove member from organization |
| PATCH | `/{org_id}/members/{user_id}/role` | `MemberResponse` | Update member role |
| POST | `/{org_id}/transfer` | `dict` | Transfer organization ownership |

#### Key Pydantic Models

```python
class OrganizationResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str]
    avatar_url: Optional[str]
    created_at: datetime
    updated_at: datetime
    member_count: int

class MemberResponse(BaseModel):
    user_id: str
    email: str
    name: str
    role: str  # owner, admin, member
    joined_at: datetime
```

### 1.4 Onboarding (`onboarding.py`)

**Base Path:** `/api/v1/onboarding`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| GET | `/status` | `OnboardingStatusResponse` | Get user's onboarding status |
| POST | `/step` | `OnboardingStatusResponse` | Update current onboarding step |
| POST | `/complete` | `OnboardingStatusResponse` | Mark onboarding as complete |
| POST | `/reset` | `OnboardingStatusResponse` | Reset onboarding progress |
| GET | `/detect` | `OnboardingDetectResponse` | Auto-detect user's current state |
| POST | `/sync` | `OnboardingStatusResponse` | Sync onboarding state |
| POST | `/admin/reset/{user_id}` | `OnboardingStatusResponse` | Admin reset for any user |

#### Key Pydantic Models

```python
class OnboardingStatusResponse(BaseModel):
    is_completed: bool
    current_step: str
    completed_steps: List[str]
    completed_checklist_items: List[str]
    completed_at: Optional[datetime]
    data: dict
    sync_version: int

class OnboardingDetectResponse(BaseModel):
    github: DetectedStepState
    organization: DetectedStepState
    repo: DetectedStepState
    plan: DetectedStepState
    suggested_step: str
```

---

## 2. Projects & Specs

### Files Overview

| File | Lines | Description |
|------|-------|-------------|
| `projects.py` | 575 | Project CRUD with multi-tenant filtering |
| `specs.py` | 1,599 | Spec management with requirements, design, tasks |
| `explore.py` | 882 | AI-powered codebase exploration |
| `phases.py` | 467 | Phase transitions and gate validation |
| `public.py` | 158 | Public showcase endpoints |
| `prototype.py` | 234 | Rapid prototyping mode |

### 2.1 Projects (`projects.py`)

**Base Path:** `/api/v1/projects`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| GET | `/` | `List[ProjectResponse]` | List projects for current organization |
| POST | `/` | `ProjectResponse` | Create new project |
| GET | `/{project_id}` | `ProjectResponse` | Get project details |
| PATCH | `/{project_id}` | `ProjectResponse` | Update project |
| DELETE | `/{project_id}` | `dict` | Delete project |
| POST | `/{project_id}/archive` | `ProjectResponse` | Archive project |
| POST | `/{project_id}/unarchive` | `ProjectResponse` | Unarchive project |
| GET | `/{project_id}/stats` | `ProjectStatsResponse` | Get project statistics |

#### Key Pydantic Models

```python
class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    organization_id: str
    github_repo: Optional[str]
    github_owner: Optional[str]
    default_branch: str = "main"
    is_archived: bool
    created_at: datetime
    updated_at: datetime

class ProjectStatsResponse(BaseModel):
    total_specs: int
    active_specs: int
    completed_specs: int
    total_tickets: int
    open_tickets: int
```

### 2.2 Specs (`specs.py`)

**Base Path:** `/api/v1/specs`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| GET | `/` | `List[SpecListResponse]` | List specs for project |
| POST | `/` | `SpecResponse` | Create new spec |
| GET | `/{spec_id}` | `SpecResponse` | Get spec details |
| PATCH | `/{spec_id}` | `SpecResponse` | Update spec |
| DELETE | `/{spec_id}` | `dict` | Delete spec |
| POST | `/{spec_id}/submit` | `SpecResponse` | Submit spec for processing |
| GET | `/{spec_id}/state` | `SpecStateResponse` | Get spec state machine status |
| POST | `/{spec_id}/transition` | `SpecStateResponse` | Trigger state transition |
| GET | `/{spec_id}/requirements` | `RequirementsResponse` | Get spec requirements |
| POST | `/{spec_id}/requirements` | `RequirementsResponse` | Update requirements |
| GET | `/{spec_id}/design` | `DesignResponse` | Get spec design |
| POST | `/{spec_id}/design` | `DesignResponse` | Update design |
| GET | `/{spec_id}/tasks` | `List[TaskResponse]` | Get spec tasks |
| POST | `/{spec_id}/tasks/generate` | `TaskGenerationResponse` | Auto-generate tasks from spec |
| GET | `/{spec_id}/artifacts` | `List[ArtifactResponse]` | Get spec artifacts |
| POST | `/{spec_id}/artifacts` | `ArtifactResponse` | Add artifact to spec |
| GET | `/{spec_id}/export` | `SpecExportResponse` | Export spec to markdown |
| POST | `/{spec_id}/clone` | `SpecResponse` | Clone existing spec |
| POST | `/{spec_id}/pause` | `SpecResponse` | Pause spec processing |
| POST | `/{spec_id}/resume` | `SpecResponse` | Resume spec processing |
| POST | `/{spec_id}/cancel` | `SpecResponse` | Cancel spec processing |

#### Key Pydantic Models

```python
class SpecResponse(BaseModel):
    id: str
    project_id: str
    title: str
    description: str
    status: str  # draft, exploring, requirements, design, tasks, syncing, complete, error
    current_phase: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]

class SpecStateResponse(BaseModel):
    spec_id: str
    current_state: str
    available_transitions: List[str]
    phase_progress: dict
    gate_status: dict
    last_transition_at: Optional[datetime]

class RequirementsResponse(BaseModel):
    spec_id: str
    requirements: List[RequirementItem]
    acceptance_criteria: List[AcceptanceCriterion]
    ears_format_text: Optional[str]

class DesignResponse(BaseModel):
    spec_id: str
    architecture: Optional[dict]
    data_models: Optional[dict]
    api_design: Optional[dict]
    error_handling: Optional[dict]
    sequence_diagrams: Optional[List[dict]]
```

### 2.3 Explore (`explore.py`)

**Base Path:** `/api/v1/explore`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| POST | `/start` | `ExploreSessionResponse` | Start new codebase exploration |
| GET | `/sessions` | `List[ExploreSessionResponse]` | List exploration sessions |
| GET | `/sessions/{session_id}` | `ExploreSessionResponse` | Get session details |
| POST | `/sessions/{session_id}/query` | `ExploreQueryResponse` | Send query to exploration agent |
| GET | `/sessions/{session_id}/conversations` | `List[ConversationMessage]` | Get conversation history |
| POST | `/sessions/{session_id}/generate-spec` | `SpecResponse` | Generate spec from exploration |
| DELETE | `/sessions/{session_id}` | `dict` | Delete exploration session |
| POST | `/sessions/{session_id}/pause` | `ExploreSessionResponse` | Pause exploration |
| POST | `/sessions/{session_id}/resume` | `ExploreSessionResponse` | Resume exploration |

#### Key Pydantic Models

```python
class ExploreSessionResponse(BaseModel):
    id: str
    project_id: str
    status: str  # active, paused, completed, error
    repository_url: str
    branch: str
    created_at: datetime
    last_activity_at: datetime
    summary: Optional[str]

class ExploreQueryResponse(BaseModel):
    session_id: str
    query: str
    response: str
    files_referenced: List[str]
    timestamp: datetime
```

### 2.4 Phases (`phases.py`)

**Base Path:** `/api/v1/phases`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| GET | `/` | `List[PhaseResponse]` | List all phases |
| GET | `/current` | `PhaseResponse` | Get current active phase |
| POST | `/{phase_id}/enter` | `PhaseTransitionResponse` | Enter phase |
| POST | `/{phase_id}/exit` | `PhaseTransitionResponse` | Exit phase |
| POST | `/{phase_id}/gate/check` | `GateCheckResponse` | Check if gate passes |
| POST | `/{phase_id}/gate/validate` | `GateValidationResponse` | Validate gate requirements |
| GET | `/{phase_id}/tickets` | `List[TicketResponse]` | Get tickets in phase |
| POST | `/{phase_id}/tickets/advance` | `TicketAdvanceResponse` | Advance eligible tickets |
| GET | `/transitions` | `List[PhaseTransitionRule]` | Get phase transition rules |

#### Key Pydantic Models

```python
class PhaseResponse(BaseModel):
    id: str
    name: str
    description: str
    order: int
    is_active: bool
    entry_criteria: List[str]
    exit_criteria: List[str]
    required_artifacts: List[str]

class GateCheckResponse(BaseModel):
    ticket_id: str
    phase_id: str
    can_advance: bool
    requirements_met: dict
    missing_requirements: List[str]
    artifacts_present: List[str]

class PhaseTransitionResponse(BaseModel):
    ticket_id: str
    from_phase: str
    to_phase: str
    transitioned_at: datetime
    success: bool
    message: Optional[str]
```

### 2.5 Public (`public.py`)

**Base Path:** `/api/v1/public`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| GET | `/showcases` | `List[PublicShowcaseResponse]` | List public showcases |
| GET | `/showcases/{showcase_id}` | `PublicShowcaseResponse` | Get showcase details |
| POST | `/specs/{spec_id}/publish` | `PublicShowcaseResponse` | Publish spec as showcase |
| DELETE | `/specs/{spec_id}/unpublish` | `dict` | Unpublish showcase |
| GET | `/specs/{spec_id}/share` | `ShareableLinkResponse` | Generate shareable link |

### 2.6 Prototype (`prototype.py`)

**Base Path:** `/api/v1/prototype`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| POST | `/session` | `SessionResponse` | Start prototype session |
| GET | `/session/{session_id}` | `SessionResponse` | Get session status |
| POST | `/session/{session_id}/prompt` | `PromptResponse` | Apply prompt to prototype |
| POST | `/session/{session_id}/export` | `ExportResponse` | Export to git repo |
| DELETE | `/session/{session_id}` | `dict` | End session |

---

## 3. Task Management

### Files Overview

| File | Lines | Description |
|------|-------|-------------|
| `tasks.py` | 1,360 | Task CRUD, dependencies, timeouts |
| `tickets.py` | 1,443 | Ticket workflows and transitions |
| `sandbox.py` | 1,357 | Sandbox event handling and sync |
| `board.py` | 352 | Kanban board operations |
| `graph.py` | 160 | Dependency graph visualization |

### 3.1 Tasks (`tasks.py`)

**Base Path:** `/api/v1/tasks`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| GET | `/` | `List[TaskResponse]` | List tasks with filters |
| POST | `/` | `TaskResponse` | Create new task |
| GET | `/{task_id}` | `TaskResponse` | Get task details |
| PATCH | `/{task_id}` | `TaskResponse` | Update task |
| DELETE | `/{task_id}` | `dict` | Delete task |
| POST | `/{task_id}/assign` | `TaskResponse` | Assign task to agent |
| POST | `/{task_id}/unassign` | `TaskResponse` | Unassign task |
| POST | `/{task_id}/start` | `TaskResponse` | Start task execution |
| POST | `/{task_id}/complete` | `TaskResponse` | Mark task complete |
| POST | `/{task_id}/fail` | `TaskResponse` | Mark task failed |
| POST | `/{task_id}/cancel` | `TaskResponse` | Cancel task |
| POST | `/{task_id}/retry` | `TaskResponse` | Retry failed task |
| GET | `/{task_id}/dependencies` | `DependencyResponse` | Get task dependencies |
| POST | `/{task_id}/dependencies` | `TaskResponse` | Add dependencies |
| DELETE | `/{task_id}/dependencies/{dep_id}` | `TaskResponse` | Remove dependency |
| GET | `/{task_id}/timeout` | `TimeoutResponse` | Get timeout settings |
| POST | `/{task_id}/timeout` | `TimeoutResponse` | Set timeout |
| POST | `/{task_id}/timeout/extend` | `TimeoutResponse` | Extend timeout |
| GET | `/{task_id}/context` | `TaskContextResponse` | Get full task context |
| GET | `/{task_id}/results` | `List[AgentResultDTO]` | Get task results |
| POST | `/{task_id}/results` | `AgentResultDTO` | Submit task result |

#### Key Pydantic Models

```python
class TaskResponse(BaseModel):
    id: str
    ticket_id: str
    spec_id: str
    phase_id: str
    description: str
    status: str  # pending, assigned, running, completed, failed, cancelled
    priority: int
    agent_id: Optional[str]
    dependencies: dict
    retry_count: int
    max_retries: int
    timeout_seconds: int
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

class DependencyResponse(BaseModel):
    task_id: str
    depends_on: List[str]
    blocked_by: List[str]
    all_dependencies_complete: bool

class TimeoutResponse(BaseModel):
    task_id: str
    timeout_seconds: int
    started_at: Optional[datetime]
    expires_at: Optional[datetime]
    remaining_seconds: Optional[int]
```

### 3.2 Tickets (`tickets.py`)

**Base Path:** `/api/v1/tickets`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| GET | `/` | `List[TicketResponse]` | List tickets with filters |
| POST | `/` | `TicketResponse` | Create new ticket |
| GET | `/{ticket_id}` | `TicketResponse` | Get ticket details |
| PATCH | `/{ticket_id}` | `TicketResponse` | Update ticket |
| DELETE | `/{ticket_id}` | `dict` | Delete ticket |
| POST | `/{ticket_id}/approve` | `TicketResponse` | Approve ticket for execution |
| POST | `/{ticket_id}/reject` | `TicketResponse` | Reject ticket |
| POST | `/{ticket_id}/pause` | `TicketResponse` | Pause ticket |
| POST | `/{ticket_id}/resume` | `TicketResponse` | Resume ticket |
| POST | `/{ticket_id}/cancel` | `TicketResponse` | Cancel ticket |
| GET | `/{ticket_id}/transitions` | `List[TransitionResponse]` | Get available transitions |
| POST | `/{ticket_id}/transition` | `TicketResponse` | Execute transition |
| GET | `/{ticket_id}/duplicates` | `DuplicateCheckResponse` | Check for duplicates |
| POST | `/{ticket_id}/link/{duplicate_id}` | `dict` | Link as duplicate |
| GET | `/{ticket_id}/commits` | `CommitListResponse` | Get linked commits |
| POST | `/{ticket_id}/commits/link` | `CommitResponse` | Link commit to ticket |
| GET | `/{ticket_id}/timeline` | `TicketTimelineResponse` | Get activity timeline |
| GET | `/{ticket_id}/reasoning` | `ReasoningChainResponse` | Get reasoning chain |

#### Key Pydantic Models

```python
class TicketResponse(BaseModel):
    id: str
    project_id: str
    spec_id: str
    title: str
    description: str
    phase_id: str
    status: str  # draft, pending_approval, approved, in_progress, paused, completed, cancelled
    priority: str  # low, medium, high, critical
    approval_status: str
    created_by: str
    assigned_to: Optional[str]
    created_at: datetime
    updated_at: datetime

class TransitionResponse(BaseModel):
    from_status: str
    to_status: str
    requires_approval: bool
    allowed_roles: List[str]

class DuplicateCheckResponse(BaseModel):
    ticket_id: str
    potential_duplicates: List[dict]
    similarity_scores: dict
```

### 3.3 Sandbox (`sandbox.py`)

**Base Path:** `/api/v1/sandbox`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| GET | `/events` | `List[SandboxEventResponse]` | List sandbox events |
| POST | `/events` | `SandboxEventResponse` | Create sandbox event |
| GET | `/events/{event_id}` | `SandboxEventResponse` | Get event details |
| GET | `/messages` | `List[SandboxMessageResponse]` | Get sandbox messages |
| POST | `/messages` | `SandboxMessageResponse` | Send message to sandbox |
| GET | `/queue` | `QueueStatusResponse` | Get message queue status |
| POST | `/queue/drain` | `dict` | Drain message queue |
| POST | `/sync` | `SyncResponse` | Sync spec to sandbox |
| GET | `/sync/status` | `SyncStatusResponse` | Get sync status |
| POST | `/lifecycle/start` | `LifecycleResponse` | Start sandbox lifecycle |
| POST | `/lifecycle/stop` | `LifecycleResponse` | Stop sandbox |
| GET | `/lifecycle/status` | `LifecycleStatusResponse` | Get lifecycle status |

### 3.4 Board (`board.py`)

**Base Path:** `/api/v1/board`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| GET | `/view` | `BoardViewResponse` | Get Kanban board view |
| POST | `/move` | `dict` | Move ticket to column |
| GET | `/stats` | `List[ColumnStatsResponse]` | Get column statistics |
| GET | `/wip-violations` | `List[WIPViolationResponse]` | Check WIP limit violations |
| POST | `/auto-transition/{ticket_id}` | `dict` | Auto-transition ticket |
| GET | `/column/{phase_id}` | `dict` | Get column for phase |

#### Key Pydantic Models

```python
class BoardViewResponse(BaseModel):
    columns: List[dict]  # Each with id, name, tickets, wip_limit

class ColumnStatsResponse(BaseModel):
    column_id: str
    name: str
    ticket_count: int
    wip_limit: Optional[int]
    utilization: Optional[float]
    wip_exceeded: bool

class WIPViolationResponse(BaseModel):
    column_id: str
    column_name: str
    wip_limit: int
    current_count: int
    excess: int
```

### 3.5 Graph (`graph.py`)

**Base Path:** `/api/v1`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| GET | `/dependency-graph/ticket/{ticket_id}` | `dict` | Get ticket dependency graph |
| GET | `/dependency-graph/project/{project_id}` | `dict` | Get project dependency graph |
| GET | `/dependency-graph/task/{task_id}/blocked` | `dict` | Get tasks blocked by this task |
| GET | `/dependency-graph/task/{task_id}/blocking` | `dict` | Get tasks blocking this task |

---

## 4. Agents & Monitoring

### Files Overview

| File | Lines | Description |
|------|-------|-------------|
| `agents.py` | 593 | Agent registration, health, heartbeats |
| `guardian.py` | 340 | Emergency interventions |
| `monitor.py` | 239 | System metrics and anomalies |
| `alerts.py` | 104 | Alert management |
| `watchdog.py` | 213 | Watchdog remediation |
| `validation.py` | 222 | Validation workflows |
| `reasoning.py` | 487 | Reasoning chain tracking |

### 4.1 Agents (`agents.py`)

**Base Path:** `/api/v1/agents`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| GET | `/` | `List[AgentResponse]` | List all agents |
| POST | `/register` | `AgentResponse` | Register new agent |
| GET | `/{agent_id}` | `AgentResponse` | Get agent details |
| PATCH | `/{agent_id}` | `AgentResponse` | Update agent |
| DELETE | `/{agent_id}` | `dict` | Unregister agent |
| POST | `/{agent_id}/heartbeat` | `HeartbeatResponse` | Agent heartbeat |
| GET | `/{agent_id}/health` | `HealthResponse` | Get agent health |
| GET | `/{agent_id}/tasks` | `List[TaskResponse]` | Get agent's tasks |
| POST | `/{agent_id}/tasks/claim` | `TaskResponse` | Claim next available task |
| POST | `/{agent_id}/tasks/{task_id}/release` | `dict` | Release claimed task |
| GET | `/search` | `List[AgentResponse]` | Search agents by criteria |
| GET | `/stats` | `AgentStatsResponse` | Get agent statistics |

#### Key Pydantic Models

```python
class AgentResponse(BaseModel):
    id: str
    agent_type: str  # worker, validator, orchestrator, guardian
    status: str  # idle, running, stale, error
    phase_id: Optional[str]
    current_task_id: Optional[str]
    registered_at: datetime
    last_heartbeat_at: Optional[datetime]
    capabilities: List[str]
    metadata: dict

class HeartbeatResponse(BaseModel):
    agent_id: str
    timestamp: datetime
    status: str
    current_task_id: Optional[str]
    task_progress: Optional[float]

class AgentStatsResponse(BaseModel):
    total_agents: int
    active_agents: int
    idle_agents: int
    stale_agents: int
    tasks_by_agent: dict
```

### 4.2 Guardian (`guardian.py`)

**Base Path:** `/api/v1/guardian`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| GET | `/interventions` | `List[InterventionResponse]` | List interventions |
| POST | `/intervene` | `InterventionResponse` | Create intervention |
| GET | `/interventions/{intervention_id}` | `InterventionResponse` | Get intervention details |
| POST | `/interventions/{intervention_id}/resolve` | `InterventionResponse` | Resolve intervention |
| POST | `/emergency-stop` | `dict` | Emergency stop all agents |
| POST | `/capacity/reallocate` | `CapacityResponse` | Reallocate capacity |
| GET | `/trajectory/{agent_id}` | `TrajectoryResponse` | Get agent trajectory |
| POST | `/trajectory/{agent_id}/analyze` | `TrajectoryAnalysisResponse` | Analyze trajectory |

### 4.3 Monitor (`monitor.py`)

**Base Path:** `/api/v1/monitor`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| GET | `/metrics` | `MetricsResponse` | Get system metrics |
| GET | `/metrics/{metric_name}` | `MetricDetailResponse` | Get specific metric |
| GET | `/anomalies` | `List[AnomalyResponse]` | List detected anomalies |
| GET | `/dashboard` | `DashboardResponse` | Get dashboard summary |
| GET | `/health` | `SystemHealthResponse` | Get system health |
| GET | `/agents/status` | `AgentStatusSummary` | Get agents status summary |
| GET | `/tasks/status` | `TaskStatusSummary` | Get tasks status summary |

### 4.4 Alerts (`alerts.py`)

**Base Path:** `/api/v1/alerts`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| GET | `/` | `List[AlertResponse]` | List alerts |
| POST | `/` | `AlertResponse` | Create alert |
| GET | `/{alert_id}` | `AlertResponse` | Get alert details |
| POST | `/{alert_id}/acknowledge` | `AlertResponse` | Acknowledge alert |
| POST | `/{alert_id}/resolve` | `AlertResponse` | Resolve alert |
| DELETE | `/{alert_id}` | `dict` | Delete alert |
| GET | `/unacknowledged` | `List[AlertResponse]` | Get unacknowledged alerts |

### 4.5 Watchdog (`watchdog.py`)

**Base Path:** `/api/v1/watchdog`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| GET | `/monitor-status` | `MonitorStatusResponse` | Get monitor agent status |
| POST | `/execute-remediation` | `WatchdogActionDTO` | Execute remediation |
| GET | `/remediation-history` | `List[WatchdogActionDTO]` | Get remediation history |
| GET | `/policies` | `dict` | Get remediation policies |

### 4.6 Validation (`validation.py`)

**Base Path:** `/api/v1/validation`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| POST | `/give_review` | `GiveReviewResponse` | Submit validation review |
| POST | `/spawn_validator` | `SpawnValidatorResponse` | Spawn validator agent |
| POST | `/send_feedback` | `SendFeedbackResponse` | Send feedback to agent |
| GET | `/status` | `ValidationStatusResponse` | Get validation status |

#### Key Pydantic Models

```python
class GiveReviewRequest(BaseModel):
    task_id: str
    validator_agent_id: str
    validation_passed: bool
    feedback: str
    evidence: Optional[dict]
    recommendations: Optional[List[str]]

class ValidationStatusResponse(BaseModel):
    task_id: str
    state: str
    iteration: int
    review_done: bool
    last_feedback: Optional[str]
```

### 4.7 Reasoning (`reasoning.py`)

**Base Path:** `/api/v1/reasoning`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| GET | `/{entity_type}/{entity_id}` | `ReasoningChainResponse` | Get reasoning chain |
| POST | `/{entity_type}/{entity_id}/events` | `ReasoningEvent` | Add reasoning event |
| GET | `/{entity_type}/{entity_id}/events/{event_id}` | `ReasoningEvent` | Get specific event |
| DELETE | `/{entity_type}/{entity_id}/events/{event_id}` | `dict` | Delete event |
| GET | `/types` | `dict` | Get available event types |

#### Key Pydantic Models

```python
class ReasoningEvent(BaseModel):
    id: str
    timestamp: datetime
    type: str  # ticket_created, task_spawned, discovery, agent_decision, etc.
    title: str
    description: str
    agent: Optional[str]
    details: Optional[EventDetails]
    evidence: List[Evidence]
    decision: Optional[Decision]

class ReasoningChainResponse(BaseModel):
    entity_type: str
    entity_id: str
    events: List[ReasoningEvent]
    total_count: int
    stats: dict
```

---

## 5. GitHub Integration

### Files Overview

| File | Lines | Description |
|------|-------|-------------|
| `github.py` | 213 | GitHub repository connections |
| `github_repos.py` | 1,034 | GitHub API operations |
| `commits.py` | 337 | Commit tracking |
| `branch_workflow.py` | 277 | Branch lifecycle management |

### 5.1 GitHub (`github.py`)

**Base Path:** `/api/v1/github`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| GET | `/auth/url` | `GitHubAuthUrlResponse` | Get GitHub auth URL |
| POST | `/auth/callback` | `GitHubConnectionResponse` | Handle OAuth callback |
| GET | `/connection` | `GitHubConnectionResponse` | Get connection status |
| DELETE | `/connection` | `dict` | Disconnect GitHub |
| POST | `/webhook` | `dict` | Receive GitHub webhook |
| GET | `/webhook/events` | `List[WebhookEventResponse]` | List recent webhook events |

### 5.2 GitHub Repos (`github_repos.py`)

**Base Path:** `/api/v1/github/repos`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| GET | `/` | `List[RepositoryResponse]` | List connected repositories |
| POST | `/connect` | `RepositoryResponse` | Connect repository |
| GET | `/{owner}/{repo}` | `RepositoryDetailResponse` | Get repository details |
| GET | `/{owner}/{repo}/branches` | `List[BranchResponse]` | List branches |
| POST | `/{owner}/{repo}/branches` | `BranchResponse` | Create branch |
| GET | `/{owner}/{repo}/pulls` | `List[PullRequestResponse]` | List pull requests |
| POST | `/{owner}/{repo}/pulls` | `PullRequestResponse` | Create pull request |
| GET | `/{owner}/{repo}/files` | `List[FileResponse]` | List repository files |
| GET | `/{owner}/{repo}/files/content` | `FileContentResponse` | Get file content |
| GET | `/{owner}/{repo}/commits` | `List[CommitResponse]` | List commits |
| GET | `/{owner}/{repo}/issues` | `List[IssueResponse]` | List issues |
| POST | `/{owner}/{repo}/sync` | `SyncStatusResponse` | Sync repository |
| GET | `/{owner}/{repo}/tree` | `TreeResponse` | Get repository tree |

### 5.3 Commits (`commits.py`)

**Base Path:** `/api/v1/commits`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| GET | `/{commit_sha}` | `CommitResponse` | Get commit details |
| GET | `/ticket/{ticket_id}` | `CommitListResponse` | Get ticket commits |
| GET | `/agent/{agent_id}` | `CommitListResponse` | Get agent commits |
| POST | `/ticket/{ticket_id}/link` | `CommitResponse` | Link commit to ticket |
| GET | `/{commit_sha}/diff` | `CommitDiffResponse` | Get commit diff |

### 5.4 Branch Workflow (`branch_workflow.py`)

**Base Path:** `/api/v1/branch-workflow`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| POST | `/start` | `StartWorkResponse` | Create feature branch |
| POST | `/finish` | `FinishWorkResponse` | Create pull request |
| POST | `/merge` | `MergeWorkResponse` | Merge pull request |
| POST | `/status` | `BranchStatusResponse` | Get branch status |

---

## 6. Billing & Usage

### Files Overview

| File | Lines | Description |
|------|-------|-------------|
| `billing.py` | 1,523 | Stripe integration, subscriptions |
| `costs.py` | 260 | Cost tracking and forecasting |

### 6.1 Billing (`billing.py`)

**Base Path:** `/api/v1/billing`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| GET | `/subscription` | `SubscriptionResponse` | Get current subscription |
| POST | `/checkout` | `CheckoutResponse` | Create checkout session |
| POST | `/portal` | `PortalResponse` | Create customer portal |
| GET | `/invoices` | `List[InvoiceResponse]` | List invoices |
| GET | `/payment-methods` | `List[PaymentMethodResponse]` | List payment methods |
| POST | `/payment-methods` | `PaymentMethodResponse` | Add payment method |
| DELETE | `/payment-methods/{id}` | `dict` | Remove payment method |
| POST | `/webhooks/stripe` | `dict` | Stripe webhook handler |
| GET | `/usage` | `UsageResponse` | Get usage statistics |
| GET | `/tiers` | `List[TierResponse]` | List available tiers |
| POST | `/promo/apply` | `SubscriptionResponse` | Apply promo code |
| GET | `/history` | `List[BillingHistoryResponse]` | Get billing history |

#### Key Pydantic Models

```python
class SubscriptionResponse(BaseModel):
    id: str
    organization_id: str
    tier: str
    status: str  # active, trialing, past_due, cancelled
    current_period_start: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    usage_limits: dict

class CheckoutResponse(BaseModel):
    session_id: str
    url: str

class UsageResponse(BaseModel):
    organization_id: str
    period_start: datetime
    period_end: datetime
    api_calls: int
    compute_minutes: int
    storage_gb: float
    cost_usd: float
```

### 6.2 Costs (`costs.py`)

**Base Path:** `/api/v1/costs`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| GET | `/records` | `List[CostRecordResponse]` | List cost records |
| GET | `/summary` | `CostSummaryResponse` | Get cost summary |
| GET | `/budgets` | `List[BudgetResponse]` | List budgets |
| POST | `/budgets` | `BudgetResponse` | Create budget |
| GET | `/budgets/check` | `BudgetCheckResponse` | Check budget status |
| POST | `/forecast` | `ForecastResponse` | Forecast costs |

---

## 7. Memory & Learning

### Files Overview

| File | Lines | Description |
|------|-------|-------------|
| `memory.py` | 468 | Task execution memory and patterns |
| `quality.py` | 170 | Quality gates and metrics |
| `diagnostic.py` | 223 | Diagnostic workflows |
| `results.py` | 344 | Result submission |

### 7.1 Memory (`memory.py`)

**Base Path:** `/api/v1/memory`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| POST | `/store` | `dict` | Store task execution |
| POST | `/search` | `List[SimilarTaskResponse]` | Search similar tasks |
| GET | `/tasks/{task_id}/context` | `TaskContextResponse` | Get task context |
| GET | `/patterns` | `List[PatternResponse]` | List learned patterns |
| POST | `/patterns/extract` | `dict` | Extract pattern |
| POST | `/patterns/{pattern_id}/feedback` | `dict` | Pattern feedback |
| POST | `/complete-task` | `CompleteTaskResponse` | Execute ACE workflow |

### 7.2 Quality (`quality.py`)

**Base Path:** `/api/v1/quality`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| POST | `/metrics/record` | `dict` | Record quality metric |
| GET | `/metrics/{task_id}` | `dict` | Get task metrics |
| POST | `/predict` | `QualityPredictionResponse` | Predict quality |
| GET | `/trends` | `dict` | Get quality trends |
| POST | `/gates/{gate_id}/evaluate` | `dict` | Evaluate quality gate |

### 7.3 Diagnostic (`diagnostic.py`)

**Base Path:** `/api/v1/diagnostic`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| GET | `/stuck-workflows` | `dict` | List stuck workflows |
| GET | `/runs` | `List[DiagnosticRunDTO]` | Get diagnostic runs |
| POST | `/trigger/{workflow_id}` | `DiagnosticRunDTO` | Trigger diagnostic |
| GET | `/runs/{run_id}` | `DiagnosticRunDTO` | Get run details |

### 7.4 Results (`results.py`)

**Base Path:** `/api/v1/results`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| POST | `/report_results` | `AgentResultDTO` | Submit task results |
| POST | `/submit_result` | `SubmitResultResponse` | Submit workflow result |
| POST | `/submit_result_validation` | `dict` | Validate workflow result |
| GET | `/workflows/{workflow_id}/results` | `List[WorkflowResultDTO]` | Get workflow results |
| GET | `/tasks/{task_id}/results` | `List[AgentResultDTO]` | Get task results |

---

## 8. System & Utilities

### Files Overview

| File | Lines | Description |
|------|-------|-------------|
| `events.py` | 315 | WebSocket event streaming |
| `mcp.py` | 429 | MCP tool management |
| `analytics_proxy.py` | 260 | Analytics proxy for ad blocker bypass |
| `debug.py` | 578 | Debug endpoints |
| `preview.py` | 226 | Preview sessions |
| `collaboration.py` | 327 | Agent collaboration |

### 8.1 Events (`events.py`)

**Base Path:** `/api/v1/events`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| GET | `/ws` | WebSocket | WebSocket event stream |
| GET | `/` | `List[EventResponse]` | List recent events |
| POST | `/publish` | `dict` | Publish event (internal) |
| GET | `/subscriptions` | `List[SubscriptionResponse]` | Get subscriptions |
| POST | `/subscribe` | `SubscriptionResponse` | Subscribe to events |
| DELETE | `/subscribe/{sub_id}` | `dict` | Unsubscribe |

### 8.2 MCP (`mcp.py`)

**Base Path:** `/api/v1/mcp`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| GET | `/tools` | `List[ToolResponse]` | List registered tools |
| POST | `/tools/register` | `ToolResponse` | Register tool |
| GET | `/tools/{tool_id}` | `ToolResponse` | Get tool details |
| DELETE | `/tools/{tool_id}` | `dict` | Unregister tool |
| POST | `/invoke` | `ToolInvocationResponse` | Invoke tool |
| GET | `/invocations` | `List[InvocationResponse]` | List invocations |
| GET | `/invocations/{invocation_id}` | `InvocationResponse` | Get invocation status |

### 8.3 Analytics Proxy (`analytics_proxy.py`)

**Base Path:** `/api/v1/analytics`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| POST | `/ingest` | `dict` | Ingest analytics event |
| GET | `/config` | `AnalyticsConfigResponse` | Get analytics config |
| POST | `/config` | `AnalyticsConfigResponse` | Update config |

### 8.4 Debug (`debug.py`)

**Base Path:** `/api/v1/debug`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| GET | `/tasks/stats` | `TaskQueueStats` | Get task queue stats |
| GET | `/tasks/pending` | `dict` | Get pending tasks |
| GET | `/tasks/running/{org_id}` | `dict` | Get running tasks by org |
| GET | `/agents/{org_id}/stats` | `OrgAgentStats` | Get agent stats |
| GET | `/tickets/{ticket_id}/phase-gate-status` | `PhaseGateStatus` | Get phase gate status |
| GET | `/tickets/{ticket_id}/tasks-by-phase` | `dict` | Get tasks by phase |
| GET | `/event-bus/status` | `EventBusStatus` | Get event bus status |
| POST | `/event-bus/test-publish` | `dict` | Test event publish |
| GET | `/phase-progression/status` | `dict` | Get phase progression status |
| GET | `/phase-progression/initial-tasks` | `dict` | Get initial tasks config |
| GET | `/health` | `SystemHealthResponse` | Get system health |
| GET | `/tasks/{task_id}/context` | `dict` | Inspect task context |
| GET | `/branch-strategy/{spec_id}` | `dict` | Preview branch strategy |

### 8.5 Preview (`preview.py`)

**Base Path:** `/api/v1/preview`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| POST | `/` | `PreviewResponse` | Create preview |
| GET | `/{preview_id}` | `PreviewResponse` | Get preview |
| DELETE | `/{preview_id}` | `PreviewResponse` | Stop preview |
| GET | `/sandbox/{sandbox_id}` | `PreviewResponse` | Get by sandbox |
| POST | `/notify` | `dict` | Worker status callback |

### 8.6 Collaboration (`collaboration.py`)

**Base Path:** `/api/v1/collaboration`

#### Endpoints

| Method | Path | Response Model | Description |
|--------|------|----------------|-------------|
| POST | `/threads` | `ThreadDTO` | Create thread |
| GET | `/threads` | `List[ThreadDTO]` | List threads |
| POST | `/threads/{thread_id}/close` | `dict` | Close thread |
| POST | `/messages` | `MessageDTO` | Send message |
| GET | `/threads/{thread_id}/messages` | `List[MessageDTO]` | Get messages |
| POST | `/messages/{message_id}/read` | `dict` | Mark read |
| POST | `/handoff/request` | `HandoffResponse` | Request handoff |
| POST | `/handoff/{thread_id}/accept` | `MessageDTO` | Accept handoff |
| POST | `/handoff/{thread_id}/decline` | `MessageDTO` | Decline handoff |

---

## Summary Statistics

### By Domain

| Domain | Files | Endpoints | Lines of Code |
|--------|-------|-----------|---------------|
| Authentication & Users | 4 | 45+ | 2,545 |
| Projects & Specs | 6 | 60+ | 3,935 |
| Task Management | 5 | 55+ | 4,352 |
| Agents & Monitoring | 7 | 50+ | 2,198 |
| GitHub Integration | 4 | 35+ | 1,861 |
| Billing & Usage | 2 | 20+ | 1,783 |
| Memory & Learning | 4 | 25+ | 1,205 |
| System & Utilities | 6 | 35+ | 2,136 |
| **TOTAL** | **38** | **325+** | **20,015** |

### Common Patterns

All routes follow these patterns:

1. **FastAPI Router**: `router = APIRouter()` with optional prefix
2. **Pydantic Models**: Request/Response models with `ConfigDict`
3. **Dependency Injection**: `Depends(get_service)` pattern
4. **Async Support**: Most endpoints use `async def`
5. **Error Handling**: `HTTPException` with appropriate status codes
6. **Response Models**: Explicit `response_model` in decorators

### File Locations

All route files are located in:
```
backend/omoi_os/api/routes/
```

---

*Document generated from comprehensive analysis of 39 API route files*
