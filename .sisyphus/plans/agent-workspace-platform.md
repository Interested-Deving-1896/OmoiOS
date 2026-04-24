# Agent Workspace Platform — Full Roadmap

## TL;DR

> **Quick Summary**: Transform OmoiOS from "we run agents for you" to "we provide the workspace where agents operate" by implementing 8 PRs covering security encryption, credential brokering, egress control, environment management, unified artifacts, webhooks, workspace isolation, and client SDKs.
> 
> **Deliverables**:
> - Encrypted credential storage (Fernet AES-256)
> - Credential Broker service with 3 binding kinds
> - Go egress proxy (~300 LOC, hostname allowlists)
> - `Environment` resource (immutable, versioned sandbox recipes)
> - Unified artifact model (S3/GCS/local abstraction)
> - Webhook delivery with HMAC signatures
> - Workspace isolation (network + resource + data)
> - Python + TypeScript client SDKs
> 
> **Estimated Effort**: Large (~17 working days)
> **Parallel Execution**: YES - 5 waves
> **Critical Path**: PR-0c → PR-1 → PR-2 → PR-6 → PR-7

---

## Context

### Original Request
Transform OmoiOS from a multi-agent automation platform into an Agent Workspace Platform — providing the infrastructure primitives (credentials, environments, egress control, isolation) that let third-party agents operate safely.

### Interview Summary
**Key Discussions**:
- Scope: ALL 8 PRs from the analysis, one work plan
- Timeline: ASAP — maximize parallelism
- Egress proxy: Go is fine (~300 LOC)
- Client SDK: Python + TypeScript
- Testing: TDD, 80%+ coverage

**Research Findings**:
- ~70% of spec already implemented under different names (validated in doc 03 with file paths)
- Feature flag infrastructure already exists in `OmoiBaseSettings`
- Daytona sandbox integration works for current use cases
- 3 critical security gaps: plaintext keys, no session creds, no egress control

### Metis Review
**Identified Gaps** (addressed):
- Encryption key management: Fernet with env-var keys, KMS upgrade path in doc 08
- Egress proxy deployment: shared service model (not sidecar), confirmed in doc 07
- Credential rotation edge cases: versioned credentials, sessions pin to version
- SDK versioning: semantic versioning from day 1, Node.js only (not browser)
- Feature flag granularity: global flags for v1, per-org deferred
- Redis failure: fail-closed (deny access) for security

---

## Work Objectives

### Core Objective
Implement 8 coordinated PRs that add agent workspace primitives to OmoiOS: secure credential management, network egress control, environment templates, unified artifact storage, webhook delivery, workspace isolation, and client SDKs.

### Concrete Deliverables
- New DB tables: `provider_keys` (encrypted), `credential_bindings`, `environments`, `environment_versions`, `webhook_deliveries`, `workspace_configs`
- New services: `CredentialBrokerService`, `EgressProxyService` (Go), `EnvironmentService`, `UnifiedArtifactService`, `WebhookService`, `WorkspaceIsolationService`
- New routes: `/api/v1/credentials/*`, `/api/v1/environments/*`, `/api/v1/artifacts/*`, `/api/v1/webhooks/*`, `/api/v1/workspaces/*`
- Go binary: `egress-proxy` (~300 LOC)
- Python SDK package: `omoios-sdk`
- TypeScript SDK package: `@omoios/sdk`
- 6 feature flags: all default OFF

### Definition of Done
- [ ] `just test-all` passes with 80%+ coverage on new code
- [ ] `just check` passes (ruff lint + format)
- [ ] All 6 feature flags exist and default to OFF
- [ ] No plaintext credentials anywhere in DB (verified by test)
- [ ] Go egress proxy builds and runs with `go build`
- [ ] Both SDKs install and authenticate against local API
- [ ] Alembic migrations apply cleanly: `alembic upgrade head`
- [ ] All migrations reversible: `alembic downgrade -1`

### Must Have
- All credential values encrypted at rest (Fernet AES-256-GCM)
- Credential Broker with 3 binding kinds: `bearer_secret`, `user_oauth`, `github_app`
- Egress proxy blocks all outbound traffic except allowlisted hostnames
- Environment resource is immutable (create new version to change)
- All new code behind feature flags
- TDD: tests written before implementation

### Must NOT Have (Guardrails)
- No changes to existing auth system (Better Auth decision locked)
- No renaming `tasks` table to `sessions` (API alias only)
- No breaking changes to existing public API endpoints
- No credential plaintext in logs, error messages, or API responses
- No Go proxy exceeding 500 LOC
- No SDK convenience methods beyond thin REST wrappers (v1.0)
- No "while we're here" refactoring outside PR scope
- No new binding kinds beyond the 3 specified
- No webhook management UI (infrastructure only)
- No drive-by improvements to unrelated modules

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** - ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: YES (pytest + testmon for backend, vitest for frontend)
- **Automated tests**: YES (TDD)
- **Framework**: pytest (backend), go test (egress proxy), vitest (TypeScript SDK)
- **TDD**: Each task follows RED (failing test) → GREEN (minimal impl) → REFACTOR

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.sisyphus/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Backend API**: Use Bash (curl) - Send requests, assert status + response fields
- **Go service**: Use Bash (go test) - Unit tests + integration with mock sandbox
- **Python SDK**: Use Bash (pytest) - Mocked API + integration against real API
- **TypeScript SDK**: Use Bash (vitest) - Mocked API + integration against real API
- **DB migrations**: Use Bash (alembic) - Upgrade + downgrade + verify schema

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately — security foundation):
├── Task 1: Encrypt provider keys (PR-0c) [quick]
└── Task 2: Feature flag infrastructure check [quick]

Wave 2 (After Wave 1 — independent core services, MAX PARALLEL):
├── Task 4: Environment resource + DB migration (PR-3, no deps) [unspecified-high]
├── Task 5: Unified artifact model (PR-4, no deps) [unspecified-high]
└── Task 6: SDK scaffolding + API mocks (PR-7 prep, no deps) [quick]

Wave 3 (After Wave 2 — broker needs environment model for injection):
├── Task 3: Credential Broker service (PR-1, depends: 1, 4) [deep]

Wave 4 (After Task 3 — dependent services + SDKs):
├── Task 7: Go egress proxy (PR-2, depends: 3) [deep]
├── Task 8: Webhook delivery service (PR-5, depends: 3, 5) [unspecified-high]
├── Task 9: SDK Python implementation (depends: 6, 3, 4, 5) [unspecified-high]

