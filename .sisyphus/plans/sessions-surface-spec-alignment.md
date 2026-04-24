# Sessions Surface — Spec Alignment

## TL;DR

> **Quick Summary**: Extend the existing `/api/v1/sessions` surface (currently a thin alias over `/api/v1/tasks`) into a spec-compliant session API by adding four missing endpoints (events SSE, reply, fork, share), standardizing the event envelope (`seq` + `actor`), bridging the existing per-entity WebSocket into a per-session multiplayer channel, and extending both SDKs with a `sessions` resource that mirrors spec §09. Smoke test is then rewritten to drive everything through the SDK, and a dedicated SDK e2e suite exercises the four primitive interaction patterns (fire-and-forget / sync wait / live stream / multiplayer) from spec §18.
>
> **Deliverables**:
> - 2 new DB columns (`events.seq`, `events.actor`) + 2 new tables (`session_acls`, `session_forks`)
> - 6 new backend routes on `/api/v1/sessions/{id}`: `events` (SSE), `messages` (reply), `fork`, `share`, `artifacts`, `ws` (per-session multiplayer)
> - Event envelope standardization service (`SessionEventEnvelope`) that wraps all existing publish calls
> - Idempotency-Key middleware for POST /api/v1/sessions
> - Auth-header alignment: accept `Authorization: Bearer <token>` alongside existing `X-API-Key`
> - Python SDK `sessions` resource: create/get/list/cancel/reply/fork/share/events (async iterator)/connect (WS channel)/artifacts
> - TypeScript SDK same surface, idiomatic (AsyncIterable + SessionChannel)
> - Auto-pagination for `list()` methods (both SDKs)
> - Rewritten smoke test that drives lifecycle through the SDK (replaces raw-HTTP phases)
> - New SDK e2e suite: Python + TypeScript tests mirroring spec §18's 4 interaction patterns
>
> **Estimated Effort**: Large (~7 working days)
> **Parallel Execution**: YES — 5 waves
> **Critical Path**: Wave 1 (envelope + auth) → Wave 2 (endpoints) → Wave 4 (SDK) → Wave 5 (tests)

---

## Context

### Original Request
> "Let's go with the second [spec-shaped sessions API + SDK methods]. That said, I also have the Daytona spawner, so it spawns something inside of a sandbox. It does do a lot of stuff already. Geez, I'm looking at some stuff, and it might make more sense to just do some things."

The user committed to building the spec-shaped session surface but flagged that a lot is already built. The plan takes advantage of that rather than ignoring it.

### What already exists (discovery)

**Backend (confirmed by grep/read, not speculation):**
- `backend/omoi_os/services/daytona_spawner.py` — 3,866 lines. Sandbox create, bootstrap, repo clone, GitHub integration, agent event reporting back to API, cancel, timeout, polling messages. The full session-execution path is already here.
- `backend/omoi_os/api/routes/tasks.py` — 1,406 lines. `POST /api/v1/tasks` (create), `GET /api/v1/tasks/{id}` (get), `PATCH /api/v1/tasks/{id}` (update), `POST /api/v1/tasks/{id}/cancel`, dependencies, timeouts, titles.
- `backend/omoi_os/api/routes/sessions.py` — thin alias over tasks. Has list/get/create/delete/patch; missing events, fork, reply, share, per-session WS.
- `backend/omoi_os/api/routes/events.py` — global WebSocket at `/ws/events` subscribed to Redis pub/sub `events.*` pattern. Supports filters by `event_type`, `entity_type`, `entity_id`. Authenticated via `?token=<jwt>`.
- `backend/omoi_os/services/event_bus.py` — Redis pub/sub EventBusService. Graceful degradation if Redis unavailable.
- `backend/omoi_os/models/event.py` — `events` table: `id, event_type, entity_type, entity_id, payload (JSONB), timestamp`. **Missing: `seq` (monotonic per session), `actor` (agent/user_id/system).**
- `backend/omoi_os/services/credential_broker.py` + route at `/api/v1/credentials/broker` — already enforces env-declared scopes.
- Daytona spawner calls `report_event(event_type, event_data, source="agent")` back to the API during execution — the data stream to standardize is already flowing.

**SDKs:**
- `sdk/python/omoios/` — `client.py`, `resources/{artifacts,credentials,environments,webhooks,workspaces}.py`. **No `sessions.py`.**
- `sdk/typescript/src/` — mirror structure. **No `sessions.ts`.**
- Both use `X-API-Key` header; spec uses `Authorization: Bearer`.
- Neither has SSE iterator. Neither has WebSocket. Neither has auto-pagination (list returns `list[T]`, spec wants `AsyncIterable[T]`).

### Metis review

