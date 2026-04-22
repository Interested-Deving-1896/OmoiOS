# OmoiOS Agent Execution & Monitoring System — Frontend Design

## Overview

The OmoiOS Agent Execution and Monitoring system provides real-time visibility into autonomous AI agent operations. The frontend enables users to visualize agent execution, monitor system health, track reasoning chains, and manage the lifecycle of agent swarms running in isolated sandboxes.

## Core Systems

| System | Purpose | Key Components |
|--------|---------|----------------|
| **Agent Management** | Register, monitor, and control agents | Agent list, detail views, health metrics |
| **Guardian Monitoring** | Trajectory analysis and drift detection | Trajectory dashboard, alignment scoring |
| **Conductor** | System-wide coherence and duplicate detection | Intervention history, anomaly tracking |
| **Health Check** | Real-time system health monitoring | Health dashboard, service status |
| **Reasoning Display** | Chain-of-thought visualization | Diagnostic timeline, evidence display |
| **Event System** | Real-time WebSocket event streaming | Live updates, event filtering |
| **Dependency Graph** | Task DAG visualization | React Flow graph, node interactions |

---

## 1. Agent Execution Visualization

### 1.1 Agent List Page (`/agents`)

**Purpose**: Overview of all registered agents with filtering and statistics.

**Key Features**:
- **Metrics Cards**: Total agents, active (busy/working), idle, healthy, stale counts
- **Filterable Grid**: Search by agent ID, type, or capabilities; filter by status
- **Status Indicators**: Visual badges with icons (idle, busy, working, completed, failed, timeout, maintenance)
- **Health Indicators**: Heart icons showing healthy/degraded/unhealthy states
- **Quick Actions**: Links to agent details and workspace terminal

**Hook Usage**:
```typescript
const { data: agents, isLoading } = useAgents();
const { data: statistics } = useAgentStatistics();
```

**Status Configuration**:
| Status | Icon | Color | Animation |
|--------|------|-------|-----------|
| idle | Clock | secondary | None |
| busy/working | Loader2 | warning | animate-spin |
| completed | CheckCircle | success | None |
| failed | XCircle | destructive | None |
| timeout | AlertCircle | warning | None |
| maintenance | AlertCircle | secondary | None |

### 1.2 Agent Detail Page (`/agents/[agentId]`)

**Purpose**: Deep-dive view into a single agent's configuration, health, and activity.

**Layout**: Two-column layout with main content and sidebar.

**Tabs**:
1. **Details**: Agent ID, type, phase, status, health, capabilities, last heartbeat
2. **Health**: Health status, last heartbeat, seconds since heartbeat, stale flag
3. **Activity**: Recent activity log (placeholder for future implementation)

**Sidebar**:
- Quick status overview
- Command input to send messages to agent

**Hook Usage**:
```typescript
const { data: agent } = useAgent(agentId);
const { data: health } = useAgentHealth(agentId);
```

### 1.3 Agent Workspace (`/agents/[agentId]/workspace`)

**Purpose**: Terminal-like interface for direct agent interaction.

**Features**:
- xterm.js-based terminal emulation
- Real-time command execution
- Output streaming from sandbox

---

## 2. Monitoring Dashboard

### 2.1 System Health Overview (`/health`)

**Purpose**: Central dashboard for Guardian, Conductor, and system health monitoring.

**Metrics Cards**:
| Metric | Source | Refresh Interval |
|--------|--------|------------------|
| System Status | `useSystemHealth()` | 30s |
| Active Agents | `useDashboardSummary()` | 15s |
| Pending Tasks | `useDashboardSummary()` | 15s |
| Open Alerts | `useAnomalies()` | 60s |

**Service Status Section**:
Displays status for Guardian, System, and Alerts services with:
- Service name and icon
- Current status (healthy/degraded/warning)
- Status message
- Color-coded badges

**Recent Anomalies**:
- Lists last 5 anomalies from 24h window
- Shows anomaly type, description, severity
- Acknowledgment status with color coding

**Hook Usage**:
```typescript
const { data: health } = useSystemHealth();
const { data: dashboard } = useDashboardSummary();
const { data: anomalies } = useAnomalies({ hours: 24 });
```

### 2.2 Trajectory Analysis (`/health/trajectories`)

