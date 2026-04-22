# WebSocket & Real-Time Events Troubleshooting

**Status**: Active | **Last Updated**: 2026-04-22 | **Applies To**: OmoiOS v1.0+

**Source Files**:
- `backend/omoi_os/api/routes/events.py` — WebSocket endpoint and connection management
- `backend/omoi_os/services/event_bus.py` — Redis pub/sub event bus
- `frontend/hooks/useWebSocket.ts` — Client-side WebSocket hook
- `frontend/providers/` — WebSocket context providers

**Related Documentation**:
- **Architecture: Real-Time Events**
- [Design: Real-Time Events Architecture](../design/frontend/realtime_events_architecture.md)
- [Redis Issues](redis-issues.md)

---

## Overview

OmoiOS uses WebSocket connections for real-time event streaming between the backend and frontend. The system is built on:

- **FastAPI WebSocket** — server-side connection handling at `/ws/events`
- **Redis pub/sub** — event bus for broadcasting across backend services
- **JWT authentication** — token passed as `?token=<jwt>` query parameter
- **Event filtering** — clients subscribe to specific event types or entity IDs

### Connection Architecture

```
Frontend (React)
    ↓ WebSocket ws://localhost:18000/ws/events?token=<jwt>
FastAPI events.py router
    ↓ subscribes to
Redis pub/sub channels
    ↑ publishes to
Backend services (OrchestratorWorker, SandboxSpawner, etc.)
```

### Event Types

| Event Type | Description | Payload |
|------------|-------------|---------|
| `spec.phase_changed` | Spec moved to new phase | `{spec_id, from_phase, to_phase}` |
| `task.status_changed` | Task status update | `{task_id, status, agent_id}` |
| `sandbox.started` | Sandbox provisioned | `{sandbox_id, spec_id}` |
| `sandbox.completed` | Sandbox finished | `{sandbox_id, exit_code}` |
| `agent.progress` | Agent progress update | `{agent_id, message, percentage}` |
| `system.health` | System health ping | `{status, timestamp}` |

---

## Common Error Codes

| Code | Meaning | Cause |
|------|---------|-------|
| `4401` | Unauthorized | Missing or invalid JWT token |
| `4403` | Forbidden | Token valid but insufficient permissions |
| `4429` | Rate limited | Too many connection attempts |
| `1001` | Going away | Server restart or graceful shutdown |
| `1006` | Abnormal closure | Network interruption, no close frame sent |
| `1011` | Internal error | Unhandled exception in server handler |
| `1012` | Service restart | Backend redeploying |

---

## Issue 1: Connection Refused / Cannot Connect

### Symptoms
```
WebSocket connection to 'ws://localhost:18000/ws/events' failed
Error: connect ECONNREFUSED 127.0.0.1:18000
```

### Root Cause Analysis

The backend API is not running or is not listening on port 18000.

### Diagnosis

```bash
# Check if backend is running
just status

# Check port 18000 specifically
lsof -i :18000

# Check backend logs
just backend-logs
# or
tail -f backend/logs/api.log
```

### Recovery Procedures

```bash
# Start the backend
just backend-api

# Or start full stack
just dev-all

# If port is occupied by another process
just kill-port 18000
just backend-api
```

---

## Issue 2: Authentication Failure (Code 4401)

### Symptoms
```json
{"error": "Authentication required. Pass ?token=<jwt>"}
{"error": "Invalid or expired token"}
```
Connection closes immediately after opening.

### Root Cause Analysis

The WebSocket endpoint at `events.py` calls `_authenticate_websocket()` which verifies the JWT access token. Access tokens expire after 15 minutes. If the frontend sends an expired token, the connection is rejected with code 4401.

### Diagnosis

```bash
# Decode the JWT to check expiry (replace TOKEN with actual token)
python3 -c "
import base64, json
token = 'TOKEN'
payload = token.split('.')[1]
# Add padding
payload += '=' * (4 - len(payload) % 4)
print(json.dumps(json.loads(base64.b64decode(payload)), indent=2))
"
```

Check the `exp` field — if it's in the past, the token is expired.

### Recovery Procedures

**Frontend fix** — ensure the WebSocket hook refreshes the token before connecting:

```typescript
// hooks/useWebSocket.ts — correct pattern
const { data: session } = useSession();

useEffect(() => {
  if (!session?.accessToken) return;

  const ws = new WebSocket(
    `${WS_BASE_URL}/ws/events?token=${session.accessToken}`
  );

  ws.onclose = (event) => {
    if (event.code === 4401) {
      // Token expired — trigger refresh then reconnect
      refreshToken().then(() => reconnect());
    }
  };
}, [session?.accessToken]);
```

**Backend diagnosis** — check JWT secret configuration:

