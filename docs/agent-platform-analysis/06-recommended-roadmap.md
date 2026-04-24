# 06 · Recommended Roadmap

Given the analysis in §02–§05, here is the concrete plan to get OmoiOS to spec conformance. **One PR per item**, in this order. Each PR is independently shippable; none blocks the production service.

## 6.1 · The Principles

Before the plan, three principles that shape every PR:

1. **No behavior change without a flag.** Every migration ships behind a feature flag or per-org override. Flip for one tenant first, watch metrics for 48h, then roll out.
2. **Spec surface first, storage later.** API aliases expose spec-compliant shapes over existing tables. Don't touch `tasks` table just to rename it to `sessions` — alias in the serializer. DB renames wait for a maintenance window (or never happen).
3. **Adapter interfaces before implementations.** Every new provider (Modal, OpenCode) lands as a new class implementing an existing Protocol. No behavior change unless the flag flips.

## 6.2 · The Plan

| PR | Scope | Effort | Prereqs | Risk |
|---|---|---|---|---|
| 0 | Audit + decision doc | 1 hour | — | None |
| 1 | Adapter interfaces for sandbox + agent | 1 day | — | None (pure refactor) |
| 2 | Session API alias + event envelope | 1–2 days | PR 1 | Low |
| 3 | Session token + Credential Broker | 2–3 days | PR 2 + §6.5 pricing decision | Medium |
| 4 | Environment resource | 2–3 days | PR 3 | Medium |
| 5 | Egress proxy | 3–5 days | PR 4 | Medium |
| 6 | Modal provider (parallel to prod) | 1 week | PR 1, 4 | Medium |
| 7 | Public SDK (TS + Python) | 2–3 days | PR 2 | Low |
| 8 | Client surfaces (Slack, CI, Chrome ext) | Per priority | PR 7 | Low |
| 9 | Polish: Artifact adapter, webhook dispatcher, multiplayer ACL, quota dims | 1 week | Various | Low |

**Critical path (PRs 0–5) = 2 weeks and closes every security gap.**
**Full plan = 6–8 weeks** (roughly aligns with `17-omoi-os-adaptation.md §9`).

## 6.3 · PR-by-PR Breakdown

### PR 0 · Audit + Decision Doc (1 hour)

**What:** Confirm the findings in [`03-current-implementation.md`](./03-current-implementation.md) are current. Any changes since 2026-04-23 get reflected. Write a decision doc committing to Option B and naming the owners for each PR.

**Output:** `docs/decisions/adr-202604-agent-platform-spec-adoption.md`.

**No code changes.**

### PR 1 · Adapter Interfaces (1 day) — **Start here**

**What:** Refactor `services/sandbox_provider.py` to be the *only* way code accesses sandboxes. Mirror for agent runtime — if `OpenHandsAgent` is the current runtime, define `AgentRuntime` Protocol; subsequent migration slots into this boundary.

**Why first:** Risk-free. Pays down a layer of debt. Every downstream PR depends on it.

**Files:**
```
backend/omoi_os/services/sandbox_provider.py     # unchanged — already good
backend/omoi_os/services/agent_runtime.py        # NEW Protocol
backend/omoi_os/services/openhands_agent.py      # NEW class moving logic from orchestrator
backend/omoi_os/workers/orchestrator_worker.py   # use AgentRuntime, not direct OpenHands
```

**Tests:** All existing sandbox tests pass unchanged.

### PR 2 · Session API Alias + Event Envelope (1–2 days)

**What:**
1. New routes at `/v1/organizations/{org}/sessions/*` that delegate to existing task handlers.
2. Response serializer wraps `Task` as a spec-shaped `Session` (rename `task_id` → `id`, add `environment_version`, `acl`, `urls.*`, `usage.*`).
3. Event emission wraps with spec envelope: `{id, seq, type, session_id, actor, timestamp, data}`.
4. Add `seq`, `actor` columns to `Event` via migration (nullable; populate for new events).
5. Add SSE endpoint `GET /v1/organizations/{org}/sessions/{id}/events`.

