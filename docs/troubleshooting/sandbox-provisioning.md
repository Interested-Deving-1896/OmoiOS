# Troubleshooting Sandbox Provisioning

This guide provides diagnostic procedures and resolution steps for failures related to OmoiOS Daytona sandboxes and the Claude Agent SDK execution environment.

## 1. Sandbox Lifecycle Overview

OmoiOS uses a tiered sandboxing architecture:
1. **Daytona Service**: Orchestrates the provisioning of microVMs or containerized environments.
2. **DaytonaSpawner**: The backend service in `omoi_os/services/daytona_spawner.py` that interfaces with the Daytona API.
3. **ClaudeSandboxWorker**: The background worker process that executes code within the provisioned sandbox.

## 2. Common Provisioning Symptoms

### Symptom: Stuck in `provisioning` State
The sandbox status in the UI remains "provisioning" for more than 120 seconds.

**Actual Error Pattern (Backend Logs):**
`TimeoutError: Daytona spawner failed to reach 'ready' state for sandbox-uuid-123 within 120s`

**Root Causes:**
- **Resource Exhaustion**: The Daytona server is at maximum capacity (CPU/RAM).
- **Network Congestion**: Slow image pulls from the registry.
- **Service Stall**: The Daytona daemon is unresponsive.

**Fix Procedure:**
1. Check Daytona server health:
   ```bash
   # Check Daytona status
   daytona status
   
   # View recent logs
   daytona server logs --tail 50
   ```
2. Manually terminate the stalled sandbox to free resources:
   ```bash
   daytona workspace delete <sandbox-id>
   ```
3. Restart the Daytona service if unresponsive:
   ```bash
   just restart-daytona
   ```

### Symptom: `DAYTONA_API_KEY` Validation Failure
The orchestrator fails to initialize any sandbox tasks.

**Actual Error Pattern:**
`ValueError: DAYTONA_API_KEY is not set or invalid in OmoiBaseSettings`

**Root Cause:**
Missing or incorrect environment variable in `backend/.env`.

**Fix Procedure:**
1. Verify the key in `backend/.env`:
   ```bash
   grep DAYTONA_API_KEY backend/.env
   ```
2. If missing, retrieve a new key from the Daytona console and update the file.
3. Restart the backend services:
   ```bash
   just dev-backend
   ```

## 3. Worker Connectivity Issues

### Symptom: `ConnectionError` During Task Dispatch
The worker is running, but cannot send commands to the sandbox.

**Actual Error Pattern:**
`ConnectionError: Failed to connect to sandbox agent at 10.0.x.x:4000`

**Root Cause:**
- **Firewall Rules**: Port 4000 (Agent SDK) is blocked.
- **Agent Crash**: The `omoios-agent` process inside the sandbox exited unexpectedly.

**Diagnostic Commands:**
```bash
# Test connectivity to the sandbox IP
ping <sandbox-ip>

# Check if port 4000 is listening inside the sandbox (if reachable via SSH)
ssh daytona@<sandbox-ip> "ss -lntp | grep 4000"
```

## 4. Resource Limit Violations

OmoiOS enforces strict resource limits for sandboxes to prevent "noisy neighbor" issues.

**Default Limits:**
- **CPU**: 2.0 Cores
- **Memory**: 4GB RAM
- **Storage**: 10GB Root Disk

### Symptom: `OOMKill` or Task Termination
The agent process disappears during a large build or data processing task.

**Actual Error Pattern (Daytona Logs):**
`container_oom_killer: Memory limit reached for sandbox-uuid-456`

**Fix Procedure:**
1. Optimize the task to use less memory.
2. If the task is legitimately resource-intensive, increase the limit in `backend/config/base.yaml`:
   ```yaml
   daytona:
     resource_profiles:
       default:
         cpu_limit: 4.0
         memory_limit_gb: 8
   ```
3. Note: Changes require a restart of the `OrchestratorWorker`.

