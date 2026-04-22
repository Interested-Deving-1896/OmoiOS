# Redis and Message Queue Troubleshooting Guide

**Status**: Active | **Last Updated**: 2025-04-22 | **Applies To**: OmoiOS v1.0+

**Source Files**:
- `backend/omoi_os/services/event_bus.py` - Redis pub/sub event system
- `backend/omoi_os/services/message_queue.py` - Redis-based message queue
- `backend/omoi_os/config.py` - Redis settings configuration
- `backend/config/base.yaml` - Redis connection parameters

**Related Documentation**:
- [Architecture: Real-Time Events](../architecture/06-realtime-events.md)
- [Backend CLAUDE.md](../../backend/CLAUDE.md)
- [WebSocket Events](websocket-events.md)

---

## Overview

OmoiOS uses **Redis 7** (Port: **16379**) for distributed caching, the event bus (pub/sub), and as the backend for message queues. The system implements graceful degradation when Redis is unavailable, ensuring the API remains functional even without real-time features.

### Redis Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   API Server    │────▶│   Redis 7        │────▶│   Subscribers   │
│  (FastAPI/ASGI) │◄────│  (Port 16379)    │◄────│  (Workers,      │
└─────────────────┘     └──────────────────┘     │   WebSocket)    │
        │                        │                 └─────────────────┘
        │              ┌─────────┴─────────┐
        │              │  Key Patterns:    │
        │              │  - events.{type}   │
        │              │  - sandbox:msg:* │
        │              │  - token:blacklist│
        │              │  - auth:events     │
        │              └───────────────────┘
        │
   ┌────┴────────────────────────────┐
   │  Graceful Degradation:          │
   │  - Events become no-ops         │
   │  - Messages queue in memory     │
   │  - Auth falls back to DB        │
   └─────────────────────────────────┘
```

### Redis Use Cases in OmoiOS

| Feature | Redis Data Structure | Key Pattern |
|---------|---------------------|-------------|
| Event Bus | Pub/Sub | `events.{event_type}` |
| Message Queue | List (LPUSH/RPOP) | `sandbox:messages:{sandbox_id}` |
| Token Blacklist | String with TTL | `token:blacklist:{jti}` |
| Auth Events | List | `auth:events` |
| Failed Logins | String with TTL | `auth:failed:{email}` |
| Rate Limiting | String with TTL | `rate_limit:{endpoint}:{ip}` |

---

## Common Errors Table

| Error Message | Cause | Fix |
|--------------|-------|-----|
| `redis.exceptions.ConnectionError: Error 61 connecting to localhost:16379` | Redis container not running | Start Docker container with `just docker-up` |
| `omoi_os.exceptions.event_bus.BusTimeoutError: Timed out waiting for response` | Subscriber (worker) not responding | Check worker status, increase timeout |
| `redis.exceptions.ResponseError: OOM command not allowed when used memory > 'maxmemory'` | Redis memory limit reached | Flush expired data or increase memory limit |
| `redis.exceptions.ConnectionError: Error 32 while writing to socket. Broken pipe` | TCP connection closed due to inactivity | Enable health checks and retry logic |
| `Events published but listener not triggering` | Listener background task crashed | Restart API service, check channel names |
| `redis.exceptions.TimeoutError: Connection timed out` | Network latency or Redis overloaded | Check Redis latency, increase timeout |
| `WRONGTYPE Operation against a key holding the wrong kind of value` | Key collision (wrong data type) | Use prefixed keys, flush conflicting keys |
| `NOAUTH Authentication required` | Redis password not provided | Configure AUTH in connection URL |
| `LOADING Redis is loading the dataset in memory` | Redis restarting and loading RDB | Wait for loading to complete |
| `MASTERDOWN Link with MASTER is down` | Redis replica can't reach master | Check replication status |

---

## Diagnostic Commands

### Check Redis Status

```bash
# Check if Redis is running
docker ps | grep redis

# Ping Redis to test connectivity
redis-cli -h localhost -p 16379 ping

# Monitor Redis commands in real-time
redis-cli -h localhost -p 16379 monitor

# Check memory usage
redis-cli -h localhost -p 16379 info memory

# List current pub/sub channels
redis-cli -h localhost -p 16379 pubsub channels

# Check Redis info
redis-cli -h localhost -p 16379 info server

# Test latency
redis-cli -h localhost -p 16379 --latency
```

### Event Bus Diagnostics

```bash
# Check if EventBus is connected
cd backend && uv run python -c "
from omoi_os.services.event_bus import get_event_bus
bus = get_event_bus()
print(f'EventBus available: {bus._available}')
print(f'Redis client: {bus.redis_client}')
"

