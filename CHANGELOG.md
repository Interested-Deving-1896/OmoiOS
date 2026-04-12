# Changelog

All notable changes to OmoiOS will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-03-05

### Security

- Add JTI (JWT ID) claims to all token types (access, refresh, verification, reset) for per-token revocation
- Add Redis-based token blacklist service with automatic TTL expiry
- Implement refresh token rotation with reuse detection (invalidates family on replay)
- Add account lockout after configurable failed login attempts (`auth.max_failed_attempts`, `auth.lockout_duration_minutes`)
- Make email verification and password reset tokens single-use
- Require special characters in passwords; block common passwords
- Add auth audit logging for security events (login, logout, lockout, token reuse)
- Migrate to httpOnly secure cookies for token delivery (additive, backwards-compatible with Authorization header)
- Strip sensitive OAuth fields (tokens, raw provider data) from `UserResponse`
- Gate admin-only endpoints behind `is_super_admin` flag
- Fix SQLAlchemy `.is_(True)` boolean comparisons in auth queries
- Switch OAuth redirect from query params to URL fragments (prevents server-side token logging)
- Add cookie fallback in auth dependency layer for cookie-based flows
- Fix slowapi rate-limiter compatibility (`http_request` → `request` rename)
- Make `HTTPBearer` optional to support cookie-based auth without an Authorization header

### Tests

- Add 31 new security-focused tests (`tests/unit/test_security_features.py`)
- Total auth test coverage: 55 tests (12 unit + 12 API + 31 security)

---

## [0.1.0] - 2026-02-07

Initial open-source release.

### Added
- Spec-driven workflow engine (EXPLORE → REQUIREMENTS → DESIGN → TASKS → SYNC)
- Multi-agent orchestration with Claude Agent SDK and OpenHands SDK
- Priority-based task queue with dependency management
- Agent health monitoring (30s heartbeats, 90s timeout)
- Intelligent Guardian with LLM-powered trajectory analysis
- Conductor service for system-wide coherence
- Redis-based event bus for real-time state
- FastAPI backend with PostgreSQL + pgvector
- Next.js 15 frontend with React Flow, ShadCN UI
- Daytona sandbox integration for isolated execution
- OAuth login (GitHub, Google, GitLab)
- Stripe billing integration
- Sentry + PostHog observability
- Comprehensive YAML-based configuration system