```bash
# Verify JWT_SECRET_KEY is set
grep JWT_SECRET_KEY backend/.env

# Check token expiry settings in config
grep -A5 "access_token" backend/config/base.yaml
```

---

## Issue 3: Connection Drops Repeatedly

### Symptoms
- WebSocket connects, then disconnects after 30–60 seconds
- Frontend shows "Reconnecting..." in a loop
- Browser console: `WebSocket is closed before the connection is established`

### Root Cause Analysis

Several causes:

1. **Redis pub/sub disconnection** — `EventBusService` loses its Redis connection, causing the WebSocket handler to exit
2. **Nginx/proxy timeout** — Load balancer closes idle WebSocket connections (default 60s)
3. **Memory pressure** — Backend OOM kills the connection handler
4. **Unhandled exception** — Bug in event handler causes silent close

### Diagnosis

```bash
# Check Redis connectivity
redis-cli -p 16379 ping
# Expected: PONG

# Check Redis pub/sub channels
redis-cli -p 16379 pubsub channels "*"

# Check backend error logs for WebSocket exceptions
grep -i "websocket\|disconnect\|exception" backend/logs/api.log | tail -50

# Check memory usage
just status
ps aux | grep uvicorn | awk '{print $6}' # RSS in KB
```

### Recovery Procedures

**Increase proxy timeout** (if behind nginx):

```nginx
# nginx.conf
location /ws/ {
    proxy_pass http://backend:18000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 3600s;   # 1 hour
    proxy_send_timeout 3600s;
}
```

**Add heartbeat ping** to keep connection alive:

```python
# events.py — add ping loop
async def _ping_loop(websocket: WebSocket):
    while True:
        await asyncio.sleep(30)
        try:
            await websocket.send_json({"type": "ping", "timestamp": time.time()})
        except Exception:
            break
```

**Restart Redis** if pub/sub is broken:

```bash
just docker-up
# Wait for Redis to be ready
redis-cli -p 16379 ping
```

---

## Issue 4: Events Not Received / Missing Updates

### Symptoms
- WebSocket connects successfully (no errors)
- UI does not update when backend state changes
- Events visible in Redis but not forwarded to client

### Root Cause Analysis

1. **Channel subscription mismatch** — client subscribed to wrong channel name
2. **Event filtering too strict** — backend filters out events the client expects
3. **Redis message serialization error** — event payload fails JSON parsing
4. **Slow consumer** — client processing backlog causes dropped messages

### Diagnosis

```bash
# Monitor Redis pub/sub in real time
redis-cli -p 16379 subscribe "omoi:events:*"

# Check what channels are active
redis-cli -p 16379 pubsub channels "omoi:*"

# Publish a test event manually
redis-cli -p 16379 publish "omoi:events:system" '{"type":"test","data":{}}'

# Check event_bus.py for channel naming
grep -n "publish\|channel\|subscribe" backend/omoi_os/services/event_bus.py | head -30
```

### Recovery Procedures

**Verify channel names match** between publisher and subscriber:

```python
# event_bus.py — check channel format
CHANNEL_PREFIX = "omoi:events"

def get_channel(event_type: str, entity_id: str | None = None) -> str:
    if entity_id:
        return f"{CHANNEL_PREFIX}:{event_type}:{entity_id}"
    return f"{CHANNEL_PREFIX}:{event_type}"
```

**Check frontend subscription**:

```typescript
// Ensure the frontend subscribes to the correct channel pattern
const ws = new WebSocket(
  `${WS_BASE_URL}/ws/events?token=${token}&channels=spec.phase_changed,task.status_changed`
);
```

**Force a test event** to verify the pipeline:

```bash
# From Python shell
python3 -c "
import asyncio
from omoi_os.services.event_bus import EventBusService

async def test():
    bus = EventBusService()
    await bus.publish('system.test', {'message': 'hello'})

asyncio.run(test())
"
```

---

## Issue 5: Event Deduplication / Duplicate Events

### Symptoms
- UI shows the same notification twice
- State updates applied multiple times
- React Query cache invalidated in a loop

### Root Cause Analysis

1. **Multiple WebSocket connections** — component mounts twice (React StrictMode in dev)
2. **Reconnection without deduplication** — client reconnects and replays buffered events
3. **Multiple Redis subscribers** — multiple backend instances each forwarding the same event

### Diagnosis

```bash
# Check how many WebSocket connections are open
ss -tnp | grep 18000 | grep ESTABLISHED | wc -l

# Check for multiple backend instances
ps aux | grep uvicorn | grep -v grep
```

### Recovery Procedures

**Frontend deduplication** — track processed event IDs:

```typescript
const processedEventIds = useRef(new Set<string>());

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.id && processedEventIds.current.has(data.id)) {
    return; // Skip duplicate
  }
  if (data.id) {
    processedEventIds.current.add(data.id);
    // Prune old IDs to prevent memory leak
    if (processedEventIds.current.size > 1000) {
      const arr = [...processedEventIds.current];
      processedEventIds.current = new Set(arr.slice(-500));
    }
  }
  handleEvent(data);
};
```