# List active subscriptions
redis-cli -h localhost -p 16379 pubsub numsub events.TASK_ASSIGNED

# Monitor event flow
redis-cli -h localhost -p 16379 subscribe "events.*"
```

### Message Queue Diagnostics

```bash
# Check pending messages for a sandbox
redis-cli -h localhost -p 16379 lrange "sandbox:messages:abc123" 0 -1

# Count messages in queue
redis-cli -h localhost -p 16379 llen "sandbox:messages:abc123"

# Check all sandbox message queues
redis-cli -h localhost -p 16379 keys "sandbox:messages:*"
```

### Memory and Performance

```bash
# Check memory usage by key pattern
redis-cli -h localhost -p 16379 --bigkeys

# Memory stats
redis-cli -h localhost -p 16379 info memory | grep used_memory

# Check slow queries
redis-cli -h localhost -p 16379 slowlog get 10

# Database size
redis-cli -h localhost -p 16379 dbsize
```

---

## Symptom 1: Connection Refused

**Error Message**: `redis.exceptions.ConnectionError: Error 61 connecting to localhost:16379. Connection refused.`

**Root Cause**: The backend service cannot reach the Redis instance.
1. The Redis Docker container (`omoi_os_redis`) is not running
2. The port in `config/base.yaml` is incorrectly set (default is 16379)
3. Redis has hit the `maxclients` limit

### Diagnostic Steps

1. **Check container status**:
   ```bash
   docker ps | grep redis
   docker-compose ps
   ```

2. **Verify port configuration**:
   ```bash
   grep -A5 "redis:" backend/config/base.yaml
   grep REDIS_URL backend/.env
   ```

3. **Test direct connection**:
   ```bash
   redis-cli -h localhost -p 16379 ping
   telnet localhost 16379
   ```

4. **Check Docker port mapping**:
   ```bash
   docker port omoi_os_redis
   docker inspect omoi_os_redis | grep -A10 "PortBindings"
   ```

### Fix Procedure

1. **Start Redis**:
   ```bash
   docker-compose up -d redis
   just docker-up
   ```

2. **Check Configuration**:
   Verify `backend/config/base.yaml`:
   ```yaml
   redis:
     host: localhost
     port: 16379
     db: 0
   ```

3. **Verify Port Mapping**:
   Check `docker-compose.yml` has `16379:6379`:
   ```yaml
   services:
     redis:
       ports:
         - "16379:6379"
   ```

4. **Check maxclients**:
   ```bash
   redis-cli -h localhost -p 16379 info clients | grep connected_clients
   redis-cli -h localhost -p 16379 CONFIG GET maxclients
   ```

---

## Symptom 2: Event Bus Timeout

**Error Message**: `omoi_os.exceptions.event_bus.BusTimeoutError: Timed out waiting for response on channel 'events:response:task-123' after 30.0s`

**Root Cause**: This happens when a service publishes an event (e.g., to trigger a sandbox task) but the subscriber (the `OrchestratorWorker`) doesn't respond in time.
1. `OrchestratorWorker` is down
2. Redis pub/sub message was dropped
3. The worker is stuck processing another long-running task and the message reached its expiry

### Diagnostic Steps

1. **Check worker status**:
   ```bash
   just worker-logs
   docker ps | grep worker
   ```

2. **Verify subscriptions**:
   ```bash
   redis-cli -h localhost -p 16379 pubsub numsub events.request.tasks
   redis-cli -h localhost -p 16379 pubsub channels
   ```

3. **Test event publishing**:
   ```python
   from omoi_os.services.event_bus import get_event_bus, SystemEvent
   
   bus = get_event_bus()
   event = SystemEvent(
       event_type="TEST_EVENT",
       entity_type="test",
       entity_id="123",
       payload={"message": "test"}
   )
   bus.publish(event)
   print("Event published successfully")
   ```

4. **Check worker heartbeat**:
   ```bash
   redis-cli -h localhost -p 16379 keys "worker:*:heartbeat"
   ```

### Fix Procedure

1. **Check Workers**:
   Ensure workers are active: `just worker-logs`

2. **Increase Timeout**:
   If the task is intentionally long-running, adjust the `request_timeout` in `backend/omoi_os/services/event_bus.py`:
   ```python
   # In EventBusService or calling code
   timeout = 60.0  # Increase from 30.0
   ```

3. **Inspect Subscriptions**:
   Use `redis-cli pubsub numsub events:request:tasks` to see if anyone is listening.

4. **Restart Event Bus**:
   ```bash
   just dev-backend-restart
   ```

5. **Check for Message Loss**:
   Redis pub/sub doesn't persist messages. If subscriber was down, messages are lost. Consider using message queues for critical operations.

---

## Symptom 3: Redis Out of Memory

**Error Message**: `redis.exceptions.ResponseError: OOM command not allowed when used memory > 'maxmemory'.`

**Root Cause**: Redis has exhausted its allocated memory. In OmoiOS, this is often caused by:
1. Large amounts of task logs being cached in Redis
2. Excessive state data from many concurrent sandboxes
3. Missing TTL (Time To Live) on temporary keys

### Diagnostic Steps

1. **Check memory usage**:
   ```bash
   redis-cli -h localhost -p 16379 info memory | grep used_memory
   redis-cli -h localhost -p 16379 info memory | grep maxmemory
   ```

2. **Find largest keys**:
   ```bash
   redis-cli -h localhost -p 16379 --bigkeys
   ```

3. **Check key expiration**:
   ```bash
   redis-cli -h localhost -p 16379 info keyspace
   ```

4. **Memory by pattern**:
   ```bash
   # Approximate memory usage by key pattern
   redis-cli -h localhost -p 16379 eval "
   local keys = redis.call('keys', ARGV[1])
   local total = 0
   for _,key in ipairs(keys) do
     total = total + redis.call('memory', 'usage', key)
   end
   return total
   " 0 "sandbox:*"
   ```

### Fix Procedure

1. **Flush Expired Data** (Emergency):
   ```bash
   # Clear all cache (WARNING: destructive)
   redis-cli -h localhost -p 16379 FLUSHDB
   
   # Or clear specific patterns
   redis-cli -h localhost -p 16379 keys "sandbox:messages:*" | xargs redis-cli del
   ```

2. **Increase Memory Limit**:
   Modify the `command` in `docker-compose.yml`:
   ```yaml
   redis:
     command: ["redis-server", "--maxmemory", "512mb", "--maxmemory-policy", "allkeys-lru"]
   ```

3. **Clean Task States**:
   Run `just db-shell` and clear the `task_states` table if those are being mirrored to Redis:
   ```sql
   -- Check if task states are large
   SELECT COUNT(*) FROM task_states WHERE updated_at < NOW() - INTERVAL '1 day';
   ```

4. **Set TTL on Keys**:
   Ensure all temporary keys have expiry:
   ```python
   # In application code
   await redis.set(key, value, ex=3600)  # 1 hour TTL
   ```

5. **Eviction Policy**:
   Configure appropriate eviction:
   ```bash
   redis-cli -h localhost -p 16379 CONFIG SET maxmemory-policy allkeys-lru
   ```

---

## Symptom 4: Broken Pipe Error

**Error Message**: `redis.exceptions.ConnectionError: Error 32 while writing to socket. Broken pipe.`

**Root Cause**: The TCP connection was closed by Redis due to inactivity or a client timeout.

### Diagnostic Steps

1. **Check connection settings**:
   ```bash
   redis-cli -h localhost -p 16379 CONFIG GET timeout
   redis-cli -h localhost -p 16379 CONFIG GET tcp-keepalive
   ```

2. **Review client list**:
   ```bash
   redis-cli -h localhost -p 16379 client list | grep -c "idle"
   ```

3. **Check application logs**:
   ```bash
   tail -f backend/logs/api.log | grep -i "broken pipe\|connection"
   ```

### Fix Procedure

1. **Enable Health Checks**:
   Ensure the Redis client uses `health_check_interval`:
   ```python
   # In EventBusService and other Redis clients
   self.redis_client = redis.from_url(
       redis_url,
       decode_responses=True,
       socket_timeout=5.0,
       socket_connect_timeout=5.0,
       health_check_interval=30,  # Check connection every 30s
   )
   ```

2. **Retry Logic**:
   Wrap Redis calls in retry decorator:
   ```python
   from omoi_os.utils.resilience import retry_on_error
   
   @retry_on_error(max_retries=3, exceptions=(redis.ConnectionError,))
   async def publish_event(event):
       bus.publish(event)
   ```

3. **Connection Pool Settings**:
   ```python
   redis_client = redis.Redis(
       host='localhost',
       port=16379,
       socket_keepalive=True,
       socket_keepalive_options={
           socket.TCP_KEEPIDLE: 60,
           socket.TCP_KEEPINTVL: 10,
           socket.TCP_KEEPCNT: 3,
       }
   )
   ```

4. **Handle Gracefully**:
   The `EventBusService` already handles this gracefully - operations become no-ops when Redis is unavailable.

---

## Symptom 5: Subscriptions Not Receiving Messages

**Error Message**: Events are published to Redis (verified with `monitor`), but the `EventBus` listener does not trigger callbacks.

**Root Cause**:
1. The listener's background task crashed
2. The listener is stuck in an infinite loop
3. The channel naming convention changed

### Diagnostic Steps

1. **Verify message publication**:
   ```bash
   redis-cli -h localhost -p 16379 monitor
   # In another terminal, trigger an event and watch for PUBLISH
   ```

2. **Check subscription pattern**:
   ```bash
   redis-cli -h localhost -p 16379 pubsub channels "events.*"
   ```

3. **Test with wildcard subscription**:
   ```bash
   redis-cli -h localhost -p 16379 psubscribe "*"
   ```

4. **Check application logs**:
   ```bash
   tail -f backend/logs/api.log | grep -i "event\|pubsub\|subscribe"
   ```

### Fix Procedure

1. **Restart API Service**:
   `just dev-backend-restart` to restart the lifespan listener.

2. **Debug Channels**:
   Use `redis-cli psubscribe "*"` to verify messages are arriving.

3. **Check Channel Names**:
   Ensure publisher and subscriber use the same channel pattern:
   ```python
   # Publisher
   channel = f"events.{event.event_type}"  # e.g., "events.TASK_ASSIGNED"
   
   # Subscriber
   bus.subscribe("TASK_ASSIGNED", callback)  # Matches pattern
   ```

4. **Verify EventBus Initialization**:
   ```python
   from omoi_os.services.event_bus import get_event_bus
   bus = get_event_bus()
   print(f"Available: {bus._available}")
   print(f"Redis: {bus.redis_client}")
   print(f"PubSub: {bus.pubsub}")
   ```

---

## Configuration Reference

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|---------------|
| `REDIS_URL` | Yes | `redis://localhost:16379` | Full Redis connection URL |
| `REDIS_HOST` | No | `localhost` | Redis server hostname |
| `REDIS_PORT` | No | `16379` | Redis server port |
| `REDIS_DB` | No | `0` | Redis database number |
| `REDIS_PASSWORD` | No | `null` | Redis AUTH password |

