# OmoiOS Frontend Design: Sandbox, Preview & Prototype System

## Overview

The OmoiOS frontend provides three integrated systems for AI agent execution and visualization:

| System | Purpose | Key Files |
|--------|---------|-----------|
| **Sandbox** | Real-time agent execution monitoring with event streaming | `components/sandbox/`, `hooks/useSandbox.ts` |
| **Preview** | Live iframe rendering of deployed applications | `components/preview/`, `hooks/usePreview.ts` |
| **Prototype** | Rapid prototyping workspace with AI code generation | `components/prototype/`, `hooks/usePrototype.ts` |

---

## 1. Sandbox System

### 1.1 Lifecycle

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Create    │───▶│  Provision  │───▶│   Execute   │───▶│   Monitor   │───▶│   Teardown  │
│  (Task →    │    │  (Daytona   │    │  (Agent     │    │  (Events +  │    │  (Cleanup   │
│  Sandbox)   │    │  Sandbox)   │    │  Worker)    │    │  WebSocket) │    │  + Stop)    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

### 1.2 Component Hierarchy

```
sandbox/
├── index.ts                    # Public exports
├── EventRenderer.tsx           # Main event visualization (3,158 lines)
│   ├── MessageCard             # Agent/user chat messages
│   ├── FileWriteCard           # File creation/modification with diff
│   ├── ReadCard                # File content display with syntax highlighting
│   ├── BashCard                # Terminal command execution
│   ├── GlobCard                # File tree search results
│   ├── GrepCard                # Content search results
│   ├── ToolCard                # Generic tool usage display
│   ├── McpToolCard             # MCP server tool calls
│   ├── TodoCard                # Task list updates
│   ├── AskUserQuestionCard     # Interactive user prompts
│   ├── SkillInvokedCard        # Skill execution indicator
│   ├── SubagentCard            # Subagent invocation/completion
│   └── SystemEventCard         # Lifecycle events
├── ToolUseCard.tsx             # Compact tool usage summary
├── FileEditCard.tsx            # Simple file change display
└── ChatMessage.tsx             # Basic chat bubble
```

### 1.3 Hook Patterns

| Hook | Purpose | Query Key Strategy |
|------|---------|-------------------|
| `useSandboxMonitor` | Combined real-time + historical events | `sandboxKeys.trajectory(sandboxId)` + WebSocket |
| `useSandboxRealtimeEvents` | WebSocket event subscription | `useEvents({ entity_types: ["sandbox"] })` |
| `useSandboxTrajectory` | Cursor-based pagination for history | `["sandboxes", "trajectory", sandboxId, { cursor }]` |
| `useSandboxTask` | Associated task metadata | `["sandboxes", "task", sandboxId]` |
| `useSendSandboxMessage` | Send user messages to agent | Mutation with invalidation |

### 1.4 React Query Key Structure

```typescript
export const sandboxKeys = {
  all: ["sandboxes"] as const,
  events: (sandboxId: string) => 
    [...sandboxKeys.all, "events", sandboxId] as const,
  trajectory: (sandboxId: string) => 
    [...sandboxKeys.all, "trajectory", sandboxId] as const,
  messages: (sandboxId: string) => 
    [...sandboxKeys.all, "messages", sandboxId] as const,
  task: (sandboxId: string) => 
    [...sandboxKeys.all, "task", sandboxId] as const,
};
```

### 1.5 API Client Functions

| Function | Endpoint | Parameters | Response |
|----------|----------|------------|----------|
| `getSandboxEvents` | `GET /api/v1/sandboxes/{id}/events` | `limit`, `offset`, `event_type` | `SandboxEventsListResponse` |
| `getSandboxTrajectory` | `GET /api/v1/sandboxes/{id}/trajectory` | `limit`, `cursor`, `direction` | `TrajectorySummaryResponse` |
| `sendSandboxMessage` | `POST /api/v1/sandboxes/{id}/messages` | `SandboxMessage` | `SandboxEventResponse` |
| `getSandboxMessages` | `GET /api/v1/sandboxes/{id}/messages` | — | `MessageQueueResponse` |
| `getTaskBySandbox` | `GET /api/v1/sandboxes/{id}/task` | — | `SandboxTask` |

### 1.6 Real-Time Updates (WebSocket)