**Files:**
```
backend/omoi_os/api/routes/sessions.py        # NEW
backend/omoi_os/schemas/session.py            # NEW
backend/omoi_os/services/event_bus.py         # add emit_envelope()
backend/omoi_os/alembic/versions/xxxx_add_event_seq_actor.py  # migration
```

**Backward compat:** `/v1/organizations/{org}/tasks/*` keeps working. Don't break existing consumers. Deprecate on your own schedule.

**Risk:** Low. Both surfaces coexist; internal code unchanged.

### PR 3 · Session Token + Credential Broker (2–3 days)

**What:**
1. Add `kind` enum column to `APIKey` (values: `platform`, `user`, `agent`, `session`).
2. New `auth_service.create_session_token(task_id) -> (plaintext, APIKey)` with 1h TTL.
3. New `/broker/creds/{provider}` endpoint (see [`04-gap-analysis.md §4.3`](./04-gap-analysis.md) for the FastAPI sketch).
4. Modify orchestrator to mint session token on task create and pass `SESSION_TOKEN` env var to sandbox (in addition to existing plaintext for now — feature flag the switch).
5. Add `brokerMint` audit table.

**Flag:** `config.broker.enabled = False` initially. Only Broker-aware environments will resolve credentials via broker; old sandboxes still use plaintext injection.

**Files:**
```
backend/omoi_os/models/auth.py                # add kind column, APIKey.kind='session'
backend/omoi_os/models/broker_mint.py         # NEW audit table
backend/omoi_os/api/routes/broker.py          # NEW router
backend/omoi_os/services/auth_service.py      # create_session_token, verify_session_token
backend/omoi_os/workers/orchestrator_worker.py # inject SESSION_TOKEN
backend/omoi_os/alembic/versions/xxxx_session_token_broker.py
```

**Blocks:** §6.5 pricing decision (do we mint platform-aggregator keys on tenant Claude exhaustion? see `14-omo-opencode-sandbox.md §Reflective question`).

### PR 4 · Environment Resource (2–3 days)

**What:** First-class, versioned `Environment` per the spec.

**Schema:**
```sql
-- environments table
id UUID PK, organization_id UUID FK, project_id UUID FK NULL,
name TEXT, created_at, deleted_at;

-- environment_versions table
id UUID PK, environment_id UUID FK, version INT,
image JSONB, env JSONB, tools TEXT[], egress JSONB,
resources JSONB, credentials JSONB, files JSONB,
exposed_ports INT[], persistent_volume BOOL,
build_status TEXT, built_at TIMESTAMPTZ, built_image_ref TEXT,
UNIQUE(environment_id, version);
```

**Migration of existing tasks:**
- Tasks without `environment_id` keep working via a compat path that constructs an ad-hoc Environment from `Task.execution_config`
- New tasks pin `environment_id` + `environment_version` explicitly

**Routes:**
```
POST   /v1/organizations/{org}/environments
GET    /v1/organizations/{org}/environments
GET    /v1/organizations/{org}/environments/{id}
GET    /v1/organizations/{org}/environments/{id}/versions/{n}
POST   /v1/organizations/{org}/environments/{id}/versions
```

**Files:**
```
backend/omoi_os/models/environment.py         # NEW
backend/omoi_os/api/routes/environments.py    # NEW
backend/omoi_os/services/environment_service.py # NEW
backend/omoi_os/schemas/environment.py        # NEW
backend/omoi_os/alembic/versions/xxxx_environments.py
```

**Image build path:** For MVP, accept only `kind: "platform"` (pre-built images like `omo-runtime:2026-04`). Defer `dockerfile` and `snapshot` builds to a follow-up. This limits customer flexibility but unblocks everything else.

### PR 5 · Egress Proxy (3–5 days)