Wave 5 (After Tasks 7 + 3 — isolation + remaining):
├── Task 10: Workspace isolation (PR-6, depends: 1, 7, 4) [deep]
├── Task 11: SDK TypeScript implementation (depends: 6, 3, 4, 5) [unspecified-high]
└── Task 12: API route aliases (sessions → tasks) [quick]

Wave FINAL (After ALL tasks — 4 parallel reviews):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)
→ Present results → Get explicit user okay

Critical Path: T1 → T4 → T3 → T7 → T10 → F1-F4 → user okay
Parallel Speedup: ~45% faster than sequential
Max Concurrent: 3 (Waves 2, 4, 5)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| 1 | - | 3 | 1 |
| 2 | - | 3 | 1 |
| 4 | - | 3, 8, 10 | 2 |
| 5 | - | 8, 9, 10 | 2 |
| 6 | - | 9, 11 | 2 |
| 3 | 1, 4 | 7, 8, 9 | 3 |
| 7 | 3 | 10 | 4 |
| 8 | 3, 5 | - | 4 |
| 9 | 3, 4, 5, 6 | - | 4 |
| 10 | 1, 7, 4 | F1-F4 | 5 |
| 11 | 3, 4, 5, 6 | - | 5 |
| 12 | 3, 4 | - | 5 |

### Agent Dispatch Summary

- **Wave 1**: 2 tasks - T1 → `quick`, T2 → `quick`
- **Wave 2**: 3 tasks - T4 → `unspecified-high`, T5 → `unspecified-high`, T6 → `quick`
- **Wave 3**: 1 task - T3 → `deep`
- **Wave 4**: 3 tasks - T7 → `deep`, T8 → `unspecified-high`, T9 → `unspecified-high`
- **Wave 5**: 3 tasks - T10 → `deep`, T11 → `unspecified-high`, T12 → `quick`
- **FINAL**: 4 tasks - F1 → `oracle`, F2 → `unspecified-high`, F3 → `unspecified-high`, F4 → `deep`

---

## TODOs

---

## TODOs

> Implementation + Test = ONE Task. Never separate.
> EVERY task MUST have: Recommended Agent Profile + Parallelization info + QA Scenarios.
> **A task WITHOUT QA Scenarios is INCOMPLETE. No exceptions.**

- [x] 1. **Encrypt Provider API Keys (PR-0c)**

  **What to do**:
  - Write failing tests for encryption/decryption of provider key values
  - Create `backend/omoi_os/services/credential_encryption.py` with Fernet AES-256-GCM encryption
  - Add `encrypted_value` column to provider key model (keep old `value` for migration)
  - Create Alembic migration to add encrypted column + backfill existing keys
  - Add encryption key from `CREDENTIAL_ENCRYPTION_KEY` env var (generate with `openssl rand -hex 32`)
  - Update all provider key read/write paths to encrypt/decrypt transparently
  - Remove old plaintext `value` column in a follow-up migration
  - Add audit logging for all encryption operations

  **Must NOT do**:
  - No changes to auth system or session management
  - No changes to API endpoint signatures
  - No logging of decrypted values

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Security-critical code requiring careful encryption implementation
  - **Skills**: [`security-review`, `python-patterns`]
    - `security-review`: Cryptographic implementation validation
    - `python-patterns`: Pythonic patterns for service layer
  - **Skills Evaluated but Omitted**:
    - `better-auth-best-practices`: No auth changes in this task

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 2)
  - **Parallel Group**: Wave 1 (with Task 2)
  - **Blocks**: Task 3 (Credential Broker)
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References**:
  - `backend/omoi_os/services/llm_service.py` - Service pattern with `get_llm_service()` singleton
  - `backend/omoi_os/models/` - SQLAlchemy 2.0 model patterns (look at any model for column conventions)
  - `backend/omoi_os/config.py` - `OmoiBaseSettings` pattern for env-var config

  **API/Type References**:
  - `docs/agent-platform-analysis/08-implementation-plan.md` lines 164–213 — PR-0c Adapter Interfaces with encryption specs and migration guidance
  - `docs/agent-platform-analysis/04-gap-analysis.md` - Gap #1 (plaintext provider keys) with severity and effort estimate

  **Test References**:
  - `backend/tests/unit/` - Follow existing unit test patterns (pytest fixtures, mocking)
  - `backend/tests/integration/` - Integration test patterns with real DB

  **Acceptance Criteria**:
  - [ ] Test file created: `backend/tests/unit/test_credential_encryption.py`
  - [ ] `just test-unit` → PASS (encryption tests pass)
  - [ ] Encryption uses Fernet (AES-256-GCM) from `cryptography` library
  - [ ] `just test-all` passes
  - [ ] Migration applies cleanly: `uv run alembic upgrade head`
  - [ ] Migration reverses cleanly: `uv run alembic downgrade -1`

  **QA Scenarios (MANDATORY)**:
  ```
  Scenario: Encrypt and decrypt a provider key value
    Tool: Bash (pytest)
    Preconditions: Encryption key set in env var
    Steps:
      1. Run: `cd backend && uv run pytest tests/unit/test_credential_encryption.py -v`
      2. Assert all tests pass, including round-trip encrypt/decrypt
      3. Assert encrypted output != plaintext input
    Expected Result: All encryption tests pass, no plaintext in encrypted output
    Failure Indicators: Decryption returns wrong value, plaintext visible in output
    Evidence: .sisyphus/evidence/task-1-encrypt-decrypt.txt

  Scenario: Verify no plaintext in database after migration
    Tool: Bash (pytest)
    Preconditions: Migration applied, encryption service running
    Steps:
      1. In test: create a ProviderKey model instance with plaintext value
      2. Call encryption service to encrypt the value
      3. Store encrypted value to DB via SQLAlchemy session
      4. Query DB directly: `SELECT encrypted_value FROM provider_keys WHERE id = <test_id>`
      5. Assert `encrypted_value` is not the plaintext key
      6. Assert decryption round-trip produces original value
    Expected Result: No plaintext key values in any DB column, round-trip works
    Failure Indicators: Plaintext key visible in `encrypted_value` column, decryption fails
    Evidence: .sisyphus/evidence/task-1-no-plaintext.txt
  ```

  **Commit**: YES
  - Message: `security: encrypt provider API keys with Fernet AES-256`
  - Files: `backend/omoi_os/services/credential_encryption.py`, `backend/omoi_os/models/provider_key.py`, migration
  - Pre-commit: `just test-unit`