**Purpose**: Guardian's trajectory monitoring with alignment scoring per agent.

**Features**:
- Table view of all agent trajectories
- Alignment status: aligned, warning, drifting, stuck
- Health indicators per agent
- Search and filter by status
- Direct navigation to agent detail

**Status Mapping**:
| Agent Status | Trajectory Status |
|--------------|-------------------|
| active/idle | aligned |
| busy | drifting |
| error/offline | stuck |
| default | warning |

**Hook Usage**:
```typescript
const { data: agents } = useAgents();
const { data: healthData } = useAgentsHealth();
```

### 2.3 Intervention History (`/health/interventions`)

**Purpose**: Track Guardian steering actions and constraint enforcement.

**Features**:
- Stats cards: Total, High, Medium, Low severity anomalies
- Tabbed view: All, Pending, Acknowledged, High severity
- Anomaly details: metric name, type, description, baseline/observed values
- Deviation percentage calculation
- Acknowledge action for pending anomalies

**Hook Usage**:
```typescript
const { data: anomalies } = useAnomalies({ hours: 24 });
const acknowledgeMutation = useAcknowledgeAnomaly();
```

---

## 3. Reasoning Display (Chain-of-Thought)

### 3.1 Diagnostic Reasoning Page (`/diagnostic/[entityType]/[entityId]`)

**Purpose**: Complete timeline visualization of agent decisions, discoveries, and reasoning chains.

**Layout**: Full-height scrollable timeline with collapsible events.

**Event Types**:
| Type | Icon | Color | Description |
|------|------|-------|-------------|
| ticket_created | Plus | blue | New ticket creation |
| task_spawned | Zap | purple | Task generation |
| discovery | Lightbulb | yellow | New findings |
| agent_decision | Brain | green | Agent reasoning |
| blocking_added | AlertTriangle | orange | Dependency blocking |
| code_change | GitBranch | cyan | Code commits |
| error | AlertCircle | red | Error events |

**Event Structure**:
```typescript
interface ReasoningEvent {
  id: string;
  timestamp: string;
  type: string;
  title: string;
  description: string;
  agent: string | null;
  details: EventDetails | null;
  evidence: Evidence[];
  decision: Decision | null;
}
```

**Evidence Types**:
- error, log, code, doc, requirement, test, coverage, stats

**Decision Types**:
- complete (green) - Task completion
- block (destructive) - Blocking action
- implement (blue) - Implementation decision

**Features**:
- Collapsible event cards with expand/collapse all
- Search filtering by title/description
- Event type filtering
- Timeline visualization with connecting lines
- Evidence display with external links
- Alternative options display (rejected choices)
- Confidence scoring visualization
- Code change stats (lines added/removed, files changed, test results)

**Hook Usage**:
```typescript
const { data: chainData } = useReasoningChain(entityType, entityId, {
  event_type: typeFilter !== "all" ? typeFilter : undefined,
});
```

---

## 4. Real-Time Event System

### 4.1 WebSocket Event Hook (`useEvents`)

**Purpose**: Subscribe to real-time system events via WebSocket.

**Connection URL**: `ws://api.omoios.dev/api/v1/ws/events`

**Authentication**: JWT token passed as query parameter.

**Event Structure**:
```typescript
interface SystemEvent {
  event_type: string;
  entity_type: string;
  entity_id: string;
  payload: Record<string, unknown>;
}
```

**Features**:
- Auto-connect on mount (configurable)
- Automatic reconnection with 5s backoff
- Event filtering by type, entity type, entity ID
- Event buffer with max size (default 100 events)
- Connection state tracking (connected/connecting/error)
- Manual connect/disconnect controls
- Dynamic filter updates

**Hook API**:
```typescript
const {
  events,           // SystemEvent[] - buffered events
  isConnected,    // boolean
  isConnecting,   // boolean
  error,           // string | null
  connect,        // () => void
  disconnect,     // () => void
  clearEvents,    // () => void
  updateFilters,  // (filters) => void
} = useEvents({
  filters?: EventFilters;
  onEvent?: (event) => void;
  enabled?: boolean;
  maxEvents?: number;
});
```

**Specialized Hooks**:
- `useEntityEvents(entityType, entityId)` - Filter to specific entity
- `useEventTypes(eventTypes[])` - Filter to specific event types

