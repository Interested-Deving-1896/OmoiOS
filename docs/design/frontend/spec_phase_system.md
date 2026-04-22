# OmoiOS Spec & Phase System — Frontend Design Document

## Overview

The Spec & Phase system is the core of OmoiOS's spec-driven development workflow. It converts feature ideas through a state machine with LLM quality gates, producing requirements, design artifacts, and executable tasks that spawn agents in isolated sandboxes.

## Spec State Machine

The spec lifecycle follows a strict 7-phase progression:

```
EXPLORE → PRD → REQUIREMENTS → DESIGN → TASKS → SYNC → COMPLETE
```

| Phase | Purpose | Quality Gate | UI Indicator |
|-------|---------|--------------|--------------|
| **EXPLORE** | Codebase exploration and context gathering | LLM evaluates codebase fit | 🔍 Blue spinner |
| **PRD** | Product Requirements Document generation | Human review checkpoint | 📋 Gray pending |
| **REQUIREMENTS** | EARS-format structured requirements | All criteria defined | 📄 Gray pending |
| **DESIGN** | Architecture diagrams and data models | Design approval required | 🎨 Yellow warning |
| **TASKS** | Implementation task breakdown | Task queue validation | 📝 Gray pending |
| **SYNC** | Sync tasks to execution system | Sandbox spawn confirmation | 🔄 Blue spinner |
| **COMPLETE** | Execution finished, PR created | Completion modal trigger | ✅ Green check |

### Phase Transitions

Phase transitions are triggered by:
- **Automatic**: LLM evaluators pass and advance phase
- **Manual**: User clicks "Approve Requirements" or "Approve Design"
- **Error**: Phase fails and can be retried

## Data Models

### Core Spec Types

```typescript
// From frontend/lib/api/specs.ts
interface Spec {
  id: string;
  project_id: string;
  title: string;
  description: string | null;
  status: string;           // "draft" | "executing" | "completed" | "failed"
  phase: string;            // Display phase
  current_phase: string;    // State machine phase
  progress: number;         // 0-100 completion percentage
  test_coverage: number;
  active_agents: number;
  linked_tickets: number;
  requirements: Requirement[];
  design: DesignArtifact | null;
  tasks: SpecTask[];
  execution: SpecExecution | null;
  branch_name: string | null;
  pull_request_url: string | null;
  pull_request_number: number | null;
  created_at: string;
  updated_at: string;
}

interface Requirement {
  id: string;
  title: string;
  condition: string;        // EARS "WHEN" clause
  action: string;          // EARS "THE SYSTEM SHALL" clause
  criteria: AcceptanceCriterion[];
  linked_design: string | null;
  status: string;
}

interface AcceptanceCriterion {
  id: string;
  text: string;
  completed: boolean;
}

interface DesignArtifact {
  architecture: string | null;   // Markdown description
  data_model: string | null;     // Markdown or diagram reference
  api_spec: ApiEndpoint[];
}

interface SpecTask {
  id: string;
  title: string;
  description: string;
  phase: string;
  priority: string;
  status: string;           // "pending" | "in_progress" | "completed"
  assigned_agent: string | null;
  dependencies: string[];   // Task IDs this task depends on
  estimated_hours: number | null;
  actual_hours: number | null;
}
```

## Hook Patterns

### React Query Key Structure

```typescript
// From frontend/hooks/useSpecs.ts
export const specsKeys = {
  all: ["specs"] as const,
  project: (projectId: string) =>
    [...specsKeys.all, "project", projectId] as const,
  detail: (specId: string) => [...specsKeys.all, "detail", specId] as const,
  versions: (specId: string) => [...specsKeys.all, "versions", specId] as const,
  executionStatus: (specId: string) =>
    [...specsKeys.all, "execution", specId] as const,
  criteriaStatus: (specId: string) =>
    [...specsKeys.all, "criteria", specId] as const,
  events: (specId: string) => [...specsKeys.all, "events", specId] as const,
  linkedTickets: (specId: string) =>
    [...specsKeys.all, "linked-tickets", specId] as const,
};

// From frontend/hooks/useBoard.ts
export const boardKeys = {
  all: ["board"] as const,
  view: (projectId?: string) => [...boardKeys.all, "view", projectId] as const,
  stats: (projectId?: string) =>
    [...boardKeys.all, "stats", projectId] as const,
  violations: (projectId?: string) =>
    [...boardKeys.all, "violations", projectId] as const,
};

// From frontend/hooks/useTickets.ts
export const ticketKeys = {
  all: ["tickets"] as const,
  lists: () => [...ticketKeys.all, "list"] as const,
  list: (params: TicketListParams) => [...ticketKeys.lists(), params] as const,
  details: () => [...ticketKeys.all, "detail"] as const,
  detail: (id: string) => [...ticketKeys.details(), id] as const,
  context: (id: string) => [...ticketKeys.detail(id), "context"] as const,
  pendingCount: () => [...ticketKeys.all, "pending-count"] as const,
};
```