## 5. Environment Synchronization Failures

### Symptom: Missing Dependencies in Sandbox
Code fails with `ModuleNotFoundError` despite being in `requirements.txt`.

**Root Cause:**
The `ClaudeSandboxWorker` failed to execute the `pre_start` sync phase.

**Fix Procedure:**
1. Inspect the task execution log in the OmoiOS UI for `SYNC_FAILURE`.
2. Manual Sync Trigger (Emergency):
   ```bash
   # From inside the sandbox
   pip install -r requirements.txt
   ```
3. Check for internet access within the sandbox:
   ```bash
   ssh daytona@<sandbox-ip> "curl -I https://pypi.org"
   ```

## 6. Prevention Strategies

- **Cleanup Cron**: Ensure the OmoiOS cleanup task is running to remove orphaned sandboxes:
  ```bash
  # Check worker logs for cleanup activity
  grep "Cleaning up orphaned sandboxes" backend/logs/orchestrator.log
  ```
- **Pre-pulled Images**: Ensure the base sandbox image is pre-pulled on the Daytona host:
  ```bash
  docker pull omoios/sandbox-base:latest
  ```
- **Monitoring**: Set up Prometheus alerts for Daytona resource utilization.

## 7. Escalation Checklist

If the issue persists:
1. Provide the output of `just check-env`.
2. Attach the last 100 lines of `backend/logs/daytona.log`.
3. Provide the Sandbox ID and Task ID from the UI.
4. Verify if `daytona server` can be reached via `curl localhost:3001/health`.

---
# Troubleshooting WebSocket Events

This guide addresses real-time communication issues, event broadcasting failures, and WebSocket connection drops in the OmoiOS platform.

## 1. OmoiOS Event Architecture

Events flow through the following path:
1. **Producer**: A Service or Worker publishes to the `EventBus`.
2. **Broker**: Redis Pub/Sub receives and broadcasts the message.
3. **Consumer**: The `events.py` route (FastAPI) listens to Redis and pushes to the client via WebSocket.

## 2. Connection Failures

### Symptom: Immediate WebSocket Close (Code 4401)
The browser attempts to connect but is disconnected instantly with status code 4401.

**Actual Error Pattern:**
`WebSocket disconnected: code=4401 (Unauthorized)`

**Root Cause:**
Invalid or expired JWT passed in the connection URL or headers.

**Fix Procedure:**
1. Check the frontend console for "Auth token expired" messages.
2. Force a token refresh by navigating to `/auth/refresh`.
3. Ensure the backend has `AUTH_JWT_SECRET_KEY` correctly configured.

### Symptom: `ERR_CONNECTION_REFUSED` on Port 18000
The frontend cannot establish a connection to `ws://localhost:18000/api/v1/events/stream`.

**Fix Procedure:**
1. Verify the Backend API is running:
   ```bash
   ps aux | grep "uvicorn omoi_os.api.main:app"
   ```
2. Check for port conflicts:
   ```bash
   lsof -i :18000
   ```
3. Ensure the `WS_URL` in `frontend/.env.local` matches the actual backend host and port.

## 3. Event Broadcasting Issues

### Symptom: Events Missing in UI
The backend claims a task is "completed," but the UI never updates.

**Actual Error Pattern (Backend Logs):**
`RedisError: Connection lost while publishing to 'omoios_events'`

**Root Cause:**
The Redis server (Port 16379) is down or unreachable by the API service.

**Diagnostic Commands:**
```bash
# Test Redis connectivity
redis-cli -p 16379 ping

# Monitor live events
redis-cli -p 16379 psubscribe "omoios_events:*"
```

**Fix Procedure:**
1. Restart the Redis container:
   ```bash
   docker-compose restart redis
   ```
2. Check the `REDIS_URL` in `backend/.env`.

### Symptom: Delayed Event Delivery
Events appear in the UI several seconds after they actually occurred.

