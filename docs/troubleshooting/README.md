# Troubleshooting

Operational guides for diagnosing and fixing issues encountered during development and production operations.

---

## By Category

### Infrastructure

| Document | Description |
|----------|-------------|
| [macOS Memory Audit (2026-02-05)](macos_memory_audit_2026-02-05.md) | System memory analysis — Next.js dev server (2.8 GB), Brave extensions (640 MB), 32 GB swap. Before/after cleanup metrics. |
| [Memory Management Strategy](memory_management_strategy.md) | macOS memory pressure management with background tooling, process policies, Rust daemon design. |

### Database & ORM

| Document | Description |
|----------|-------------|
| [SQLAlchemy DetachedInstanceError Fixes](detached_instance_fixes.md) | Fixes for `DetachedInstanceError` where model instances are used outside session context. |
| [Database Issues](database-issues.md) | PostgreSQL connection problems, migration failures, query performance, pgvector issues. |
| [Redis Issues](redis-issues.md) | Redis connection errors, pub/sub failures, cache invalidation, queue processing problems. |

### Authentication & Security

| Document | Description |
|----------|-------------|
| [OAuth Redirect URI Fix](oauth_redirect_uri_fix.md) | Troubleshooting `redirect_uri is not associated with this application` errors. |
| [OAuth Redirect URI Quick Fix](oauth_redirect_uri_quick_fix.md) | 5-step quick fix for OAuth redirect URI configuration issues. |
| [Auth & JWT Issues](auth-jwt-troubleshooting.md) | JWT token expiration, refresh failures, session management, RBAC permission errors. |

### Agent Execution

| Document | Description |
|----------|-------------|
| [LLM Service Failures](llm-service-failures.md) | API key issues, rate limiting, timeout handling, structured output parsing, circuit breaker behavior. |
| [Sandbox Issues](sandbox-provisioning.md) | Daytona sandbox provisioning, resource limits, branch creation failures, preview setup. |
| [Sandbox Lifecycle Errors](sandbox-lifecycle-errors.md) | Sandbox creation, startup, health check, and teardown failures with recovery procedures. |
| [Sandbox Agent Timeouts](sandbox-agent-timeouts.md) | Agent execution timeouts, infinite loops, resource exhaustion, orchestrator communication failures. |
| [Phase Transition Failures](phase-transition-failures.md) | SpecStateMachine stuck phases, evaluator failures, transition timeouts, invalid state transitions. |
| [WebSocket Events](websocket-events.md) | WebSocket connection drops, event deduplication, real-time update failures, reconnection handling. |
| [WebSocket Disconnections](websocket-disconnections.md) | Connection drops, reconnection loops, event loss, stale connections, rate limiting, payload size limits. |
### Deployment & Operations

| Document | Description |
|----------|-------------|
| [Docker Setup](docker-setup.md) | Docker Compose issues, container networking, volume mounts, multi-service orchestration. |
| [Migration Issues](migration-issues.md) | Alembic migration conflicts, schema drift, zero-downtime migrations, rollback procedures. |
| [Database Connections](database-connections.md) | PostgreSQL connection pooling, timeout configuration, SSL setup, connection leak detection. |
| [Billing Sync Failures](billing-sync-failures.md) | Stripe webhook failures, subscription state drift, credit deduction errors, invoice reconciliation. |
| [OAuth Token Refresh](oauth-token-refresh.md) | Token refresh failures, expired tokens, provider API changes, multi-provider token management. |
| [GitHub Webhook Errors](github-webhook-errors.md) | Webhook signature validation, payload parsing, rate limiting, repository access, branch protection. |
| [Embedding & Indexing Failures](embedding-indexing-failures.md) | Embedding generation, vector dimension mismatches, index corruption, batch indexing, search quality. |

---

## Quick Diagnostics

```bash
# Check service health
just status              # See what's running

# Database issues
just docker-up           # Restart Postgres + Redis
just db-migrate          # Re-run migrations

# Port conflicts
just kill-port 18000     # Kill process on specific port
just stop-all            # Stop all OmoiOS services

# Dependency issues
cd backend && uv sync --group test   # Clean reinstall backend
just frontend-clean-install           # Clean reinstall frontend
```

---

## Related Documentation

- [Architecture Docs](../architecture/) — System design and service catalogs
- [Testing Docs](../testing/) — Test strategies and coverage
- [User Journey: Sandbox Troubleshooting](../user_journey/18_sandbox_troubleshooting.md) — User-facing sandbox troubleshooting