**Message Handling**:
- Ignores ping messages
- Ignores subscription confirmations
- Parses JSON payloads
- Maintains LIFO event buffer
- Triggers optional callback per event

---

## 5. Graph/Dependency Visualization

### 5.1 Project Dependency Graph (`/graph/[projectId]`)

**Purpose**: Visualize task dependencies and ticket relationships using React Flow.

**Node Types**:
| Type | Description | Visual |
|------|-------------|--------|
| ticket | Parent ticket | Badge with ID, status icon |
| task | Individual task | Same styling as tickets |
| discovery | Discovery events | Same styling with type indicator |

**Status Visual Configuration**:
```typescript
const statusConfig = {
  pending:    { color: "#9ca3af", bgColor: "#f3f4f6", icon: Clock },
  in_progress:{ color: "#3b82f6", bgColor: "#dbeafe", icon: Loader2 },
  completed:  { color: "#22c55e", bgColor: "#dcfce7", icon: CheckCircle },
  blocked:    { color: "#ef4444", bgColor: "#fee2e2", icon: AlertCircle },
};
```

**Priority Colors** (left border):
- critical: #dc2626 (red)
- high: #ea580c (orange)
- medium: #ca8a04 (yellow)
- low: #6b7280 (gray)

**Edge Styling**:
- Default: Gray, 2px stroke
- Blocked: Red, animated
- Ticket blocking: Amber, 3px, dashed, "blocks" label

**Features**:
- Dagre automatic layout (TB or LR direction)
- Node search filtering
- Status filtering
- Show/hide discoveries toggle
- Zoom controls
- Node click navigation to tickets/tasks
- Legend panel (status + priority)
- Info panel (stats overlay)
- Discovery overlay panel
- Ticket threading panel

**Hook Usage**:
```typescript
const { data: graphData } = useProjectDependencyGraph(projectId, {
  includeResolved: true,
});
```

**Custom Node Component**: `TicketNode`
- Tooltip on hover showing full details
- Handles for connection points
- Selection state styling
- Priority color coding via left border

---

## 6. Hook Patterns by Domain

### 6.1 Agent Hooks (`useAgents.ts`)

| Hook | Purpose | Query Key | Refetch |
|------|---------|-----------|---------|
| `useAgents()` | List all agents | `["agents", "list"]` | On mutation |
| `useAgent(id)` | Single agent | `["agents", "detail", id]` | - |
| `useRegisterAgent()` | Register new | - | Invalidates lists |
| `useUpdateAgent()` | Update agent | - | Invalidates detail |
| `useToggleAgentAvailability()` | Toggle availability | - | Invalidates detail |
| `useSearchAgents(params)` | Search by capabilities | `["agents", "search", params]` | - |
| `useAgentsHealth()` | All agents health | `["agents", "health", "all"]` | 30s |
| `useAgentStatistics()` | Aggregated stats | `["agents", "statistics"]` | 30s |
| `useAgentHealth(id)` | Single agent health | `["agents", "health", id]` | 15s |
| `useStaleAgents()` | Find stale agents | `["agents", "stale"]` | 60s |
| `useCleanupStaleAgents()` | Cleanup mutation | - | Invalidates all |

### 6.2 Monitor Hooks (`useMonitor.ts`)

| Hook | Purpose | Query Key | Refetch |
|------|---------|-----------|---------|
| `useMetrics(phaseId?)` | System metrics | `["monitor", "metrics", phaseId]` | 30s |
| `useAnomalies(params?)` | Recent anomalies | `["monitor", "anomalies", params]` | 60s |
| `useDashboardSummary()` | Dashboard stats | `["monitor", "dashboard"]` | 15s |
| `useMonitoringStatus()` | Loop status | `["monitor", "status"]` | 30s |
| `useSystemHealth()` | System health | `["monitor", "health"]` | 30s |
| `useAcknowledgeAnomaly()` | Acknowledge | - | Invalidates anomalies |
| `useAnalyzeAgentTrajectory()` | Manual analysis | - | - |
| `useTriggerEmergencyAnalysis()` | Emergency analysis | - | - |

### 6.3 Reasoning Hooks (`useReasoning.ts`)