**Root Cause:**
- **High CPU Load**: The EventBus is throttled.
- **Slow Subscribers**: A single slow WebSocket client is blocking the broadcast loop (if using sequential broadcasting).

**Fix Procedure:**
1. Check system load: `htop` or `top`.
2. Inspect `backend/omoi_os/services/event_bus.py` for queue buildup.
3. Optimize the event payload size. Avoid sending large JSON blobs (e.g., full source code) over WebSockets.

## 4. Scaling and Load Balancing

### Symptom: "Sticky Session" Failures
In multi-node deployments, users only receive events triggered by actions on their specific server.

**Root Cause:**
The frontend is connecting to Server A, but the event producer is running on Server B.

**Fix Procedure:**
1. Ensure all backend nodes share the same Redis instance for Pub/Sub.
2. Configure your load balancer (e.g., Nginx) for `ip_hash` or session persistence.
3. Verify Nginx WebSocket headers:
   ```nginx
   proxy_set_header Upgrade $http_upgrade;
   proxy_set_header Connection "upgrade";
   ```

## 5. Client-Side Debugging

### Symptom: `useEvents` Hook Errors
The React hook throws "Failed to fetch event stream."

**Diagnostic Steps:**
1. Open Chrome DevTools → Network Tab → WS.
2. Select the `stream` connection.
3. Check the "Messages" sub-tab for raw JSON data.
4. Verify the `domain` and `action` fields in the messages.

## 6. Common Error Codes

| Code | Meaning | Resolution |
|------|---------|------------|
| 1000 | Normal Closure | No action needed. |
| 1006 | Abnormal Closure | Check for backend crashes or proxy timeouts. |
| 4401 | Unauthorized | Refresh your JWT. |
| 4403 | Forbidden | User lacks permission for this event scope. |
| 4429 | Rate Limited | Reduce the frequency of client-side requests. |

## 7. Prevention and Monitoring

- **Keepalive Pings**: The OmoiOS backend sends a `ping` every 30 seconds. If the client misses 3 consecutive pings, it should reconnect.
- **Heartbeat Logs**: Enable debug logging for the event stream:
  ```bash
  export LOG_LEVEL=DEBUG
  just dev-backend
  ```
- **Circuit Breaker**: Implement a backoff strategy in the `useEvents.ts` hook for reconnections.

---
# Troubleshooting Auth & JWT Issues

This guide provides deep-dive troubleshooting for the OmoiOS authentication system, covering JWT validation, OAuth flows, and session management.

## 1. Authentication Flow Overview

1. **Identity Provider**: Google/GitHub (OAuth) or Username/Password.
2. **JWT Generation**: `backend/omoi_os/services/auth.py` issues an `access_token` and `refresh_token`.
3. **Storage**: Access tokens are kept in-memory (frontend), refresh tokens are stored in HttpOnly cookies.
4. **Validation**: API routes use `Depends(get_current_user)` to verify tokens against `AUTH_JWT_SECRET_KEY`.

## 2. JWT Validation Failures

### Symptom: `401 Unauthorized` on Valid Login
The user is logged in, but all API calls return 401.

**Actual Error Pattern:**
`JWTError: Signature verification failed`

**Root Cause:**
The `AUTH_JWT_SECRET_KEY` used to sign the token does not match the key on the current backend instance. This frequently happens after a container restart if the key was not persisted in `.env`.

**Fix Procedure:**
1. Check `backend/.env` for `AUTH_JWT_SECRET_KEY`.
2. If missing, generate one:
   ```bash
   openssl rand -hex 32 >> backend/.env
   ```
3. Restart all backend services.
4. **Note**: This will invalidate all existing user sessions.

### Symptom: `401 Unauthorized: Token Expired`
User is forced to relogin every 15 minutes.

**Root Cause:**
- Access token expiry is too short.
- Refresh token rotation is failing.

**Fix Procedure:**
1. Check expiry settings in `backend/config/base.yaml`:
   ```yaml
   auth:
     access_token_expire_minutes: 60
     refresh_token_expire_days: 7
   ```