**Architectural trade-offs considered:**
- **Parallel spec-shaped API (`/v1/organizations/{org}/sessions/*`) vs. extending the existing alias.** Parallel would match spec paths exactly but requires double-maintenance and DB shims between session_id ↔ task_id. Rejected in favor of extension because task model = session model (confirmed by spec §17's name-mapping table) and the existing alias already serves `/api/v1/sessions`. Spec path fidelity is a v2 cleanup, not a v1 blocker.
- **Per-session WS endpoint vs. extending global `/ws/events`.** Could bolt a per-session filter onto the existing global socket, but spec §07's multiplayer semantics (participant.joined/left, cursor.moved) need a *session-scoped* broadcast group, not a filter over a global firehose. A thin new `/api/v1/sessions/{id}/ws` that joins a per-session channel on the event bus is the cleaner split.
- **Event envelope: migrate existing data vs. stamp on read.** Existing `events` rows have no `seq`/`actor` — backfilling is possible but brittle. Decision: new columns nullable; envelope emitter populates them for new events; SSE reader synthesizes `seq` for old rows by ORDER BY timestamp. Low-risk.
- **Idempotency storage.** Spec requires `Idempotency-Key` to dedup retries. Simplest: Redis SETEX with the key as `{org_id}:{route}:{key}` → `{task_id}` for a 24h window. No new table.

**Risks logged:**
- Existing `/ws/events` has one socket per client subscribing to all event types. Adding per-session WS is additive, but if clients also want presence, we need to attribute messages with `user_id` from the JWT — currently only `entity_id` is propagated. ✅ Mitigated by task #10.
- Daytona spawner's `report_event` calls do not include a monotonic seq — they rely on insertion timestamp. The envelope emitter must serialize per-session to avoid `seq` collisions. ✅ Mitigated by task #2 using SQL `SELECT MAX(seq)+1 FOR UPDATE`.
- `httpx-sse` is the library for Python per `feedback_sdk_sse_library.md`. Don't hand-roll. ✅ Enforced in task #14.

---

## Work Objectives

### Core Objective
Turn `/api/v1/sessions` into a spec §03-compliant session API by adding the missing endpoints, standardizing the event envelope, and wiring both SDKs to drive the full spec §18 interaction surface. End state: smoke test and SDK e2e suite can exercise fire-and-forget, sync wait, live stream, and multiplayer patterns entirely through the SDK.

### Concrete Deliverables
- Alembic migration: `events.seq` (BIGINT, nullable), `events.actor` (VARCHAR, nullable), `session_acls` table, `session_forks` table, index on `(entity_id, seq)` for SSE reads
- `SessionEventEnvelope` service in `backend/omoi_os/services/session_event_envelope.py` — wraps `event_bus.publish()` with per-session monotonic seq + actor attribution
- 6 new routes on `/api/v1/sessions/{id}`: `GET /events` (SSE, Last-Event-Id resume), `POST /messages` (reply), `POST /fork` (from seq), `POST /share` (ACL grants), `GET /artifacts`, `WS /ws`
- Idempotency-Key middleware: Redis-backed, 24h window, applies to POST /api/v1/sessions
- `authentication.py` update: accept `Authorization: Bearer <token>` for all three token types (rpk_live_, eyJ, sess_tok_)
- Python SDK: `omoios/resources/sessions.py` with full spec §09 surface, `events` via httpx-sse, `connect` via `websockets` library, `AsyncIterator` for `list()`
- TypeScript SDK: `sdk/typescript/src/resources/sessions.ts` with `AsyncIterable<Event>`, `SessionChannel` class, auto-pagination
- Both SDKs: accept `apiKey`/`userToken`/`sessionToken` constructor params, send `Authorization: Bearer`
- Smoke test rewritten: all lifecycle phases go through Python SDK; raw-HTTP reserved for CRUD of already-built surfaces (credentials/environments/artifacts/webhooks)
- `sdk/python/tests/test_e2e_spec_patterns.py` + `sdk/typescript/tests/spec-patterns.e2e.test.ts` — mirror each other, each exercises the 4 primitive patterns against a running backend

### Definition of Done
- [ ] `alembic upgrade head` and `alembic downgrade -1` both clean
- [ ] `just test-all` passes including new SDK e2e suites
- [ ] `just check` passes (ruff + mypy + eslint + tsc)
- [ ] Smoke test reports PASS on all new `session_*` tier phases (see §Verification)
- [ ] Both SDKs' e2e suites pass against a backend with all feature flags on + real Daytona
- [ ] No breaking changes to existing `/api/v1/tasks/*` surface
- [ ] Existing `/ws/events` still works unchanged
- [ ] `openapi.json` lists all 6 new routes with correct shapes

### Must Have
- Event envelope on *every* event emitted after this plan lands: `{id, seq, type, session_id, actor, timestamp, data}`
- SSE resume from `Last-Event-Id: <seq>` returns events strictly after that seq
- Fork creates a new task with `parent_task_id` set + events copied up to `from_seq`
- Share writes to `session_acls` with role in (`owner`, `editor`, `viewer`); GET /sessions/{id} surfaces the ACL
- Per-session WS broadcasts `participant.joined` on connect and `participant.left` on disconnect to all other WS connections on that session
- Idempotency-Key: same key + same body → same response; same key + different body → `409 conflict`
- SDK `sessions.events(id)` is an async iterator that closes cleanly on AbortSignal/cancel
- SDK `sessions.connect(id, userJwt)` returns a channel with `.on(type, fn)`, `.send(msg)`, `.close()`
- Python `sessions.list()` and TS `sessions.list()` auto-paginate (return `AsyncIterator`/`AsyncIterable`)

### Must NOT Have (Guardrails)
- No renaming of `tasks` table to `sessions` (DB stays put, API is the surface)
- No new session-specific tables beyond `session_acls` and `session_forks`
- No breaking changes to existing `/api/v1/tasks/*`, `/api/v1/sessions/*` (old methods), or `/ws/events`
- No parallel `/v1/organizations/{org}/sessions/*` surface — use `/api/v1/sessions/*` only
- No backfill migration for existing `events` rows — null seq/actor is fine for historical data
- No synthesis of "fake" events in the SDK — if the backend doesn't emit it, the SDK doesn't yield it
- No SDK convenience helpers beyond what spec §09 lists (v1.0 is thin wrapper)
- No authentication rewrite — extend existing JWT + API-key verification, don't replace
- No Better Auth adoption (per `17-omoi-os-adaptation.md §6`)
- No drive-by refactoring of daytona_spawner.py
- Do NOT include `<THINKING>`, `<TASK>`, or any XML-style agent instruction wrappers in code — they're artifacts from the spec, not real Python/TS syntax

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** — all verification is agent-executed. Evidence saved to `.sisyphus/evidence/sessions-surface/task-{N}-{slug}.{ext}`.

### Test Decision
- **Framework**: pytest (backend + Python SDK), vitest (TypeScript SDK), smoke test script
- **TDD**: RED → GREEN → REFACTOR per task. New route endpoint → failing unit test → minimal impl → pass → refactor.
- **Integration surface**: mock httpx server for SDK unit tests, real local backend + real Daytona for SDK e2e and smoke test

### QA Policy
Every task MUST include agent-executed QA scenarios. Evidence:
- **Backend endpoint**: `curl` with auth header → assert status + response shape. Save `curl -i` output.
- **DB migration**: `alembic upgrade head` then inspect `\d events` and `\dt session_*` from psql. Save schema dump.
- **Envelope standardization**: emit one event, SELECT it, assert `seq IS NOT NULL AND actor IS NOT NULL`. Save query result.
- **SSE stream**: `curl -N` against `/events`, kill after 3 frames, reconnect with `Last-Event-ID: <seq>`, assert next frame's seq = last+1. Save two curl logs.
- **Python SDK**: `uv run pytest sdk/python/tests/test_e2e_spec_patterns.py -v`. Save pytest output.
- **TS SDK**: `cd sdk/typescript && pnpm test tests/spec-patterns.e2e.test.ts`. Save vitest output.
- **Smoke test**: `uv run python scripts/smoke_agent_platform.py --report .sisyphus/evidence/sessions-surface/smoke-after.json`. Diff with pre-plan smoke report.

---

## Execution Strategy

### Wave Structure

```
Wave 1 — Foundation [parallel]
  ├─ Task 1: Alembic migration (seq/actor columns + ACL + fork tables)
  ├─ Task 2: SessionEventEnvelope service
  └─ Task 3: Auth header alignment (Authorization: Bearer)

Wave 2 — Session endpoints [parallel, gated by Wave 1]
  ├─ Task 4: GET /sessions/{id}/events (SSE + resume)
  ├─ Task 5: POST /sessions/{id}/messages (reply)
  ├─ Task 6: POST /sessions/{id}/fork
  ├─ Task 7: POST /sessions/{id}/share + ACL check on GET
  ├─ Task 8: GET /sessions/{id}/artifacts
  └─ Task 9: Idempotency-Key middleware for POST /sessions

Wave 3 — Multiplayer WS [gated by Wave 2]
  └─ Task 10: WS /api/v1/sessions/{id}/ws (presence + message.send + cursor.moved)

Wave 4 — SDK expansion [parallel, gated by Wave 2]
  ├─ Task 11: Python SDK sessions resource (create/get/cancel/reply/fork/share/artifacts)
  ├─ Task 12: Python SDK events async iterator (httpx-sse)
  ├─ Task 13: Python SDK WebSocket channel (websockets lib) [gated by Wave 3]
  ├─ Task 14: Python SDK auto-pagination for list() methods
  ├─ Task 15: TS SDK sessions resource
  ├─ Task 16: TS SDK events AsyncIterable
  ├─ Task 17: TS SDK SessionChannel class [gated by Wave 3]
  └─ Task 18: SDK auth header alignment (both)

Wave 5 — Tests [parallel, gated by Wave 4]
  ├─ Task 19: Smoke test rewrite — session lifecycle via SDK
  ├─ Task 20: Smoke test Tier B (multiplayer) + Tier C (error envelope)
  ├─ Task 21: Python SDK e2e suite (4 spec patterns)
  └─ Task 22: TS SDK e2e suite (4 spec patterns)

Final Verification Wave [sequential]
  ├─ F1: OpenAPI compliance audit
  ├─ F2: Spec §03/§07 fidelity audit (envelope shape + ACL enforcement)
  └─ F3: SDK surface parity audit (Python ↔ TS method-for-method)
```

### Dependency Matrix

| Task | Depends on | Blocks |
|------|-----------|--------|
| 1    | —         | 2, 4, 6, 7 |
| 2    | 1         | 4, 5, 10 |
| 3    | —         | 18 |
| 4    | 1, 2      | 11, 12, 19 |
| 5    | 2         | 11, 19 |
| 6    | 1, 2      | 11, 19 |
| 7    | 1         | 11, 19 |
| 8    | —         | 11, 19 |
| 9    | —         | 19 |
| 10   | 2         | 13, 17, 20 |
| 11   | 4, 5, 6, 7, 8 | 19, 21 |
| 12   | 4         | 19, 21 |
| 13   | 10        | 21 |
| 14   | 11        | 21 |
| 15   | 4, 5, 6, 7, 8 | 22 |
| 16   | 4         | 22 |
| 17   | 10        | 22 |
| 18   | 3         | 21, 22 |
| 19   | 11, 12, 14, 18 | F1–F3 |
| 20   | 13, 17    | F1–F3 |
| 21   | 11–14, 18 | F1–F3 |
| 22   | 15–18     | F1–F3 |

---

## TODOs

### Wave 1 — Foundation

#### Task 1 — Alembic migration: envelope columns + ACL + fork tables
**Files**: `backend/migrations/versions/070_session_envelope_and_acls.py` (new)
**What**:
- Add `events.seq BIGINT NULL` and `events.actor VARCHAR(100) NULL`
- Create composite index `ix_events_entity_seq (entity_id, seq)` for SSE `Last-Event-Id` resume
- Create `session_acls (id UUID PK, task_id UUID FK→tasks ON DELETE CASCADE, user_id UUID FK→users, role VARCHAR(10) CHECK role IN ('owner','editor','viewer'), created_at, UNIQUE(task_id, user_id))`
- Create `session_forks (id UUID PK, parent_task_id UUID FK→tasks, child_task_id UUID FK→tasks, from_seq BIGINT, created_at)`
**QA**: `alembic upgrade head`, psql `\d events` shows new cols, `\d session_acls` exists, `\d session_forks` exists; `alembic downgrade -1` cleanly removes all four changes.
**Must not**: Don't backfill seq for existing rows. Don't add NOT NULL constraints.

#### Task 2 — SessionEventEnvelope service
**Files**: `backend/omoi_os/services/session_event_envelope.py` (new)
**What**: One function `emit(task_id, event_type, actor, data)`. Inside a DB transaction: `SELECT MAX(seq) FROM events WHERE entity_id = :task_id FOR UPDATE; next = max+1; INSERT INTO events (…, seq=next, actor=actor, payload=data); event_bus.publish(SystemEvent(…, payload={"envelope": {seq, actor, id, timestamp}, "data": data}))`. Returns the full envelope dict.
- Wrap existing call sites in `daytona_spawner.py` → `report_event` handler → this service
- Wrap task lifecycle hooks (create, assign, start, succeed, fail, cancel) in task_queue service
**QA**: pytest unit test — emit 3 events for one task, assert seq = 1, 2, 3; emit 2 events for second task concurrently, assert each has its own seq sequence (no collision).
**Must not**: Don't skip the FOR UPDATE lock. Don't bypass event_bus.publish (downstream WS depends on it).

#### Task 3 — Auth header alignment
**Files**: `backend/omoi_os/api/dependencies.py` (edit `get_current_user` and `get_auth_context`)
**What**: Already accepts `Authorization: Bearer <jwt>` for JWTs and `Authorization: Bearer <api_key>` per prior work. This task formalizes: accept any Bearer token, dispatch by prefix (`rpk_live_`/`sess_tok_`/everything else = JWT). Return an `AuthContext` dataclass `(user, org_id, token_kind: Literal["platform", "user", "session"])`. Keep `X-API-Key` header support for backward compat.
**QA**: curl tests — (a) `Authorization: Bearer rpk_live_xxx` → 200 on `/api/v1/sessions`, (b) `Authorization: Bearer eyJxxx` → 200, (c) `X-API-Key: rpk_live_xxx` → 200 (legacy), (d) no header → 401. `sess_tok_` dispatch branch exists but is only exercised once `agent-platform-gaps.md` Task 5 lands (which issues the tokens); include a unit test that verifies a `sess_tok_xxx` token is routed to a stub verifier rather than the JWT verifier.
**Must not**: Don't drop `X-API-Key` support — existing clients use it. Don't implement the session-token verifier here — that's the other plan's `SandboxSessionService`.

### Wave 2 — Session endpoints

#### Task 4 — GET /api/v1/sessions/{id}/events (SSE with resume)
**Files**: `backend/omoi_os/api/routes/sessions.py` (add endpoint)
**What**:
```
@router.get("/{session_id}/events")
async def session_events(session_id: UUID, last_event_id: Optional[str] = Header(None), …):
    async def gen():
        # 1. Replay: SELECT * FROM events WHERE entity_id=session_id AND seq > last_event_id ORDER BY seq LIMIT 1000
        # 2. Live: subscribe event_bus channel "events.*" with entity_id filter
        for event in replay + live:
            yield f"id: {event.seq}\ndata: {json.dumps(envelope(event))}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
```
- Shape the JSON per spec §03: `{id, seq, type, session_id, actor, timestamp, data}`
- Honor `Last-Event-ID` header (spec-standard name) — parse as int seq
- On disconnect (client closes connection), cancel the live subscription cleanly
**QA**: Start a Daytona session, curl -N /events, cut at 3 frames, reconnect with `Last-Event-ID: 3`, assert next frame has `seq: 4`. Save both logs.
**Must not**: Don't buffer events in memory beyond what's needed for one frame. Don't emit events that don't have seq populated (skip legacy nulls with a comment).

#### Task 5 — POST /api/v1/sessions/{id}/messages (reply)
**Files**: `backend/omoi_os/api/routes/sessions.py` + `backend/omoi_os/services/session_messages.py` (new)
**What**: Accept `{"text": "..."}`; append to a Redis list `session:{id}:inbox` for the sandbox worker to poll (spawner already has `poll_messages`); emit `session.message` event via envelope with `actor=user:<user_id>`. Return `204`.
**QA**: Start session, POST reply, assert daytona spawner's next `poll_messages` call returns it; assert an event with `type=session.message` and matching text appears in `/events` stream.
**Must not**: Don't block the HTTP response on the agent reading the message — fire-and-forget enqueue + event emit.

#### Task 6 — POST /api/v1/sessions/{id}/fork
**Files**: `backend/omoi_os/api/routes/sessions.py`
**What**: Accept `{"from_seq": int, "prompt": str}`. Create new task (same workspace, org, AND same `environment_version_id` — must preserve the pinned version so the fork inherits the same `environment_versions.credentials` map from agent-platform-gaps.md migration 068); INSERT INTO session_forks(parent, child, from_seq); copy events WHERE entity_id=parent AND seq <= from_seq into child with new seqs starting at 1 and `actor` preserved; enqueue new task via `task_queue`. Return the new session shape.
**QA**: Fork at seq 3 of a 5-event session; assert child has 3 events with seqs 1..3 matching parent's types; assert parent still has 5 events; assert child's task_queue has a row.
**Must not**: Don't copy artifacts (child produces its own). Don't reuse task_id.

#### Task 7 — POST /api/v1/sessions/{id}/share + ACL enforcement
**Files**: `backend/omoi_os/api/routes/sessions.py`, edit `verify_task_access` in `api/dependencies.py`
**What**: Accept `{"grants": [{"user_id": uuid, "role": "editor"|"viewer"}]}`. UPSERT into session_acls. Update `verify_task_access` to accept the grant: owner|editor→full access, viewer→read-only. Update `GET /sessions/{id}` response to include an `acl` field per spec §02: `{owner, editors, viewers}`.
**QA**: As user A, create session + share with user B (editor). As user B, GET /sessions/{id} succeeds; POST /messages succeeds; POST /share is 403. As user C (ungranted), GET is 404.
**Must not**: Don't allow cross-org sharing (reject if target user's org ≠ session's org). Don't let non-owners transfer ownership.

#### Task 8 — GET /api/v1/sessions/{id}/artifacts
**Files**: `backend/omoi_os/api/routes/sessions.py`
**What**: Thin proxy — `SELECT * FROM artifacts WHERE workspace_id = (SELECT workspace_id FROM tasks WHERE id = session_id) AND artifact_metadata->>'task_id' = session_id`. The artifact service already stores `task_id` in `artifact_metadata`; this query just filters.
**QA**: Upload an artifact with `metadata={"task_id": "<sid>"}`, GET /sessions/{sid}/artifacts returns it; artifact from a different task is not returned.
**Must not**: Don't duplicate the artifact data — return the same `ArtifactResponse` shape as `/api/v1/artifacts`.

#### Task 9 — Idempotency-Key middleware
**Files**: `backend/omoi_os/api/middleware/idempotency.py` (new) + register in `api/main.py`
**What**: Before POST /api/v1/sessions, read header `Idempotency-Key`. Compute `fp = sha256(body)`. Redis `GET idem:{org_id}:{route}:{key}` → if miss: `SETEX 86400 {fp}:{response_json}`, proceed; if hit with same fp: return stored response (same status); if hit with different fp: `409 conflict` with `{"error": {"code": "conflict", …}}`.
**QA**: Same key + same body twice → two 201s with same `id`; same key + different body → 409.
**Must not**: Don't block GETs. Don't cache error responses (only 2xx).

### Wave 3 — Multiplayer WS

#### Task 10 — WS /api/v1/sessions/{id}/ws
**Files**: `backend/omoi_os/api/routes/sessions.py` (add `@router.websocket("/{session_id}/ws")`)
**What**:
- Auth: `?token=<jwt>` (reuse `_authenticate_websocket` from events.py, generalize)
- On connect: call `verify_task_access(session_id, user)`; close 4403 if forbidden
- Join a per-session broadcast channel (new class `SessionChannelManager`, one set of sockets per session_id)
- Emit `participant.joined {user_id}` to peers; on disconnect emit `participant.left`
- Forward inbound messages: `{"type": "message.send", "data": {"text": …}}` → reuse task 5's reply logic + broadcast to peers; `{"type": "cursor.moved", "data": {file, line}}` → broadcast to peers only (not persisted)
- Forward outbound: subscribe to event_bus events for this session_id → push to all peers in channel
**QA**: Open two WS (userA owner, userB editor via share). userA sends `message.send`; assert userB receives it; assert event appears in `/events` SSE stream of a third observer.
**Must not**: Don't broadcast `cursor.moved` cross-session. Don't persist cursor events to `events` table.

### Wave 4 — SDK expansion

#### Task 11 — Python SDK sessions resource
**Files**: `sdk/python/omoios/resources/sessions.py` (new), `sdk/python/omoios/types.py` (add Session, Event, ACL, Artifact types)
**Coordination note**: The `Session` type must include `session_token: Optional[str] = None` to accept the one-time bearer the other plan (`agent-platform-gaps.md` Task 5) adds to the `POST /api/v1/sessions` response. Field only populates on `create`, not on `get`/`list`.
**What**:
```python
class SessionsResource:
    async def create(self, *, workspace_id, prompt, environment_id=None, share_with=None,
                     metadata=None, idempotency_key=None) -> Session: ...
    async def get(self, session_id: str) -> Session: ...
    async def cancel(self, session_id: str) -> Session: ...
    async def reply(self, session_id: str, text: str) -> None: ...
    async def fork(self, session_id: str, from_seq: int, prompt: str) -> Session: ...
    async def share(self, session_id: str, grants: list[Grant]) -> None: ...
    async def artifacts(self, session_id: str) -> list[Artifact]: ...
```
Each method: build URL, call `client._request(…)`, validate Pydantic model, return.
**QA**: Unit test against mock httpx — each method asserts URL + method + headers + body shape.
**Must not**: Don't add retry policies. Don't add caching. Per spec §18 §7.

#### Task 12 — Python SDK events async iterator
**Files**: `sdk/python/omoios/resources/sessions.py` (add `events` method), `pyproject.toml` (add `httpx-sse>=0.4`)
**What**:
```python
async def events(self, session_id: str, *, last_event_id: Optional[str] = None) -> AsyncIterator[Event]:
    from httpx_sse import aconnect_sse
    headers = {"Accept": "text/event-stream"}
    if last_event_id: headers["Last-Event-ID"] = last_event_id
    async with aconnect_sse(self._client._http, "GET", f"/api/v1/sessions/{session_id}/events", headers=headers) as es:
        async for sse in es.aiter_sse():
            yield Event(**json.loads(sse.data))
```
**QA**: e2e test — create session, `async for evt in events(id)` yields at least 3 events; break loop, re-enter with `last_event_id=<last_seq>`, assert first yielded event's seq = last_seq + 1.
**Must not**: Don't hand-roll the SSE parser (per memory `feedback_sdk_sse_library.md`).

#### Task 13 — Python SDK WebSocket channel
**Files**: `sdk/python/omoios/resources/sessions.py` (add `connect` method), `pyproject.toml` (add `websockets>=12`)
**What**:
```python
def connect(self, session_id: str, user_token: str) -> "SessionChannel":
    return SessionChannel(self._client, session_id, user_token)

class SessionChannel:
    def on(self, event_type: str, fn: Callable[[Event], None]) -> None: ...
    async def send(self, msg: dict) -> None: ...
    async def close(self) -> None: ...
    async def __aenter__(self) -> "SessionChannel": ...  # opens ws
    async def __aexit__(self, *exc) -> None: ...  # closes
```
Underneath: one `websockets.connect` call; dispatcher task reads messages and fires registered callbacks.
**QA**: e2e — two channels on same session, `ch_a.send({"type":"message.send","data":{"text":"hi"}})`, assert `ch_b.on("session.message")` callback fires with matching text.
**Must not**: Don't swallow connection errors silently — raise `ConnectionError` with detail.

#### Task 14 — Python SDK auto-pagination
**Files**: `sdk/python/omoios/resources/{credentials,artifacts,webhooks,environments,sessions}.py`
**What**: Convert `list()` methods from `async def list(…) -> list[T]` to `async def list(…) -> AsyncIterator[T]` that pages using `limit`/`offset` or `cursor` (whichever the endpoint supports). Keep a `list_sync() -> list[T]` helper for the common case.
**QA**: Seed 150 items with limit=100; `[x async for x in client.sessions.list()]` returns all 150 (two page fetches).
**Must not**: Don't break existing SDK tests — update them to use `list_sync()` or `[x async for x in]`.

#### Task 15 — TS SDK sessions resource
**Files**: `sdk/typescript/src/resources/sessions.ts` (new), `sdk/typescript/src/types.ts` (extend)
**What**: Mirror task 11 surface. Each method is `async` returning `Promise<T>` or `void`.
**QA**: Vitest against mock node:http server — each method sends correct HTTP wire format.

#### Task 16 — TS SDK events AsyncIterable
**Files**: `sdk/typescript/src/resources/sessions.ts` (add `events` method)
**What**: Use native `fetch` + `ReadableStream` to parse SSE frames (same pattern as spec §09 example). Return `AsyncIterable<Event>`. Respect `AbortSignal`.
```ts
async *events(id: string, opts: {lastEventId?: string, signal?: AbortSignal} = {}): AsyncIterable<Event>
```
**QA**: vitest e2e — consume frames with `for await`, abort midway, reconnect with `lastEventId`, assert continuation.

#### Task 17 — TS SDK SessionChannel
**Files**: `sdk/typescript/src/resources/sessions.ts` (add `connect` + `SessionChannel` class), `sdk/typescript/package.json` (add `ws`)
**What**: WebSocket wrapper. `.on<T>(type, fn)` / `.send(msg)` / `.close()`.
**QA**: vitest e2e with two channels — presence + send/receive.

#### Task 18 — SDK auth header alignment
**Files**: `sdk/python/omoios/client.py`, `sdk/typescript/src/client.ts`
**What**: Send `Authorization: Bearer <token>` for all token kinds. Keep `X-API-Key` as fallback if passed via legacy param (with deprecation warning in doc). Add `sessionToken` constructor option.
**QA**: Unit tests — constructing with `api_key`, `jwt_token`, `session_token` each produce correct header on request.

### Wave 5 — Tests

#### Task 19 — Smoke test rewrite: session lifecycle via SDK
**Files**: `scripts/smoke_agent_platform.py` (refactor new tier phases to use `AsyncOmoiOSClient`)
**What**: Add phases that construct a Python SDK client and exercise:
- `session_create` — idempotency key test (same key twice = same id)
- `session_get` — shape validation against spec §02
- `session_events_sse` — consume ≥3 events, validate envelope fields
- `session_events_resume` — disconnect, reconnect with last_event_id, assert continuity
- `session_reply` — send reply, assert next event is session.message
- `session_fork` — fork at seq 2, assert child has 2 events
- `session_share` + `session_acl` — share with test user, verify role propagation
**QA**: `uv run python scripts/smoke_agent_platform.py --only session_create,session_get,session_events_sse,session_events_resume,session_reply,session_fork,session_share --report .sisyphus/evidence/sessions-surface/smoke-tier-a.json`

#### Task 20 — Smoke Tier B + Tier C
**Files**: `scripts/smoke_agent_platform.py`
**What**:
- Tier B: `session_ws_presence` — open two WS, assert participant.joined broadcast; `session_ws_message` — send from one, receive on other; `session_ws_cursor` — cursor moves not persisted but broadcast
- Tier C: `error_envelope_shape` — hit known-403 endpoint, assert `{error: {code, type, message, request_id}}`; `idempotency_conflict` — same key + different body → 409; `egress_denied_envelope` — sandbox hits non-allowlisted host → 451 with `code=egress_denied`
**QA**: Same pattern as task 19.

#### Task 21 — Python SDK e2e suite
**Files**: `sdk/python/tests/test_e2e_spec_patterns.py` (new)
**What**: 4 test classes, one per spec §18 pattern:
```python
class TestPatternA_FireAndForget:  # create + expect webhook later
class TestPatternB_SyncWait:  # create + iter events until session_ended
class TestPatternC_LiveStream:  # create + iter events + validate envelope
class TestPatternD_Multiplayer:  # two channels + presence + cross-channel message
```
Each requires `OMOIOS_API_BASE_URL` + `OMOIOS_PLATFORM_API_KEY` + `DAYTONA_API_KEY`.
**QA**: `uv run pytest sdk/python/tests/test_e2e_spec_patterns.py -v`.

#### Task 22 — TS SDK e2e suite
**Files**: `sdk/typescript/tests/spec-patterns.e2e.test.ts` (new)
**What**: Mirror task 21 in vitest.
**QA**: `cd sdk/typescript && pnpm test tests/spec-patterns.e2e.test.ts`.

---

## Final Verification Wave

### F1 — OpenAPI compliance audit
Curl `GET /openapi.json | jq '.paths | keys[] | select(contains("sessions"))'`. Assert presence of all 6 new routes. Assert schemas for event envelope match spec §03. Save to `.sisyphus/evidence/sessions-surface/f1-openapi.json`.

### F2 — Spec §03 / §07 fidelity audit
Run smoke test with `--report` and grep the JSON for: every emitted event has all 7 envelope fields; ACL response matches spec §02 shape; WS events include `user_id` attribution per §07. Save evidence.

### F3 — SDK surface parity audit
Introspect both SDKs: Python via `dir(client.sessions)`, TS via `Object.getOwnPropertyNames(client.sessions.__proto__)`. Assert identical public method names (modulo camelCase ↔ snake_case). Save both lists.

---

## Commit Strategy

One commit per task. Wave-level commits squash to main. Commit message format:
```
feat(sessions): <task summary>

- <change 1>
- <change 2>

QA: <evidence file path>

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

Each wave lands as a mergeable PR. Wave boundaries are safe checkpoints — the repo can ship mid-plan without breaking existing clients.

---

## Success Criteria

1. Smoke test reports `PASS` on every new `session_*` and `error_*` phase; zero `FAIL`; `GAP` count reduced to ≤ current baseline
2. `sdk/python/tests/test_e2e_spec_patterns.py` — all 4 pattern classes pass against a real backend + real Daytona
3. `sdk/typescript/tests/spec-patterns.e2e.test.ts` — same, in vitest
4. `openapi.json` lists: `GET /api/v1/sessions/{id}/events`, `POST /api/v1/sessions/{id}/messages`, `POST /api/v1/sessions/{id}/fork`, `POST /api/v1/sessions/{id}/share`, `GET /api/v1/sessions/{id}/artifacts`, WS `/api/v1/sessions/{id}/ws`
5. No regression in existing `/api/v1/tasks/*` endpoints (verified by unchanged test suite output)
6. No regression in existing `/ws/events` global socket
7. Event envelope standardization applied to ALL new events post-deploy: `seq IS NOT NULL AND actor IS NOT NULL` for every row with `created_at > <deploy ts>`
8. Both SDK packages build and publish cleanly (`uv build` + `pnpm build`)

---

## Out of Scope (Deferred to v2)

- Renaming `tasks` DB table to `sessions` — cosmetic, scheduled window only
- `/v1/organizations/{org}/sessions/*` path fidelity — current `/api/v1/sessions` stays; spec-path rewriting is a gateway-level concern
- Token-exchange flow (`POST /oauth/token` grant_type=token-exchange) — tenant-backend pattern, not needed for SDK users directly
- Quota enforcement at the route level (429 + Retry-After) — current middleware does rate limiting but not per-org quota dimensions
- Per-session billing metering beyond what's already in task.usage
- Editor iframe URL (`urls.editor`) — UI integration, not SDK/backend
- OAuth-based connection management for GitHub/GitLab (already works under a different route surface)
