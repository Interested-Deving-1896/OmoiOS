# Agent Workspace Platform — Known Issues & Gotchas

## Critical Gotchas

### SQLAlchemy Reserved Words
- NEVER use `metadata` or `registry` as column names
- Use `change_metadata`, `item_metadata`, `config_metadata` instead
- Violation causes `InvalidRequestError` on import

### Service Initialization
- Two separate initialization points:
  - `api/main.py` — API server (25+ services)
  - `workers/orchestrator_worker.py` — background worker
- They run as separate processes, do not share state
- Check Service Availability Matrix in ARCHITECTURE.md

### Datetime Handling
- NEVER use `datetime.utcnow()` — naive datetime
- ALWAYS use `omoi_os.utils.datetime.utc_now()` — timezone-aware
- Database requires timezone-aware datetimes

### LLM Response Parsing
- NEVER manually parse JSON from LLM responses
- ALWAYS use `llm_service.structured_output()` with Pydantic model
- Handles streaming, validation, error cases

## Migration Safety
- Always test `alembic upgrade head` and `alembic downgrade -1`
- Never drop columns with data in same migration that adds replacement
- Use separate migrations for: add column → backfill → drop old

## Security Boundaries
- No plaintext credentials in any file (logs, errors, responses)
- No credential caching in Redis for v1 (fail-closed)
- No cross-workspace access patterns
- No WebSocket support in egress proxy v1

## Testing Requirements
- Must have 80%+ coverage on new code
- Must save evidence to `.sisyphus/evidence/`
- Must test both happy path and error cases
- Must verify feature flags guard all new routes
