# WebSocket Disconnections Troubleshooting Guide

**Status**: Active | **Last Updated**: 2025-04-22 | **Applies To**: OmoiOS v1.0+

**Source Files**:
- `backend/omoi_os/services/event_bus.py` - Event bus and Redis pub/sub
- `backend/omoi_os/api/routes/events.py` - WebSocket event streaming
- `frontend/lib/api/websocket.ts` - Frontend WebSocket client
- `frontend/providers/event-provider.tsx` - Event provider context

**Related Documentation**:
- [Architecture: Real-Time Events](../architecture/06-realtime-events.md)
- [Design: Event Bus](../design/services/event_bus.md)
- [Troubleshooting: WebSocket Events](websocket-events.md)

---

## Overview

OmoiOS uses WebSocket connections for real-time event streaming from backend to frontend. The WebSocket system is built on FastAPI's native WebSocket support with Redis Pub/Sub as the message broker. Disconnections can occur due to network issues, authentication failures, rate limiting, or client/server errors.

### WebSocket Architecture

```
┌─────────────┐      WebSocket       ┌─────────────┐      Redis Pub/Sub      ┌─────────────┐
│   Frontend  │◄────────────────────►│  FastAPI    │◄───────────────────────►│   Redis     │
│  (Browser)  │    /ws/events        │   Server    │    events.* pattern     │  (Port      │
│             │                      │             │                         │   16379)    │
└─────────────┘                      └─────────────┘                         └─────────────┘
       │                                    │
       │                                    │
       ▼                                    ▼
┌─────────────┐                      ┌─────────────┐
│  Event      │                      │  EventBus   │
│  Provider   │                      │  Service    │
│  (React)    │                      │  (Python)   │
└─────────────┘                      └─────────────┘
```

---

## Common Errors Table

| Error Message | Cause | Fix |
|--------------|-------|-----|
| `WebSocket connection closed` with code 1006 | Abnormal closure, network issue | Check network, implement reconnection |
| `Authentication required. Pass ?token=<jwt>` | Missing or invalid JWT token | Include valid token in query params |
| `Invalid or expired token` | Token expired or revoked | Refresh token and reconnect |
| `Service not ready, please retry` with code 1013 | Event bus not initialized | Wait and retry connection |
| `Redis connection failed, EventBus disabled` | Redis unavailable | Check Redis connectivity |
| `Error sending event to WebSocket client` | Client disconnected unexpectedly | Clean up disconnected clients |
| `Error in Redis listener` | Redis pub/sub error | Check Redis health, restart listener |
| `asyncio.TimeoutError` on receive | No ping/pong activity | Check keepalive settings |
| `Connection refused` | Wrong port or service down | Verify WebSocket endpoint URL |
| `429 Too Many Requests` | Rate limiting | Implement backoff, reduce connection frequency |

---

## Diagnostic Commands

### Check WebSocket Server Status

```bash
# Check if WebSocket endpoint is accessible
curl -i -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" \
  -H "Sec-WebSocket-Key: $(openssl rand -base64 16)" \
  http://localhost:18000/api/v1/ws/events?token=test

# Monitor WebSocket logs
tail -f backend/logs/api.log | grep -E "WebSocket|websocket|ws/"

# Check Redis connection for event bus
cd backend && uv run python -c "
from omoi_os.services.event_bus import get_event_bus
ebus = get_event_bus()
print(f'Event bus available: {ebus._available}')
print(f'Redis client: {ebus.redis_client}')
"
```

### Monitor WebSocket Connections

```bash
# Watch for connection/disconnection events
tail -f backend/logs/api.log | grep -E "connect|disconnect|WebSocket"

# Check active connections count
cd backend && uv run python -c "
from omoi_os.api.routes.events import get_ws_manager
ws_manager = get_ws_manager()
print(f'Active connections: {len(ws_manager.active_connections)}')
"

# Monitor Redis pub/sub
cd backend && uv run python -c "
import redis
r = redis.from_url('redis://localhost:16379')
print(f'Redis ping: {r.ping()}')
print(f'Pubsub channels: {r.pubsub_channels()}')
"
```

### Test Event Publishing

```bash
# Publish a test event via Redis
redis-cli -h localhost -p 16379 publish 'events.TEST_EVENT' '{"event_type": "TEST_EVENT", "entity_type": "test", "entity_id": "123", "payload": {}}'

# Check if event bus receives it
tail -f backend/logs/api.log | grep "TEST_EVENT"
```