- [x] 2. **Feature Flag Infrastructure Check**

  **What to do**:
  - Verify `OmoiBaseSettings` supports the 6 required feature flags
  - Add flags to `backend/config/base.yaml`: `sessions_api_v1`, `environments_v1`, `broker_enabled`, `egress_proxy_enabled`, `artifacts_unified_v1`, `webhooks_enabled`
  - All flags default to `false`
  - Add a test verifying each flag exists and defaults to `false`
  - Create a `is_feature_enabled(flag_name)` helper if one doesn't exist

  **Must NOT do**:
  - No changes to existing config values
  - No per-organization flag support (global only for v1)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple config addition with test verification
  - **Skills**: [`python-patterns`]
    - `python-patterns`: Config/validation patterns

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Task 1)
  - **Parallel Group**: Wave 1
  - **Blocks**: Task 3 (broker needs flags)
  - **Blocked By**: None

  **References**:
  - `backend/omoi_os/config.py` - `OmoiBaseSettings` class and YAML loading pattern
  - `backend/config/base.yaml` - Existing config structure to extend
  - `backend/config/test.yaml` - Test overrides pattern

  **Acceptance Criteria**:
  - [ ] `just test-unit` passes with new flag tests
  - [ ] All 6 flags exist in `base.yaml` with value `false`
  - [ ] `is_feature_enabled("broker_enabled")` returns `false` by default

  **QA Scenarios**:
  ```
  Scenario: All feature flags default to false
    Tool: Bash (pytest)
    Steps:
      1. Run: `cd backend && uv run pytest tests/unit/test_feature_flags.py -v`
      2. Assert each of the 6 flags returns `false`
    Expected Result: All 6 flags return false, no MissingKey errors
    Evidence: .sisyphus/evidence/task-2-feature-flags.txt
  ```

  **Commit**: YES
  - Message: `feat: add feature flags for agent workspace platform`
  - Files: `backend/config/base.yaml`, `backend/omoi_os/config.py`, test file
  - Pre-commit: `just test-unit`

- [x] 3. **Credential Broker Service (PR-4 · lines 444–566)**

  **What to do**:
  - Write failing tests for credential CRUD with 3 binding kinds
  - Create `backend/omoi_os/services/credential_broker.py` — the core broker service
  - Implement 3 binding kinds: `bearer_secret` (API key), `user_oauth` (OAuth token), `github_app` (installation token)
  - Create `credential_bindings` DB table (id, workspace_id, kind, encrypted_data, created_at, rotated_at)
  - Add Alembic migration
  - Create routes: `POST /api/v1/credentials`, `GET /api/v1/credentials` (list), `GET /api/v1/credentials/{id}`, `DELETE /api/v1/credentials/{id}`
  - Implement credential injection into sandbox environment (env vars)
  - Implement credential versioning (sessions pin to version for rotation safety)
  - Add access audit logging (who, when, what binding, which session)
  - Guard all routes with `broker_enabled` feature flag

  **Must NOT do**:
  - No new binding kinds beyond the 3 specified
  - No credential caching in Redis yet (fail-closed, DB-only for v1)
  - No plaintext credentials in logs or error messages
  - No changes to existing auth system

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Security-critical service with encryption integration and multiple binding types
  - **Skills**: [`security-review`, `python-patterns`, `api-design`]
    - `security-review`: Credential handling validation
    - `python-patterns`: Service layer patterns
    - `api-design`: REST API for credential management

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 4 for environment injection)
  - **Parallel Group**: Wave 3 (after Tasks 1, 2, 4)
  - **Blocks**: Tasks 7, 8, 9, 10
  - **Blocked By**: Tasks 1, 2, 4 (needs encryption service + environment model for injection)

  **References**:
  **Pattern References**:
  - `backend/omoi_os/services/credential_encryption.py` - (Task 1 output) Use this for encrypt/decrypt
  - `backend/omoi_os/api/routes/` - Follow existing route file patterns (see any domain route)
  - `docs/agent-platform-analysis/08-implementation-plan.md` lines 444–566 — Credential Broker PR with exact table schema, API contracts, and binding kind definitions
  - `docs/agent-platform-analysis/07-architecture-diagrams.md` - Broker sequence diagram

  **API/Type References**:
  - `docs/agent-platform-analysis/02-spec-overview.md` - 3 binding kind specs (bearer_secret, user_oauth, github_app)
  - `docs/agent-platform-analysis/04-gap-analysis.md` - Gap #2 (session-scoped credential injection)

  **Current Code References** (existing files that must change):
  - `backend/omoi_os/models/user_credentials.py` — Currently stores API keys as plaintext `api_key: str`; broker must replace this flow
  - `backend/omoi_os/services/auth_service.py` — Must add `create_session_token()` method for session-scoped credential injection
  - `backend/omoi_os/workers/orchestrator_worker.py` — Replace direct env-var injection with session token lookup via broker

  **Acceptance Criteria**:
  - [ ] Test file created: `backend/tests/unit/test_credential_broker.py`
  - [ ] `just test-unit` → PASS
  - [ ] Can create, read, delete each of 3 binding kinds
  - [ ] Credentials are encrypted at rest (verified by test)
  - [ ] Audit log entry created on every access
  - [ ] Feature flag `broker_enabled` guards all new routes
  - [ ] `uv run alembic upgrade head` succeeds

  **QA Scenarios**:
  ```
  Scenario: Create and retrieve a bearer_secret binding
    Tool: Bash (curl)
    Preconditions: API running, broker_enabled=true in config
    Steps:
      1. POST /api/v1/credentials with body `{"kind": "bearer_secret", "name": "test-api-key", "value": "sk-test-123"}`
      2. Assert response 201 with credential ID
      3. GET /api/v1/credentials/{id}
      4. Assert response 200 with `kind=bearer_secret` and `name=test-api-key`
      5. Assert `value` field is NOT the plaintext `sk-test-123`
    Expected Result: Credential created and retrieved, no plaintext in response
    Failure Indicators: Plaintext in response, 500 error, wrong kind
    Evidence: .sisyphus/evidence/task-3-bearer-secret.txt

  Scenario: Verify credential access is audit-logged
    Tool: Bash (curl)
    Preconditions: Credential exists from previous scenario
    Steps:
      1. GET /api/v1/credentials/{id}
      2. Query audit log table for entries with this credential ID
      3. Assert entry exists with timestamp, actor, action='read'
    Expected Result: Audit log entry exists for every access
    Failure Indicators: No audit log entry, wrong action type
    Evidence: .sisyphus/evidence/task-3-audit-log.txt
  ```

  **Commit**: YES
  - Message: `feat: add credential broker service with 3 binding kinds`
  - Files: `backend/omoi_os/services/credential_broker.py`, routes, models, migration, tests
  - Pre-commit: `just test-unit`