**React StrictMode** — use a connection ref to prevent double-mounting:

```typescript
const wsRef = useRef<WebSocket | null>(null);

useEffect(() => {
  if (wsRef.current?.readyState === WebSocket.OPEN) return;

  wsRef.current = new WebSocket(url);
  // ...

  return () => {
    wsRef.current?.close();
  };
}, [url]);
```

---

## Issue 6: High Latency / Delayed Events

### Symptoms
- Events arrive 5–30 seconds after the action
- UI feels "laggy" compared to backend state
- Redis queue depth growing

### Root Cause Analysis

1. **Redis backpressure** — event bus queue is full
2. **Slow WebSocket handler** — synchronous operations blocking the async loop
3. **Network latency** — high RTT between client and server

### Diagnosis

```bash
# Check Redis memory and queue depth
redis-cli -p 16379 info memory | grep used_memory_human
redis-cli -p 16379 info stats | grep total_commands_processed

# Check event processing time
grep "event_bus\|publish\|subscribe" backend/logs/api.log | grep -i "slow\|timeout\|warn"

# Measure WebSocket round-trip time from browser
# In browser console:
# ws.send(JSON.stringify({type: 'ping', ts: Date.now()}))
# Then check the pong response timestamp
```

### Recovery Procedures

```bash
# Flush Redis if queue is backed up (WARNING: loses pending events)
redis-cli -p 16379 flushdb

# Restart event bus
just docker-up

# Increase Redis maxmemory if needed
redis-cli -p 16379 config set maxmemory 512mb
redis-cli -p 16379 config set maxmemory-policy allkeys-lru
```

---

## Issue 7: WebSocket Not Supported (Proxy/Firewall)

### Symptoms
```
WebSocket connection failed: Error during WebSocket handshake: Unexpected response code: 400
```
Or falls back to polling with high CPU usage.

### Root Cause Analysis

A reverse proxy (nginx, Caddy, AWS ALB) is not configured to forward WebSocket upgrade headers.

### Diagnosis

```bash
# Test WebSocket upgrade manually
curl -i -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" \
  -H "Sec-WebSocket-Key: $(openssl rand -base64 16)" \
  http://localhost:18000/ws/events

# Expected: HTTP/1.1 101 Switching Protocols
```

### Recovery Procedures

**Nginx configuration**:

```nginx
location /ws/ {
    proxy_pass http://backend:18000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "Upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_cache_bypass $http_upgrade;
}
```

**AWS ALB** — enable WebSocket support in target group settings (it's on by default for ALB, but verify sticky sessions are disabled for WebSocket targets).

---

## Monitoring & Observability

### Key Metrics to Watch

```bash
# Active WebSocket connections
redis-cli -p 16379 info clients | grep connected_clients

# Event throughput
redis-cli -p 16379 info stats | grep total_commands_processed

# Backend WebSocket connection count (if instrumented)
curl http://localhost:18000/health | python3 -m json.tool
```

### Log Patterns

```bash
# Successful connection
grep "WebSocket connected\|accepted" backend/logs/api.log

# Authentication failures
grep "4401\|Authentication required\|Invalid.*token" backend/logs/api.log

# Disconnections
grep "WebSocketDisconnect\|disconnect\|closed" backend/logs/api.log

# Event publishing errors
grep "event_bus\|publish.*error\|Redis.*error" backend/logs/api.log
```

### Health Check Script

```bash
#!/bin/bash
# websocket-health-check.sh

echo "=== WebSocket Health Check ==="

# 1. Backend running?
if ! curl -sf http://localhost:18000/health > /dev/null; then
  echo "❌ Backend not responding"
  exit 1
fi
echo "✅ Backend responding"

# 2. Redis pub/sub working?
if ! redis-cli -p 16379 ping | grep -q PONG; then
  echo "❌ Redis not responding"
  exit 1
fi
echo "✅ Redis responding"

# 3. WebSocket upgrade working?
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" \
  -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
  http://localhost:18000/ws/events)

if [ "$RESPONSE" = "101" ]; then
  echo "✅ WebSocket upgrade working"
else
  echo "❌ WebSocket upgrade failed (HTTP $RESPONSE)"
  exit 1
fi

echo "=== All checks passed ==="
```

---

## Related Documentation

- [Redis Issues](redis-issues.md) — Redis connection and pub/sub problems
- [Auth & JWT Issues](auth-jwt-troubleshooting.md) — Token authentication problems
- **Architecture: Real-Time Events** — System design
- [Design: Real-Time Events Architecture](../design/frontend/realtime_events_architecture.md) — Frontend patterns