```typescript
// WebSocket event transformation
const handleEvent = useCallback((systemEvent: SystemEvent) => {
  const sandboxEvent: SandboxEvent = {
    id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
    sandbox_id: systemEvent.entity_id,
    event_type: systemEvent.payload.original_event_type || systemEvent.event_type,
    event_data: systemEvent.payload,
    source: systemEvent.payload.source || "agent",
    created_at: new Date().toISOString(),
  };
  setEvents((prev) => [sandboxEvent, ...prev].slice(0, 500));
}, []);
```

### 1.7 Event Deduplication Strategy

The `useSandboxMonitor` hook implements sophisticated deduplication:

1. **Tool Use vs Tool Completed**: Filters out `agent.tool_use` when matching `agent.tool_completed` exists
2. **File Edit Deduplication**: Content-based keys prevent duplicate file operation displays
3. **Subagent Prompt Filtering**: Removes user messages that are subagent prompts
4. **Content Hashing**: Normalizes content for comparison (`normalizeContent()`)

### 1.8 Infinite Scroll Pattern

```typescript
// Cursor-based pagination for historical events
const loadMoreEvents = useCallback(async () => {
  const data = await sandboxApi.getTrajectory(sandboxId, {
    limit: 100,
    cursor: nextCursor,
    direction: "older",
  });
  const newEvents = data.events.slice().reverse(); // Chronological order
  setOlderEvents((prev) => [...newEvents, ...prev]);
  setNextCursor(data.next_cursor);
  setHasMore(data.has_more);
}, [sandboxId, nextCursor]);
```

---

## 2. Preview System

### 2.1 Lifecycle

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Pending   │───▶│  Starting   │───▶│    Ready    │───▶│   Stopped   │
│  (Queue)    │    │  (Dev       │    │  (Live      │    │  (Cleanup)   │
│             │    │  Server)    │    │  URL)       │    │             │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
       │                    │                  │
       ▼                    ▼                  ▼
  ┌─────────┐         ┌─────────┐       ┌─────────┐
  │  Failed │         │  Failed │       │  Failed │
  │ (Error) │         │ (Error) │       │ (Error) │
  └─────────┘         └─────────┘       └─────────┘
```

### 2.2 Component Structure

```
preview/
└── PreviewPanel.tsx            # Live preview with toolbar
    ├── Pending/Starting State  # Loading spinner with status
    ├── Failed State          # Error display with retry
    ├── Stopped State         # Stopped indicator
    └── Ready State           # Toolbar + iframe
        ├── URL Display       # Preview URL with copy
        ├── Framework Badge   # React/Vite/Next.js indicator
        ├── Refresh Button    # iframe reload
        ├── Open External     # New tab launch
        └── Stop Button       # Terminate preview
```

### 2.3 Hook Patterns

| Hook | Purpose | Features |
|------|---------|----------|
| `usePreview` | Manage preview session | Polling + WebSocket hybrid |

**Polling Strategy:**
- No preview: 30s interval
- Pending/Starting: 10s interval
- Terminal states (ready/stopped/failed): Stop polling

**WebSocket Integration:**
- Listens for `PREVIEW_READY` event
- Invalidates query on event receipt
- Provides `justBecameReady` flag for UI transitions

### 2.4 React Query Key Structure

```typescript
export const previewKeys = {
  all: ["previews"] as const,
  bySandbox: (sandboxId: string) => 
    [...previewKeys.all, "sandbox", sandboxId] as const,
};
```

### 2.5 API Client Functions

| Function | Endpoint | Parameters | Response |
|----------|----------|------------|----------|
| `getPreviewBySandbox` | `GET /api/v1/preview/sandbox/{id}` | `sandboxId` | `PreviewSession` |
| `getPreview` | `GET /api/v1/preview/{id}` | `previewId` | `PreviewSession` |
| `stopPreview` | `DELETE /api/v1/preview/{id}` | `previewId` | `PreviewSession` |

### 2.6 Iframe Security

```typescript
<iframe
  src={preview.preview_url}
  sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
  title="Live Preview"