- [x] 4. **Environment Resource + DB Migration (PR-3)**

  **What to do**:
  - Write failing tests for Environment CRUD
  - Create `backend/omoi_os/models/environment.py` — Environment + EnvironmentVersion models
  - Environment is immutable: editing creates a new version, old versions preserved
  - Create `environments` table (id, org_id, name, description, created_at)
  - Create `environment_versions` table (id, env_id, version_number, variables JSONB, created_at)
  - `variables` supports types: string, secret (encrypted), json
  - Create service: `backend/omoi_os/services/environment_service.py`
  - Create routes: `POST /api/v1/environments`, `GET /api/v1/environments`, `GET /api/v1/environments/{id}`, `POST /api/v1/environments/{id}/versions`
  - Guard all routes with `environments_v1` feature flag
  - Secret variables encrypted using Task 1's encryption service

  **Must NOT do**:
  - No environment variable inheritance (v1 is flat)
  - No project-scoped environments (org-level only for v1)
  - No variable name validation beyond basic sanitization

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Standard CRUD service with encryption integration, moderate complexity
  - **Skills**: [`python-patterns`, `api-design`]
    - `python-patterns`: Service/model patterns
    - `api-design`: REST API design for resources

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 3, 5, 6)
  - `docs/agent-platform-analysis/08-implementation-plan.md` lines 296–374 — PR-2 Environment Resource with exact schema
  - **Blocks**: Tasks 8, 9, 10
  - **Blocked By**: None (can start immediately — only needs Task 1 for secret encryption)

  **References**:
  - `docs/agent-platform-analysis/08-implementation-plan.md` lines 296–374 — PR-2 Environment Resource with exact schema, versioned configs, and secret encryption
  - `docs/agent-platform-analysis/04-gap-analysis.md` - Gap #4 (missing Environment resource)
  - `backend/omoi_os/models/` - Follow existing model patterns for new tables
  - `backend/omoi_os/services/credential_encryption.py` - (Task 1 output) Use for secret variable encryption

  **Acceptance Criteria**:
  - [ ] Test file: `backend/tests/unit/test_environment_service.py`
  - [ ] `just test-unit` → PASS
  - [ ] Can create environment, list environments, get by ID
  - [ ] Creating a new version preserves old versions
  - [ ] Secret variables encrypted at rest
  - [ ] Feature flag `environments_v1` guards all routes

  **QA Scenarios**:
  ```
  Scenario: Create environment and add versioned variables
    Tool: Bash (curl)
    Preconditions: API running, environments_v1=true
    Steps:
      1. POST /api/v1/environments `{"name": "staging", "description": "Staging env"}`
      2. Assert 201 with env ID
      3. POST /api/v1/environments/{id}/versions `{"variables": {"DB_URL": {"type": "string", "value": "postgres://..."}, "API_KEY": {"type": "secret", "value": "sk-xxx"}}}`
      4. Assert 201, version_number=1
      5. POST another version with updated API_KEY
      6. Assert version_number=2, version 1 still exists
    Expected Result: Environment with 2 versions, secret encrypted
    Evidence: .sisyphus/evidence/task-4-environment-versions.txt
  ```

  **Commit**: YES
  - Message: `feat: add environment resource with versioned immutable configs`
  - Pre-commit: `just test-unit`

- [x] 5. **Unified Artifact Model (PR-4)**

  **What to do**:
  - Write failing tests for artifact upload/download/delete
  - Create `backend/omoi_os/services/artifact_service.py` — abstract storage backend
  - Implement local filesystem backend (v1 default)
  - Add S3 backend interface (implementation deferred, interface ready)
  - Create `artifacts` table (id, workspace_id, name, storage_backend, storage_path, checksum, size_bytes, metadata JSONB)
  - Create routes: `POST /api/v1/artifacts/upload`, `GET /api/v1/artifacts` (list), `GET /api/v1/artifacts/{id}`, `GET /api/v1/artifacts/{id}/download`, `DELETE /api/v1/artifacts/{id}`
  - Support streaming for large files (> 1GB)
  - Guard with `artifacts_unified_v1` feature flag

  **Must NOT do**:
  - No S3 implementation (interface only for v1)
  - No artifact lifecycle policies (cleanup) yet
  - No artifact versioning (overwrite only for v1)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Storage abstraction layer with streaming support
  - **Skills**: [`python-patterns`, `api-design`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 3, 4, 6)
  - **Parallel Group**: Wave 2
  - **Blocks**: Tasks 8, 10
  - **Blocked By**: None

  **References**:
  - `docs/agent-platform-analysis/08-implementation-plan.md` lines 444–566 — PR-4 Credential Broker includes artifact storage specs within broker context
  - `docs/agent-platform-analysis/04-gap-analysis.md` - Gap #6 (artifact model mismatch)
  - `backend/omoi_os/models/` - Existing model patterns

  **Acceptance Criteria**:
  - [ ] Test file: `backend/tests/unit/test_artifact_service.py`
  - [ ] `just test-unit` → PASS
  - [ ] Upload → download produces identical file
  - [ ] Checksum validation on upload
  - [ ] Feature flag `artifacts_unified_v1` guards all routes

  **QA Scenarios**:
  ```
  Scenario: Upload and download an artifact
    Tool: Bash (curl)
    Steps:
      1. Upload file: `curl -F 'file=@test.txt' POST /api/v1/artifacts/upload`
      2. Assert 201 with artifact ID and checksum
      3. Download: `GET /api/v1/artifacts/{id}/download`
      4. Assert downloaded content matches original file
    Expected Result: Round-trip upload/download works, checksums match
    Evidence: .sisyphus/evidence/task-5-artifact-upload.txt
  ```

  **Commit**: YES
  - Message: `feat: add unified artifact model with multi-backend storage`
  - Pre-commit: `just test-unit`