**What:** HTTP(S) proxy that enforces `environment.egress.allowed_hosts`. Sandbox network ACL allows outbound only to the proxy IP.

**Two implementations, pick one:**

**A. Envoy + Lua filter** — production-grade, steep learning curve. ~5 days.
**B. Custom Go proxy** — minimal, easy to debug, ~300 LOC. ~3 days. Recommended for MVP.

Either way:
- SNI sniffing for TLS without termination (don't decrypt tenant traffic — you'd need to manage tenant-specific CA trust)
- `Host:` header validation for plain HTTP (rare in an agent sandbox)
- Metrics: allowed/denied count per host per session
- Configurable per-tenant allowlist via session claims in the session token

**Files:**
```
services/egress-proxy/                  # NEW subdirectory or separate repo
    main.go                             # 300 LOC Go proxy
    Dockerfile
    k8s/deployment.yaml                 # or Fly.io / Railway config
```

**Integration:**
- Orchestrator sets `HTTP_PROXY` / `HTTPS_PROXY` env vars at sandbox boot
- Sandbox network ACL: allow outbound only to proxy CIDR
- Proxy receives session token via header, looks up environment, enforces

### PR 6 · Modal Provider (1 week, parallel to prod)

**What:** `ModalProvider(SandboxProvider)` implementation. Uses Python Modal SDK (mature, has all features).

**Why parallel:** Modal's billing is separate from Daytona. Running in parallel lets you A/B cost + latency + success-rate before flipping.

**Files:**
```
backend/omoi_os/services/modal_provider.py    # NEW
backend/omoi_os/services/modal_spawner.py     # NEW, analog to daytona_spawner
backend/omoi_os/services/sandbox_factory.py   # add elif provider_type == "modal"
```

**Key translation work** (per `15-modal-integration.md §4`):
- `env.image.kind: "platform"` → `modal.images.fromRegistry(ref)`
- `env.credentials[bearer_secret]` → per-session `modal.secrets.fromObject({...})`
- `env.exposed_ports` → `encryptedPorts: [...]` + tunnels
- `env.persistent_volume` → `modal.volumes.fromName(f"ws-{workspace_id}")`

**Rollout:**
1. Deploy with `config.sandbox.provider = "daytona"` (default) — no change
2. Add `Organization.sandbox_provider: Optional[str]` column
3. Flip one test tenant to `"modal"`, monitor 48h
4. Expand

### PR 7 · Public SDK (2–3 days)

**What:** Auto-generate TypeScript + Python clients from FastAPI OpenAPI.

**Tools:**
- TS: `openapi-typescript-codegen` or `@hey-api/openapi-ts`
- Python: `openapi-python-client`

**Surface:** resource-oriented (`client.sessions.create`, `client.environments.list`) matching `09-sdks.md`.

**Streaming:** custom hand-wrapped because openapi generators don't do SSE well. Pattern from `09-sdks.md §TypeScript §Internals` is copyable.

**Files:**
```
packages/agent-sdk-ts/           # NEW monorepo subdirectory
    src/index.ts                 # auto-generated + hand-written streaming
    package.json

packages/agent-sdk-python/       # NEW
    agent_sdk/__init__.py        # auto-generated + hand-written streaming
    pyproject.toml
```

**Publish:** npm `@omoios/agent-sdk`, PyPI `omoios-agent-sdk`. Version tied to API version.

### PR 8 · Client Surfaces (priority-driven)

**Options, in order of value:**

1. **CLI for GitHub Action** (`09-sdks.md §Python` + `10-client-patterns.md §2`). Sync loop. Ideal for CI gating. **1–2 days.**
2. **Slack bot reference** (`10-client-patterns.md §1`). Ships with a generic HMAC webhook + thread update pattern. **3 days.**
3. **Chrome extension (Plasmo)** (`11-chrome-extension-plasmo.md`). Full walkthrough in spec. **1 week.**
4. **Hosted editor iframe** (`10-client-patterns.md §3`). Requires sandbox-side code-server/openvscode-server. **1 week.**

