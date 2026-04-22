# OmoiOS Project Rules

**Document Purpose**: Project-specific development rules and conventions to ensure consistency and avoid common pitfalls.

**Created**: 2025-11-16

---

## Port Selection Policy

### Rule: Avoid Common Default Ports

**Problem**: Using default ports (5432 for PostgreSQL, 6379 for Redis, 8000 for web servers) causes port conflicts when multiple services or projects run on the same machine.

**Solution**: Use non-standard ports by adding 10000 to the default port number.

**Port Mapping**:
- PostgreSQL: `15432` (default: 5432)
- Redis: `16379` (default: 6379)
- Web API Server: `18000` (default: 8000)
- WebSocket Server: `18001` (default: 8001)

**Rationale**:
- Easy to remember (default + 10000)
- Avoids conflicts with system services and other projects
- Still clearly indicates the service type
- High enough to avoid conflicts with most common services

**Implementation**:
- All `docker-compose.yml` services must use non-standard exposed ports
- All connection strings and configuration files must reference these ports
- Document port mappings in README.md and docker-compose.yml comments

**Example**:
```yaml
services:
  postgres:
    ports:
      - "15432:5432"  # Non-standard port to avoid conflicts
```

---

## Project Naming Conventions

### Database Names

- Use descriptive database names: `omoi_os_dev`, `omoi_os_test`, `omoi_os_prod`
- Never use generic names like `test`, `dev`, `app`
- Match the environment: `_dev` for development, `_test` for testing, `_prod` for production

### Branch Names

Follow [Conventional Commits](https://www.conventionalcommits.org/) style for branch naming:

- `feat/description` — New features
- `fix/description` — Bug fixes
- `refactor/description` — Code refactoring
- `docs/description` — Documentation changes
- `test/description` — Test additions or fixes
- `security/description` — Security-related changes
- `chore/description` — Maintenance tasks

**Examples**:
- `feat/add-oip-proposal-skill`
- `fix/correct-api-error-handling`
- `docs/expand-design-principles`

### File and Directory Names

- **Backend (Python)**: `snake_case.py` for files, `snake_case/` for directories
- **Frontend (TypeScript)**: `kebab-case.ts` for files, `kebab-case/` for directories
- **Documentation**: `kebab-case.md` for files
- **Components**: PascalCase for React components (`PromptInput.tsx`)

---

## Environment Requirements

### Required Environment Variables

**Backend** (`.env`):
- `AUTH_JWT_SECRET_KEY` — Generate with `openssl rand -hex 32`
- `DATABASE_URL` — PostgreSQL connection string (port 15432)
- `REDIS_URL` — Redis connection string (port 16379)

**Optional but Recommended**:
- `LLM_API_KEY` — For AI-dependent features
- `ANTHROPIC_API_KEY` — For Claude agent features
- `GITHUB_TOKEN` — For Git integration
- `DAYTONA_API_KEY` — For sandbox execution

**Frontend** (`.env.local`):
- `NEXT_PUBLIC_API_URL` — Backend API URL (default: http://localhost:18000)
- `NEXT_PUBLIC_WS_URL` — WebSocket URL (default: ws://localhost:18001)

### Environment File Management

- `.env` and `.env.local` are gitignored — never commit them
- `.env.example` files provide templates with safe defaults
- Secrets go in `.env` files only, never in YAML configs or code
- Application settings go in `backend/config/*.yaml`

---

## Development Conventions

### Backend (Python)

- **Formatting/linting**: ruff
- **Async**: Use `async/await` for all I/O
- **Datetime**: Always `omoi_os.utils.datetime.utc_now()`, never `datetime.utcnow()`
- **LLM calls**: Use `llm_service.structured_output()` with Pydantic models
- **SQLAlchemy**: Never use `metadata` or `registry` as column names (reserved words)
- **Settings classes**: Extend `OmoiBaseSettings` with `yaml_section` and `@lru_cache` factory

### Frontend (TypeScript)

- **Framework**: Next.js 15 App Router
- **UI components**: ShadCN UI (Radix + Tailwind). Check `components/ui/` before creating new primitives.
- **State**: React Query for server state, Zustand for client state
- **API calls**: Use the typed client in `lib/api/client.ts`
- **Hooks**: One hook per domain in `hooks/`

### Commit Messages

Format: `<type>: <short description>`

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `security`, `chore`

Examples:
```
feat: add OIP proposal skill for interactive proposal creation
fix: correct ApiError constructor call for 429 rate limit handling
security: require authentication on all explore API endpoints
docs: add OIP proposal system, rewrite contributor docs for AI agents
```

---

## Service Initialization

Two separate service initialization points exist:

1. **`api/main.py`** — API server initializes 25+ services for HTTP handling
2. **`workers/orchestrator_worker.py`** — Background worker initializes services for task execution

They run as separate processes and do not share state. See the Service Availability Matrix in ARCHITECTURE.md.

---

## Document Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-11-16 | AI Assistant | Initial port selection policy |
| 1.1 | 2025-04-22 | AI Assistant | Renamed Senior Sandbox → OmoiOS, added naming conventions, environment requirements, and development conventions |
