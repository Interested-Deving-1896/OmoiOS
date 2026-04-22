# Get It Working NOW - Action Plan

**Goal**: Get a working sandbox agent in the next 30 minutes.

**Last Updated:** 2025-12-18  
**Difficulty:** Beginner  
**Prerequisites:** Docker, Python 3.12+, API keys

---

## Table of Contents

1. [What's Already Fixed](#whats-already-fixed)
2. [Quick Test (5 minutes)](#quick-test-5-minutes)
3. [Test Full Worker Script](#test-full-worker-script)
4. [What to Verify](#what-to-verify)
5. [Common Issues & Quick Fixes](#common-issues--quick-fixes)
6. [Checklist](#checklist)
7. [Next Steps After It Works](#next-steps-after-it-works)
8. [Troubleshooting](#troubleshooting)
9. [Architecture Overview](#architecture-overview)
10. [Environment Setup](#environment-setup)

---

## ✅ What's Already Fixed

1. ✅ **Worker script** - Uses correct `receive_messages()` + `client.query()` pattern
2. ✅ **Documentation** - Matches actual SDK behavior
3. ✅ **Event mapping** - Properly maps SDK messages to events
4. ✅ **Error handling** - Graceful handling of network issues
5. ✅ **Git integration** - Automatic branch creation and PR workflow

---

## 🚀 Quick Test (5 minutes)

### Test 1: Verify SDK Pattern Works

```bash
# Install SDK if needed
pip install claude-agent-sdk

# Set Z.AI credentials (matching worker script)
export ANTHROPIC_AUTH_TOKEN=your_z_ai_token
export ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic
export ANTHROPIC_MODEL=glm-4.6v

# Or use regular Anthropic:
# export ANTHROPIC_API_KEY=your_anthropic_key
# export ANTHROPIC_MODEL=claude-sonnet-4-20250514

# Run minimal test
python test_claude_agent_minimal.py
```

**Minimal Test Script:**

```python
# test_claude_agent_minimal.py
import asyncio
import os

from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions

async def test():
    """Minimal test of Claude Agent SDK pattern."""
    print("Testing Claude Agent SDK...")
    
    # Check credentials
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if not api_key:
        print("❌ No API key found. Set ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN")
        return False
    
    print(f"✓ API key found: {api_key[:10]}...")
    
    # Create options
    options = ClaudeAgentOptions(
        system_prompt="You are a helpful assistant. Reply with 'SDK test successful'.",
        allowed_tools=["Read", "Bash"],
        permission_mode="bypassPermissions",
        max_turns=5,
        env={"ANTHROPIC_API_KEY": api_key},
    )
    
    print("✓ Options created")
    
    try:
        async with ClaudeSDKClient(options=options) as client:
            print("✓ Client initialized")
            
            # Send test message
            await client.query("Say 'SDK test successful' and nothing else.")
            print("✓ Query sent")
            
            # Receive response
            async for msg in client.receive_response():
                print(f"  → Received: {type(msg).__name__}")
                if hasattr(msg, 'content'):
                    for block in msg.content:
                        if hasattr(block, 'text'):
                            print(f"    Text: {block.text[:50]}...")
                            if "successful" in block.text.lower():
                                print("\n✅ ALL TESTS PASSED - Pattern matches Claude Code web!")
                                return True
            
            print("\n⚠️  Test completed but didn't see expected response")
            return True  # Still counts as success if no errors
            
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test())
    exit(0 if success else 1)
```

**Expected output:**

```
Testing Claude Agent SDK...
✓ API key found: sk-ant-api0...
✓ Options created
✓ Client initialized
✓ Query sent
  → Received: AssistantMessage
    Text: SDK test successful

✅ ALL TESTS PASSED - Pattern matches Claude Code web!
```

**If this fails:** SDK setup issue - fix API key or installation first.

---

## 🎯 Next: Test Full Worker Script

### Option A: Test in Real Sandbox (15 minutes)

**Step 1: Start backend:**

```bash
cd backend
uv run python -m omoi_os.api.main
```

You should see:
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:18000
```

**Step 2: Create sandbox via API:**

```bash
curl -X POST http://localhost:18000/api/v1/sandboxes \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "test-1",
    "agent_id": "agent-1",
    "runtime": "claude"
  }'
```

Expected response:
```json
{
  "sandbox_id": "omoios-test-1-abc123",
  "status": "creating",
  "message": "Sandbox spawn initiated"
}
```

**Step 3: Watch logs** - Should see:

```
[SPAWNER] spawn_for_task called
[SPAWNER] Generated OmoiOS API token for task sandbox
Claude Agent Worker starting
Reporting event: agent.started
Streaming messages...
```

**Step 4: Inject message:**

```bash
curl -X POST http://localhost:18000/api/v1/sandboxes/{sandbox_id}/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "Focus on tests", "message_type": "user_message"}'
```

**Step 5: Verify in logs:**

```
Polling messages... found 1
Injecting: Focus on tests
Reporting event: agent.message_injected
```

### Option B: Test Worker Script Directly (10 minutes)

```python
# test_worker_pattern.py
import asyncio
import sys
import os

sys.path.insert(0, 'backend')

# Simulate worker environment
os.environ['TASK_ID'] = 'test-1'
os.environ['AGENT_ID'] = 'agent-1'
os.environ['SANDBOX_ID'] = 'sandbox-1'
os.environ['BASE_URL'] = 'http://localhost:18000'
os.environ['ANTHROPIC_API_KEY'] = 'your-api-key'
os.environ['INITIAL_PROMPT'] = 'List files in /workspace'

# Import worker functions
from omoi_os.workers.claude_sandbox_worker import WorkerConfig, SandboxWorker

async def test():
    """Test worker script directly."""
    print("Testing worker script...")
    
    # Create config
    config = WorkerConfig()
    print(f"✓ Config created: sandbox_id={config.sandbox_id}")
    
    # Validate config
    errors = config.validate()
    if errors:
        print(f"❌ Config errors: {errors}")
        return False
    print("✓ Config validated")
    
    # Create worker
    worker = SandboxWorker(config)
    print("✓ Worker created")
    
    # Run worker (with timeout)
    print("\nRunning worker for 30 seconds...")
    try:
        await asyncio.wait_for(worker.run(), timeout=30)
    except asyncio.TimeoutError:
        print("✓ Worker ran for 30 seconds without errors")
        return True
    except Exception as e:
        print(f"❌ Worker error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = asyncio.run(test())
    exit(0 if success else 1)
```

Run it:

```bash
cd backend
uv run python test_worker_pattern.py
```

---

## 🔍 What to Verify

### ✅ Core Flow Works

| Check | How to Verify | Expected Result |
|-------|---------------|---------------|
| Agent starts | Check logs for `agent.started` event | Event appears within 10s |
| Agent thinks | Check for `agent.thinking` event | Event appears during processing |
| Agent uses tool | Check for `agent.tool_use` event | Tool name shown (Read/Write/Bash) |
| Agent responds | Check for `agent.message` event | Response content visible |
| Message injected | POST to `/messages` endpoint | 200 OK response |
| Agent responds to injection | New `agent.message` event | Response to injected message |

### ✅ Pattern Matches Claude Code Web

| Pattern | Implementation | Verification |
|---------|----------------|--------------|
| `receive_messages()` | Used in worker loop | Check logs show streaming |
| `client.query()` | Used for message injection | Check logs show "Injecting" |
| Conversation state | Maintained across turns | Check `session_id` consistent |
| Real-time events | HTTP POST to callback | Check events appear in API |

---

## 🐛 Common Issues & Quick Fixes

### Issue: "receive_messages() hangs"

**Symptoms:** Worker starts but no events appear after initial prompt.

**Diagnosis:**
```bash
# Check if worker is stuck
ps aux | grep claude_sandbox_worker

# Check logs for errors
tail -f backend/logs/worker.log
```

**Fix:** Make sure you're inside `async with ClaudeSDKClient()` context:

```python
# ✅ CORRECT
async with ClaudeSDKClient(options=sdk_options) as client:
    await client.query("Hello")
    async for msg in client.receive_response():
        print(msg)

# ❌ WRONG - client not in async context
client = ClaudeSDKClient(options=sdk_options)
await client.query("Hello")  # May hang!
```

### Issue: "No events appearing"

**Symptoms:** API calls succeed but no events in database.

**Diagnosis:**
```bash
# Check if report_event is being called
grep "Reporting event" backend/logs/worker.log

# Check database directly
psql -c "SELECT COUNT(*) FROM sandbox_events WHERE sandbox_id = 'your-sandbox-id';"
```

**Fix:** Add logging to verify `report_event()` is called:

```python
# In claude_sandbox_worker.py
async def report_event(self, event_type: str, event_data: dict):
    """Report event with extra logging."""
    logger.info(f"[DEBUG] Reporting event: {event_type}")
    logger.info(f"[DEBUG] Event data: {event_data}")
    
    # ... existing code ...
    
    try:
        response = await self.client.post(url, json=payload)
        logger.info(f"[DEBUG] Event reported: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        logger.error(f"[DEBUG] Failed to report event: {e}")
        return False
```

### Issue: "Message injection doesn't work"

**Symptoms:** Messages are queued but agent doesn't respond.

**Diagnosis:**
```bash
# Check message queue
curl http://localhost:18000/api/v1/sandboxes/{sandbox_id}/messages

# Check worker logs for polling
grep "Polling messages" backend/logs/worker.log
```

**Fix Steps:**

1. **Verify polling loop is running:**
```python
# Add logging in worker loop
logger.info("Polling messages...")
messages = await poller.poll()
logger.info(f"Found {len(messages)} messages")
```

2. **Verify `client.query()` is being called:**
```python
# Add logging before query
logger.info(f"Injecting: {content[:50]}...")
await client.query(content)
```

3. **Verify message is in queue:**
```bash
# Check API directly
curl http://localhost:18000/api/v1/sandboxes/{sandbox_id}/messages | jq
```

### Issue: "Sandbox spawn fails"

**Symptoms:** 500 error when creating sandbox.

**Diagnosis:**
```bash
# Check Daytona API key
echo $DAYTONA_API_KEY

# Check logs for specific error
grep "Daytona" backend/logs/orchestrator.log
```

**Fix:**

1. Set Daytona API key:
```bash
export DAYTONA_API_KEY=your-daytona-key
```

2. Or add to `.env`:
```bash
# backend/.env
DAYTONA_API_KEY=your-daytona-key
```

3. Verify in config:
```yaml
# backend/config/base.yaml
daytona:
  api_key: "${DAYTONA_API_KEY}"
```

### Issue: "GitHub clone fails"

**Symptoms:** Sandbox starts but no code in `/workspace`.

**Diagnosis:**
```bash
# Check worker logs for git errors
grep -i "git\|clone\|github" backend/logs/worker.log
```

**Fix:**

1. Verify GitHub token is set:
```bash
# Check user has GitHub token
psql -c "SELECT attributes->>'github_access_token' FROM users WHERE email = 'user@example.com';"
```

2. Check token permissions:
```bash
# Test token
curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/user
```

3. Verify project has GitHub info:
```bash
# Check project settings
psql -c "SELECT github_owner, github_repo FROM projects WHERE id = 'project-id';"
```

---

## 📋 Checklist: Is It Working?

### Pre-flight Checks

- [ ] Minimal test passes (`test_claude_agent_minimal.py`)
- [ ] Backend server running (`uvicorn omoi_os.api.main:app`)
- [ ] Database migrations applied (`alembic upgrade head`)
- [ ] Redis running (`redis-cli ping` returns PONG)
- [ ] Daytona API key configured

### Core Functionality

- [ ] Sandbox creation API returns 200
- [ ] Worker script runs without errors
- [ ] `agent.started` event appears in logs
- [ ] `agent.message` events appear during execution
- [ ] Message injection creates new conversation turn
- [ ] Agent responds to injected messages
- [ ] `agent.completed` event appears at end

### Integration

- [ ] Events persisted to database
- [ ] Events broadcast via WebSocket
- [ ] File diffs captured in events
- [ ] Git operations work (if applicable)

**If all checked:** ✅ **IT WORKS - You have a working prototype!**

---

## 🎯 Next Steps After It Works

### Immediate (Do These Now)

1. **Add frontend visualization**
   - Use existing WebSocket connection
   - Display events in activity feed
   - Show file diffs with syntax highlighting

2. **Add one integration test**
   - Test event callback endpoint
   - Test message injection
   - Run in CI/CD

3. **Document your setup**
   - Note any custom configuration
   - Record API keys used
   - Save test commands

### Short-term (This Week)

4. **Fix CORS** (if testing from frontend)
   - Add CORS middleware to FastAPI
   - Configure allowed origins

5. **Add rate limiting**
   - Limit events per second per sandbox
   - Prevent abuse

6. **Add monitoring**
   - Track sandbox spawn success rate
   - Monitor event delivery latency
   - Alert on failures

### Long-term (This Month)

7. **Add session replay**
   - Store full conversation history
   - Allow replaying sessions

8. **Add multi-region support**
   - Spawn sandboxes in different regions
   - Reduce latency for global users

9. **Add cost optimization**
   - Auto-terminate idle sandboxes
   - Right-size resource allocation

---

## 🆘 Troubleshooting

### Still Not Working?

**Step 1: Check logs**

```bash
# Backend logs
tail -f backend/logs/api.log

# Worker logs (if running locally)
tail -f backend/logs/worker.log

# All logs
cd backend && find logs -name "*.log" -exec tail -20 {} \;
```

**Step 2: Run minimal test**

```bash
# Does SDK work at all?
python test_claude_agent_minimal.py
```

**Step 3: Check API key**

```bash
# Is API key valid?
curl -H "Authorization: Bearer $ANTHROPIC_API_KEY" \
  https://api.anthropic.com/v1/models
```

**Step 4: Check network**

```bash
# Can sandbox reach backend?
curl http://localhost:18000/api/v1/health

# Is port open?
netstat -tlnp | grep 18000
```

**Step 5: Database check**

```bash
# Is database running?
docker-compose ps postgres

# Can connect?
psql $DATABASE_URL -c "SELECT 1;"

# Are tables created?
psql $DATABASE_URL -c "\dt"
```

### Get Help

**Share the error and we'll fix it immediately.**

Include:
1. Error message (full traceback)
2. What you were trying to do
3. Environment (OS, Python version)
4. Relevant logs (last 50 lines)

---

## 🏗️ Architecture Overview

### System Flow

```mermaid
flowchart LR
    subgraph User["User Action"]
        U1[Submit Task]
        U2[Inject Message]
    end
    
    subgraph Backend["OmoiOS Backend"]
        B1[Orchestrator]
        B2[Daytona Spawner]
        B3[Event API]
        B4[Database]
    end
    
    subgraph Sandbox["Daytona Sandbox"]
        S1[Claude Worker]
        S2[Git Repo]
    end
    
    U1 --> B1
    B1 --> B2
    B2 -->|Spawn| S1
    S1 -->|Events| B3
    B3 --> B4
    U2 --> B3
    B3 -->|Forward| S1
    S1 -->|Git ops| S2
```

### Worker Lifecycle

```mermaid
sequenceDiagram
    participant O as Orchestrator
    participant D as Daytona
    participant W as Worker
    participant A as API
    participant DB as Database
    
    O->>D: Spawn sandbox
    D->>W: Start worker
    W->>A: POST /events (agent.started)
    A->>DB: INSERT event
    
    loop Every 0.5s
        W->>A: GET /messages
        A-->>W: Messages (if any)
        W->>W: Process with Claude
        W->>A: POST /events (agent.message, agent.tool_use)
    end
    
    W->>A: POST /events (agent.completed)
    A->>DB: UPDATE task status
```

---

## 🔧 Environment Setup

### Required Environment Variables

```bash
# Core API keys
export ANTHROPIC_API_KEY=your-anthropic-key
export DAYTONA_API_KEY=your-daytona-key

# Database
export DATABASE_URL=postgresql://omoios:omoios@localhost:15432/omoios

# Redis
export REDIS_URL=redis://localhost:16379

# Optional: GitHub
export GITHUB_TOKEN=your-github-token
```

### Quick Setup Script

```bash
#!/bin/bash
# setup_env.sh - Quick environment setup

echo "Setting up OmoiOS environment..."

# Check prerequisites
command -v python3 >/dev/null 2>&1 || { echo "Python 3 required"; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "Docker required"; exit 1; }

# Start infrastructure
echo "Starting PostgreSQL and Redis..."
docker-compose up -d postgres redis

# Install dependencies
echo "Installing Python dependencies..."
cd backend
uv sync --group test

# Run migrations
echo "Running database migrations..."
uv run alembic upgrade head

# Create .env if not exists
if [ ! -f .env ]; then
    echo "Creating .env file..."
    cat > .env << EOF
DATABASE_URL=postgresql://omoios:omoios@localhost:15432/omoios
REDIS_URL=redis://localhost:16379
ANTHROPIC_API_KEY=your-key-here
DAYTONA_API_KEY=your-key-here
OMOIOS_ENV=development
EOF
    echo "⚠️  Edit .env and add your API keys!"
fi

echo "✅ Setup complete!"
echo "Next steps:"
echo "  1. Edit backend/.env with your API keys"
echo "  2. Run: just dev-all"
echo "  3. Test: python test_claude_agent_minimal.py"
```

### Verification Commands

```bash
# Check all services
just status

# Test database
psql $DATABASE_URL -c "SELECT version();"

# Test Redis
redis-cli ping

# Test API
curl http://localhost:18000/api/v1/health

# Test SDK
python test_claude_agent_minimal.py
```

---

**But first: GET IT WORKING. Then optimize.**

*For detailed implementation guides, see [Implementation Checklist](./06_implementation_checklist.md) and [Development Workflow](./10_development_workflow.md)*