2. Inspect the "Set-Cookie" header in the `/auth/login` response to ensure `refresh_token` is being sent.

## 3. OAuth Flow Issues

### Symptom: Redirect URI Mismatch
After selecting a Google/GitHub account, the provider shows a "redirect_uri_mismatch" error.

**Fix Procedure:**
1. Verify the callback URL in your provider console (e.g., GitHub Developer Settings).
2. It must EXACTLY match: `http://localhost:18000/api/v1/auth/callback/github` (adjust host/port for prod).
3. Ensure `BACKEND_URL` is correctly set in `backend/.env`.

### Symptom: Stuck on `auth/callback` Page
The UI shows a loading spinner forever after OAuth.

**Actual Error Pattern (Browser Console):**
`Failed to fetch: /api/v1/auth/exchange-token`

**Root Cause:**
The backend is unable to reach the OAuth provider's API to exchange the code for a token (e.g., GitHub is down or DNS issues in the container).

**Diagnostic Commands:**
```bash
# Test if the backend can reach GitHub
docker exec omoios-backend curl -I https://github.com/login/oauth/access_token
```

## 4. Account Lockouts and Security

### Symptom: `403 Forbidden: Account Locked`
A user cannot log in despite having the correct password.

**Actual Error Pattern:**
`AuthError: Maximum login attempts exceeded for user: user@example.com`

**Root Cause:**
OmoiOS locks accounts after 5 failed attempts within 10 minutes to prevent brute-force attacks.

**Fix Procedure:**
1. Wait 10 minutes for the automatic cooldown.
2. Manual Unlock (Admin):
   ```bash
   # Using the OmoiOS CLI
   just unlock-user user@example.com
   ```

## 5. Cross-Origin (CORS) Issues

### Symptom: `Preflight Request Failed`
Browser blocks requests from `localhost:3000` to `localhost:18000`.

**Root Cause:**
Frontend origin is not in the backend's allowed list.

**Fix Procedure:**
1. Update `backend/config/base.yaml`:
   ```yaml
   api:
     cors_origins:
       - "http://localhost:3000"
       - "https://omoios.dev"
   ```
2. Restart the API service.

## 6. Token Rotation and Logout

### Symptom: "Zombie" Sessions
User clicks logout, but can still access protected routes.

**Root Cause:**
The access token is still valid and stored in the browser's local state or cache.

**Fix Procedure:**
1. Ensure `logout()` in the frontend clears the React Query cache and local state.
2. Verify the backend blacklists the token in Redis if `token_revocation` is enabled.
3. Check Redis for blacklisted tokens:
   ```bash
   redis-cli -p 16379 keys "blacklist:*"
   ```

## 7. Prevention Strategies

- **Use Secure Cookies**: In production, ensure `AUTH_COOKIE_SECURE=true`.
- **Key Rotation**: Rotate your `AUTH_JWT_SECRET_KEY` every 90 days.
- **Audit Logs**: Monitor `backend/logs/auth.log` for suspicious patterns.
- **Environment Parity**: Ensure `NEXT_PUBLIC_API_URL` is correctly set for all environments.

---
# Troubleshooting Docker Deployment

This guide covers common issues when deploying OmoiOS using Docker and Docker Compose.

## 1. Container Status Overview

**Core Containers:**
- `omoios-backend`: FastAPI Service (Port 18000)
- `omoios-frontend`: Next.js Service (Port 3000)
- `postgres`: Database (Port 15432)
- `redis`: Event Broker (Port 16379)
- `daytona`: Sandbox Orchestrator

## 2. Startup Failures

### Symptom: `omoios-backend` Exits with Status 1
The backend container keeps restarting.

**Actual Error Pattern:**
`ConnectionRefusedError: [Errno 111] Connect call failed ('127.0.0.1', 15432)`

**Root Cause:**
The backend is trying to connect to the database on `localhost` instead of the Docker service name `postgres`.

