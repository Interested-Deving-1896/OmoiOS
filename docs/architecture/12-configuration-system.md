# Part 12: Configuration System

> **Status**: Production-Ready | **Last Updated**: 2025-04-22
> 
> This document covers the dual configuration system using YAML files for application settings and environment variables for secrets, built on Pydantic's `OmoiBaseSettings`.

## Purpose

OmoiOS uses a **dual configuration system** that separates concerns between version-controlled application settings and gitignored secrets. This approach enables:

- **Environment-specific overrides** without code changes
- **Secret rotation** without redeployment
- **Type-safe configuration** with Pydantic validation
- **Hierarchical precedence** (env vars override YAML defaults)

## Architecture Overview

```mermaid
flowchart TB
    subgraph Sources["Configuration Sources"]
        direction TB
        INIT[Constructor Args]
        ENV[Environment Variables]
        YAML[YAML Files]
        DOTENV[.env / .env.local]
    end
    
    subgraph Precedence["Precedence (High to Low)"]
        P1[1. Constructor Args]
        P2[2. Environment Variables]
        P3[3. .env / .env.local]
        P4[4. YAML Files]
    end
    
    subgraph Settings["Settings Classes"]
        BASE[OmoiBaseSettings]
        LLM[LLMSettings]
        DB[DatabaseSettings]
        REDIS[RedisSettings]
        AUTH[AuthSettings]
        MON[MonitoringSettings]
    end
    
    subgraph Factory["Factory Functions"]
        GET[get_app_settings]
        LOAD[load_*_settings]
    end
    
    Sources --> Precedence
    Precedence --> BASE
    BASE --> LLM
    BASE --> DB
    BASE --> REDIS
    BASE --> AUTH
    BASE --> MON
    LLM --> Factory
    DB --> Factory
    REDIS --> Factory
```

## Configuration Hierarchy

**Priority (highest to lowest)**:

1. **Constructor arguments** (init values)
2. **Environment variables** (`OMOI_SECTION_KEY` format)
3. **.env / .env.local files** (dotenv format)
4. **YAML file defaults** (`config/{environment}.yaml`)

## YAML Structure

**Location**: `backend/config/`

```
config/
├── base.yaml          # Default settings (always loaded)
├── local.yaml         # Local development overrides
├── staging.yaml       # Staging environment
├── production.yaml    # Production environment
└── test.yaml          # Test environment (fast intervals, mocks)
```

### YAML Loading Order

```python
def _yaml_layers(env_name: str) -> list[Path]:
    layers = []
    base_path = CONFIG_ROOT / "base.yaml"
    if base_path.exists():
        layers.append(base_path)
    
    env_path = CONFIG_ROOT / f"{env_name}.yaml"
    if env_path.exists():
        layers.append(env_path)
    return layers
```

**Merge Strategy**: Deep merge with override (nested dicts are merged, not replaced)

### YAML Sections

| Section | Purpose | Example Settings |
|---------|---------|------------------|
| `llm` | LLM configuration | `model`, `api_key`, `base_url` |
| `database` | Database connection | `url`, `pool_size`, `timeout` |
| `redis` | Redis connection | `url`, `connection_timeout` |
| `task_queue` | Task polling | `poll_interval`, `max_concurrent` |
| `monitoring` | Guardian/Conductor | `guardian_interval`, `conductor_interval` |
| `auth` | JWT configuration | `access_token_expire_minutes` |
| `features` | Feature flags | `enable_discovery`, `enable_guardian` |
| `daytona` | Sandbox configuration | `memory_gb`, `cpu`, `disk_gb` |
| `integrations` | External services | `github_token`, `mcp_server_url` |
| `embedding` | Embedding provider | `provider`, `model_name` |
| `billing` | Stripe configuration | `workflow_price_usd` |

## OmoiBaseSettings

**Location**: `backend/omoi_os/config.py:99-127`

The base class for all configuration classes, extending Pydantic's `BaseSettings` with YAML support.

```python
class OmoiBaseSettings(BaseSettings):
    yaml_section: ClassVar[Optional[str]] = None
    
    model_config = SettingsConfigDict(
        env_file=get_env_files(),
        env_file_encoding="utf-8",
        extra="ignore",
    )
    
    @classmethod
    def settings_customise_sources(cls, ...):
        # Priority: init > env > dotenv > secrets > yaml
        sources = [
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        ]
        if cls.yaml_section:
            sources.append(YamlSectionSettingsSource(...))
        return tuple(sources)
```

### Settings Pattern

All configuration classes follow this pattern:

```python
class MonitoringSettings(OmoiBaseSettings):
    """Monitoring loop configuration."""
    
    yaml_section = "monitoring"
    model_config = SettingsConfigDict(
        env_prefix="MONITORING_",
        extra="ignore"
    )
    
    # Settings with defaults (from YAML or env)
    guardian_interval_seconds: int = 60
    conductor_interval_seconds: int = 300
    health_check_interval_seconds: int = 30
    auto_steering_enabled: bool = False

# Singleton factory with caching
@lru_cache
def load_monitoring_settings() -> MonitoringSettings:
    return get_app_settings().monitoring
```

## Settings Classes

### LLMSettings

**Location**: `backend/omoi_os/config.py:154-176`

```python
class LLMSettings(OmoiBaseSettings):
    yaml_section = "llm"
    model_config = SettingsConfigDict(env_prefix="LLM_")
    
    model: str = "openhands/claude-sonnet-4-5-20250929"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    fireworks_api_key: Optional[str] = None
    mode: str = "live"  # "live" | "record" | "replay" | "null"
```

### DatabaseSettings

**Location**: `backend/omoi_os/config.py:240-268`

```python
class DatabaseSettings(OmoiBaseSettings):
    yaml_section = "database"
    model_config = SettingsConfigDict(env_prefix="DATABASE_")
    
    url: str = "postgresql+psycopg://postgres:postgres@localhost:15432/app_db"
    
    # Connection pool settings
    pool_size: int = 5
    max_overflow: int = 5
    pool_timeout: int = 30
    pool_recycle: int = 1800
    pool_pre_ping: bool = True
    pool_use_lifo: bool = True
    
    # Timeouts
    command_timeout: int = 30
    connect_timeout: int = 10
```

### AuthSettings

**Location**: `backend/omoi_os/config.py:369-464`

```python
class AuthSettings(OmoiBaseSettings):
    yaml_section = "auth"
    model_config = SettingsConfigDict(env_prefix="AUTH_")
    
    # JWT settings
    jwt_secret_key: str = "dev-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    
    # Password requirements
    min_password_length: int = 8
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_digit: bool = True
    
    # Rate limiting
    max_login_attempts: int = 5
    login_attempt_window_minutes: int = 15
    
    # OAuth providers
    github_client_id: Optional[str] = None
    github_client_secret: Optional[str] = None
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
```

### MonitoringSettings

**Location**: `backend/omoi_os/config.py:493-524`

```python
class MonitoringSettings(OmoiBaseSettings):
    yaml_section = "monitoring"
    model_config = SettingsConfigDict(env_prefix="MONITORING_")
    
    enabled: bool = False  # Master toggle
    orchestrator_enabled: bool = False
    
    guardian_interval_seconds: int = 60
    conductor_interval_seconds: int = 300
    health_check_interval_seconds: int = 30
    auto_steering_enabled: bool = False
    max_concurrent_analyses: int = 5
    llm_analysis_enabled: bool = True
```

### DaytonaSettings

**Location**: `backend/omoi_os/config.py:614-645`

```python
class DaytonaSettings(OmoiBaseSettings):
    yaml_section = "daytona"
    model_config = SettingsConfigDict(env_prefix="DAYTONA_")
    
    api_key: Optional[str] = None
    api_url: str = "https://app.daytona.io/api"
    target: str = "us"
    snapshot: Optional[str] = "ai-agent-dev-light"
    timeout: int = 300
    
    # Sandbox execution mode
    sandbox_execution: bool = False
    
    # Resource limits
    sandbox_memory_gb: int = 4
    sandbox_cpu: int = 2
    sandbox_disk_gb: int = 8
```

## Environment Variables

### Secret Management

Secrets go in `.env` (never committed):

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:15432/omoios

# Redis
REDIS_URL=redis://localhost:16379

# API Keys
ANTHROPIC_API_KEY=sk-ant-...
DAYTONA_API_KEY=...
GITHUB_TOKEN=ghp_...
STRIPE_SECRET_KEY=sk_...
STRIPE_WEBHOOK_SECRET=whsec_...

# JWT
AUTH_JWT_SECRET_KEY=...
```

### Environment File Priority

```python
def get_env_files():
    """Get environment files in priority order."""
    env_files = []
    if os.path.exists(".env"):
        env_files.append(".env")
    if os.path.exists(".env.local"):
        env_files.append(".env.local")
    return env_files if env_files else None