---

## Symptom 1: WebSocket Connection Drops

**Error Message**: `WebSocketDisconnect` or connection closed with code 1006 (abnormal closure)

**Root Cause**: Network instability, client closed connection, server restart, or idle timeout.

### Diagnostic Steps

1. **Check Connection Close Code**:
   ```python
   # WebSocket close codes
   # 1000 - Normal closure
   # 1001 - Going away (server shutdown)
   # 1006 - Abnormal closure (network issue)
   # 1011 - Server error
   # 1013 - Try again later (service unavailable)
   ```

2. **Monitor Server Logs**:
   ```bash
   # Look for disconnect reasons
   tail -f backend/logs/api.log | grep -E "WebSocketDisconnect|disconnect|connection"
   ```

3. **Check Network Connectivity**:
   ```bash
   # Test WebSocket endpoint
   wscat -c "ws://localhost:18000/api/v1/ws/events?token=$JWT_TOKEN"
   
   # Check for packet loss
   ping -c 10 localhost
   ```

### Fix Procedure

1. **Implement Reconnection Logic** (Frontend):
   ```typescript
   // frontend/lib/api/websocket.ts
   class WebSocketClient {
     private reconnectAttempts = 0;
     private maxReconnectAttempts = 5;
     private reconnectDelay = 1000; // Start with 1s
     
     private handleDisconnect() {
       if (this.reconnectAttempts < this.maxReconnectAttempts) {
         setTimeout(() => {
           this.reconnectAttempts++;
           this.connect();
         }, this.reconnectDelay * Math.pow(2, this.reconnectAttempts)); // Exponential backoff
       }
     }
   }
   ```

2. **Configure Keepalive** (Backend):
   ```python
   # In events.py, the WebSocket already sends pings every 30s
   # Adjust timeout if needed:
   data = await asyncio.wait_for(
       websocket.receive_text(), 
       timeout=30.0  # Increase if clients are slow
   )
   ```

3. **Handle 1013 Service Unavailable**:
   ```typescript
   // Retry with backoff when service not ready
   if (event.code === 1013) {
     setTimeout(() => this.connect(), 5000);
   }
   ```

---

## Symptom 2: Reconnection Loops

**Error Message**: Continuous connect/disconnect cycles in logs

**Root Cause**: Authentication failing on reconnect, or rapid reconnection triggering rate limits.

### Diagnostic Steps

1. **Check Authentication on Reconnect**:
   ```bash
   # Look for auth failures during reconnect
   tail -f backend/logs/api.log | grep -E "Authentication|token|4401"
   ```

2. **Monitor Reconnection Frequency**:
   ```bash
   # Count connections per minute
   tail -1000 backend/logs/api.log | grep "WebSocket connected" | wc -l
   ```

3. **Check Token Expiry**:
   ```python
   # Verify token hasn't expired
   from omoi_os.services.auth_service import AuthService
   auth = AuthService(...)
   token_data = auth.verify_token(token, token_type="access")
   print(f"Token valid: {token_data is not None}")
   ```

### Fix Procedure

1. **Refresh Token Before Reconnect**:
   ```typescript
   // frontend/lib/api/websocket.ts
   async reconnect() {
     // Refresh token if needed
     const token = await this.getValidToken();
     this.ws = new WebSocket(`${WS_URL}?token=${token}`);
   }
   ```

2. **Implement Exponential Backoff**:
   ```typescript
   private getReconnectDelay(): number {
     const delay = Math.min(
       1000 * Math.pow(2, this.reconnectAttempts),
       30000 // Max 30s
     );
     return delay + Math.random() * 1000; // Add jitter
   }
   ```

3. **Limit Reconnection Attempts**:
   ```typescript
   if (this.reconnectAttempts >= this.maxReconnectAttempts) {
     this.emit('error', new Error('Max reconnection attempts reached'));
     return;
   }
   ```

---

## Symptom 3: Event Loss During Disconnect

**Error Message**: Missing events on reconnection, or `events_received` count doesn't match expected

**Root Cause**: Events published while client is disconnected are not queued for replay.

### Diagnostic Steps

1. **Check Event Sequence**:
   ```bash
   # Monitor event publishing
   tail -f backend/logs/api.log | grep "event_bus.publish"
   
   # Check if events are being dropped
   grep "Error sending event to WebSocket client" backend/logs/api.log
   ```