**Fix Procedure:**
1. Verify the `DATABASE_URL` in `backend/.env`:
   - **Correct**: `postgresql+asyncpg://user:pass@postgres:5432/neondb`
   - **Incorrect**: `...localhost:15432...`
2. Ensure the container is part of the same network in `docker-compose.yml`.

### Symptom: `exec format error`
Container fails to start on Apple Silicon (M1/M2/M3) or ARM servers.

**Root Cause:**
Image was built for `linux/amd64` but is running on `linux/arm64`.

**Fix Procedure:**
1. Rebuild with the correct platform:
   ```bash
   just docker-build --platform linux/arm64
   ```
2. Or use the `--build-arg` in Docker Compose.

## 3. Network and Port Issues

### Symptom: Port Already Allocated
`Error: Bind for 0.0.0.0:18000 failed: port is already allocated`

**Fix Procedure:**
1. Identify the process using the port:
   ```bash
   lsof -i :18000
   ```
2. Kill the conflicting process or change the mapping in `docker-compose.yml`:
   ```yaml
   services:
     backend:
       ports:
         - "18001:18000"
   ```

### Symptom: Inter-Container Communication Failure
The backend cannot reach Redis at `redis:6379`.

**Diagnostic Commands:**
```bash
# Check if the backend can resolve the redis hostname
docker exec omoios-backend getent hosts redis

# Test connection from backend to redis
docker exec omoios-backend nc -zv redis 6379
```

## 4. Volume and Permission Issues

### Symptom: Database `Permission Denied`
The `postgres` container fails to initialize the data directory.

**Root Cause:**
The host directory mounted to `/var/lib/postgresql/data` has incorrect ownership.

**Fix Procedure:**
1. Reset permissions on the host:
   ```bash
   sudo chown -R 999:999 ./docker-data/postgres
   ```
2. Restart the container.

### Symptom: Changes to `base.yaml` Not Reflecting
The container is still using old configuration settings.

**Fix Procedure:**
1. Ensure the volume mount is correct in `docker-compose.yml`:
   ```yaml
   volumes:
     - ./backend/config:/app/config:ro
   ```
2. Force a container recreation:
   ```bash
   docker-compose up -d --force-recreate backend
   ```

## 5. Performance and Resource Constraints

### Symptom: Container Sluggishness or Random Crashes
**Actual Error Pattern (Docker Events):**
`die (exitCode=137)`

**Root Cause:**
Exit code 137 indicates the container was OOM (Out Of Memory) killed by the Docker daemon.

**Fix Procedure:**
1. Increase the memory limit in `docker-compose.yml`:
   ```yaml
   deploy:
     resources:
       limits:
         memory: 2G
   ```
2. Monitor utilization: `docker stats`.

## 6. Logs and Diagnostics

**View all logs:**
```bash
docker-compose logs -f
```

**View backend logs specifically:**
```bash
docker-compose logs -f backend
```

**Inspect container configuration:**
```bash
docker inspect omoios-backend
```

## 7. Prevention Strategies

- **Health Checks**: Always include health checks in `docker-compose.yml` to ensure dependencies are ready before the backend starts.
- **Immutable Images**: Tag your images with version numbers (e.g., `omoios:1.2.3`) instead of using `latest`.
- **Environment Overrides**: Use a dedicated `docker-compose.override.yml` for local development tweaks.

---
# Troubleshooting Performance Optimization

This guide identifies and resolves performance bottlenecks across the OmoiOS stack, from database queries to frontend rendering.

## 1. Backend Performance (FastAPI)

### Symptom: High Response Latency on `/api/v1/specs`
API requests take >500ms even with low traffic.

**Actual Error Pattern (Sentry/Slow Logs):**
`SlowQuery: SELECT * FROM specs ... (Duration: 420ms)`

**Root Cause:**
Missing indexes on frequently filtered columns like `project_id` or `status`.