/>
```

---

## 3. Prototype System

### 3.1 Workflow

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  1. Start       │    │  2. Prompt      │    │  3. Export      │
│     Session     │───▶│     Loop        │───▶│     to Repo     │
│                 │    │                 │    │                 │
│ • Select        │    │ • Send prompt   │    │ • GitHub URL    │
│   framework     │    │ • AI generates  │    │ • Branch name   │
│ • Create        │    │   code          │    │ • Commit & push │
│   sandbox       │    │ • Live preview  │    │                 │
│ • Start dev     │    │   updates       │    │                 │
│   server        │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                        │                      │
         ▼                        ▼                      ▼
    Status: creating         Status: prompting      Status: exporting
         │                        │                      │
         ▼                        ▼                      ▼
    Status: ready              Status: ready         Status: stopped
```

### 3.2 Component Structure

```
prototype/
└── PrototypeWorkspace.tsx      # Full workspace UI (374 lines)
    ├── Start Session View      # Framework selector + create button
    └── Active Session View     # Split-pane workspace
        ├── Header              # Status badge + framework + end button
        ├── Left Panel          # Prompt input + history + export
        │   ├── Prompt Textarea # User input with Enter-to-send
        │   ├── Send Button     # Submit prompt
        │   ├── History List    # Previous prompts/responses
        │   └── Export Section  # GitHub URL input + export button
        └── Right Panel         # Live preview via PreviewPanel
```

### 3.3 Framework Templates

```typescript
const FRAMEWORKS = [
  { value: "react-vite", label: "React + Vite + TypeScript" },
  { value: "next", label: "Next.js + TypeScript + Tailwind" },
  { value: "vue-vite", label: "Vue + Vite + TypeScript" },
];
```

### 3.4 Hook Patterns

| Hook | Purpose | Features |
|------|---------|----------|
| `usePrototype` | Full session lifecycle | Start, prompt, export, end |

**Session Status Polling:**
- `creating`/`prompting`/`exporting`: 5s interval
- `ready`/`stopped`/`failed`: Stop polling

**WebSocket Events:**
- `PROTOTYPE_PROMPT_APPLIED`: Invalidate session query
- `PROTOTYPE_EXPORTED`: Invalidate session query

### 3.5 React Query Key Structure

```typescript
export const prototypeKeys = {
  all: ["prototype"] as const,
  session: (sessionId: string) => 
    [...prototypeKeys.all, "session", sessionId] as const,
};
```

### 3.6 API Client Functions

| Function | Endpoint | Parameters | Response |
|----------|----------|------------|----------|
| `startSession` | `POST /api/v1/prototype/session` | `framework` | `PrototypeSession` |
| `getSession` | `GET /api/v1/prototype/session/{id}` | `sessionId` | `PrototypeSession` |
| `applyPrompt` | `POST /api/v1/prototype/session/{id}/prompt` | `prompt` | `PromptResponse` |
| `exportToRepo` | `POST /api/v1/prototype/session/{id}/export` | `repo_url`, `branch`, `commit_message` | `ExportResponse` |
| `endSession` | `DELETE /api/v1/prototype/session/{id}` | `sessionId` | `void` |

### 3.7 Preview Integration

The PrototypeWorkspace converts `PrototypeSession` to `PreviewSession` for reuse:

```typescript
function toPreviewSession(session: PrototypeSession): PreviewSession | null {
  if (!session.preview_id) return null;
  return {
    id: session.preview_id,
    sandbox_id: session.sandbox_id || "",
    task_id: null,
    project_id: null,
    status: session.status === "ready" ? "ready" : "pending",
    preview_url: session.preview_url,
    port: 3000,
    framework: session.framework,
    error_message: session.error_message,
    created_at: session.created_at,
    ready_at: null,
    stopped_at: null,
  };
}
```

---

## 4. Page Routes

| Route | File | Purpose |
|-------|------|---------|
| `/sandboxes` | `app/(app)/sandboxes/page.tsx` | List all sandbox tasks with filtering |
| `/sandbox/[sandboxId]` | `app/(app)/sandbox/[sandboxId]/page.tsx` | Detailed sandbox monitoring |
| `/prototype` | `app/(app)/prototype/page.tsx` | Rapid prototyping workspace |

### 4.1 Sandbox Detail Page Features

- **Tabs**: Events | Preview (conditional) | Details
- **Event Stream**: Infinite scroll + real-time updates
- **Message Input**: Send user messages to agent
- **Connection Status**: WebSocket connection indicator
- **Auto-switch**: Automatically switches to Preview tab when ready

---

## 5. Type Definitions

### 5.1 Core Types

