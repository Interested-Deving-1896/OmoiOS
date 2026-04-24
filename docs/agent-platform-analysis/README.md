# Agent Platform Analysis — OmoiOS vs. Multi-Tenant Agent API Spec

**Date:** 2026-04-23
**Author:** Analysis via Claude Code `/smart-docs`
**Source Spec:** `agent_spec.zip` (19 files, v0.2, ~146 KB)
**Source Codebase:** `/Users/kevinhill/Coding/Experiments/senior-sandbox/omoi_os`

## The Question

The user extracted a spec for an agent platform that lets an organization spin up a workspace to do whatever they want, and asked:

1. Where are the breakages / issues in the sandbox system?
2. What would we actually need to implement?
3. Should we write it in TypeScript from scratch, OR refactor / extract from the current OmoiOS SaaS?

## The Answer (TL;DR)

**Refactor OmoiOS — do NOT rewrite in TypeScript.**

The spec itself (file `17-omoi-os-adaptation.md`) is unusually candid about this: if you already have FastAPI working with billing, orgs, tasks, RBAC, and a sandbox abstraction, rewriting in TypeScript would cost months and gain nothing customer-visible. OmoiOS already has **~70% of the spec** implemented under different names. The real work is:

- **One genuinely new primitive** — the `Environment` resource (immutable sandbox recipe, versioned, with egress allowlist and credentials map)
- **One non-trivial addition** — the Credential Broker + `sess_tok_…` session-scoped credential
- **Three adapters** — TS SDK, Modal provider, OpenCode/OmO runtime
- **Polish** — unified Artifact model, standardized event envelope, generic webhook dispatcher, egress proxy, multiplayer ACL

See [`06-recommended-roadmap.md`](./06-recommended-roadmap.md) for the eight-PR plan.

## Documents in This Folder

| # | File | What's in it |
|---|---|---|
| 0 | [`README.md`](./README.md) | this file — navigation + TL;DR |
| 1 | [`01-executive-summary.md`](./01-executive-summary.md) | one-page overview for stakeholders |
| 2 | [`02-spec-overview.md`](./02-spec-overview.md) | what the spec actually demands, C4 architecture |
| 3 | [`03-current-implementation.md`](./03-current-implementation.md) | what OmoiOS has today, with file references |
| 4 | [`04-gap-analysis.md`](./04-gap-analysis.md) | breakages, issues, missing pieces — prioritized |
| 5 | [`05-implementation-strategies.md`](./05-implementation-strategies.md) | TS rewrite vs FastAPI refactor, honest comparison |
| 6 | [`06-recommended-roadmap.md`](./06-recommended-roadmap.md) | the eight-PR migration plan |
| 7 | [`07-architecture-diagrams.md`](./07-architecture-diagrams.md) | C4, sequence, and component diagrams |
| 8 | [`08-implementation-plan.md`](./08-implementation-plan.md) | detailed PR-by-PR plan with schemas, acceptance tests, security checklist |

## Top Three Findings

1. **The sandbox system isn't broken — it's incomplete.** OmoiOS has `SandboxProvider` Protocol (`backend/omoi_os/services/sandbox_provider.py:28-49`) with Daytona + LocalDocker implementations. The "breakage" is the absence of the adjacent primitives the spec needs: Environment versioning, session-scoped credentials, hostname egress, artifact unification.

2. **The trust boundary is currently collapsed.** Provider API keys (Anthropic, OpenAI) live in `UserCredential.api_key` as **plaintext** (see `backend/omoi_os/models/user_credentials.py`), and are injected into sandboxes as env vars at boot. A compromised sandbox leaks the user's raw key. The spec's session-token → Broker flow is the fix — short-lived, scope-checked, ephemeral mint per session.

3. **TypeScript rewrite is a ~4 month detour for no customer-visible gain.** OmoiOS ships ~30+ fields per Task, ~125+ service classes, ~60+ DB models, billing integration, 40+ routers. Rewriting this in TS would replicate work Better Auth saves in a greenfield but that doesn't need saving here. The Modal TS SDK is still beta — specifically missing snapshot-restore, which is the one gap that would push an OmoiOS-class product from TS-first.

## Start Here

- **If you have 5 minutes:** read [`01-executive-summary.md`](./01-executive-summary.md)
- **If you have 30 minutes:** read 01, skim 04 (gaps) and 05 (strategies), then 06 (roadmap)
- **If you have 2 hours:** read everything in order