**Fix Procedure:**
1. Identify the slow query using `just sql-shell`:
   ```sql
   EXPLAIN ANALYZE SELECT * FROM specs WHERE status = 'pending';
   ```
2. Add the missing index via an Alembic migration:
   ```python
   op.create_index('ix_specs_status', 'specs', ['status'])
   ```
3. Verify the improvement.

### Symptom: Synchronous I/O Blocking
The API becomes unresponsive when multiple users are running LLM tasks.

**Root Cause:**
Calling `requests` or other blocking libraries instead of `httpx` (async) within a route.

**Fix Procedure:**
1. Audit `omoi_os/services/` for synchronous network calls.
2. Replace with `httpx.AsyncClient`.
3. Ensure no `time.sleep()` calls exist; use `await asyncio.sleep()`.

## 2. LLM and Worker Performance

### Symptom: Orchestrator Throughput is Low
The orchestrator takes several seconds to pick up new tasks from the queue.

**Root Cause:**
The `OrchestratorWorker` polling interval is too high or the Redis queue is congested.

**Fix Procedure:**
1. Adjust `poll_interval` in `backend/config/base.yaml`.
2. Increase the number of worker instances for the `high_priority` queue.
3. Check Redis memory usage: `redis-cli -p 16379 info memory`.

## 3. Frontend Performance (Next.js)

### Symptom: Large Bundle Sizes (TBT > 300ms)
The initial page load is slow, especially on mobile.

**Diagnostic Commands:**
```bash
# Analyze the build bundle
cd frontend && pnpm build --profile
```

**Fix Procedure:**
1. Implement dynamic imports (lazy loading) for large components like the Code Editor:
   ```tsx
   const CodeEditor = dynamic(() => import('./CodeEditor'), { ssr: false });
   ```
2. Remove unused icons or UI primitives.
3. Use the `next/image` component for all assets.

### Symptom: Excessive Re-renders in the Command Panel
Typing in the command box feels laggy.

**Root Cause:**
Parent components are re-rendering on every keystroke because state is not properly localized or memoized.

**Fix Procedure:**
1. Use `React.memo` for heavy sub-components.
2. Debounce the state update for the search query (e.g., 200ms delay).
3. Move Keystroke-level state into a local `useRef` or a specialized input component.

## 4. Database Optimization

### Symptom: Connection Pool Exhaustion
Backend logs show `QueuePool limit of size 10 overflow 10 reached`.

**Root Cause:**
- Leaking database sessions (sessions not being closed).
- Pool size is too small for the concurrency level.

**Fix Procedure:**
1. Increase pool size in `backend/config/base.yaml`:
   ```yaml
   database:
     pool_size: 20
     max_overflow: 10
   ```
2. Ensure every service uses the `get_session` context manager correctly.

## 5. Caching Strategy

### Symptom: Redundant LLM Calls
The system generates the same requirement analysis multiple times for identical prompts.

**Fix Procedure:**
1. Implement semantic caching in `omoi_os/services/llm_service.py`.
2. Use Redis to cache the results of expensive computations:
   ```python
   await cache.set(f"requirement:{prompt_hash}", result, expire=3600)
   ```

## 6. Monitoring and Profiling

- **Backend Profiling**: Use `py-spy` to identify CPU-bound functions in the running worker.
- **Database Profiling**: Enable `pg_stat_statements` on Postgres.
- **Frontend Profiling**: Use Chrome DevTools → Performance Tab.
- **Alerting**: Configure Sentry to alert on any transaction taking >2 seconds.

## 7. Performance Benchmarks (OmoiOS Baseline)

| Operation | Target | Critical Threshold |
|-----------|--------|-------------------|
| API Health Check | < 10ms | > 50ms |
| List Projects (100) | < 50ms | > 200ms |
| WebSocket Event Latency| < 100ms | > 500ms |
| Sandbox Spawning | < 30s | > 120s |
| LLM Analysis (Start) | < 2s | > 10s |

---