- [x] 6. **SDK Scaffolding + API Type Definitions (PR-7 prep)**

  **What to do**:
  - Create `sdk/python/omoios/` package structure
  - Create `sdk/typescript/` package structure
  - Define TypeScript types for all new API endpoints (credentials, environments, artifacts, webhooks, workspaces)
  - Define Python dataclasses/Pydantic models for same
  - Set up build configs: `pyproject.toml` for Python, `package.json` + `tsconfig.json` for TypeScript
  - Create mock API client that returns fixture data (for SDK development against while backend is being built)
  - Write initial tests that validate mock client works

  **Must NOT do**:
  - No real API implementation (mocks only)
  - No convenience methods beyond basic REST wrappers
  - No browser/edge runtime support for TypeScript (Node.js only)

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Scaffolding and type definitions, no complex logic
  - **Skills**: [`python-patterns`, `coding-standards`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 3, 4, 5)
  - **Parallel Group**: Wave 2
  - **Blocks**: Tasks 9, 11
  - **Blocked By**: None

  **References**:
  - `docs/agent-platform-analysis/08-implementation-plan.md` lines 633–658 — PR-7 Public SDK with API contract definitions
  - `backend/omoi_os/api/routes/` - Existing route patterns to mirror in SDK types

  **Acceptance Criteria**:
  - [ ] `sdk/python/omoios/` has package structure with types
  - [ ] `sdk/typescript/src/` has package structure with types
  - [ ] Both packages have mock client that returns fixture data
  - [ ] `cd sdk/python && uv run pytest` passes
  - [ ] `cd sdk/typescript && pnpm test` passes

  **QA Scenarios**:
  ```
  Scenario: SDK mock client returns expected types
    Tool: Bash
    Steps:
      1. `cd sdk/python && uv run pytest tests/ -v`
      2. Assert mock client returns credential, environment, artifact types
      3. `cd ../../sdk/typescript && pnpm test`
      4. Assert same for TypeScript types
    Expected Result: Both SDK mock clients work, types validated
    Evidence: .sisyphus/evidence/task-6-sdk-scaffold.txt
  ```

  **Commit**: YES
  - Message: `chore: scaffold SDK packages with API types and mock clients`
  - Pre-commit: `cd sdk/python && uv run pytest && cd ../../sdk/typescript && pnpm test`

- [x] 7. **Go Egress Proxy (PR-2)**

  **What to do**:
  - Create `egress-proxy/` directory with Go module
  - Write failing tests for hostname allowlist filtering
  - Implement HTTP/HTTPS proxy that blocks all outbound traffic except allowlisted hostnames
  - Read allowlist from config file or env var (e.g., `ALLOWED_HOSTS=api.github.com,registry.npmjs.org`)
  - Add `/health` endpoint for k8s/liveness probes
  - Add Prometheus metrics (requests_total, blocked_total, latency_histogram)
  - Keep implementation STRICTLY ≤ 300 LOC (excluding tests)
  - Write unit tests for filtering logic
  - Write integration test with mock sandbox
  - Containerize with minimal Dockerfile (multi-stage build, ~10MB image)

  **Must NOT do**:
  - No load balancing or circuit breaking
  - No request transformation
  - No WebSocket support (v1 HTTP/HTTPS only)
  - No more than 500 LOC total (Go source + tests separate)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Network proxy implementation requiring Go expertise and security review
  - **Skills**: [`security-review`, `golang-patterns`]
    - `security-review`: Network security validation
    - `golang-patterns`: Idiomatic Go patterns

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Task 3 broker for credential injection design)
  - **Parallel Group**: Wave 4 (sequential after Task 3)
  - **Blocks**: Task 10 (workspace isolation needs egress control)
  - **Blocked By**: Task 3

  **References**:
  - `docs/agent-platform-analysis/08-implementation-plan.md` lines 567–615 — PR-5 Egress Proxy with exact Go proxy specs and hostname allowlist design
  - `docs/agent-platform-analysis/07-architecture-diagrams.md` - Egress proxy C4 diagram and sequence flow
  - `docs/agent-platform-analysis/02-spec-overview.md` - Hostname allowlist design

  **Acceptance Criteria**:
  - [ ] `cd egress-proxy && go test ./...` passes
  - [ ] `go build` produces working binary
  - [ ] Proxy blocks requests to non-allowlisted hosts
  - [ ] Proxy allows requests to allowlisted hosts
  - [ ] `/health` endpoint returns 200
  - [ ] Total Go source ≤ 300 LOC
  - [ ] Docker image builds

  **QA Scenarios**:
  ```
  Scenario: Proxy blocks non-allowlisted hostname
    Tool: Bash
    Steps:
      1. Start proxy with ALLOWED_HOSTS=api.github.com
      2. curl through proxy to http://evil.example.com
      3. Assert connection blocked (403 or connection refused)
      4. curl through proxy to https://api.github.com
      5. Assert 200 or valid response
    Expected Result: Non-allowlisted host blocked, allowlisted host allowed
    Evidence: .sisyphus/evidence/task-7-egress-filter.txt
  ```

  **Commit**: YES
  - Message: `feat: add Go egress proxy with hostname allowlists`
  - Pre-commit: `cd egress-proxy && go test ./...`

- [ ] 8. **Webhook Delivery Service (PR-5)**

  **What to do**:
  - Write failing tests for webhook delivery lifecycle
  - Create `backend/omoi_os/services/webhook_service.py`
  - Create `webhook_subscriptions` table (id, org_id, url, events[], secret, active)
  - Create `webhook_deliveries` table (id, subscription_id, event, payload, status, attempts, next_retry_at, created_at)
  - Implement at-least-once delivery with exponential backoff (max 24 hours)
  - Sign payloads with HMAC-SHA256 using subscription secret
  - Include timestamp in signature to prevent replay attacks (reject > 5 min old)
  - Event types: `spec.created`, `task.started`, `task.completed`, `session.created`, `artifact.uploaded`
  - Create routes: `POST /api/v1/webhooks`, `GET /api/v1/webhooks`, `DELETE /api/v1/webhooks/{id}`, `GET /api/v1/webhooks/{id}/deliveries`
  - Guard with `webhooks_enabled` feature flag

  **Must NOT do**:
  - No webhook management UI
  - No retry dashboard
  - No more than 5 event types for v1

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: [`python-patterns`, `api-design`, `security-review`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 7, 9)
  - **Parallel Group**: Wave 4 (after Task 3 broker)
  - **Blocks**: Tasks 9, 11
  - **Blocked By**: Task 3 (broker), Task 5 (artifacts — for artifact.uploaded event)

  **References**:
  - `docs/agent-platform-analysis/08-implementation-plan.md` lines 567–615 — PR-5 Egress Proxy with event types and delivery specs
  - `docs/agent-platform-analysis/04-gap-analysis.md` - Gap #5 (no webhook delivery)

  **Acceptance Criteria**:
  - [ ] Test file: `backend/tests/unit/test_webhook_service.py`
  - [ ] `just test-unit` → PASS
  - [ ] Webhook delivery succeeds to test endpoint
  - [ ] HMAC signature validated by test consumer
  - [ ] Retry with backoff on failure
  - [ ] Feature flag `webhooks_enabled` guards all routes

  **QA Scenarios**:
  ```
  Scenario: Deliver webhook and verify HMAC signature
    Tool: Bash (curl + python)
    Steps:
      1. Create subscription: POST /api/v1/webhooks `{"url": "http://localhost:9999/hook", "events": ["task.completed"], "secret": "whsec_test"}`
      2. Trigger task.completed event
      3. Verify delivery was attempted at the test endpoint
      4. Verify HMAC signature header matches expected value
    Expected Result: Webhook delivered with valid HMAC signature
    Evidence: .sisyphus/evidence/task-8-webhook-delivery.txt
  ```

  **Commit**: YES
  - Message: `feat: add webhook delivery with HMAC signatures and retry logic`
  - Pre-commit: `just test-unit`