### YAML Configuration (base.yaml)

```yaml
redis:
  url: redis://localhost:16379
  # Connection settings
  socket_timeout: 5.0
  socket_connect_timeout: 5.0
  health_check_interval: 30
  decode_responses: true
```

### Docker Compose Configuration

```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "16379:6379"
    command: >
      redis-server
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
      --appendonly yes
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 3
```

### Memory Policies

| Policy | Description | Use Case |
|--------|-------------|----------|
| `noeviction` | Don't evict, return errors | Development only |
| `allkeys-lru` | Evict least recently used keys | Production default |
| `volatile-lru` | Evict LRU keys with TTL | When some data must persist |
| `allkeys-random` | Random eviction | Uniform access patterns |

---

## Step-by-Step Recovery Procedures

### Procedure 1: Clear Redis and Restart

1. **Check current state**:
   ```bash
   redis-cli -h localhost -p 16379 info keyspace
   redis-cli -h localhost -p 16379 dbsize
   ```

2. **Backup if needed**:
   ```bash
   redis-cli -h localhost -p 16379 SAVE
   docker cp omoi_os_redis:/data/dump.rdb ./redis-backup.rdb
   ```

3. **Flush database**:
   ```bash
   redis-cli -h localhost -p 16379 FLUSHDB
   ```

