# Feature-Flagged v1 API Surfaces

**Category**: Rule · **Severity**: Medium · **Last updated**: 2026-04-24

## The error that brings you here

A route you just wrote returns `404 {"detail":"Not Found"}` even though it's
clearly registered in `openapi.json`. Or a brand-new route file returns
`{"detail":"Artifacts API not available"}` — a 404 with a custom message.

## Why it happens in this codebase

The agent-workspace platform v1 surfaces (`sessions_api_v1`,
`environments_v1`, `broker_enabled`, `egress_proxy_enabled`,
`artifacts_unified_v1`, `webhooks_enabled`) are **off by default**. Each
route gates itself with `check_feature_flag()` — if the flag is off, it
returns 404.

Flags are set by env vars with a `FEATURE_` prefix:

```bash
FEATURE_SESSIONS_API_V1=true
FEATURE_ENVIRONMENTS_V1=true
FEATURE_BROKER_ENABLED=true
FEATURE_ARTIFACTS_UNIFIED_V1=true
FEATURE_WEBHOOKS_ENABLED=true
FEATURE_EGRESS_PROXY_ENABLED=true
```

`backend/.env` is where dev-loop values live. Restart the API server after
changing them — `uvicorn --reload` watches files, not the environment.

## The rule

1. When you add a **new v1 surface**, mirror the existing pattern: add the
   flag to `FeatureFlagsSettings` in `backend/omoi_os/config.py` *and* to
   `backend/config/base.yaml`. Default `False`. Guard every route with
   `check_feature_flag()`.
2. When you **enable** a surface for local dev, set the env var, then kill
   and restart the uvicorn process. `--reload` only picks up code changes.
3. When you're **debugging a 404**, check whether the route is behind a flag
   before assuming it isn't registered. `curl /openapi.json | jq '.paths'`
   will list it; the feature flag is the separate reason it's gated.

## Why the default is off

These surfaces are partially implemented, and leaving them dark on
production (Railway) is intentional. The flag is the kill switch while the
spec (`docs/agent-platform-analysis/agent-platform-spec.zip`) is still
settling.

## Related

- `backend/config/base.yaml` → `feature_flags` section
- `backend/omoi_os/config.py::FeatureFlagsSettings`
- `backend/omoi_os/api/routes/credentials_broker.py::check_feature_flag` (the
  canonical implementation to copy)
