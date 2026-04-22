# OmoiOS Project Overview

> **Start a feature before bed. Wake up to a PR.**

OmoiOS is a spec-driven, multi-agent orchestration system that transforms feature ideas into production-ready pull requests using autonomous AI agents. It combines structured planning, isolated execution, adaptive discovery, and active supervision to enable true autonomous software development.

**Production URLs:**
- Frontend: `https://omoios.dev`
- Backend API: `https://api.omoios.dev`

---

## What is OmoiOS?

OmoiOS is an autonomous engineering platform that orchestrates multiple AI agents through a **spec-driven, discovery-enabled, self-adjusting workflow**. Unlike simple prompt chaining or single-agent coding assistants, OmoiOS provides:

1. **Structured Planning**: Converts high-level feature ideas into executable work units through a 7-phase pipeline
2. **Isolated Execution**: Runs agents in isolated Daytona sandboxes with full audit trails
3. **Adaptive Discovery**: Detects new work during execution and spawns branch tasks automatically
4. **Active Supervision**: Monitors agent trajectories and intervenes when goals drift

The system handles the entire lifecycle from feature request to merged PR, with human approval gates at strategic points.

---

## Core Value Proposition

**"Start a feature before bed. Wake up to a PR."**

This isn't just a tagline—it is the core promise of OmoiOS:

- **You describe what you want** → OmoiOS explores your codebase
- **Generates grounded specs** (requirements, design, tasks) based on actual code
- **Builds a dependency DAG** with real dependencies from your repo
- **Spawns agents in isolated sandboxes** (Daytona containers)
- **Agents execute in parallel**, discovering new work as they go
- **Supervisor agent merges code** and steers stuck agents
- **PRs land on your repo** with full traceability

This is a **structured runtime for agent swarms**—not prompt chaining. It includes dependency graphs, sandboxed execution, active supervision, and code that actually merges.

---

## System Architecture at a Glance

OmoiOS consists of four core systems working together:

### The Four Core Systems

| System | Purpose | Key Components |
|--------|---------|----------------|
| **Planning** | Convert feature ideas into structured work units | Spec-Sandbox State Machine, Phase Evaluators, HTTPReporter |
| **Execution** | Execute tasks in isolated sandboxes with full audit trail | OrchestratorWorker, DaytonaSpawner, ClaudeSandboxWorker |
| **Discovery** | Enable adaptive workflow branching when agents find new requirements | DiscoveryService, DiscoveryAnalyzerService |
| **Readjustment** | Monitor agent trajectories and intervene when goals drift | MonitoringLoop, IntelligentGuardian, ConductorService |

---

## Tech Stack Summary

### Backend

| Component | Technology | Version |
|-----------|------------|---------|
| Framework | FastAPI | 0.104+ |
| Language | Python | 3.12+ |
| Database | PostgreSQL | 16 |
| Vector Search | pgvector | 1536-dim |
| Cache/Queue | Redis | 7 |
| ORM | SQLAlchemy | 2.0+ |
| LLM | Claude Agent SDK | Latest |
| Sandboxes | Daytona | Production |
| Auth | JWT + API Keys | Custom |
| Observability | Sentry + OpenTelemetry + Logfire | — |

### Frontend

| Component | Technology | Version |
|-----------|------------|---------|
| Framework | Next.js | 15 (App Router) |
| UI Library | ShadCN UI | 40+ components |
| Styling | Tailwind CSS | Latest |
| State (Client) | Zustand | — |
| State (Server) | React Query | — |
| Graphs | React Flow | v12 |
| Terminal | xterm.js | — |

### Infrastructure

| Service | Port | Note |
|---------|------|------|
| PostgreSQL | 15432 | +10000 offset |
| Redis | 16379 | +10000 offset |
| Backend API | 18000 | +10000 offset |
| Frontend | 3000 | Standard |

---

## Repository Structure Overview