- [ ] 9. **Python SDK Implementation**

  **What to do**:
  - Write failing tests for each SDK method
  - Replace mock client from Task 6 with real HTTP client using `httpx` (async)
  - Implement authentication: API key + JWT token support
  - Implement all credential, environment, artifact, webhook, workspace endpoints
  - Add type hints throughout (Pydantic models for request/response)
  - Add docstrings with examples for each public method
  - Ensure tests pass against real local API (integration tests)

  **Must NOT do**:
  - No convenience methods beyond thin REST wrappers
  - No auto-retry logic (leave to user)
  - No framework integrations (FastAPI, Django, etc.)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: [`python-patterns`, `coding-standards`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 7, 8, 10)
  - **Parallel Group**: Wave 4 (can start after Tasks 3, 4, 5, 6 complete)
  - **Blocks**: None
  - **Blocked By**: Tasks 3, 4, 5, 6

  **References**:
  - `sdk/python/omoios/` - (Task 6 output) Package structure and types
  - `backend/omoi_os/api/routes/` - Real API route implementations to mirror

  **Acceptance Criteria**:
  - [ ] `cd sdk/python && uv run pytest` passes
  - [ ] All new API endpoints covered by SDK methods
  - [ ] Integration tests pass against local API
  - [ ] Type hints on all public methods

  **QA Scenarios**:
  ```
  Scenario: SDK authenticates and lists environments
    Tool: Bash
    Steps:
      1. `cd sdk/python && uv run pytest tests/test_integration.py -v`
      2. Assert SDK can authenticate with API key
      3. Assert SDK can list environments (or get empty list)
    Expected Result: SDK authenticates, list_environments() returns list
    Evidence: .sisyphus/evidence/task-9-python-sdk.txt
  ```

  **Commit**: YES
  - Message: `feat: implement Python SDK with full API coverage`
  - Pre-commit: `cd sdk/python && uv run pytest`

- [ ] 10. **Workspace Isolation Layer (PR-6)**

  **What to do**:
  - Write failing tests for workspace isolation guarantees
  - Create `backend/omoi_os/services/workspace_isolation_service.py`
  - Implement file-level isolation: each workspace gets isolated storage path under `/workspaces/{id}/`
  - Implement credential scoping: sessions can only access credentials bound to their workspace
  - Implement environment variable injection: sessions receive their workspace's environment variables
  - Implement network egress controls: sessions inherit egress proxy config from workspace settings
  - Create `workspace_settings` table (id, workspace_id, egress_allowlist JSONB, max_artifact_size_mb, allowed_binding_kinds JSONB)
  - Create routes: `GET /api/v1/workspaces/{id}/settings`, `PUT /api/v1/workspaces/{id}/settings`
  - Wire isolation checks into existing session creation flow
  - Guard with `sessions_api_v1` feature flag

  **Must NOT do**:
  - No container-level isolation (Daytona handles that)
  - No cross-workspace access patterns
  - No changes to existing workspace CRUD (isolation only)
  - No UI for workspace settings (API only for v1)

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: Cross-cutting security layer touching session, credential, environment, and egress services
  - **Skills**: [`security-review`, `python-patterns`]
    - `security-review`: Isolation boundary validation
    - `python-patterns`: Service integration patterns

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 9, 11)
  - **Parallel Group**: Wave 5 (after Tasks 1, 3, 4, 7)
  - **Blocks**: None (final implementation task)
  - **Blocked By**: Tasks 1 (encryption), 3 (credentials), 4 (environments), 7 (egress proxy)

  **References**:
  - `docs/agent-platform-analysis/08-implementation-plan.md` lines 616–632 — PR-6 Polish Bundle with exact workspace isolation specs
  - `docs/agent-platform-analysis/07-architecture-diagrams.md` - Workspace isolation C4 diagram
  - `docs/agent-platform-analysis/04-gap-analysis.md` - Gap #1 (no workspace isolation)
  - `backend/omoi_os/services/credential_broker.py` - (Task 3 output) Credential scoping integration
  - `backend/omoi_os/services/environment_service.py` - (Task 4 output) Environment injection
  - `egress-proxy/` - (Task 7 output) Egress proxy config format

  **Acceptance Criteria**:
  - [ ] Test file: `backend/tests/unit/test_workspace_isolation.py`
  - [ ] `just test-unit` → PASS
  - [ ] Session cannot access credentials from another workspace
  - [ ] Session receives correct environment variables for its workspace
  - [ ] Session's egress is limited to workspace allowlist
  - [ ] Feature flag `sessions_api_v1` guards all routes

  **QA Scenarios**:
  ```
  Scenario: Session cannot access cross-workspace credentials
    Tool: Bash (curl)
    Preconditions: 2 workspaces with separate credentials
    Steps:
      1. Create credential in workspace A
      2. Create credential in workspace B
      3. Create session in workspace A
      4. Attempt to list credentials from session A context
      5. Assert only workspace A credentials visible
      6. Attempt to access workspace B credential by ID from session A
      7. Assert 403 Forbidden
    Expected Result: Workspace A session sees only A's credentials, B's are blocked
    Evidence: .sisyphus/evidence/task-10-isolation-credentials.txt

  Scenario: Workspace egress allowlist enforced
    Tool: Bash
    Steps:
      1. Set workspace egress_allowlist to `["api.github.com"]`
      2. Verify session proxy config only allows api.github.com
      3. Set different workspace to allow `["registry.npmjs.org"]`
      4. Verify each workspace gets its own allowlist
    Expected Result: Each workspace has independent egress config
    Evidence: .sisyphus/evidence/task-10-isolation-egress.txt
  ```

  **Commit**: YES
  - Message: `feat: add workspace isolation for credentials, environments, and egress`
  - Pre-commit: `just test-unit`