```

**Priority**: `.env.local` > `.env`

## AppSettings Aggregator

**Location**: `backend/omoi_os/config.py:853-902`

The `AppSettings` class aggregates all settings into a single access point:

```python
class AppSettings:
    def __init__(self) -> None:
        self.llm = LLMSettings()
        self.anthropic = AnthropicSettings()
        self.database = DatabaseSettings()
        self.redis = RedisSettings()
        self.task_queue = TaskQueueSettings()
        self.approval = ApprovalSettings()
        self.auth = AuthSettings()
        self.workspace = WorkspaceSettings()
        self.monitoring = MonitoringSettings()
        self.orchestrator = OrchestratorSettings()
        self.git = GitSettings()
        self.spec = SpecSettings()
        self.sandbox = SandboxSettings()
        self.diagnostic = DiagnosticSettings()
        self.worker = WorkerSettings()
        self.daytona = DaytonaSettings()
        self.integrations = IntegrationSettings()
        self.embedding = EmbeddingSettings()
        self.observability = ObservabilitySettings()
        self.sentry = SentrySettings()
        self.posthog = PostHogSettings()
        self.title_generation = TitleGenerationSettings()
        self.demo = DemoSettings()

@lru_cache(maxsize=1)
def get_app_settings() -> AppSettings:
    return AppSettings()
```

## Test Configuration

**Location**: `backend/config/test.yaml`

Test environment uses fast intervals and disables external integrations:

```yaml
monitoring:
  guardian_interval_seconds: 1      # 1s instead of 60s
  conductor_interval_seconds: 2     # 2s instead of 300s

auth:
  access_token_expire_minutes: 5    # Short for tests
  min_password_length: 6            # Less strict

integrations:
  enable_mcp_tools: false           # No real external calls
  enable_github_sync: false

features:
  enable_guardian: false            # Too slow for tests
```

## Validation

### Production Security Checks

**Location**: `backend/omoi_os/config.py:397-411`

```python
@model_validator(mode="after")
def _reject_weak_jwt_secret_in_production(self) -> "AuthSettings":
    env = os.environ.get(ENVIRONMENT_VARIABLE, DEFAULT_ENVIRONMENT)
    if env == "production":
        if self.jwt_secret_key in self._INSECURE_DEFAULTS:
            raise ValueError(
                "CRITICAL: Using a default JWT secret in production!"
            )
        if len(self.jwt_secret_key) < 32:
            raise ValueError(
                "JWT secret key is too short for production."
            )
    return self
```

## Usage Examples

### Basic Usage

```python
from omoi_os.config import get_app_settings

settings = get_app_settings()
database_url = settings.database.url
redis_url = settings.redis.url
```

### Service Initialization

```python
from omoi_os.config import get_app_settings
from omoi_os.services.database import DatabaseService

settings = get_app_settings()
db = DatabaseService(
    connection_string=settings.database.url,
    pool_size=settings.database.pool_size,
    max_overflow=settings.database.max_overflow,
)
```

### Environment-Specific Settings

```python
# Development (default)
OMOIOS_ENV=local python -m omoi_os.api.main

# Production
OMOIOS_ENV=production python -m omoi_os.api.main

# Testing
OMOIOS_ENV=test pytest
```

## Configuration Checklist

When adding new settings:

- [ ] Is this a secret? → Use `.env` ONLY
- [ ] Is this a business setting? → Use YAML
- [ ] Does a Settings class exist? → Use it
- [ ] Need new Settings class? → Extend `OmoiBaseSettings`
- [ ] Add to `config/base.yaml` with default value
- [ ] Add to `config/test.yaml` with test value (if different)
- [ ] Add to `AppSettings` aggregator
- [ ] Document in this file
- [ ] NEVER hardcode values in code

## Anti-Patterns

### ❌ Wrong: Hardcoded Value
```python
def process_task():
    timeout = 60  # Never hardcode!
```

### ❌ Wrong: Secret in YAML
```yaml
# config/base.yaml
llm:
  api_key: sk-ant-...  # NEVER put secrets in YAML!
```

### ❌ Wrong: Setting in .env
```bash
# .env
TASK_QUEUE_AGE_CEILING=3600  # Settings belong in YAML!
```

### ✅ Correct: Use Settings Class
```python
from omoi_os.config import load_task_queue_settings

def process_task():
    settings = load_task_queue_settings()
    timeout = settings.age_ceiling  # From YAML
```

## Related Documentation

### Architecture Deep-Dives
- [Part 11: Database Schema](11-database-schema.md) — Settings storage
- [Part 16: Service Catalog](16-service-catalog.md) — Configuration services

### Design Docs
- Configuration Architecture — YAML + env design
- Config Migration Guide — Migration patterns

### Requirements
- [Monitoring](../requirements/monitoring/monitoring_architecture.md) — Config requirements