2. **Verify Client Subscription**:
   ```python
   # Check active filters for a connection
   ws_manager = get_ws_manager()
   for ws, filters in ws_manager.connection_filters.items():
       print(f"Filters: {filters}")
   ```

3. **Test Event Delivery**:
   ```bash
   # Publish test events while client reconnects
   for i in {1..10}; do
     redis-cli publish 'events.TEST' "{\"seq\": $i}"
     sleep 1
   done
   ```

### Fix Procedure

1. **Implement Event Replay** (Application Layer):
   ```typescript
   // On reconnect, fetch missed events
   async onReconnect() {
     const lastEventId = localStorage.getItem('lastEventId');
     const missedEvents = await fetchMissedEvents(lastEventId);
     missedEvents.forEach(event => this.handleEvent(event));
   }
   ```

2. **Use Persistent Queue for Critical Events**:
   ```python
   # For critical events, use a persistent queue
   # instead of just pub/sub
   from omoi_os.services.task_queue import get_task_queue
   tq = get_task_queue()
   tq.enqueue_notification(event)  # Persistent queue
   ```

3. **Client-Side Buffering**:
   ```typescript
   // Buffer events during reconnection
   private eventBuffer: SystemEvent[] = [];
   
   private handleEvent(event: SystemEvent) {
     if (this.state === 'connected') {
       this.processEvent(event);
     } else {
       this.eventBuffer.push(event);
     }
   }
   ```

---

## Symptom 4: Stale Connections

**Error Message**: `active_connections` count higher than actual connected clients

**Root Cause**: Disconnections not properly detected, leaving ghost connections in the manager.

### Diagnostic Steps

1. **Check Connection Count**:
   ```python
   from omoi_os.api.routes.events import get_ws_manager
   
   ws_manager = get_ws_manager()
   print(f"Active connections: {len(ws_manager.active_connections)}")
   print(f"Connection filters: {len(ws_manager.connection_filters)}")
   ```

2. **Monitor Disconnect Handling**:
   ```bash
   # Check if disconnect is being handled
   tail -f backend/logs/api.log | grep "disconnect"
   ```

3. **Test Connection Cleanup**:
   ```python
   # Simulate disconnect and check cleanup
   # Close a connection and verify it's removed from active_connections
   ```

### Fix Procedure

1. **Force Cleanup on Error**:
   ```python
   # In _broadcast_event, already handles this:
   disconnected = set()
   for websocket in self.active_connections:
       try:
           await websocket.send_json(...)
       except Exception:
           disconnected.add(websocket)
   
   # Clean up disconnected clients
   for ws in disconnected:
       self.disconnect(ws)
   ```

2. **Periodic Connection Pruning**:
   ```python
   # Add a periodic cleanup task
   async def prune_stale_connections():
       stale = []
       for ws in ws_manager.active_connections:
           if not ws.client_state.connected:
               stale.append(ws)
       for ws in stale:
           ws_manager.disconnect(ws)
   ```

3. **Manual Cleanup** (Emergency):
   ```python
   # Force close all connections
   ws_manager = get_ws_manager()
   await ws_manager.close_all()
   ```

---

## Symptom 5: Rate Limiting

**Error Message**: `429 Too Many Requests` or connection throttled

**Root Cause**: Too many connection attempts in a short time period.

### Diagnostic Steps

1. **Check Connection Rate**:
   ```bash
   # Count connections per second
   tail -f backend/logs/api.log | grep "WebSocket connected" | pv -l -i 1 > /dev/null
   ```

2. **Monitor Client Behavior**:
   ```bash
   # Check for rapid reconnect patterns
   grep "WebSocket" backend/logs/api.log | grep -E "connect|disconnect" | head -50
   ```

3. **Verify Rate Limit Configuration**:
   ```python
   # Check if rate limiting is configured
   from omoi_os.config import get_app_settings
   settings = get_app_settings()
   print(f"Rate limits: {settings.rate_limit}")
   ```

### Fix Procedure

1. **Implement Client-Side Throttling**:
   ```typescript
   private lastConnectAttempt = 0;
   private minConnectInterval = 5000; // 5 seconds
   
   connect() {
     const now = Date.now();
     if (now - this.lastConnectAttempt < this.minConnectInterval) {
       console.log('Throttling connection attempt');
       return;
     }
     this.lastConnectAttempt = now;
     // ... connect
   }
   ```