- [ ] 11. **TypeScript SDK Implementation**

  **What to do**:
  - Write failing tests for each SDK method
  - Replace mock client from Task 6 with real HTTP client using `fetch` (Node.js native)
  - Implement authentication: API key + JWT token support
  - Implement all credential, environment, artifact, webhook, workspace endpoints
  - Add full TypeScript types for all request/response shapes
  - Add JSDoc comments with examples for each public method
  - Ensure tests pass against real local API (integration tests)

  **Must NOT do**:
  - No browser runtime support (Node.js only)
  - No convenience methods beyond thin REST wrappers
  - No auto-retry logic
  - No framework integrations

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: [`coding-standards`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 9, 10)
  - **Parallel Group**: Wave 5 (after Tasks 3, 4)
  - **Blocks**: None
  - **Blocked By**: Tasks 3, 4, 5, 6

  **References**:
  - `sdk/typescript/src/` - (Task 6 output) Package structure and types
  - `backend/omoi_os/api/routes/` - Real API route implementations to mirror
  - `sdk/python/omoios/` - (Task 9 output) Python SDK for API contract reference

  **Acceptance Criteria**:
  - [ ] `cd sdk/typescript && pnpm test` passes
  - [ ] All new API endpoints covered by SDK methods
  - [ ] Integration tests pass against local API
  - [ ] TypeScript strict mode, no `any` types

  **QA Scenarios**:
  ```
  Scenario: TypeScript SDK authenticates and creates credential
    Tool: Bash
    Steps:
      1. `cd sdk/typescript && pnpm test tests/integration.test.ts`
      2. Assert SDK authenticates with API key
      3. Assert SDK can create a bearer_secret credential
    Expected Result: SDK authenticates, createCredential returns typed response
    Evidence: .sisyphus/evidence/task-11-typescript-sdk.txt
  ```

  **Commit**: YES
  - Message: `feat: implement TypeScript SDK with full API coverage`
  - Pre-commit: `cd sdk/typescript && pnpm test`

- [ ] 12. **API Route Aliases (sessions → tasks)**

  **What to do**:
  - Write failing tests for route alias behavior
  - Add `GET /api/v1/sessions` route that internally calls the existing `GET /api/v1/tasks` handler
  - Add `GET /api/v1/sessions/{id}` → `GET /api/v1/tasks/{id}`
  - Add `POST /api/v1/sessions` → `POST /api/v1/tasks`
  - Add `DELETE /api/v1/sessions/{id}` → `DELETE /api/v1/tasks/{id}`
  - Response bodies: include both `id` and `session_id` fields (backward compat)
  - Request bodies: accept both `task_id` and `session_id` params
  - Add deprecation header: `X-Deprecated: Use /api/v1/tasks instead. Removed in v2.0.`
  - Update API docs (Swagger) with deprecation notice
  - Guard with `sessions_api_v1` feature flag
  - **DO NOT** rename any DB columns or tables

  **Must NOT do**:
  - No database migration or column renames
  - No changes to existing `/tasks` routes or their handlers
  - No changes to frontend (it continues using `/tasks`)
  - No renaming `tasks` table to `sessions`

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Thin alias layer, no complex logic
  - **Skills**: [`python-patterns`, `api-design`]

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 9, 10, 11)
  - **Parallel Group**: Wave 5 (after Task 2 feature flags)
  - **Blocks**: None
  - **Blocked By**: Task 2 (feature flags must exist)

  **References**:
  - `backend/omoi_os/api/routes/tasks.py` - Existing task routes to alias
  - `backend/omoi_os/api/main.py` - Route registration patterns
  - `docs/agent-platform-analysis/08-implementation-plan.md` - Route alias specs

  **Acceptance Criteria**:
  - [ ] Test file: `backend/tests/unit/test_session_aliases.py`
  - [ ] `just test-unit` → PASS
  - [ ] `GET /api/v1/sessions` returns same data as `GET /api/v1/tasks`
  - [ ] Response includes deprecation header
  - [ ] Feature flag `sessions_api_v1` controls alias availability
  - [ ] No changes to existing task routes

  **QA Scenarios**:
  ```
  Scenario: Session alias returns same data as tasks with deprecation header
    Tool: Bash (curl)
    Steps:
      1. GET /api/v1/tasks — capture response body
      2. GET /api/v1/sessions — capture response body + headers
      3. Assert response bodies are identical
      4. Assert X-Deprecated header present
    Expected Result: Same data, deprecation header on /sessions
    Evidence: .sisyphus/evidence/task-12-session-aliases.txt
  ```

  **Commit**: YES
  - Message: `feat: add session API aliases with deprecation headers`
  - Pre-commit: `just test-unit`


## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, curl endpoint, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .sisyphus/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

  **QA Scenario**:
  ```
  Scenario: Verify all Must Have items exist in codebase
    Tool: Bash (grep + curl)
    Steps:
      1. Grep for `credential_encryption.py` — must exist
      2. Grep for `credential_broker.py` — must exist
      3. Grep for `environment_service.py` — must exist
      4. Grep for `artifact_service.py` — must exist
      5. Grep for `webhook_service.py` — must exist
      6. Grep for `workspace_isolation_service.py` — must exist
      7. Grep for `egress-proxy/main.go` — must exist
      8. Grep for `sdk/python/omoios/` — must exist
      9. Grep for `sdk/typescript/src/` — must exist
      10. Grep for `sessions_api_v1`, `environments_v1`, `broker_enabled`, `egress_proxy_enabled`, `artifacts_unified_v1`, `webhooks_enabled` in base.yaml — all must exist and be false
      11. Grep for plaintext credential patterns (sk-test, api_key=) in service files — must NOT find any
      12. List files in `.sisyphus/evidence/` — all task evidence files must exist
    Expected Result: All 12 items verified, no forbidden patterns found
    Evidence: .sisyphus/evidence/f1-compliance-audit.txt
  ```

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run `just check` + `just test-all` + `go test ./...` (for egress proxy). Review all changed files for: `as any`/type ignores, empty catches, console.log in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names. Verify no plaintext credentials in any file.
  Output: `Build [PASS/FAIL] | Lint [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

  **QA Scenario**:
  ```
  Scenario: Full build + lint + test passes with zero issues
    Tool: Bash
    Steps:
      1. Run `just check` — assert exit code 0
      2. Run `just test-all` — assert 0 failures
      3. Run `cd egress-proxy && go test ./...` — assert PASS
      4. Run `cd sdk/python && uv run pytest` — assert PASS
      5. Run `cd sdk/typescript && pnpm test` — assert PASS
      6. Run `grep -r 'as any' backend/omoi_os/services/credential_broker.py backend/omoi_os/services/webhook_service.py` — assert no matches
      7. Run `grep -rn 'console\.log' backend/omoi_os/services/` — assert no matches in new services
      8. Run `wc -l egress-proxy/*.go` — assert ≤ 500 LOC total
    Expected Result: All builds pass, no code smells, Go proxy within LOC limit
    Evidence: .sisyphus/evidence/f2-code-quality.txt
  ```

- [ ] F3. **Real Manual QA** — `unspecified-high`
  Start from clean state. Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Test cross-task integration: create environment → launch sandbox with broker → verify egress blocked → check webhook delivered → verify artifact stored. Test edge cases: empty state, invalid credentials, network failure during egress. Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

  **QA Scenario**:
  ```
  Scenario: Cross-task integration — full workflow
    Tool: Bash (curl)
    Steps:
      1. Create environment: POST /api/v1/environments `{"name": "integration-test"}`
      2. Add version with secret: POST /api/v1/environments/{id}/versions `{"variables": {"API_KEY": {"type": "secret", "value": "sk-test-123"}}}`
      3. Create credential: POST /api/v1/credentials `{"kind": "bearer_secret", "name": "test-key", "value": "sk-bearer-456"}`
      4. Upload artifact: POST /api/v1/artifacts/upload (test file)
      5. Create webhook subscription: POST /api/v1/webhooks `{"url": "http://localhost:9999/hook", "events": ["artifact.uploaded"]}`
      6. Verify webhook was delivered for artifact.uploaded event
      7. Verify workspace isolation: workspace A cannot see workspace B credentials
    Expected Result: Full workflow succeeds end-to-end, webhook delivered, isolation enforced
    Evidence: .sisyphus/evidence/f3-integration-qa.txt

  Scenario: Edge case — empty state returns valid responses
    Tool: Bash (curl)
    Steps:
      1. GET /api/v1/environments — assert 200 with empty list
      2. GET /api/v1/credentials — assert 200 with empty list
      3. GET /api/v1/artifacts — assert 200 with empty list
      4. GET /api/v1/webhooks — assert 200 with empty list
    Expected Result: All endpoints return valid empty-state responses
    Evidence: .sisyphus/evidence/f3-empty-state.txt
  ```

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff (git log/diff). Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT do" compliance. Detect cross-task contamination: Task N touching Task M's files. Flag unaccounted changes. Verify Go proxy ≤ 500 LOC.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

  **QA Scenario**:
  ```
  Scenario: No scope creep — tasks match spec exactly
    Tool: Bash (git diff)
    Steps:
      1. For each task, list files changed: `git diff --name-only main..HEAD | grep <task-pattern>`
      2. Verify Task 3 only touches credential_broker.py, routes, models — not environment_service.py
      3. Verify Task 12 only touches sessions route alias file — not existing tasks routes
      4. Verify Task 7 only touches egress-proxy/ directory — not backend Python files
      5. Verify no new binding kinds beyond bearer_secret, user_oauth, github_app
      6. Verify no webhook management UI files created
      7. Verify Go proxy source ≤ 500 LOC: `find egress-proxy -name '*.go' -not -path '*_test.go' -exec cat {} + | wc -l`
    Expected Result: Zero cross-task contamination, no scope creep, LOC limits respected
    Evidence: .sisyphus/evidence/f4-scope-fidelity.txt
  ```

---

## Commit Strategy

| Wave | Commit Message | Files |
|------|---------------|-------|
| 1 | `security: encrypt provider API keys with Fernet` | `backend/omoi_os/services/credential_encryption.py`, `backend/omoi_os/models/provider_key.py`, migration |
| 1 | `feat: add feature flags for agent workspace platform` | `backend/config/base.yaml`, `backend/omoi_os/config.py` |
| 2 | `feat: add environment resource with versioned immutable configs` | `backend/omoi_os/models/environment.py`, service, routes, migration |
| 2 | `feat: add unified artifact model with multi-backend storage` | `backend/omoi_os/services/artifact_service.py`, routes, migration |
| 2 | `chore: scaffold SDK packages with API types` | `sdk/python/`, `sdk/typescript/` |
| 3 | `feat: add credential broker service with 3 binding kinds` | `backend/omoi_os/services/credential_broker.py`, routes, models, migration |
| 4 | `feat: add Go egress proxy with hostname allowlists` | `egress-proxy/` |
| 4 | `feat: add webhook delivery with HMAC signatures` | `backend/omoi_os/services/webhook_service.py`, routes, migration |
| 4 | `feat: implement Python SDK with full API coverage` | `sdk/python/omoios/` |
| 5 | `feat: add workspace isolation for credentials, environments, and egress` | `backend/omoi_os/services/workspace_isolation_service.py`, routes, migration |
| 5 | `feat: implement TypeScript SDK with full API coverage` | `sdk/typescript/src/` |
| 5 | `feat: add sessions API aliases with deprecation headers` | `backend/omoi_os/api/routes/sessions.py` |

---

## Success Criteria

### Verification Commands
```bash
just test-all                              # Expected: all pass, 80%+ coverage on new files
just check                                 # Expected: no lint errors
cd egress-proxy && go test ./...           # Expected: all pass
cd sdk/python && uv run pytest             # Expected: all pass
cd sdk/typescript && pnpm test             # Expected: all pass
uv run alembic upgrade head                # Expected: no errors
uv run alembic downgrade -1                # Expected: clean rollback
grep -r "plaintext\|unencrypted" backend/  # Expected: no matches in service code
wc -l egress-proxy/*.go                    # Expected: ≤ 500 total
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass with 80%+ coverage on new code
- [ ] All 6 feature flags exist and default OFF
- [ ] No plaintext credentials in DB, logs, or error messages
- [ ] Go proxy ≤ 500 LOC
- [ ] Both SDKs install and authenticate
- [ ] All migrations reversible