### Polling Patterns

Specs use adaptive polling based on execution state:

```typescript
// Fast polling during execution (1.5s), slower otherwise (10s)
const { data: spec } = useSpec(specId, {
  refetchInterval: (query) => {
    const specData = query.state.data;
    return specData?.status === "executing" ? 1500 : 10000;
  },
  refetchOnWindowFocus: true,
  staleTime: 2000,
});

// Project specs list polls when any spec is executing
const { data } = useProjectSpecs(projectId, {
  refetchInterval: (query) => {
    const hasExecuting = query.state.data?.specs.some(
      (s) => s.status === "executing"
    );
    return hasExecuting ? 5000 : false;
  },
});
```

### Mutation Patterns

All mutations follow the same pattern:
1. Execute API call
2. Invalidate affected queries on success
3. Update cache optimistically where appropriate

```typescript
export function useApproveRequirements(specId: string) {
  const queryClient = useQueryClient();

  return useMutation<{ message: string }, Error, void>({
    mutationFn: () => approveRequirements(specId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: specsKeys.detail(specId) });
    },
  });
}
```

## API Client Inventory

### Spec API (`frontend/lib/api/specs.ts`)

| Function | Method | Endpoint | Purpose |
|----------|--------|----------|---------|
| `listProjectSpecs` | GET | `/api/v1/specs/project/{projectId}` | List specs with optional status filter |
| `createSpec` | POST | `/api/v1/specs` | Create new spec |
| `getSpec` | GET | `/api/v1/specs/{specId}` | Get spec detail |
| `updateSpec` | PATCH | `/api/v1/specs/{specId}` | Update spec metadata |
| `deleteSpec` | DELETE | `/api/v1/specs/{specId}` | Archive spec |
| `addRequirement` | POST | `/api/v1/specs/{specId}/requirements` | Add EARS requirement |
| `updateRequirement` | PATCH | `/api/v1/specs/{specId}/requirements/{reqId}` | Update requirement |
| `deleteRequirement` | DELETE | `/api/v1/specs/{specId}/requirements/{reqId}` | Remove requirement |
| `addCriterion` | POST | `/api/v1/specs/{specId}/requirements/{reqId}/criteria` | Add acceptance criterion |
| `updateCriterion` | PATCH | `/api/v1/specs/{specId}/requirements/{reqId}/criteria/{criterionId}` | Update criterion |
| `deleteCriterion` | DELETE | `/api/v1/specs/{specId}/requirements/{reqId}/criteria/{criterionId}` | Remove criterion |
| `updateDesign` | PUT | `/api/v1/specs/{specId}/design` | Update design artifact |
| `addTask` | POST | `/api/v1/specs/{specId}/tasks` | Add implementation task |
| `updateTask` | PATCH | `/api/v1/specs/{specId}/tasks/{taskId}` | Update task |
| `deleteTask` | DELETE | `/api/v1/specs/{specId}/tasks/{taskId}` | Remove task |
| `approveRequirements` | POST | `/api/v1/specs/{specId}/approve-requirements` | Advance to design phase |
| `approveDesign` | POST | `/api/v1/specs/{specId}/approve-design` | Advance to execution |
| `listSpecVersions` | GET | `/api/v1/specs/{specId}/versions` | Get version history |
| `executeSpecTasks` | POST | `/api/v1/specs/{specId}/execute-tasks` | Queue tasks for sandbox execution |
| `getExecutionStatus` | GET | `/api/v1/specs/{specId}/execution-status` | Poll execution progress |
| `getCriteriaStatus` | GET | `/api/v1/specs/{specId}/criteria-status` | Get criteria completion |
| `createSpecBranch` | POST | `/api/v1/specs/{specId}/create-branch` | Create GitHub branch |
| `createSpecPR` | POST | `/api/v1/specs/{specId}/create-pr` | Create pull request |
| `launchSpec` | POST | `/api/v1/specs/launch` | Direct spec creation from command page |
| `getSpecEvents` | GET | `/api/v1/specs/{specId}/events` | Real-time event stream |
| `linkTicketsToSpec` | POST | `/api/v1/specs/{specId}/link-tickets` | Associate tickets |
| `unlinkTicketsFromSpec` | POST | `/api/v1/specs/{specId}/unlink-tickets` | Remove ticket associations |
| `getLinkedTickets` | GET | `/api/v1/specs/{specId}/linked-tickets` | Get linked tickets |
| `exportSpec` | GET | `/api/v1/specs/{specId}/export` | Export JSON or Markdown |

### Phase API (`frontend/lib/api/phases.ts`)