4. **Restart services**:
   ```bash
   just dev-backend-restart
   just worker-restart
   ```

### Procedure 2: Fix Memory Issues

1. **Identify memory hogs**:
   ```bash
   redis-cli -h localhost -p 16379 --bigkeys
   ```

2. **Set expiration on large keys**:
   ```bash
   # Set 1-hour TTL on all sandbox messages
   redis-cli -h localhost -p 16379 keys "sandbox:messages:*" | \
     xargs -I {} redis-cli -h localhost -p 16379 EXPIRE {} 3600
   ```

3. **Increase memory limit**:
   ```bash
   # Temporary (until restart)
   redis-cli -h localhost -p 16379 CONFIG SET maxmemory 512mb
   
   # Permanent (update docker-compose.yml)
   ```

4. **Monitor recovery**:
   ```bash
   watch -n 2 'redis-cli -h localhost -p 16379 info memory | grep used_memory_human'
   ```

### Procedure 3: Reconnect Event Bus

1. **Check EventBus status**:
   ```python
   from omoi_os.services.event_bus import get_event_bus
   bus = get_event_bus()
   print(f"Before: Available={bus._available}")
   ```

2. **Force reconnection**:
   ```python
   # Clear singleton instance
   import omoi_os.services.event_bus as eb
   eb._event_bus_instance = None
   
   # Get new instance
   bus = get_event_bus()
   print(f"After: Available={bus._available}")
   ```

