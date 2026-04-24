# Agent Workspace Platform — Learnings & Conventions

## Project Conventions (from AGENTS.md)

### Backend (Python)
- **Never use `metadata` or `registry` as SQLAlchemy column names** — reserved by SQLAlchemy
- **Always use `omoi_os.utils.datetime.utc_now()`** — timezone-aware datetimes
- **Use `structured_output()` for LLM calls** — never manually parse JSON
- **Settings in YAML, secrets in .env** — `OmoiBaseSettings` pattern
- **Two service initialization points**: `api/main.py` and `workers/orchestrator_worker.py`

### Frontend (TypeScript)
- **Check `components/ui/` before creating new primitives** — 40+ ShadCN components available
- **One hook per domain in `hooks/`** — follow `useProjects.ts` pattern
- **API calls through `lib/api/client.ts`** — never call `fetch` directly

## Security Requirements

### Encryption (Task 1)
- Fernet AES-256-GCM from `cryptography` library
- Key from `CREDENTIAL_ENCRYPTION_KEY` env var (32 bytes, hex-encoded)
- Transparent encrypt/decrypt at service layer
- No plaintext in logs, error messages, or API responses

### Credential Broker (Task 3)
- 3 binding kinds only: `bearer_secret`, `user_oauth`, `github_app`
- Fail-closed: deny access if Redis unavailable
- Versioned credentials for rotation safety
- Audit log every access

### Egress Proxy (Task 7)
- Go implementation, ≤300 LOC
- Hostname allowlist only (no IP, no regex)
- Blocks all outbound except allowlisted
- Prometheus metrics

## Feature Flags (Task 2)
All 6 flags default to `false`:
1. `sessions_api_v1`
2. `environments_v1`
3. `broker_enabled`
4. `egress_proxy_enabled`
5. `artifacts_unified_v1`
6. `webhooks_enabled`

## Database Patterns
- Alembic migrations required for all schema changes
- Test both `upgrade head` and `downgrade -1`
- Never use reserved words: `metadata`, `registry`

## SDK Patterns (Tasks 6, 9, 11)
- Thin REST wrappers only (no convenience methods)
- Python: `httpx` async client, Pydantic models
- TypeScript: native `fetch`, strict types, Node.js only
- No auto-retry logic (leave to user)

## Testing Requirements
- TDD: RED → GREEN → REFACTOR
- 80%+ coverage on new code
- Unit tests: `backend/tests/unit/`
- Integration tests: `backend/tests/integration/`
- Evidence saved to `.sisyphus/evidence/`

## Implementation: Feature Flags (Task 2) - COMPLETED

### Files Modified
- `backend/config/base.yaml` - Added 6 feature flags with default `false`
- `backend/omoi_os/config.py` - Added `FeatureFlagsSettings` class and helper functions
- `backend/tests/unit/test_feature_flags.py` - Created comprehensive test suite

### Feature Flags Added
1. `sessions_api_v1: false` - Sessions API v1
2. `environments_v1: false` - Environments v1
3. `broker_enabled: false` - Credential broker
4. `egress_proxy_enabled: false` - Egress proxy
5. `artifacts_unified_v1: false` - Unified artifacts v1
6. `webhooks_enabled: false` - Webhooks

### API Usage
```python
from omoi_os.config import is_feature_enabled, load_feature_flags_settings

# Check if feature is enabled
if is_feature_enabled("sessions_api_v1"):
    # Feature is enabled
    pass

# Or access settings directly
settings = load_feature_flags_settings()
if settings.broker_enabled:
    # Broker is enabled
    pass
```

### Pattern Followed
- Extended `OmoiBaseSettings` with `yaml_section="feature_flags"`
- Environment variable prefix: `FEATURE_`
- Cached settings via `@lru_cache` in `load_feature_flags_settings()`
- Helper function `is_feature_enabled(flag_name)` for safe flag checking
- All tests pass (8/8)

## Task 5: Unified Artifact Model - COMPLETED

### Files Created
- backend/omoi_os/models/artifact.py - Artifact SQLAlchemy model
- backend/omoi_os/services/artifact_service.py - Service with storage backend abstraction
- backend/omoi_os/api/routes/artifacts.py - API routes with feature flag guard
- backend/migrations/versions/063_add_artifacts.py - Alembic migration
- backend/tests/unit/test_artifact_service.py - Unit tests (TDD)

### API Endpoints
- POST /api/v1/artifacts/upload - Multipart file upload
- GET /api/v1/artifacts - List artifacts by workspace
- GET /api/v1/artifacts/{id} - Get metadata
- GET /api/v1/artifacts/{id}/download - Stream download
- DELETE /api/v1/artifacts/{id} - Delete artifact

### Storage Backends
- LocalFilesystemBackend (v1) - Stores files at {base_dir}/{workspace_id}/{artifact_id}/{filename}
- S3Backend (interface only) - Raises NotImplementedError

### Test Results
- 12/12 storage backend tests PASSED
- 9/9 LocalFilesystemBackend tests PASSED
- 2/2 singleton tests PASSED
- 1/1 S3Backend interface test PASSED

### Pattern Compliance
- Uses artifact_metadata (not metadata - SQLAlchemy reserved word)
- Uses utc_now() for timezone-aware datetimes
- SQLAlchemy 2.0 Mapped[] + mapped_column() pattern
- Service singleton pattern with get_artifact_service()
- Feature flag guard on all routes


## Task 6: SDK Scaffolding - Learnings (2025-04-23)

### Python SDK Patterns
- Used Pydantic v2 for type definitions with proper Field descriptions
- Abstract base class with @abstractmethod enforces client interface
- Mock client stores data in Maps for efficient lookups
- Fixtures initialized in constructor for consistent test state
- UUID generation using uuid.uuid4().hex[:8] for readable IDs

### TypeScript SDK Patterns
- TypeScript strict mode with noUncheckedIndexedAccess catches edge cases
- Using `type` keyword for type-only imports reduces bundle size
- Maps provide better type safety than plain objects for storage
- Buffer type for binary data (Node.js only, no browser support)
- Import paths use .js extension for ES module compatibility

### Build Configuration
- Python: hatchling build backend works well with uv
- TypeScript: ES2022 + ESNext modules for modern Node.js
- Vitest for fast testing with built-in type checking
- pytest-asyncio for async test support (future-proofing)

### Type Definitions
- Credentials: 3 binding kinds (bearer_secret, user_oauth, github_app)
- Environments: Immutable versions with variable types (string, secret, json)
- Artifacts: Checksum validation, multi-backend support (local, s3)
- Webhooks: Event types, subscription management, delivery tracking
- Workspaces: Settings with egress allowlist and binding kind restrictions

### Testing Strategy
- 26 tests per SDK covering all CRUD operations
- Error cases verified (NotFoundError on invalid IDs)
- Type validation through runtime assertions
- Mock data fixtures provide realistic test scenarios