| Function | Method | Endpoint | Purpose |
|----------|--------|----------|---------|
| `validateGate` | POST | `/api/v1/tickets/{ticketId}/validate-gate` | Check phase gate criteria |
| `getGateStatus` | GET | `/api/v1/tickets/{ticketId}/gate-status` | Get current gate status |
| `addArtifact` | POST | `/api/v1/tickets/{ticketId}/artifacts` | Add phase artifact |

### Board API (`frontend/lib/api/board.ts`)

| Function | Method | Endpoint | Purpose |
|----------|--------|----------|---------|
| `getBoardView` | GET | `/api/v1/board/view` | Get complete Kanban board |
| `moveTicket` | POST | `/api/v1/board/move` | Move ticket between columns |
| `getColumnStats` | GET | `/api/v1/board/stats` | Get column statistics |
| `checkWIPViolations` | GET | `/api/v1/board/wip-violations` | Check WIP limit violations |
| `autoTransitionTicket` | POST | `/api/v1/board/auto-transition/{ticketId}` | Auto-advance ticket phase |
| `getColumnForPhase` | GET | `/api/v1/board/column/{phaseId}` | Get column for phase |

### Ticket API (`frontend/lib/api/tickets.ts`)

| Function | Method | Endpoint | Purpose |
|----------|--------|----------|---------|
| `listTickets` | GET | `/api/v1/tickets` | List with filtering |
| `checkDuplicates` | POST | `/api/v1/tickets/check-duplicates` | Check for duplicates |
| `getTicket` | GET | `/api/v1/tickets/{ticketId}` | Get ticket detail |
| `createTicket` | POST | `/api/v1/tickets` | Create new ticket |
| `transitionTicket` | POST | `/api/v1/tickets/{ticketId}/transition` | Change status |
| `blockTicket` | POST | `/api/v1/tickets/{ticketId}/block` | Mark as blocked |
| `unblockTicket` | POST | `/api/v1/tickets/{ticketId}/unblock` | Remove blocker |
| `progressTicket` | POST | `/api/v1/tickets/{ticketId}/progress` | Advance phase |
| `approveTicket` | POST | `/api/v1/tickets/approve` | Approve pending ticket |
| `rejectTicket` | POST | `/api/v1/tickets/reject` | Reject pending ticket |
| `getPendingReviewCount` | GET | `/api/v1/tickets/pending-review-count` | Get pending count |
| `getTicketContext` | GET | `/api/v1/tickets/{ticketId}/context` | Get full context |
| `spawnPhaseTasks` | POST | `/api/v1/tickets/{ticketId}/spawn-phase-tasks` | Trigger phase workflow |
| `batchSpawnPhaseTasks` | POST | (batch wrapper) | Batch spawn for multiple tickets |

## UI Components

### Phase Progress Component

**File**: `frontend/components/spec/PhaseProgress.tsx`

Visual indicator showing the 6-phase progression:

```typescript
interface PhaseProgressProps {
  currentPhase: string;     // "explore" | "prd" | "requirements" | "design" | "tasks" | "sync"
  status: string;          // "draft" | "executing" | "completed" | "failed"
  className?: string;
  showLabels?: boolean;    // Show phase names below icons
  size?: "sm" | "md" | "lg";
}
```

**Visual States**:
- **Completed phases**: Green circle with checkmark
- **Current phase**: Blue circle with spinner (if executing)
- **Pending phases**: Gray muted circle
- **Failed phase**: Red circle

**Usage**:
```tsx
<PhaseProgress
  currentPhase={spec.current_phase}
  status={spec.status}
  size="sm"
  showLabels={false}
/>
```

### Event Timeline Component

**File**: `frontend/components/spec/EventTimeline.tsx`

Real-time event feed showing spec execution activity:

```typescript
interface EventTimelineProps {
  specId: string;
  isExecuting?: boolean;   // Enables 1.5s polling when true
  maxHeight?: string;       // Default "400px"
  className?: string;
}
```

**Event Types Displayed**:
- `spec.execution_started` → Play icon, blue
- `spec.phase_completed` → CheckCircle, green
- `spec.phase_failed` → XCircle, red
- `agent.started` → Bot icon, blue
- `agent.completed` → CheckCircle, green
- `agent.failed` → XCircle, red

**Features**:
- Auto-scrolls to top on new events
- Highlights new events with pulse animation
- Pause/resume live updates
- Direct link to active sandbox

### Spec Completion Modal

**File**: `frontend/components/spec/SpecCompletionModal.tsx`

Viral loop sharing modal triggered when spec completes:

**Features**:
- Shows stats: requirements count, tasks completed, test coverage
- Displays PR link if available
- Generates shareable link for social sharing
- Twitter/X and LinkedIn share buttons
- GitHub star CTA

## Page Structure