2. **Add Server-Side Rate Limiting**:
   ```python
   # In events.py, add rate limiting decorator
   from fastapi_limiter import WebSocketRateLimiter
   
   @router.websocket("/ws/events")
   @WebSocketRateLimiter(times=5, seconds=60)  # 5 connections per minute
   async def websocket_events(...):
       ...
   ```

3. **Use Connection Pooling**:
   ```typescript
   // Share WebSocket connection across components
   // instead of creating multiple connections
   export const sharedWS = new WebSocketClient();
   ```

---

## Symptom 6: Payload Size Limits

**Error Message**: `Message size exceeds limit` or connection drops on large events

**Root Cause**: WebSocket message size exceeds server or client limits.

### Diagnostic Steps

1. **Check Message Sizes**:
   ```python
   # Log event payload sizes
   import json
   event_size = len(json.dumps(event.model_dump()))
   if event_size > 10000:  # 10KB
       logger.warning(f"Large event: {event_size} bytes")
   ```

2. **Monitor for Large Payloads**:
   ```bash
   # Look for large events in logs
   tail -f backend/logs/api.log | grep "Large event"
   ```

3. **Test with Different Payload Sizes**:
   ```python
   # Publish test events of varying sizes
   for size in [100, 1000, 10000, 100000]:
       payload = "x" * size
       event_bus.publish(SystemEvent(..., payload={"data": payload}))
   ```

### Fix Procedure

1. **Chunk Large Events**:
   ```python
   # Split large payloads into chunks
   def publish_large_event(event: SystemEvent, chunk_size: int = 10000):
       payload_str = json.dumps(event.payload)
       if len(payload_str) <= chunk_size:
           event_bus.publish(event)
           return
       
       # Split into chunks
       chunks = [payload_str[i:i+chunk_size] for i in range(0, len(payload_str), chunk_size)]
       for i, chunk in enumerate(chunks):
           event_bus.publish(SystemEvent(
               event_type=f"{event.event_type}_chunk",
               entity_type=event.entity_type,
               entity_id=f"{event.entity_id}_{i}",
               payload={"chunk": chunk, "index": i, "total": len(chunks)}
           ))
   ```

2. **Compress Large Payloads**:
   ```python
   import gzip
   import base64
   
   def compress_payload(payload: dict) -> str:
       json_str = json.dumps(payload)
       compressed = gzip.compress(json_str.encode())
       return base64.b64encode(compressed).decode()
   ```

3. **Use Alternative Transport for Large Data**:
   ```typescript
   // For large data, use HTTP instead of WebSocket
   async function fetchLargeData(entityId: string) {
     const response = await fetch(`/api/v1/entities/${entityId}/large-data`);
     return response.json();
   }
   ```

---

## Configuration Reference

### WebSocket Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `WS_PING_INTERVAL` | 30s | Ping interval to keep connection alive |
| `WS_TIMEOUT` | 30s | Receive timeout before sending ping |
| `MAX_MESSAGE_SIZE` | 1MB | Maximum WebSocket message size |
| `MAX_CONNECTIONS_PER_CLIENT` | 1 | Max concurrent connections per client |
| `RECONNECT_DELAY` | 1s | Base delay between reconnection attempts |
| `MAX_RECONNECT_ATTEMPTS` | 5 | Maximum reconnection attempts |

### Redis Pub/Sub Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `REDIS_URL` | `redis://localhost:16379` | Redis connection URL |
| `REDIS_SOCKET_TIMEOUT` | 5s | Socket timeout for Redis operations |
| `REDIS_SOCKET_CONNECT_TIMEOUT` | 5s | Connection timeout |
| `EVENT_CHANNEL_PATTERN` | `events.*` | Pub/sub channel pattern |

### Event Bus Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `EVENT_BUS_ENABLED` | `true` | Enable event bus |
| `EVENT_BUS_GRACEFUL_DEGRADATION` | `true` | Continue if Redis unavailable |
| `EVENT_PUBLISH_TIMEOUT` | 5s | Timeout for publish operations |

---

## Step-by-Step Recovery Procedures

### Procedure 1: Reset WebSocket Manager

1. **Check current state**:
   ```python
   from omoi_os.api.routes.events import get_ws_manager
   
   ws_manager = get_ws_manager()
   print(f"Active connections: {len(ws_manager.active_connections)}")
   print(f"Redis listener: {ws_manager.redis_listener_task}")
   ```