| Hook | Purpose | Query Key | Notes |
|------|---------|-----------|-------|
| `useReasoningChain(type, id, params?)` | Get chain | `["reasoning", "chain", type, id]` | Filterable by event_type |
| `useReasoningEvent(type, id, eventId)` | Single event | `["reasoning", "event", ...]` | - |
| `useEventTypes()` | Type config | `["reasoning", "types"]` | 1h stale time |
| `useAddReasoningEvent(type, id)` | Add event | - | Invalidates chain |
| `useDeleteReasoningEvent(type, id)` | Delete event | - | Invalidates chain |

### 6.4 Event Hooks (`useEvents.ts`)

| Hook | Purpose | Connection |
|------|---------|--------------|
| `useEvents(options)` | Generic event subscription | WebSocket |
| `useEntityEvents(type, id)` | Entity-scoped events | WebSocket with filters |
| `useEventTypes(types[])` | Type-filtered events | WebSocket with filters |

### 6.5 Graph Hooks (`useGraph.ts`)

| Hook | Purpose | Query Key |
|------|---------|-----------|
| `useProjectDependencyGraph(id, params?)` | Project graph | `["graph", "project", id]` |
| `useTicketDependencyGraph(id, params?)` | Ticket graph | `["graph", "ticket", id]` |
| `useBlockedTasks(taskId)` | Blocked by task | `["graph", "blocked", taskId]` |
| `useBlockingTasks(taskId)` | Blocking task | `["graph", "blocking", taskId]` |

### 6.6 Explore Hooks (`useExplore.ts`)

| Hook | Purpose | Query Key |
|------|---------|-----------|
| `useConversations(projectId)` | List conversations | `["explore", "conversations", projectId]` |
| `useConversation(projectId, id)` | Single conversation | `["explore", "conversation", ...]` |
| `useCreateConversation(projectId)` | Create mutation | - |
| `useSendMessage(projectId, id)` | Send message | - |
| `useDeleteConversation(projectId)` | Delete mutation | - |
| `useProjectFiles(projectId)` | File listing | `["explore", "files", projectId]` |
| `useSuggestions(projectId, context?)` | AI suggestions | `["explore", "suggestions", ...]` |

### 6.7 Commit Hooks (`useCommits.ts`)

| Hook | Purpose | Query Key |
|------|---------|-----------|
| `useCommit(sha)` | Single commit | `["commits", "detail", sha]` |
| `useTicketCommits(ticketId, params?)` | Ticket commits | `["commits", "ticket", ticketId]` |
| `useAgentCommits(agentId, params?)` | Agent commits | `["commits", "agent", agentId]` |
| `useCommitDiff(sha, filePath?)` | Commit diff | `["commits", "detail", sha, "diff"]` |
| `useLinkCommit()` | Link mutation | - |

---

## 7. API Client Function Inventory

### 7.1 Agents API (`lib/api/agents.ts`)

| Function | Method | Endpoint | Params |
|----------|--------|----------|--------|
| `listAgents()` | GET | `/api/v1/agents` | - |
| `getAgent(id)` | GET | `/api/v1/agents/${id}` | - |
| `registerAgent(data)` | POST | `/api/v1/agents/register` | AgentRegisterRequest |
| `updateAgent(id, data)` | PATCH | `/api/v1/agents/${id}` | AgentUpdateRequest |
| `toggleAgentAvailability(id, available)` | POST | `/api/v1/agents/${id}/availability` | boolean |
| `searchAgents(params?)` | GET | `/api/v1/agents/search` | capabilities, phase_id, agent_type, limit |
| `getAgentsHealth(timeout?)` | GET | `/api/v1/agents/health` | timeout_seconds |
| `getAgentStatistics()` | GET | `/api/v1/agents/statistics` | - |
| `getAgentHealth(id, timeout?)` | GET | `/api/v1/agents/${id}/health` | timeout_seconds |
| `getStaleAgents(timeout?)` | GET | `/api/v1/agents/stale` | timeout_seconds |
| `cleanupStaleAgents(params?)` | POST | `/api/v1/agents/cleanup-stale` | timeout_seconds, mark_as |

### 7.2 Monitor API (`lib/api/monitor.ts`)