### Spec List Page

**Route**: `/projects/{projectId}/specs`

**File**: `frontend/app/(app)/projects/[id]/specs/page.tsx`

**Features**:
- List view with status badges
- Bulk selection and archive
- Create spec dialog
- Progress bars per spec
- Time ago display ("2h ago", "3d ago")
- Polls every 5s when any spec is executing

### Spec Workspace Page

**Route**: `/projects/{projectId}/specs/{specId}`

**File**: `frontend/app/(app)/projects/[id]/specs/[specId]/page.tsx`

**Layout**:
```
┌─────────────────────────────────────────────────────────────┐
│  Spec Switcher  │  Header (title, phase badge, progress)     │
│  (left nav)     │  PhaseProgress component                   │
│                 │                                            │
│  - Spec A       ├────────────────────────────────────────────┤
│  - Spec B       │  Tabs: Requirements | Design | Tasks | Exec│
│  - Spec C       │                                            │
│                 │  [Tab Content]                             │
│                 │                                            │
│                 │  EventTimeline (bottom/right)              │
└─────────────────────────────────────────────────────────────┘
```

**Tab Contents**:
- **Requirements**: EARS-format cards, expandable, criteria checkboxes
- **Design**: Architecture description, data model, API endpoints
- **Tasks**: Task list with status, priority badges, assignee
- **Execution**: Progress stats, execution status, agent activity

### Kanban Board Page

**Route**: `/board/{projectId}`

**File**: `frontend/app/(app)/board/[projectId]/page.tsx`

**Features**:
- Drag-and-drop columns using @dnd-kit
- WIP limit indicators
- Real-time WebSocket updates
- Running task indicators (green pulse)
- Agent panel slide-out for live sandbox viewing
- Filter by status, priority, search
- "Start Processing" button for batch task spawning
- Autonomous execution toggle

**WebSocket Events Handled**:
- `TICKET_CREATED` → Toast notification
- `TICKET_UPDATED` → Invalidate board queries
- `TASK_ASSIGNED` → Show agent indicator
- `TASK_COMPLETED` → Remove agent indicator
- `SANDBOX_SPAWNED` → Auto-open agent panel

## Spec-Driven Settings

**File**: `frontend/hooks/useSpecDrivenSettings.ts`

User-configurable settings for spec execution:

```typescript
interface SpecDrivenSettings {
  auto_execute: boolean;           // Auto-start execution after design approval
  execution_mode: "auto" | "manual";
  coverage_threshold: number;      // 0-100, default 80
  enforce_coverage: boolean;
  parallel_execution: boolean;     // Run tasks in parallel
  max_parallel_tasks: number;      // 1-10, default 3
  validation_mode: "strict" | "relaxed" | "none";
  require_tests: boolean;
  require_docs: boolean;
  auto_merge: boolean;             // Auto-merge PRs (risky)
  notify_on_completion: boolean;
}
```

**Validation Warnings**:
- Auto-merge + no validation → Warning
- Coverage < 50% + enforced → Warning
- Max parallel > 5 → Performance warning
- Auto-merge + no tests → Error

## Integration Points

### Ticket → Spec Linking

Tickets can be linked to specs via:
- `useLinkTickets(specId)` mutation
- `useLinkedTickets(specId)` query
- Displayed as "Spec" badge on board cards

### Spec → Sandbox Execution

When `executeSpecTasks` is called:
1. Backend converts SpecTasks to executable Tasks
2. Tasks queued for Daytona sandboxes
3. OrchestratorWorker spawns agents
4. Events published via WebSocket
5. Frontend receives real-time updates

### Spec → GitHub PR

When spec completes:
1. `createSpecBranch` creates Git branch
2. Agents commit code to branch
3. `createSpecPR` opens pull request
4. PR link stored in `pull_request_url`
5. SpecCompletionModal shows PR link

## Error Handling

### Phase Failure

When a phase fails:
1. Spec status changes to "failed"
2. Current phase shows red indicator
3. EventTimeline shows failure event
4. User can retry from current phase
5. Toast notification with error details

### Network Errors

All hooks handle errors with:
- Toast notifications via sonner
- Query retry with exponential backoff
- Cache invalidation on mutation failure
- Optimistic updates rolled back on error

## Performance Considerations

1. **Polling Strategy**: Adaptive polling based on execution state (1.5s vs 10s)
2. **Query Keys**: Hierarchical invalidation (project → detail → events)
3. **Virtualization**: EventTimeline uses ScrollArea for large lists
4. **Debouncing**: Search inputs debounced 300ms
5. **Memoization**: useMemo for derived data (ticketsByColumn, filteredTickets)

## Security

- All API calls include credentials via `apiRequest` helper
- WebSocket connections include auth token in query params
- Spec export respects user permissions
- Ticket linking validates project membership