2. **Close all connections**:
   ```python
   await ws_manager.close_all()
   print("All connections closed")
   ```

3. **Restart Redis listener**:
   ```python
   # The listener will restart automatically on next connection
   # Or manually restart:
   ws_manager._start_redis_listener()
   ```

### Procedure 2: Debug Event Flow

1. **Subscribe to all events**:
   ```bash
   # Use wscat to monitor all events
   wscat -c "ws://localhost:18000/api/v1/ws/events?token=$TOKEN" | jq .
   ```

2. **Publish test events**:
   ```python
   from omoi_os.services.event_bus import get_event_bus, SystemEvent
   
   event_bus = get_event_bus()
   event_bus.publish(SystemEvent(
       event_type="TEST_DEBUG",
       entity_type="test",
       entity_id="debug-1",
       payload={"timestamp": "2025-01-01T00:00:00"}
   ))
   ```

3. **Verify Redis pub/sub**:
   ```bash
   # Subscribe to events channel
   redis-cli -h localhost -p 16379 psubscribe 'events.*'
   ```

---

## Prevention Strategies

1. **Implement Heartbeat**:
   ```typescript
   // Client-side heartbeat
   private heartbeatInterval: NodeJS.Timeout;
   
   private startHeartbeat() {
     this.heartbeatInterval = setInterval(() => {
       if (this.ws?.readyState === WebSocket.OPEN) {
         this.ws.send(JSON.stringify({ type: 'ping' }));
       }
     }, 30000);
   }
   ```

2. **Monitor Connection Health**:
   ```python
   # Log connection metrics
   logger.info(
       "websocket_metrics",
       active_connections=len(ws_manager.active_connections),
       events_per_minute=event_count,
       avg_latency=avg_latency
   )
   ```

3. **Graceful Degradation**:
   ```typescript
   // Fall back to polling if WebSocket fails
   if (this.reconnectAttempts >= this.maxReconnectAttempts) {
     this.emit('degraded', { mode: 'polling' });
     this.startPolling();
   }
   ```

4. **Connection Pooling**:
   - Limit connections per user/session
   - Reuse connections across tabs (BroadcastChannel API)
   - Implement connection sharing

---

## Troubleshooting Flowchart

```
WebSocket disconnecting frequently?
├── Check close code
│   ├── 1006 (abnormal) → Network issue, check connectivity
│   ├── 1001 (going away) → Server restart, normal
│   ├── 1011 (server error) → Check server logs
│   └── 1013 (try again) → Service not ready, wait and retry
├── Check authentication
│   ├── 4401 (auth required) → Include valid token
│   └── Token expired → Refresh before reconnect
└── Implement reconnection
    ├── Exponential backoff
    └── Max attempt limit

Events not received?
├── Check subscription filters → Verify event types match
├── Check Redis pub/sub → Ensure events are published
├── Check connection state → Must be OPEN
└── Check for payload size → May exceed limits

Stale connections accumulating?
├── Check disconnect handling → Should cleanup properly
├── Implement periodic pruning
└── Force cleanup if needed

Rate limited?
├── Check connection frequency → May be too high
├── Implement client throttling
└── Add server-side rate limits
```

---

## Common Diagnostic Commands

```bash
# Monitor WebSocket connections in real-time
tail -f backend/logs/api.log | grep -E "WebSocket|websocket"

# Check Redis pub/sub channels
redis-cli -h localhost -p 16379 pubsub channels

# Test WebSocket with authentication
wscat -c "ws://localhost:18000/api/v1/ws/events?token=$(cat token.txt)"

# Monitor event publishing
tail -f backend/logs/api.log | grep "event_bus.publish"

# Check for connection errors
grep -E "WebSocket.*error|Error.*WebSocket" backend/logs/api.log

# Test Redis connectivity
redis-cli -h localhost -p 16379 ping

# View active WebSocket connections
cd backend && uv run python -c "
from omoi_os.api.routes.events import get_ws_manager
ws = get_ws_manager()
print(f'Active: {len(ws.active_connections)}')
print(f'Filters: {len(ws.connection_filters)}')
"
```

---

*End of WebSocket Disconnections Troubleshooting Guide*

*This guide covers WebSocket connection management, reconnection strategies, event delivery, and troubleshooting in OmoiOS.*
