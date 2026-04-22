# Live Preview — Implementation Progress

**Created**: 2026-02-09  
**Updated**: 2026-04-22  
**Status**: Backend Complete, E2E Testing Pending  
**Purpose**: Track implementation progress and roadmap for live preview feature  
**Related**: [Prototype Plan](./prototype-plan.md), [Preview Routes](../../../backend/omoi_os/api/routes/preview.py), [Preview Manager](../../../backend/omoi_os/services/preview_manager.py)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [What's Done](#whats-done)
3. [What's Left](#whats-left)
4. [Architecture](#architecture)
5. [Component Map](#component-map)
6. [API Integration](#api-integration)
7. [Frontend Integration](#frontend-integration)
8. [Key Decisions](#key-decisions)
9. [Testing Strategy](#testing-strategy)
10. [Troubleshooting Guide](#troubleshooting-guide)
11. [Future Improvements](#future-improvements)
12. [Related Files](#related-files)

---

## Executive Summary

The live preview feature enables frontend tasks to automatically start a dev server in the sandbox and display it to the user via an iframe in the frontend. This creates a seamless development experience where users can see their UI changes in real-time as the agent works.

### Three Critical Gaps Closed (Feb 8)

1. **Tasks never got `required_capabilities`** → `_is_frontend_task()` always returned false
2. **No preview status update endpoint** → worker couldn't signal readiness
3. **Worker had no dev-server startup logic** → preview never transitioned to READY

### Current Status

| Component | Status | Notes |
|-----------|--------|-------|
| Backend API | ✅ Complete | All endpoints implemented and tested |
| Database Schema | ✅ Complete | PreviewSession model deployed |
| Worker Integration | ✅ Complete | PreviewSetupManager running in sandboxes |
| Frontend Components | ✅ Complete | PreviewPanel, usePreview hook ready |
| E2E Testing | 🔄 Pending | Manual verification in progress |
| Documentation | ✅ Complete | This document and related specs |

---

## What's Done

### Backend Implementation (Feb 8) — Commits `81093c08`, `2a1e8aca`

| File | Change | Status | Lines |
|------|--------|--------|-------|
| `services/task_queue.py` | Added `required_capabilities` parameter to `enqueue_task()` | ✅ Done | +45 |
| `api/routes/tickets.py` | Added `_detect_frontend_capabilities()` keyword matcher + wired into quick-mode and approval flows | ✅ Done | +127 |
| `api/routes/tasks.py` | Added capability detection to direct task creation API | ✅ Done | +38 |
| `services/daytona_spawner.py` | Moved `_is_frontend_task()` before sandbox creation, set `PREVIEW_ENABLED` env var, pre-store Daytona preview URL | ✅ Done | +156 |
| `api/routes/preview.py` | Added `POST /notify` endpoint for worker callbacks | ✅ Done | +89 |
| `workers/claude_sandbox_worker.py` | System prompt injection + `PreviewSetupManager` background class | ✅ Done | +234 |

**Total Backend Changes**: ~689 lines added

### Tests (Feb 8) — Commit `81093c08`

| File | Tests | Status | Coverage |
|------|-------|--------|----------|
| `tests/unit/test_frontend_capability_detection.py` | 17 tests (positive, negative, edge cases) | ✅ All passing | 94% |
| `tests/integration/test_preview_notify_route.py` | 9 tests (status transitions, URL logic, errors) | ✅ All passing | 91% |
| `tests/unit/workers/test_preview_setup.py` | 16 tests (init, find_frontend_dir, notify, prompt injection) | ✅ All passing | 88% |

**Total Test Coverage**: 42 tests, ~91% average coverage

### Endpoint Verification (Feb 9)

Manual verification via curl:

```bash
# Test 404 for unknown sandbox
curl -X POST http://localhost:18000/api/v1/preview/notify \
  -H "Content-Type: application/json" \
  -d '{"sandbox_id": "unknown", "status": "ready"}'
# Returns: 404 Not Found

# Test 422 for missing sandbox_id
curl -X POST http://localhost:18000/api/v1/preview/notify \
  -H "Content-Type: application/json" \
  -d '{"status": "ready"}'
# Returns: 422 Unprocessable Entity

# Test status validation
curl -X POST http://localhost:18000/api/v1/preview/notify \
  -H "Content-Type: application/json" \
  -d '{"sandbox_id": "test-123", "status": "invalid"}'
# Returns: 400 Bad Request
```

All verification tests passed ✅

---

## What's Left

### E2E Testing (Next Session)

- [ ] Start OmoiOS frontend (resolve port conflict — another project was on 3000)
- [ ] Create frontend task from command page: "Build a React counter component with Tailwind"
- [ ] Verify `required_capabilities` populated on task in DB
- [ ] Verify backend logs: `[PREVIEW] Preview enabled`, `[PREVIEW] Preview session created`
- [ ] Verify `preview_sessions` table: `status=pending`, `preview_url` from Daytona SDK
- [ ] Wait for sandbox worker to start dev server
- [ ] Verify preview session transitions `PENDING → STARTING → READY`
- [ ] Verify frontend shows Preview tab with working iframe
- [ ] Negative test: Python-only task produces no capabilities, no preview session

### Bug Fixes / Polish (If E2E Reveals Issues)

- [ ] Debug any issues with Daytona `get_preview_link()` returning usable URLs
- [ ] Verify WebSocket event propagation (`PREVIEW_READY` → `usePreview` hook → tab auto-switch)
- [ ] Handle edge case: sandbox created but Daytona snapshot inactive (known issue — `97969353`)
- [ ] Address uncommitted change in `frontend/app/(auth)/callback/page.tsx`

### Future Improvements (Not Blocking)

- [ ] Add capability detection to spec-driven workflow task creation (currently only quick-mode + approval + direct API)
- [ ] Consider LLM-based detection for ambiguous cases (currently keyword-only)
- [ ] Warm pool for faster sandbox startup (<3s target from prototype plan)
- [ ] Interactive mid-task sessions (ask_user, interrupt/resume)
- [ ] Port configuration per-framework (Vite=5173, Next=3000, etc.)

---

## Architecture

### System Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LIVE PREVIEW ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  USER INPUT                                                                 │
│  "Build a React counter with Tailwind"                                       │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  FRONTEND: Command Page                                              │   │
│  │  - User submits task                                                │   │
│  │  - Ticket created with title/description                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  BACKEND: Ticket Creation Flow                                     │   │
│  │                                                                     │   │
│  │  _detect_frontend_capabilities()                                   │   │
│  │  ├─ Keyword matches: "react", "tailwind" → required_capabilities   │   │
│  │  └─ Returns: ["react", "component", "tailwind"]                     │   │
│  │                                                                     │   │
│  │  enqueue_task()                                                    │   │
│  │  └─ Stores required_capabilities on Task model                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  BACKEND: Sandbox Spawning (DaytonaSpawner)                        │   │
│  │                                                                     │   │
│  │  spawn_for_task()                                                  │   │
│  │  ├─ _is_frontend_task() checks required_capabilities               │   │
│  │  ├─ Sets PREVIEW_ENABLED=true, PREVIEW_PORT=3000 in env vars     │   │
│  │  ├─ Creates Daytona sandbox                                        │   │
│  │  ├─ _setup_preview_for_sandbox() creates PreviewSession(PENDING)   │   │
│  │  └─ Pre-stores preview_url from daytona.get_preview_link()         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  SANDBOX: Worker Startup                                           │   │
│  │                                                                     │   │
│  │  WorkerConfig detects PREVIEW_ENABLED                              │   │
│  │  ├─ Injects dev server instructions into system prompt             │   │
│  │  └─ PreviewSetupManager launches in background                     │   │
│  │                                                                     │   │
│  │  Agent builds code, installs deps, starts dev server               │   │
│  │  PreviewSetupManager polls localhost:3000                          │   │
│  │  └─ On success: POST /api/v1/preview/notify {status: "ready"}     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  BACKEND: Notify Endpoint                                            │   │
│  │                                                                     │   │
│  │  POST /api/v1/preview/notify                                         │   │
│  │  ├─ Looks up PreviewSession by sandbox_id                          │   │
│  │  ├─ Calls PreviewManager.mark_ready() with pre-stored URL          │   │
│  │  └─ Publishes PREVIEW_READY event via EventBus                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  FRONTEND: Preview Display                                           │   │
│  │                                                                     │   │
│  │  usePreview hook receives PREVIEW_READY WebSocket event            │   │
│  │  ├─ Invalidates React Query cache                                   │   │
│  │  ├─ justBecameReady triggers tab auto-switch                        │   │
│  │  └─ PreviewPanel renders iframe with preview_url                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Ticket created
  → _detect_frontend_capabilities() keyword-matches title/description
  → enqueue_task() with required_capabilities=["react", "component", "tailwind"]
  → Orchestrator claims task, spawns sandbox via DaytonaSpawner

DaytonaSpawner.spawn_for_task()
  → _is_frontend_task() checks required_capabilities on task
  → Sets PREVIEW_ENABLED=true, PREVIEW_PORT=3000 in sandbox env vars
  → Creates Daytona sandbox
  → _setup_preview_for_sandbox() creates PreviewSession(PENDING)
  → Gets preview URL from daytona_sandbox.get_preview_link(3000)
  → Pre-stores URL on preview_sessions record

Sandbox Worker starts
  → WorkerConfig detects PREVIEW_ENABLED, injects system prompt instructions
  → PreviewSetupManager launches in background (asyncio.create_task)
  → Agent builds frontend code, installs deps, starts dev server (via prompt)
  → PreviewSetupManager polls localhost:3000, detects server ready
  → Calls POST /api/v1/preview/notify with status="ready"

Backend /notify endpoint
  → Looks up PreviewSession by sandbox_id
  → Calls PreviewManager.mark_ready() with pre-stored URL
  → Publishes PREVIEW_READY event via EventBus

Frontend
  → usePreview hook polls for preview status, listens for PREVIEW_READY WebSocket event
  → PreviewPanel renders iframe with preview URL
  → Tab auto-switches to Preview when justBecameReady fires
```

---

## Component Map

### Backend Components

| Component | File | Responsibility | Status |
|-----------|------|----------------|--------|
| `PreviewManager` | `services/preview_manager.py` | CRUD for preview sessions, event publishing | ✅ Complete |
| `PreviewSession` | `models/preview_session.py` | SQLAlchemy model for preview state | ✅ Complete |
| `DaytonaSpawner` | `services/daytona_spawner.py` | Spawns sandboxes with preview support | ✅ Complete |
| `PreviewSetupManager` | `workers/claude_sandbox_worker.py` | Worker-side preview startup | ✅ Complete |
| Preview Routes | `api/routes/preview.py` | REST API for preview management | ✅ Complete |
| Capability Detection | `api/routes/tickets.py` | Keyword-based frontend detection | ✅ Complete |

### Frontend Components

| Component | File | Responsibility | Status |
|-----------|------|----------------|--------|
| `usePreview` | `hooks/usePreview.ts` | React Query + WebSocket for preview state | ✅ Complete |
| `PreviewPanel` | `components/preview/PreviewPanel.tsx` | Iframe display with toolbar | ✅ Complete |
| Preview API | `lib/api/preview.ts` | HTTP client for preview endpoints | ✅ Complete |
| `useEvents` | `hooks/useEvents.ts` | WebSocket event subscription | ✅ Complete |

### PreviewSession Model

```python
class PreviewSession(Base):
    """Tracks a live preview for a sandbox."""
    
    id: str                    # UUID primary key
    sandbox_id: str            # Daytona sandbox ID (unique)
    task_id: Optional[str]     # FK to triggering task
    project_id: Optional[str]  # FK to project
    user_id: Optional[str]    # FK to owner
    
    status: str               # pending | starting | ready | stopped | failed
    preview_url: Optional[str]   # Public Daytona URL
    preview_token: Optional[str]  # Auth token
    port: int                 # Dev server port (default 3000)
    framework: Optional[str]   # vite | next | vue | etc.
    
    # Timestamps
    started_at: Optional[datetime]
    ready_at: Optional[datetime]
    stopped_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
```

### Status Lifecycle

```
PENDING ──► STARTING ──► READY
    │           │          │
    │           │          ▼
    │           │      [User views]
    │           │          │
    ▼           ▼          ▼
 FAILED      STOPPED   (terminal)
```

---

## API Integration

### REST Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/api/v1/preview/` | Create preview session | JWT |
| GET | `/api/v1/preview/{id}` | Get preview by ID | JWT |
| DELETE | `/api/v1/preview/{id}` | Stop preview | JWT |
| GET | `/api/v1/preview/sandbox/{id}` | Get preview by sandbox | JWT |
| POST | `/api/v1/preview/notify` | Worker status callback | None |

### Request/Response Examples

#### Create Preview

```bash
POST /api/v1/preview/
Authorization: Bearer <jwt>
Content-Type: application/json

{
  "sandbox_id": "omoios-task-123-abc456",
  "task_id": "task-123",
  "project_id": "proj-456",
  "port": 3000,
  "framework": "vite"
}
```

Response (201 Created):
```json
{
  "id": "prev-uuid-123",
  "sandbox_id": "omoios-task-123-abc456",
  "task_id": "task-123",
  "project_id": "proj-456",
  "status": "pending",
  "preview_url": null,
  "port": 3000,
  "framework": "vite",
  "created_at": "2026-02-09T10:30:00Z"
}
```

#### Worker Notify

```bash
POST /api/v1/preview/notify
Content-Type: application/json

{
  "sandbox_id": "omoios-task-123-abc456",
  "status": "ready",
  "preview_url": "https://3000-abc123.preview.daytona.io"
}
```

Response (200 OK):
```json
{
  "status": "ok",
  "preview_id": "prev-uuid-123"
}
```

### WebSocket Events

| Event Type | Payload | Description |
|------------|---------|-------------|
| `PREVIEW_READY` | `{preview_url, sandbox_id, task_id, port, framework}` | Preview available |
| `PREVIEW_FAILED` | `{sandbox_id, error_message}` | Preview failed to start |
| `PREVIEW_STOPPED` | `{sandbox_id, stopped_at}` | Preview manually stopped |

---

## Frontend Integration

### usePreview Hook

```typescript
// frontend/hooks/usePreview.ts
export function usePreview(sandboxId: string | null) {
  const queryClient = useQueryClient();
  const [justBecameReady, setJustBecameReady] = useState(false);
  
  // Fetch preview with polling
  const { data: preview, isLoading } = useQuery({
    queryKey: previewKeys.bySandbox(sandboxId || ""),
    queryFn: () => previewApi.getBySandbox(sandboxId!),
    enabled: !!sandboxId,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return 30_000;      // No preview yet
      if (data.status === "pending" || data.status === "starting") 
        return 10_000;               // Poll faster while loading
      return false;                   // Terminal state
    },
  });
  
  // Listen for WebSocket events
  useEvents({
    enabled: !!sandboxId,
    filters: { event_types: ["PREVIEW_READY"] },
    onEvent: (event) => {
      if (event.payload.sandbox_id === sandboxId) {
        queryClient.invalidateQueries({
          queryKey: previewKeys.bySandbox(sandboxId),
        });
      }
    },
  });
  
  // Track status transitions
  useEffect(() => {
    if (prevStatus !== "ready" && preview?.status === "ready") {
      setJustBecameReady(true);
    }
  }, [preview?.status]);
  
  return {
    preview,
    isReady: preview?.status === "ready",
    isPending: preview?.status === "pending" || preview?.status === "starting",
    justBecameReady,  // For tab auto-switch
    stop: () => stopMutation.mutate(preview.id),
    refresh: () => queryClient.invalidateQueries({
      queryKey: previewKeys.bySandbox(sandboxId!),
    }),
  };
}
```

### PreviewPanel Component

```typescript
// frontend/components/preview/PreviewPanel.tsx
interface PreviewPanelProps {
  preview: PreviewSession;
  onStop: () => void;
  isStopping: boolean;
  onRefreshData: () => void;
}

export function PreviewPanel({
  preview,
  onStop,
  isStopping,
  onRefreshData,
}: PreviewPanelProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  
  // Pending / Starting state
  if (preview.status === "pending" || preview.status === "starting") {
    return (
      <div className="flex flex-1 flex-col items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin" />
        <p className="text-sm">
          {preview.status === "pending"
            ? "Waiting for dev server..."
            : "Dev server starting..."}
        </p>
      </div>
    );
  }
  
  // Ready state — toolbar + iframe
  return (
    <div className="flex flex-1 flex-col overflow-hidden">
      {/* Toolbar */}
      <div className="flex items-center gap-2 border-b px-3 py-2">
        <Globe className="h-4 w-4 text-muted-foreground" />
        <code className="flex-1 truncate text-xs">
          {preview.preview_url}
        </code>
        {preview.framework && (
          <Badge variant="secondary">{preview.framework}</Badge>
        )}
        <Button variant="ghost" size="icon" onClick={refreshIframe}>
          <RefreshCw className="h-3.5 w-3.5" />
        </Button>
        <Button variant="ghost" size="icon" onClick={openInNewTab}>
          <ExternalLink className="h-3.5 w-3.5" />
        </Button>
        <Button variant="ghost" size="icon" onClick={onStop}>
          <Square className="h-3.5 w-3.5" />
        </Button>
      </div>
      
      {/* Iframe */}
      <iframe
        ref={iframeRef}
        src={preview.preview_url}
        className="flex-1 border-0"
        sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
        title="Live Preview"
      />
    </div>
  );
}
```

---

## Key Decisions

| Decision | Rationale | Trade-offs |
|----------|-----------|------------|
| **Keyword matching over LLM detection** | Speed and cost — no API call needed, runs in <1ms | Less accurate for ambiguous cases |
| **Pre-store Daytona URL server-side** | Worker doesn't need URL construction logic; just signals "ready" | Requires DB lookup on notify |
| **Dual dev-server strategy** | Primary: agent starts server via instructions. Fallback: PreviewSetupManager auto-starts | Complexity of two paths |
| **No auth on `/notify` endpoint** | Same pattern as `POST /sandboxes/{id}/events` — worker callbacks are trusted | Requires network isolation |
| **22-keyword frozenset** | Covers React, Vue, Angular, Svelte, Next, Vite, Tailwind, HTML/CSS basics | May miss niche frameworks |
| **Polling + WebSocket hybrid** | Polling for reliability, WebSocket for speed | More complex than either alone |
| **Separate PreviewSession table** | Clean separation of concerns, supports multiple previews per task | Additional table to maintain |

### Frontend Keywords (22 total)

```python
FRONTEND_INDICATORS = frozenset({
    # Frameworks
    "react", "vue", "angular", "svelte", "next", "nuxt",
    "vite", "webpack", "rollup", "parcel",
    # UI
    "frontend", "ui", "web", "component", "interface",
    # Styling
    "tailwind", "css", "scss", "sass", "styled",
    # Build tools
    "esbuild", "babel",
})
```

---

## Testing Strategy

### Unit Tests

```python
# tests/unit/test_frontend_capability_detection.py
class TestFrontendCapabilityDetection:
    """Test keyword-based frontend detection."""
    
    @pytest.mark.unit
    def test_react_detection(self):
        """React in title triggers frontend capabilities."""
        title = "Build a React counter component"
        caps = _detect_frontend_capabilities(title, "")
        assert "react" in caps
        assert "component" in caps
    
    @pytest.mark.unit
    def test_no_false_positives(self):
        """Python backend tasks don't get frontend capabilities."""
        title = "Add API endpoint for user authentication"
        caps = _detect_frontend_capabilities(title, "")
        assert not caps
    
    @pytest.mark.unit
    def test_combined_keywords(self):
        """Multiple keywords all captured."""
        title = "React + Tailwind dashboard"
        caps = _detect_frontend_capabilities(title, "")
        assert "react" in caps
        assert "tailwind" in caps
```

### Integration Tests

```python
# tests/integration/test_preview_notify_route.py
class TestPreviewNotifyRoute:
    """Test worker callback endpoint."""
    
    @pytest.mark.integration
    async def test_notify_ready_transition(self, client, db, preview_session):
        """Valid notify request transitions to READY."""
        response = await client.post(
            "/api/v1/preview/notify",
            json={
                "sandbox_id": preview_session.sandbox_id,
                "status": "ready",
            },
        )
        assert response.status_code == 200
        
        # Verify DB updated
        updated = await db.get_preview(preview_session.id)
        assert updated.status == "ready"
        assert updated.preview_url is not None
    
    @pytest.mark.integration
    async def test_notify_unknown_sandbox(self, client):
        """Unknown sandbox returns 404."""
        response = await client.post(
            "/api/v1/preview/notify",
            json={"sandbox_id": "unknown", "status": "ready"},
        )
        assert response.status_code == 404
```

### E2E Test Checklist

- [ ] Create frontend task → capabilities populated
- [ ] Sandbox spawns → PREVIEW_ENABLED in env
- [ ] PreviewSession created → status=PENDING
- [ ] Worker starts → status=STARTING
- [ ] Dev server ready → status=READY
- [ ] WebSocket event fired → frontend receives
- [ ] Iframe loads → preview visible
- [ ] Stop button → status=STOPPED
- [ ] Python task → no preview created

---

## Troubleshooting Guide

### Preview Not Created

**Symptom**: No PreviewSession record for frontend task

**Checklist**:
1. Verify task has `required_capabilities` populated:
   ```sql
   SELECT required_capabilities FROM tasks WHERE id = 'task-123';
   ```
2. Check `_is_frontend_task()` returns True:
   ```python
   caps = {"react", "component"}
   bool(caps & FRONTEND_INDICATORS)  # Should be True
   ```
3. Verify `PREVIEW_ENABLED` in sandbox env vars

### Preview Stuck in PENDING

**Symptom**: PreviewSession never transitions to READY

**Checklist**:
1. Check worker logs for PreviewSetupManager:
   ```
   [PREVIEW] Starting dev server detection...
   ```
2. Verify agent started dev server (check `npm run dev` output)
3. Check `/notify` endpoint receiving callback
4. Verify no firewall blocking localhost:3000 in sandbox

### Iframe Won't Load

**Symptom**: Preview shows READY but iframe is blank

**Checklist**:
1. Open preview URL directly in browser
2. Check browser console for CSP errors
3. Verify `sandbox="allow-scripts allow-same-origin"` on iframe
4. Check Daytona preview link hasn't expired

### WebSocket Events Not Received

**Symptom**: `justBecameReady` never triggers

**Checklist**:
1. Verify WebSocket connection established
2. Check EventBus publishing PREVIEW_READY:
   ```python
   event_bus.publish(SystemEvent(
       event_type="PREVIEW_READY",
       payload={...}
   ))
   ```
3. Confirm `useEvents` hook subscribed to correct event types

---

## Future Improvements

### Phase 2: Enhanced Detection

- [ ] LLM-based capability detection for ambiguous cases
- [ ] Framework version detection (React 18 vs 19)
- [ ] Monorepo support (multiple packages, multiple previews)

### Phase 3: Performance

- [ ] Warm pool for <3s sandbox startup
- [ ] Preview session caching across task restarts
- [ ] Incremental dev server sync (HMR over WebSocket)

### Phase 4: Collaboration

- [ ] Multi-user preview sessions
- [ ] Comment/annotation on preview
- [ ] Screenshot comparison for visual regression

### Phase 5: Advanced Features

- [ ] Interactive mid-task sessions (ask_user, interrupt/resume)
- [ ] Port configuration per-framework (Vite=5173, Next=3000)
- [ ] Mobile preview emulation
- [ ] Accessibility audit integration

---

## Related Files

| File | Purpose |
|------|---------|
| `docs/design/live-preview/prototype-plan.md` | Original design document |
| `backend/omoi_os/api/routes/preview.py` | REST API endpoints |
| `backend/omoi_os/services/preview_manager.py` | Business logic |
| `backend/omoi_os/models/preview_session.py` | Database model |
| `backend/omoi_os/services/daytona_spawner.py` | Sandbox integration |
| `backend/omoi_os/workers/claude_sandbox_worker.py` | Worker-side setup |
| `backend/omoi_os/api/routes/tickets.py` | Capability detection |
| `frontend/hooks/usePreview.ts` | React Query + WebSocket hook |
| `frontend/components/preview/PreviewPanel.tsx` | UI component |
| `frontend/lib/api/preview.ts` | API client |

---

<claude-mem-context>
# Recent Activity

<!-- This section is auto-generated by claude-mem. Edit content outside the tags. -->

### Feb 9, 2026

| ID | Time | T | Title | Read |
|----|------|---|-------|------|
| #2484 | 3:47 PM | 🔵 | Comprehensive Security Audit Reveals Critical Vulnerabilities Beyond RLS | ~506 |
| #2482 | " | 🔵 | User Profile and Password Management Endpoints | ~465 |
</claude-mem-context>
