# Testing Quick Start Guide

**Quick reference for testing the sandbox agents system**

**Last Updated:** 2025-12-18  
**Scope:** Unit, integration, E2E, and manual testing  
**Estimated Time:** 5-30 minutes depending on test type

---

## Table of Contents

1. [Quick Commands](#quick-commands)
2. [Testing Decision Tree](#testing-decision-tree)
3. [Common Testing Scenarios](#common-testing-scenarios)
4. [Test Organization](#test-organization)
5. [Writing New Tests](#writing-new-tests)
6. [Debugging Tests](#debugging-tests)
7. [Manual Validation](#manual-validation)
8. [CI/CD Integration](#cicd-integration)
9. [Pro Tips](#pro-tips)

---

## 🚀 Quick Commands

### Fast Feedback Loop (Development)

```bash
# Run unit + integration tests (fast)
cd backend
pytest tests/unit/ tests/integration/sandbox/ -v --maxfail=1

# Run specific test
pytest tests/integration/sandbox/test_event_callback.py::test_endpoint_exists_and_accepts_valid_event -v

# Run with coverage
pytest tests/integration/sandbox/ --cov=omoi_os.api.routes.sandbox --cov-report=html

# Run tests matching a keyword
pytest tests/ -k "sandbox" -v

# Run with testmon (only affected tests - fastest)
pytest tests/ --testmon -v
```

### Script-Based Testing (Manual Validation)

```bash
# E2E flow test
cd backend
uv run python scripts/test_spawner_e2e.py

# Claude SDK test
uv run python scripts/test_sandbox_claude_sdk.py

# Simple smoke test
uv run python scripts/test_sandbox_simple.py

# Query sandbox events
uv run python scripts/query_sandbox_events.py --sandbox-id <id>

# Compare events across sandboxes
uv run python scripts/compare_sandbox_events.py --sandbox-ids <id1> <id2>

# List recent sandboxes
uv run python scripts/list_recent_sandboxes.py --limit 10
```

### Full Test Suite

```bash
# All integration tests
pytest tests/integration/sandbox/ -v

# E2E tests (slow, requires real sandboxes)
pytest tests/e2e/ -v --slow

# All tests with markers
pytest tests/ -v -m "integration and not slow"

# All tests with coverage report
pytest tests/ --cov=omoi_os --cov-report=html --cov-report=term
```

---

## 📋 Testing Decision Tree

**What are you testing?**

```
┌─────────────────────────────────────────────────────────────────┐
│                    TESTING DECISION TREE                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Logic/Algorithm? ────────► pytest tests/unit/                 │
│       │                                                         │
│       ▼                                                         │
│  API Endpoint? ───────────► pytest tests/integration/sandbox/   │
│       │                                                         │
│       ▼                                                         │
│  Full User Flow? ─────────► pytest tests/e2e/                    │
│       │            OR    scripts/test_*.py                      │
│       ▼                                                         │
│  Debugging? ──────────────► scripts/debug_*.py                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Test Type Guide

| Test Type | When to Use | Speed | Isolation |
|-----------|-------------|-------|-----------|
| **Unit** | Testing functions, utilities, algorithms | < 1s | Full |
| **Integration** | Testing API endpoints, services | < 10s | Partial |
| **E2E** | Testing full workflows | < 60s | None |
| **Manual** | Debugging, exploration | Variable | N/A |

---

## 🎯 Common Testing Scenarios

### Scenario 1: Testing New Feature

```bash
# 1. Write test first (TDD)
# Create tests/integration/sandbox/test_new_feature.py

# 2. Run test - should fail
pytest tests/integration/sandbox/test_new_feature.py -v

# 3. Implement feature
# ... edit code in backend/omoi_os/ ...

# 4. Run test again - should pass
pytest tests/integration/sandbox/test_new_feature.py -v

# 5. Run all related tests
pytest tests/ -k "sandbox" -v --maxfail=1

# 6. Check coverage
pytest tests/integration/sandbox/test_new_feature.py --cov=omoi_os.api.routes.sandbox --cov-report=html
```

**Example Test Structure:**

```python
# tests/integration/sandbox/test_event_callback.py
import pytest
from fastapi.testclient import TestClient
from omoi_os.api.main import app

client = TestClient(app)

class TestEventCallback:
    """Test suite for sandbox event callback endpoint."""

    @pytest.mark.integration
    def test_endpoint_exists_and_accepts_valid_event(self):
        """Test that the event callback endpoint accepts valid events."""
        # Arrange
        sandbox_id = "test-sandbox-123"
        event_data = {
            "event_type": "agent.started",
            "event_data": {"timestamp": "2025-01-01T00:00:00Z"},
            "source": "worker"
        }
        
        # Act
        response = client.post(
            f"/api/v1/sandboxes/{sandbox_id}/events",
            json=event_data
        )
        
        # Assert
        assert response.status_code == 200
        assert response.json()["status"] == "received"
        assert "event_id" in response.json()

    @pytest.mark.integration
    def test_endpoint_rejects_invalid_event_type(self):
        """Test that invalid event types are rejected."""
        # Arrange
        sandbox_id = "test-sandbox-123"
        event_data = {
            "event_type": "invalid.event.type",
            "event_data": {},
        }
        
        # Act
        response = client.post(
            f"/api/v1/sandboxes/{sandbox_id}/events",
            json=event_data
        )
        
        # Assert
        assert response.status_code == 422
```

### Scenario 2: Debugging Failing Test

```bash
# Run with verbose output
pytest tests/integration/sandbox/test_event_callback.py::test_name -v -s

# Run with debugger
pytest tests/integration/sandbox/test_event_callback.py::test_name --pdb

# Run with full traceback
pytest tests/integration/sandbox/test_event_callback.py::test_name -v --tb=long

# Run with logging visible
pytest tests/integration/sandbox/test_event_callback.py::test_name -v -s --log-cli-level=DEBUG
```

**Debugging Tips:**

1. **Add breakpoints in test:**
```python
def test_something():
    import pdb; pdb.set_trace()  # Breakpoint
    result = some_function()
    assert result
```

2. **Use pytest's built-in debugger:**
```bash
pytest test_file.py --pdb  # Drop into pdb on failure
pytest test_file.py --pdbcls=IPython.terminal.debugger:TerminalPdb  # Use IPython
```

3. **Print debugging:**
```python
def test_something(capsys):
    result = some_function()
    print(f"DEBUG: result = {result}")  # Will be captured
    assert result
    
    captured = capsys.readouterr()
    assert "DEBUG" in captured.out
```

### Scenario 3: Manual E2E Validation

```bash
# Terminal 1: Start server
cd backend
uv run uvicorn omoi_os.api.main:app --reload --port 8000

# Terminal 2: Run E2E script
cd backend
uv run python scripts/test_spawner_e2e.py
```

**E2E Test Script Example:**

```python
# scripts/test_spawner_e2e.py
import asyncio
import httpx

async def test_full_flow():
    """Test complete sandbox spawn → execution → completion flow."""
    base_url = "http://localhost:8000"
    
    async with httpx.AsyncClient() as client:
        # 1. Create sandbox
        print("1. Creating sandbox...")
        response = await client.post(
            f"{base_url}/api/v1/sandboxes",
            json={
                "task_id": "test-task-123",
                "agent_id": "test-agent-456",
                "runtime": "claude"
            }
        )
        assert response.status_code == 200
        sandbox_id = response.json()["sandbox_id"]
        print(f"   ✓ Sandbox created: {sandbox_id}")
        
        # 2. Wait for agent.started event
        print("2. Waiting for agent.started event...")
        await asyncio.sleep(5)
        
        events_response = await client.get(
            f"{base_url}/api/v1/sandboxes/{sandbox_id}/events"
        )
        events = events_response.json()["events"]
        started_events = [e for e in events if e["event_type"] == "agent.started"]
        assert len(started_events) > 0
        print(f"   ✓ Agent started event received")
        
        # 3. Inject message
        print("3. Injecting message...")
        message_response = await client.post(
            f"{base_url}/api/v1/sandboxes/{sandbox_id}/messages",
            json={
                "content": "List files in /workspace",
                "message_type": "user_message"
            }
        )
        assert message_response.status_code == 200
        print(f"   ✓ Message injected")
        
        # 4. Wait for response
        print("4. Waiting for agent response...")
        await asyncio.sleep(10)
        
        events_response = await client.get(
            f"{base_url}/api/v1/sandboxes/{sandbox_id}/events"
        )
        events = events_response.json()["events"]
        message_events = [e for e in events if e["event_type"] == "agent.message"]
        assert len(message_events) > 0
        print(f"   ✓ Agent response received")
        
        print("\n✅ All E2E tests passed!")

if __name__ == "__main__":
    asyncio.run(test_full_flow())
```

---

## 📚 Test Organization

### Directory Structure

```
backend/
├── tests/
│   ├── unit/                    # Fast, isolated tests
│   │   ├── services/
│   │   │   ├── test_daytona_spawner.py
│   │   │   └── test_task_queue.py
│   │   ├── models/
│   │   │   └── test_sandbox_event.py
│   │   └── utils/
│   │       └── test_datetime.py
│   │
│   ├── integration/             # API, services, database
│   │   ├── sandbox/
│   │   │   ├── test_event_callback.py
│   │   │   ├── test_message_injection.py
│   │   │   └── test_sandbox_lifecycle.py
│   │   ├── api/
│   │   │   └── test_routes.py
│   │   └── services/
│   │       └── test_task_queue_integration.py
│   │
│   ├── e2e/                    # Full workflows
│   │   ├── test_full_sandbox_flow.py
│   │   └── test_spec_execution.py
│   │
│   ├── contract/               # API contracts
│   │   └── test_api_contracts.py
│   │
│   ├── fixtures/               # Shared test fixtures
│   │   ├── database.py
│   │   ├── sandbox.py
│   │   └── tasks.py
│   │
│   └── helpers/                # Test utilities
│       ├── assertions.py
│       └── factories.py
│
└── scripts/                    # Manual/exploratory
    ├── test_spawner_e2e.py
    ├── test_sandbox_claude_sdk.py
    ├── test_sandbox_simple.py
    ├── debug_event_flow.py
    └── query_sandbox_events.py
```

### Test File Naming Convention

| Pattern | Example | Purpose |
|---------|---------|---------|
| `test_<component>_<scenario>.py` | `test_event_callback_validation.py` | Specific scenario |
| `test_<component>.py` | `test_daytona_spawner.py` | Component tests |
| `test_<feature>_e2e.py` | `test_sandbox_flow_e2e.py` | End-to-end |

### Test Function Naming

```python
# Pattern: test_<scenario>_<expected_outcome>
def test_valid_event_is_persisted_to_database():
    """Test that valid events are saved to the database."""
    pass

def test_invalid_event_type_returns_422():
    """Test that invalid event types return 422 Unprocessable Entity."""
    pass

def test_missing_required_field_returns_error():
    """Test that missing required fields return validation error."""
    pass
```

---

## ✍️ Writing New Tests

### Unit Test Example

```python
# tests/unit/services/test_file_change_tracker.py
import pytest
from omoi_os.workers.claude_sandbox_worker import FileChangeTracker

class TestFileChangeTracker:
    """Test suite for FileChangeTracker."""

    @pytest.fixture
    def tracker(self):
        """Create a fresh FileChangeTracker instance."""
        return FileChangeTracker()

    def test_cache_file_before_edit(self, tracker):
        """Test that file content is cached before edit."""
        # Arrange
        path = "/workspace/test.py"
        content = "print('hello')"
        
        # Act
        tracker.cache_file_before_edit(path, content)
        
        # Assert
        assert tracker.file_cache[path] == content

    def test_generate_diff_for_new_file(self, tracker):
        """Test diff generation for new files."""
        # Arrange
        path = "/workspace/new_file.py"
        new_content = "print('hello')\nprint('world')"
        
        # Act
        diff_result = tracker.generate_diff(path, new_content)
        
        # Assert
        assert diff_result["file_path"] == path
        assert diff_result["change_type"] == "created"
        assert diff_result["lines_added"] == 2
        assert diff_result["lines_removed"] == 0
        assert "--- /dev/null" in diff_result["full_diff"]

    def test_generate_diff_for_modified_file(self, tracker):
        """Test diff generation for modified files."""
        # Arrange
        path = "/workspace/existing.py"
        old_content = "print('hello')"
        new_content = "print('hello')\nprint('world')"
        
        # Act
        tracker.cache_file_before_edit(path, old_content)
        diff_result = tracker.generate_diff(path, new_content)
        
        # Assert
        assert diff_result["change_type"] == "modified"
        assert diff_result["lines_added"] == 1
        assert diff_result["lines_removed"] == 0
        assert "--- a/existing.py" in diff_result["full_diff"]
```

### Integration Test Example

```python
# tests/integration/sandbox/test_message_injection.py
import pytest
from fastapi.testclient import TestClient
from omoi_os.api.main import app
from omoi_os.services.database import DatabaseService

client = TestClient(app)

class TestMessageInjection:
    """Test suite for message injection endpoints."""

    @pytest.fixture
    def sandbox_id(self):
        """Create a test sandbox and return its ID."""
        response = client.post("/api/v1/sandboxes", json={
            "task_id": "test-task",
            "agent_id": "test-agent",
            "runtime": "claude"
        })
        return response.json()["sandbox_id"]

    @pytest.mark.integration
    def test_inject_user_message(self, sandbox_id):
        """Test injecting a user message into a sandbox."""
        # Arrange
        message = {
            "content": "Focus on writing tests",
            "message_type": "user_message"
        }
        
        # Act
        response = client.post(
            f"/api/v1/sandboxes/{sandbox_id}/messages",
            json=message
        )
        
        # Assert
        assert response.status_code == 200
        assert response.json()["status"] == "queued"
        
        # Verify message is in queue
        queue_response = client.get(
            f"/api/v1/sandboxes/{sandbox_id}/messages"
        )
        assert queue_response.status_code == 200
        messages = queue_response.json()
        assert len(messages) == 1
        assert messages[0]["content"] == message["content"]

    @pytest.mark.integration
    def test_inject_interrupt_message(self, sandbox_id):
        """Test injecting an interrupt message."""
        # Arrange
        message = {
            "content": "Stop current task",
            "message_type": "interrupt"
        }
        
        # Act
        response = client.post(
            f"/api/v1/sandboxes/{sandbox_id}/messages",
            json=message
        )
        
        # Assert
        assert response.status_code == 200
        assert response.json()["status"] == "queued"
        assert response.json()["message_type"] == "interrupt"
```

### E2E Test Example

```python
# tests/e2e/test_sandbox_lifecycle.py
import pytest
import asyncio
import httpx

@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.asyncio
async def test_complete_sandbox_lifecycle():
    """Test full sandbox lifecycle from spawn to completion."""
    base_url = "http://localhost:8000"
    
    async with httpx.AsyncClient() as client:
        # 1. Spawn sandbox
        spawn_response = await client.post(
            f"{base_url}/api/v1/sandboxes",
            json={
                "task_id": "e2e-test-task",
                "agent_id": "e2e-test-agent",
                "runtime": "claude",
                "initial_prompt": "Write a Python function to calculate factorial"
            }
        )
        assert spawn_response.status_code == 200
        sandbox_id = spawn_response.json()["sandbox_id"]
        
        # 2. Poll for events
        max_wait = 120  # seconds
        poll_interval = 5
        elapsed = 0
        
        completed = False
        while elapsed < max_wait and not completed:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
            
            events_response = await client.get(
                f"{base_url}/api/v1/sandboxes/{sandbox_id}/events"
            )
            events = events_response.json()["events"]
            
            # Check for completion
            completed_events = [
                e for e in events 
                if e["event_type"] == "agent.completed"
            ]
            if completed_events:
                completed = True
                break
        
        assert completed, "Sandbox did not complete within timeout"
        
        # 3. Verify file edits
        events_response = await client.get(
            f"{base_url}/api/v1/sandboxes/{sandbox_id}/events"
        )
        events = events_response.json()["events"]
        file_edits = [e for e in events if e["event_type"] == "agent.file_edited"]
        
        assert len(file_edits) > 0, "No file edits recorded"
        
        # 4. Cleanup
        await client.delete(f"{base_url}/api/v1/sandboxes/{sandbox_id}")
```

---

## 🐛 Debugging Tests

### Common Issues and Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| `ModuleNotFoundError` | Missing import path | Add `sys.path.insert(0, 'backend')` |
| Database locked | SQLite concurrency | Use PostgreSQL for tests |
| Event timeout | Slow sandbox spawn | Increase timeout in test |
| 502 errors | Server not ready | Add retry logic with backoff |
| Test pollution | Shared state | Use fixtures with cleanup |

### Debug Script Template

```python
# scripts/debug_event_flow.py
import asyncio
import httpx
from datetime import datetime

async def debug_event_flow(sandbox_id: str):
    """Debug event flow for a specific sandbox."""
    base_url = "http://localhost:8000"
    
    async with httpx.AsyncClient() as client:
        # Get all events
        response = await client.get(
            f"{base_url}/api/v1/sandboxes/{sandbox_id}/events?limit=100"
        )
        events = response.json()["events"]
        
        print(f"\n{'='*60}")
        print(f"Event Flow for Sandbox: {sandbox_id}")
        print(f"{'='*60}")
        print(f"Total Events: {len(events)}")
        print()
        
        # Group by type
        by_type = {}
        for event in events:
            event_type = event["event_type"]
            if event_type not in by_type:
                by_type[event_type] = []
            by_type[event_type].append(event)
        
        print("Event Counts by Type:")
        for event_type, type_events in sorted(by_type.items()):
            print(f"  {event_type}: {len(type_events)}")
        
        print("\nEvent Timeline:")
        for event in events:
            timestamp = event.get("created_at", "?")
            event_type = event["event_type"]
            print(f"  [{timestamp}] {event_type}")
            
            # Show details for important events
            if event_type == "agent.file_edited":
                data = event.get("event_data", {})
                print(f"    → File: {data.get('file_path')}")
                print(f"    → Change: {data.get('change_type')}")
            elif event_type == "agent.tool_use":
                data = event.get("event_data", {})
                print(f"    → Tool: {data.get('tool_name')}")

if __name__ == "__main__":
    import sys
    sandbox_id = sys.argv[1] if len(sys.argv) > 1 else "test-sandbox"
    asyncio.run(debug_event_flow(sandbox_id))
```

---

## 🔧 CI/CD Integration

### GitHub Actions Example

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      
      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh
      
      - name: Install dependencies
        run: uv sync --group test
      
      - name: Run migrations
        run: uv run alembic upgrade head
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/omoios
      
      - name: Run unit tests
        run: uv run pytest tests/unit/ -v --cov=omoi_os --cov-report=xml
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/omoios
          REDIS_URL: redis://localhost:6379
      
      - name: Run integration tests
        run: uv run pytest tests/integration/ -v -m "not slow"
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/omoios
          REDIS_URL: redis://localhost:6379
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
```

---

## 💡 Pro Tips

### 1. Test First (TDD)

Always write tests before implementation. This ensures:
- Clear requirements before coding
- Testable design
- Regression protection

```bash
# Red-Green-Refactor cycle
pytest test_new_feature.py  # Should fail (RED)
# ... implement feature ...
pytest test_new_feature.py  # Should pass (GREEN)
# ... refactor ...
pytest test_new_feature.py  # Still passes (REFACTOR)
```

### 2. Fast Feedback

Use `--maxfail=1` to stop on first failure during development:

```bash
pytest tests/ -v --maxfail=1  # Stop immediately on failure
```

### 3. Use Scripts for Manual Validation

Scripts are great for:
- Exploring behavior
- Debugging issues
- Validating assumptions
- One-off checks

### 4. Check Coverage

Aim for 80%+ coverage on critical paths:

```bash
pytest tests/ --cov=omoi_os --cov-report=html
open htmlcov/index.html  # View coverage report
```

### 5. Parallel Testing

Speed up test runs with parallel execution:

```bash
pytest tests/ -n auto  # Auto-detect CPU count
pytest tests/ -n 4     # Use 4 workers
```

### 6. Test Markers

Use markers to categorize tests:

```python
@pytest.mark.unit
def test_simple_function(): pass

@pytest.mark.integration
def test_api_endpoint(): pass

@pytest.mark.e2e
@pytest.mark.slow
def test_full_workflow(): pass
```

Run specific markers:

```bash
pytest -m unit        # Only unit tests
pytest -m "not slow"  # Exclude slow tests
pytest -m integration # Only integration tests
```

### 7. Fixture Reuse

Create reusable fixtures in `conftest.py`:

```python
# tests/conftest.py
import pytest
from omoi_os.services.database import DatabaseService

@pytest.fixture(scope="session")
def database():
    """Provide database service for tests."""
    db = DatabaseService(connection_string="postgresql://...")
    yield db
    db.close()

@pytest.fixture
def db_session(database):
    """Provide a database session that rolls back after test."""
    with database.get_session() as session:
        yield session
        session.rollback()
```

---

## 📚 Documentation

- **[Testing Workflows](./11_testing_workflows.md)** - Comprehensive testing guide
- **[Development Workflow](./10_development_workflow.md)** - Implementation guide
- **[Implementation Checklist](./06_implementation_checklist.md)** - Test specifications

---

## 🆘 Need Help?

Use these AI prompts:

```
@docs/design/sandbox-agents/11_testing_workflows.md
@docs/design/sandbox-agents/TESTING_QUICK_START.md

[DESCRIBE YOUR TESTING NEED]
```

---

*For detailed testing strategies, see [Testing Workflows](./11_testing_workflows.md)*