```
senior_sandbox/
├── backend/                    # Python FastAPI backend
│   ├── omoi_os/
│   │   ├── api/
│   │   │   ├── main.py         # FastAPI app + lifespan (25+ services)
│   │   │   └── routes/         # 39 route files by domain
│   │   ├── services/           # 100+ service modules
│   │   │   ├── models/         # 61 SQLAlchemy model files (~77 classes)
│   │   ├── workers/            # Background workers
│   │   └── config.py           # OmoiBaseSettings (YAML + env)
│   ├── config/
│   │   ├── base.yaml           # Default application settings
│   │   └── test.yaml           # Test overrides
│   ├── migrations/versions/    # 70+ Alembic migrations
│   └── tests/                  # unit/, integration/, e2e/
│
├── frontend/                   # Next.js 15 frontend
│   ├── app/                    # App Router
│   │   ├── (app)/              # Authenticated routes
│   │   ├── (auth)/             # Login, register, OAuth
│   │   └── (dashboard)/        # Root redirect
│   ├── components/
│   │   ├── ui/                 # ShadCN primitives (40+)
│   │   ├── layout/             # App shell
│   │   ├── panels/             # Sidebar panels
│   │   └── {domain}/           # Domain components
│   ├── hooks/                  # 29 React Query + Zustand hooks
│   ├── lib/api/                # HTTP client + domain APIs
│   └── providers/              # Context providers
│
├── subsystems/
│   └── spec-sandbox/           # Lightweight spec execution runtime
│
├── docs/                       # 30,000+ lines of documentation
│   ├── architecture/           # 19 deep-dive docs (01-19)
│   ├── proposals/              # OIPs (OmoiOS Improvement Proposals)
│   ├── page_flows/             # 24 page-by-page UI flows
│   └── user_journey/           # End-to-end journey docs
│
├── Justfile                    # Task runner (just --list)
├── docker-compose.yml          # Full stack orchestration
├── ARCHITECTURE.md             # System architecture deep-dive
├── CLAUDE.md                   # Monorepo guide
├── AGENTS.md                   # AI agent guide
└── README.md                   # Project readme
```

---

## Key Concepts

### SpecStateMachine

The SpecStateMachine runs a 7-phase pipeline that converts feature ideas into executable work:

```
EXPLORE → PRD → REQUIREMENTS → DESIGN → TASKS → SYNC → COMPLETE
```

Each phase has an LLM evaluator (quality gate) that scores output and retries on failure. All phases use incremental writing to prevent data loss.

**Key files:**
- `backend/omoi_os/services/phase_manager.py`
- `backend/omoi_os/services/phase_progression_service.py`
- `backend/omoi_os/models/phases.py`

### DAG-Based Execution

Tasks form a dependency graph (`DependencyGraphService`). Nothing executes until its dependencies are met. Critical path analysis determines what runs in parallel. This enables 5+ agents working simultaneously without interference.

**Key files:**
- `backend/omoi_os/services/dependency_graph.py`
- `backend/omoi_os/services/coordination.py`
- `backend/omoi_os/services/convergence_merge_service.py`

### Sandbox Isolation

Each agent runs in an isolated Daytona container with its own Git branch, filesystem, and resources. No shared state. No interference. When agents finish, `ConvergenceMergeService` merges their branches in optimal order.

**Key files:**
- `backend/omoi_os/services/daytona_spawner.py`
- `backend/omoi_os/services/claude_agent_worker.py`
- `backend/omoi_os/services/sandbox_git_operations.py`

### Active Supervision

`IntelligentGuardian` analyzes every agent's trajectory every 60 seconds—scoring alignment, detecting drift, and injecting steering interventions mid-task. `ConductorService` monitors system-wide coherence, detects duplicate work, and coordinates across agents.

**Key files:**
- `backend/omoi_os/services/intelligent_guardian.py`
- `backend/omoi_os/services/monitoring_loop.py`
- `backend/omoi_os/services/conductor.py`

### Adaptive Discovery

During execution, agents find bugs, missing requirements, optimization opportunities. `DiscoveryService` spawns new tasks in the appropriate phase automatically. The DAG grows and adapts—workflows build themselves based on what agents actually encounter.

**Key files:**
- `backend/omoi_os/services/discovery.py`
- `backend/omoi_os/services/discovery_analyzer.py`
- `backend/omoi_os/models/task_discovery.py`

---

## Development Workflow

### Quick Start

See docs/installation.md for detailed setup instructions.

```bash
# One command sets up everything
just quickstart

# Start developing
just dev-all         # Start API + frontend (http://localhost:3000)
```

### Everyday Commands

```bash
just dev-all             # Start full stack
just test                # Run affected tests only (fast, ~10-30s)
just test-all            # Full test suite
just check               # Lint + format (auto-fix)
just status              # Check what is running
just stop-all            # Stop everything
```

### Testing

```bash
just test                # Smart: only tests affected by your changes (testmon)
just test-all            # Full suite with coverage
just test-unit           # Unit tests only
just test-integration    # Integration tests only
just test-watch          # Watch mode
```

### Code Quality

```bash
just check               # Auto-fix lint issues + format (ruff)
just lint                # Lint only (no fixes)
just format              # Format only
just frontend-check      # Frontend format + type check
```

---

## Documentation Map

### Start Here

| Document | Purpose |
|----------|---------|
| [ARCHITECTURE.md](../ARCHITECTURE.md) | Complete system architecture (start here for backend work) |
| [AGENTS.md](../AGENTS.md) | AI coding agent guide |
| [CLAUDE.md](../CLAUDE.md) | Monorepo structure, dev commands, ports |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | Contribution guide, PR process |

### Architecture Deep-Dives (01-19)