| Function | Method | Endpoint | Params |
|----------|--------|----------|--------|
| `getMetrics(phaseId?)` | GET | `/api/v1/monitor/metrics` | phase_id |
| `getAnomalies(params?)` | GET | `/api/v1/monitor/anomalies` | hours, severity |
| `acknowledgeAnomaly(id)` | POST | `/api/v1/monitor/anomalies/${id}/acknowledge` | - |
| `getDashboardSummary()` | GET | `/api/v1/monitor/dashboard` | - |
| `getMonitoringStatus()` | GET | `/api/v1/monitor/intelligent/status` | - |
| `getSystemHealth()` | GET | `/api/v1/monitor/intelligent/health` | - |
| `analyzeAgentTrajectory(id, force?)` | POST | `/api/v1/monitor/intelligent/analyze/${id}` | force |
| `triggerEmergencyAnalysis(ids[])` | POST | `/api/v1/monitor/intelligent/emergency` | agentIds |

### 7.3 Reasoning API (`lib/api/reasoning.ts`)

| Function | Method | Endpoint | Params |
|----------|--------|----------|--------|
| `getReasoningChain(type, id, params?)` | GET | `/api/v1/reasoning/${type}/${id}` | event_type, limit |
| `addReasoningEvent(type, id, event)` | POST | `/api/v1/reasoning/${type}/${id}/events` | ReasoningEventCreate |
| `getReasoningEvent(type, id, eventId)` | GET | `/api/v1/reasoning/${type}/${id}/events/${eventId}` | - |
| `deleteReasoningEvent(type, id, eventId)` | DELETE | `/api/v1/reasoning/${type}/${id}/events/${eventId}` | - |
| `getEventTypes()` | GET | `/api/v1/reasoning/types` | - |

### 7.4 Graph API (`lib/api/graph.ts`)

| Function | Method | Endpoint | Params |
|----------|--------|----------|--------|
| `getProjectDependencyGraph(id, params?)` | GET | `/api/v1/graph/dependency-graph/project/${id}` | include_resolved |
| `getTicketDependencyGraph(id, params?)` | GET | `/api/v1/graph/dependency-graph/ticket/${id}` | include_resolved, include_discoveries |
| `getBlockedTasks(taskId)` | GET | `/api/v1/graph/dependency-graph/task/${taskId}/blocked` | - |
| `getBlockingTasks(taskId)` | GET | `/api/v1/graph/dependency-graph/task/${taskId}/blocking` | - |

### 7.5 Explore API (`lib/api/explore.ts`)

| Function | Method | Endpoint | Params |
|----------|--------|----------|--------|
| `listConversations(projectId, limit?)` | GET | `/api/v1/explore/project/${id}/conversations` | limit |
| `createConversation(projectId)` | POST | `/api/v1/explore/project/${id}/conversations` | - |
| `getConversation(projectId, id)` | GET | `/api/v1/explore/project/${id}/conversations/${id}` | - |
| `sendMessage(projectId, id, content)` | POST | `/api/v1/explore/project/${id}/conversations/${id}/messages` | content |
| `deleteConversation(projectId, id)` | DELETE | `/api/v1/explore/project/${id}/conversations/${id}` | - |
| `getProjectFiles(projectId)` | GET | `/api/v1/explore/project/${id}/files` | - |
| `getSuggestions(projectId, context?)` | GET | `/api/v1/explore/project/${id}/suggestions` | context |

### 7.6 Commits API (`lib/api/commits.ts`)

| Function | Method | Endpoint | Params |
|----------|--------|----------|--------|
| `getCommit(sha)` | GET | `/api/v1/commits/${sha}` | - |
| `getTicketCommits(ticketId, params?)` | GET | `/api/v1/commits/ticket/${ticketId}` | limit, offset |
| `getAgentCommits(agentId, params?)` | GET | `/api/v1/commits/agent/${agentId}` | limit, offset |
| `linkCommitToTicket(ticketId, data)` | POST | `/api/v1/commits/ticket/${ticketId}/link` | LinkCommitRequest |
| `getCommitDiff(sha, filePath?)` | GET | `/api/v1/commits/${sha}/diff` | file_path |

---

## 8. Data Types Reference

### 8.1 Core Agent Types