3. **Test event flow**:
   ```python
   from omoi_os.services.event_bus import SystemEvent
   
   event = SystemEvent(
       event_type="TEST",
       entity_type="test",
       entity_id="123",
       payload={"test": True}
   )
   bus.publish(event)
   ```

---

## Prevention Strategies

- **Use Prefixed Keys**: Always use the `omoi_os:` prefix for all Redis keys to avoid collisions:
  ```python
  key = f"omoi_os:sandbox:{sandbox_id}:state"
  ```

- **Set TTLs**: Every temporary key should have an expiry:
  ```python
  await redis.set(key, value, ex=3600)  # 1 hour
  await redis.setex(key, 3600, value)     # Same
  ```

- **Monitor Latency**: Use `redis-cli --latency` to detect slow command execution:
  ```bash
  redis-cli -h localhost -p 16379 --latency -i 1
  ```

- **Log Pub/Sub Failures**: Ensure `backend/omoi_os/api/main.py` logs any unhandled exceptions in the Redis listener loop.

- **Health Checks**: Implement regular health checks:
  ```python
  async def redis_health_check():
      try:
          await redis.ping()
          return True
      except redis.ConnectionError:
          return False
  ```

- **Graceful Degradation**: Design features to work without Redis:
  ```python
  if not event_bus._available:
      logger.warning("EventBus unavailable, using direct call")
      await process_directly()  # Fallback
  else:
      event_bus.publish(event)
  ```

- **Memory Monitoring**: Set up alerts for:
  - Memory usage > 80%
  - Connection count > 90% of maxclients
  - Hit rate < 50%

---

## Troubleshooting Flowchart

```
Redis Connection Fails?
├── Check Docker → docker ps | grep redis
├── Check Port → redis-cli ping
├── Check URL → grep REDIS_URL .env
└── Check Firewall → telnet localhost 16379

Event Bus Not Working?
├── Check Available → bus._available
├── Check Subscribers → redis-cli pubsub channels
├── Check Messages → redis-cli monitor
└── Restart API → just dev-backend-restart

Out of Memory?
├── Check Usage → info memory
├── Find Big Keys → --bigkeys
├── Set TTLs → EXPIRE key 3600
└── Increase Limit → CONFIG SET maxmemory 512mb

Broken Pipe Errors?
├── Enable Keepalive → socket_keepalive=True
├── Add Health Checks → health_check_interval=30
├── Implement Retry → @retry_on_error
└── Check Timeouts → CONFIG GET timeout
```

---

## Common Diagnostic Commands

```bash
# Quick health check
redis-cli -h localhost -p 16379 ping && echo "Redis OK" || echo "Redis FAIL"

# Monitor all commands (use with caution in production)
redis-cli -h localhost -p 16379 monitor

# Check slow log
redis-cli -h localhost -p 16379 slowlog get 10

# Memory stats
redis-cli -h localhost -p 16379 info memory | grep -E "used_memory|maxmemory"

# Connection stats
redis-cli -h localhost -p 16379 info clients

# Keyspace stats
redis-cli -h localhost -p 16379 info keyspace

# Find large keys
redis-cli -h localhost -p 16379 --bigkeys

# Test latency
redis-cli -h localhost -p 16379 --latency

# List all keys (careful in production!)
redis-cli -h localhost -p 16379 keys "*" | wc -l

# Clear specific pattern
redis-cli -h localhost -p 16379 keys "sandbox:messages:*" | xargs redis-cli del

# Force save to disk
redis-cli -h localhost -p 16379 SAVE

# Check replication status
redis-cli -h localhost -p 16379 info replication
```

---

*End of Redis and Message Queue Troubleshooting Guide*

*This guide covers Redis pub/sub, message queues, connection management, and graceful degradation in OmoiOS.*