| Document | Description |
|----------|-------------|
| [01-planning-system.md](architecture/01-planning-system.md) | Spec-Sandbox state machine, phase evaluators |
| [02-execution-system.md](architecture/02-execution-system.md) | Orchestrator, Daytona sandboxes, agent workers |
| [03-discovery-system.md](architecture/03-discovery-system.md) | Adaptive workflow branching |
| [04-readjustment-system.md](architecture/04-readjustment-system.md) | Guardian, Conductor, steering interventions |
| [05-frontend-architecture.md](architecture/05-frontend-architecture.md) | Next.js 15 App Router, state management |
| [06-realtime-events.md](architecture/06-realtime-events.md) | Redis pub/sub, WebSocket forwarding |
| [07-auth-and-security.md](architecture/07-auth-and-security.md) | JWT, OAuth, RBAC, API keys |
| [08-billing-and-subscriptions.md](architecture/08-billing-and-subscriptions.md) | Stripe, tiers, cost tracking |
| [09-mcp-integration.md](architecture/09-mcp-integration.md) | Model Context Protocol, circuit breakers |
| [10-github-integration.md](architecture/10-github-integration.md) | Branch management, PR workflows |
| [11-database-schema.md](architecture/11-database-schema.md) | PostgreSQL + pgvector, 75+ model classes |
| [12-configuration-system.md](architecture/12-configuration-system.md) | YAML + env, Pydantic validation |
| [13-api-route-catalog.md](architecture/13-api-route-catalog.md) | All FastAPI route modules |
| [14-integration-gaps.md](architecture/14-integration-gaps.md) | Known issues, resolved gaps |
| [15-llm-service.md](architecture/15-llm-service.md) | LLM architecture, structured outputs |
| [16-service-catalog.md](architecture/16-service-catalog.md) | All backend services cataloged |
| [17-monitoring-replay.md](architecture/17-monitoring-replay.md) | Monitoring replay system |
| [18-llm-service-internals.md](architecture/18-llm-service-internals.md) | LLM service internals |
| [19-git-provider-abstraction.md](architecture/19-git-provider-abstraction.md) | Git provider abstraction layer |

### Other Documentation

| Document | Description |
|----------|-------------|
| installation.md | AI-executable setup guide |
| product_vision.md | Full product vision + target audience |
| app_overview.md | Core features + user flows |
| page_architecture.md | All frontend pages detailed |
| design_system.md | Complete design system |
| [backend/CLAUDE.md](../backend/CLAUDE.md) | Backend development reference |

---

## Critical Rules for Developers

### Backend (Python)

1. **Never use `metadata` or `registry` as SQLAlchemy column names.** They are reserved by SQLAlchemy's declarative API. Use `change_metadata`, `item_metadata`, etc.

2. **Always use `omoi_os.utils.datetime.utc_now()`** instead of `datetime.utcnow()`. The former returns timezone-aware datetimes compatible with the database.

3. **Use `structured_output()` for LLM calls** that need structured data. Never manually parse JSON from LLM responses.

4. **Settings go in YAML, secrets go in .env.** Application settings in `config/base.yaml`, secret keys/passwords in `.env`.

5. **Two separate service initialization points exist.** `api/main.py` (API server) and `workers/orchestrator_worker.py` (background worker) initialize different service sets. They run as separate processes and do not share state.

### Frontend (TypeScript)

1. **Check `components/ui/` before creating new primitives.** 40+ ShadCN components are available.

2. **One hook per domain in `hooks/`**. Follow the pattern in `useProjects.ts` or `useSpecs.ts`.

3. **API calls go through `lib/api/client.ts`.** Add domain-specific files to `lib/api/`. Never call `fetch` directly.

4. **Route groups**: `(app)` for authenticated pages, `(auth)` for auth flows.

---

## Glossary

| Term | Definition |
|------|------------|
| **Spec** | A feature specification that goes through EXPLORE → SYNC phases |
| **Ticket** | A work grouping (TKT-NNN) containing multiple tasks |
| **Task** | An atomic work unit (TSK-NNN) executable by an agent |
| **Discovery** | New work found during execution that spawns branch tasks |
| **Trajectory** | An agent's conversation and tool usage history |
| **Alignment** | How well an agent's trajectory matches its goal |
| **Coherence** | System-wide measure of agent coordination |
| **Synthesis** | Merging results from parallel predecessor tasks |
| **Phase Gate** | Quality evaluation that must pass to proceed |
| **EARS** | "Easy Approach to Requirements Syntax" format |

---

## Next Steps

1. Read [ARCHITECTURE.md](../ARCHITECTURE.md) for the complete system picture
2. Follow docs/installation.md to set up your development environment
3. Review [AGENTS.md](../AGENTS.md) if you are an AI coding agent
4. Check [CONTRIBUTING.md](../CONTRIBUTING.md) for contribution guidelines

---

*Last updated: April 2026*