```typescript
interface Agent {
  agent_id: string;
  agent_type: string;
  phase_id: string | null;
  status: string;  // idle, busy, working, completed, failed, timeout, maintenance
  capabilities: string[];
  capacity: number;
  health_status: string;  // healthy, degraded, unhealthy
  tags: string[];
  last_heartbeat: string | null;
  created_at: string | null;
}

interface AgentHealth {
  agent_id: string;
  status: string;
  health_status: string;
  last_heartbeat: string | null;
  seconds_since_heartbeat: number | null;
  is_stale: boolean;
}

interface AgentStatistics {
  total_agents: number;
  by_status: Record<string, number>;
  by_type: Record<string, number>;
  by_health: Record<string, number>;
  stale_count: number;
}
```

### 8.2 Monitoring Types

```typescript
interface DashboardSummary {
  active_agents: number;
  total_tasks_pending: number;
  recent_anomalies: number;
}

interface Anomaly {
  anomaly_id: string;
  anomaly_type: string;
  description: string;
  severity: string;  // low, medium, high
  metric_name: string;
  baseline_value: number;
  observed_value: number;
  deviation_percent: number;
  detected_at: string;
  acknowledged_at: string | null;
}

interface SystemHealth {
  overall_status: string;  // healthy, degraded, unhealthy
  last_updated: string;
}
```

### 8.3 Reasoning Types

```typescript
interface ReasoningChainResponse {
  entity_type: string;
  entity_id: string;
  events: ReasoningEvent[];
  total_count: number;
  stats: {
    total: number;
    decisions: number;
    discoveries: number;
    errors: number;
    by_type: Record<string, number>;
  };
}

interface ReasoningEvent {
  id: string;
  timestamp: string;
  type: string;
  title: string;
  description: string;
  agent: string | null;
  details: EventDetails | null;
  evidence: Evidence[];
  decision: Decision | null;
}

interface Evidence {
  type: string;
  content: string;
  link?: string;
}

interface Decision {
  type: string;  // complete, block, implement
  action: string;
  reasoning: string;
}
```

### 8.4 Graph Types

```typescript
interface DependencyGraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

interface GraphNode {
  id: string;
  type: "task" | "discovery" | "ticket";
  label: string;
  description?: string;
  status: string;
  priority: string;
  ticket_id?: string;
}

interface GraphEdge {
  source: string;
  target: string;
  type?: string;  // ticket_blocks, depends_on, etc.
}
```

---

## 9. Page Routes Summary

| Route | Component | Purpose |
|-------|-----------|---------|
| `/agents` | AgentsPage | Agent list with stats and filtering |
| `/agents/[agentId]` | AgentDetailPage | Single agent details, health, activity |
| `/agents/[agentId]/workspace` | AgentWorkspacePage | Terminal interface |
| `/agents/spawn` | SpawnAgentPage | Create new agent |
| `/health` | HealthOverviewPage | System health dashboard |
| `/health/trajectories` | TrajectoriesPage | Guardian trajectory analysis |
| `/health/interventions` | InterventionsPage | Anomaly and intervention history |
| `/health/settings` | HealthSettingsPage | Monitoring configuration |
| `/diagnostic/[type]/[id]` | DiagnosticPage | Reasoning chain visualization |
| `/graph/[projectId]` | DependencyGraphPage | Task dependency graph |
| `/projects/[id]/explore` | ExplorePage | AI codebase exploration |

---

## 10. Key Implementation Patterns

### 10.1 React Query Patterns

All hooks follow consistent React Query patterns:
- **Query Keys**: Hierarchical arrays for cache invalidation
- **Refetch Intervals**: Health data refreshes every 15-60s
- **Enabled Flag**: Queries disabled until required params available
- **Invalidation**: Mutations invalidate related query keys

### 10.2 WebSocket Patterns

- Connection established on component mount (when enabled)
- Automatic reconnection on abnormal close
- JWT authentication via query parameter
- Event buffering with configurable max size
- Filter updates sent via WebSocket message

### 10.3 Visualization Patterns

- **React Flow**: Used for dependency graphs with custom nodes
- **Dagre**: Automatic hierarchical layout (TB/LR)
- **Tooltips**: Rich hover information for nodes
- **Color Coding**: Consistent status/priority colors across UI
- **Interactive Navigation**: Click nodes to navigate to details

### 10.4 Real-Time Updates

- WebSocket for immediate event delivery
- React Query polling for periodic health checks
- Optimistic UI updates for mutations
- Toast notifications for async operation results