```typescript
// Sandbox Event
interface SandboxEvent {
  id: string;
  sandbox_id: string;
  event_type: string;
  event_data: Record<string, unknown>;
  source: "agent" | "worker" | "system";
  created_at: string;
}

// Preview Session
interface PreviewSession {
  id: string;
  sandbox_id: string;
  task_id: string | null;
  project_id: string | null;
  status: "pending" | "starting" | "ready" | "stopped" | "failed";
  preview_url: string | null;
  port: number;
  framework: string | null;
  error_message: string | null;
  created_at: string;
  ready_at: string | null;
  stopped_at: string | null;
}

// Prototype Session
interface PrototypeSession {
  id: string;
  user_id: string;
  framework: string;
  sandbox_id: string | null;
  preview_id: string | null;
  status: "creating" | "ready" | "prompting" | "exporting" | "stopped" | "failed";
  preview_url: string | null;
  prompt_history: PromptHistoryItem[];
  error_message: string | null;
  created_at: string;
}
```

---

## 6. WebSocket Event Types

| Event Type | System | Description |
|------------|--------|-------------|
| `PREVIEW_READY` | Preview | Preview URL is live |
| `PROTOTYPE_PROMPT_APPLIED` | Prototype | Code generation complete |
| `PROTOTYPE_EXPORTED` | Prototype | Git export complete |
| `agent.*` | Sandbox | Agent execution events |
| `iteration.*` | Sandbox | Continuous mode events |
| `SANDBOX_SPAWNED` | Sandbox | New sandbox created |

---

## 7. Key Design Decisions

### 7.1 Event Rendering Strategy

The `EventRenderer` component uses a **type-based switch** with 30+ event type handlers:

- **Tool-specific cards**: Write, Edit, Read, Bash, Glob, Grep each have dedicated UI
- **MCP tool detection**: Parsed from `mcp__{server}__{tool}` naming convention
- **Deduplication**: Content-based keys prevent duplicate displays
- **Collapsible sections**: Complex content (file reads, bash output) starts collapsed

### 7.2 State Management Pattern

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Server State | React Query | API data with caching |
| Real-time | WebSocket | Live event streaming |
| Local UI | useState | Component-level UI state |
| Cross-cutting | Zustand | Global UI state (sidebar, theme) |

### 7.3 Error Handling

- **404 Graceful Degradation**: Returns `null` instead of throwing for missing previews
- **WebSocket Reconnection**: Auto-reconnects with 5s delay on abnormal closure
- **Polling Backoff**: Slower polling when no preview exists

---

## 8. File Inventory

| File | Lines | Purpose |
|------|-------|---------|
| `components/sandbox/EventRenderer.tsx` | 3,158 | Main event visualization engine |
| `components/sandbox/ToolUseCard.tsx` | 106 | Compact tool summary |
| `components/sandbox/FileEditCard.tsx` | 109 | Simple file change display |
| `components/sandbox/ChatMessage.tsx` | 68 | Basic chat bubble |
| `components/preview/PreviewPanel.tsx` | 152 | Live preview with toolbar |
| `components/prototype/PrototypeWorkspace.tsx` | 374 | Full prototyping UI |
| `hooks/useSandbox.ts` | 377 | Sandbox monitoring hooks |
| `hooks/usePreview.ts` | 164 | Preview session management |
| `hooks/usePrototype.ts` | 171 | Prototype lifecycle hooks |
| `hooks/useEvents.ts` | 291 | WebSocket event subscription |
| `lib/api/sandbox.ts` | 136 | Sandbox API client |
| `lib/api/preview.ts` | 45 | Preview API client |
| `lib/api/prototype.ts` | 116 | Prototype API client |
| `lib/api/types.ts` | 1,424 | TypeScript type definitions |

---

## 9. Integration Points

### 9.1 Sandbox ↔ Preview

- Sandbox detail page conditionally shows Preview tab
- `usePreview` accepts `sandboxId` and polls for preview status
- Auto-switch to Preview tab when `justBecameReady` is true

### 9.2 Prototype ↔ Preview

- Prototype session creates embedded preview
- `toPreviewSession()` adapter converts types
- Reuses `PreviewPanel` component for live rendering

### 9.3 Sandbox ↔ Tasks

- Sandboxes list page displays tasks with sandbox associations
- `useSandboxTasks` hook fetches tasks with `sandbox_id`
- Task status drives sandbox status display