**Guidance:** ship whichever the first customer asks for. Chrome extension is the highest "wow factor" for demo; CLI is the highest "real user value" for CI-integration customers.

### PR 9 · Polish (1 week, ongoing)

**Bundle of smaller gaps:**
- Unified `Artifact` adapter (§4.6) — 2 days
- Generic webhook dispatcher (§4.9) — 2 days
- Multiplayer ACL (§4.10) — 2 days
- Quota dims (§4.14) — 1 day
- Idempotency keys (§4.15) — 1 day
- Error envelope (§4.16) — 1 day

Ship these as smaller PRs interleaved with PRs 3–8 as you hit the need.

## 6.4 · What's NOT on This Plan

From `17-omoi-os-adaptation.md §9` and our analysis:

| Not doing | Why |
|---|---|
| Better Auth migration | OmoiOS has working auth. See [`05-implementation-strategies.md §5.1`](./05-implementation-strategies.md). |
| Task → Session DB rename | API alias is enough. Rename only during scheduled maintenance, or never. |
| FastAPI → Next.js replacement | §17 explicitly recommends against. |
| Monorepo restructuring | Works. Leave alone. |
| Rewriting billing | No spec requirement forces this. |
| Python build pipeline as Modal Function | OmoiOS orchestrator is already Python — no cross-language bridge needed for builds. |
| TS Modal SDK | Python SDK is mature and OmoiOS is Python. Use it. |

## 6.5 · The Pricing Question to Answer Before PR 3

Per `14-omo-opencode-sandbox.md §Reflective question`:

> When Claude rate-limits the tenant's session, should the platform fall back to its own aggregator keys (OpenCode Go, Vercel Gateway) and bill the tenant a markup? Or fail the session and let the tenant decide?

This decision affects Broker design:
- **Platform-fallback mode:** Broker has its own OpenCode Go / Vercel keys. If tenant's Anthropic key rate-limits, Broker mints from platform pool, logs usage for billing.
- **Fail-fast mode:** Broker only uses tenant-owned keys. If rate-limited, session fails with `quota_exceeded`.

**The right default for OmoiOS:** fail-fast. Platform-fallback is a pricing-plan upsell that you can add later without schema changes (just add binding kind `"platform_aggregator"`).

## 6.6 · Success Metrics

Per-PR acceptance criteria. Ship each only when these hold:

### PR 2 (Session API alias)
- `curl /v1/.../sessions` returns same shape as spec §03
- Existing `/v1/.../tasks` unchanged
- Integration test: create session, stream 5 events via SSE, cancel, assert envelope shape

### PR 3 (Session token + Broker)
- Sandbox receives `SESSION_TOKEN`, not raw provider keys (flag-on mode)
- `GET /broker/creds/anthropic` with valid session token returns `{token, expires_at, scope}`
- Audit log has one `broker_mint` row per successful mint
- RBAC: session from org A can't mint for org B's environment (403)

### PR 5 (Egress proxy)
- Sandbox can reach `api.anthropic.com` (allowlisted)
- Sandbox cannot reach `attacker.com` (blocked with 451)
- Blocked attempt emits `egress_denied` event
- p50 latency overhead < 20ms

### PR 6 (Modal)
- One tenant running 100+ sessions on Modal with zero regression vs Daytona
- Cost per session comparable (within ±20%)
- Cold start ≤ 10s (without warm pool)

## 6.7 · The Single-Sentence Plan

**Refactor OmoiOS in 8 PRs over 6–8 weeks: add adapters, alias session API, ship session-scoped credential broker, add Environment resource with egress proxy, plug in Modal, generate public SDK, and layer in client surfaces as demanded — all while leaving billing, auth, and orchestration untouched.**

Next: [`07-architecture-diagrams.md`](./07-architecture-diagrams.md) — current vs target architecture, visualized.
