# FastMCP Server Testing Guide

**Created**: 2025-01-20  
**Updated**: 2025-04-22  
**Status**: Active  
**Purpose**: Comprehensive testing guide for MCP (Model Context Protocol) integration in OmoiOS

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Test Setup](#test-setup)
3. [Unit Test Patterns](#unit-test-patterns)
4. [Integration Test Patterns](#integration-test-patterns)
5. [Mock Strategies](#mock-strategies)
6. [CI Configuration](#ci-configuration)
7. [Testing Individual Tools](#testing-individual-tools)
8. [Agent Configuration](#agent-configuration)
9. [Troubleshooting Tests](#troubleshooting-tests)
10. [Related Documentation](#related-documentation)

---

## Quick Start

### 1. Start the API Server

```bash
# Start the FastAPI server (which includes the FastMCP server at /mcp)
uv run uvicorn omoi_os.api.main:app --host 0.0.0.0 --port 18000 --reload
```

### 2. Test with FastMCP Client

```bash
# Run the test script
uv run python scripts/test_fastmcp_server.py

# Or specify a custom URL
uv run python scripts/test_fastmcp_server.py --url http://localhost:18000/mcp
```

### 3. Run Pytest Tests

```bash
# Run FastMCP server tests
uv run pytest tests/test_fastmcp_server.py -v

# Run with coverage
uv run pytest tests/test_fastmcp_server.py --cov=omoi_os.services.mcp --cov-report=html

# Run specific test
uv run pytest tests/test_fastmcp_server.py::TestMCPServer::test_list_tools -v
```

---

## Test Setup

### Environment Configuration

Create a `.env.test` file for testing:

```bash
# .env.test
OMOIOS_ENV=test
DATABASE_URL_TEST=postgresql://postgres:postgres@localhost:15432/omoios_test
REDIS_URL=redis://localhost:16379/1
LLM_API_KEY=test-key-mock
ENABLE_MCP_TOOLS=true
MCP_SERVER_URL=http://localhost:18000/mcp
```

### Test Database Setup

```python
# tests/conftest.py

import pytest
from omoi_os.services.database import DatabaseService
from omoi_os.config import get_test_settings

@pytest.fixture(scope="session")
def test_db():
    """Create test database instance."""
    settings = get_test_settings()
    db = DatabaseService(
        connection_string=settings.database.url,
        pool_size=2,
        max_overflow=0
    )
    
    # Create tables
    db.create_tables()
    
    yield db
    
    # Cleanup
    db.drop_tables()
    db.close()

@pytest.fixture
def db_session(test_db):
    """Provide a database session for a test."""
    with test_db.get_session() as session:
        yield session
        session.rollback()
```

### MCP Test Fixtures

```python
# tests/fixtures/mcp_fixtures.py

import pytest
from unittest.mock import Mock, AsyncMock
from omoi_os.services.mcp_integration import MCPIntegrationService
from omoi_os.services.mcp_registry import MCPRegistryService
from omoi_os.services.mcp_authorization import MCPAuthorizationService
from omoi_os.services.mcp_circuit_breaker import MCPCircuitBreaker
from omoi_os.services.mcp_retry import MCPRetryManager

@pytest.fixture
def mock_db():
    """Create a mock database service."""
    db = Mock()
    db.get_session = Mock()
    db.get_session.return_value.__enter__ = Mock(return_value=Mock())
    db.get_session.return_value.__exit__ = Mock(return_value=False)
    return db

@pytest.fixture
def mcp_registry(mock_db):
    """Create MCP registry service."""
    return MCPRegistryService(db=mock_db)

@pytest.fixture
def mcp_authorization(mock_db):
    """Create MCP authorization service."""
    auth = MCPAuthorizationService(db=mock_db)
    return auth

@pytest.fixture
def mcp_retry_manager():
    """Create MCP retry manager."""
    return MCPRetryManager(
        max_retries=3,
        base_delay=0.1,  # Fast for tests
        max_delay=1.0
    )

@pytest.fixture
def mcp_integration(mock_db, mcp_registry, mcp_authorization, mcp_retry_manager):
    """Create MCP integration service with mocked dependencies."""
    return MCPIntegrationService(
        db=mock_db,
        registry=mcp_registry,
        authorization=mcp_authorization,
        retry_manager=mcp_retry_manager,
        event_bus=None,
        fallback_config={}
    )
```

---

## Unit Test Patterns

### Testing MCP Registry

```python
# tests/unit/services/test_mcp_registry.py

import pytest
from omoi_os.services.mcp_registry import MCPRegistryService
from omoi_os.models.mcp_server import MCPServer, MCPTool

class TestMCPRegistryService:
    """Unit tests for MCP registry service."""
    
    @pytest.mark.unit
    def test_register_server_creates_server_record(self, mock_db):
        """Test that register_server creates a server record."""
        # Arrange
        registry = MCPRegistryService(db=mock_db)
        tools = [
            {
                "name": "create_ticket",
                "schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"}
                    }
                }
            }
        ]
        
        # Act
        result = registry.register_server(
            server_id="test-server",
            version="1.0.0",
            capabilities=["tools"],
            tools=tools,
            connection_url="http://localhost:8000/mcp"
        )
        
        # Assert
        assert result.server_id == "test-server"
        assert result.registered_count == 1
        assert result.rejected_count == 0
    
    @pytest.mark.unit
    def test_register_server_validates_tool_schema(self, mock_db):
        """Test that invalid tool schemas are rejected."""
        # Arrange
        registry = MCPRegistryService(db=mock_db)
        tools = [
            {
                "name": "invalid_tool",
                "schema": {"invalid": "schema"}  # Missing type
            }
        ]
        
        # Act
        result = registry.register_server(
            server_id="test-server",
            version="1.0.0",
            capabilities=["tools"],
            tools=tools
        )
        
        # Assert
        assert result.registered_count == 0
        assert result.rejected_count == 1
        assert "Invalid JSON schema" in result.rejected_tools[0]["reason"]
    
    @pytest.mark.unit
    def test_get_tool_returns_tool(self, mock_db, mcp_registry):
        """Test that get_tool returns a registered tool."""
        # Arrange - register a server first
        tools = [{"name": "test_tool", "schema": {"type": "object"}}]
        mcp_registry.register_server(
            server_id="test-server",
            version="1.0.0",
            capabilities=["tools"],
            tools=tools
        )
        
        # Act
        tool = mcp_registry.get_tool("test-server", "test_tool")
        
        # Assert
        assert tool is not None
        assert tool.tool_name == "test_tool"
    
    @pytest.mark.unit
    def test_list_tools_returns_enabled_tools_only(self, mock_db, mcp_registry):
        """Test that list_tools respects enabled_only filter."""
        # Arrange
        tools = [
            {"name": "enabled_tool", "schema": {"type": "object"}},
            {"name": "disabled_tool", "schema": {"type": "object"}, "enabled": False}
        ]
        mcp_registry.register_server(
            server_id="test-server",
            version="1.0.0",
            capabilities=["tools"],
            tools=tools
        )
        
        # Act
        enabled_tools = mcp_registry.list_tools("test-server", enabled_only=True)
        all_tools = mcp_registry.list_tools("test-server", enabled_only=False)
        
        # Assert
        assert len(enabled_tools) == 1
        assert enabled_tools[0].tool_name == "enabled_tool"
        assert len(all_tools) == 2
```

### Testing MCP Circuit Breaker

```python
# tests/unit/services/test_mcp_circuit_breaker.py

import pytest
import asyncio
from datetime import datetime
from omoi_os.services.mcp_circuit_breaker import (
    MCPCircuitBreaker, 
    CircuitState, 
    CircuitOpenError
)

class TestMCPCircuitBreaker:
    """Unit tests for MCP circuit breaker."""
    
    @pytest.mark.unit
    def test_circuit_starts_closed(self, mock_db):
        """Test that circuit breaker starts in CLOSED state."""
        # Arrange & Act
        breaker = MCPCircuitBreaker(
            circuit_key="test:circuit",
            db=mock_db,
            failure_threshold=3,
            cooldown_seconds=60
        )
        
        # Assert
        metrics = breaker.get_metrics()
        assert metrics.state == CircuitState.CLOSED
        assert metrics.failure_count == 0
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_circuit_opens_after_failures(self, mock_db):
        """Test that circuit opens after threshold failures."""
        # Arrange
        breaker = MCPCircuitBreaker(
            circuit_key="test:circuit",
            db=mock_db,
            failure_threshold=3,
            cooldown_seconds=60
        )
        
        async def failing_func():
            raise Exception("Test failure")
        
        # Act - trigger failures
        for _ in range(3):
            try:
                await breaker.call(failing_func)
            except Exception:
                pass
        
        # Assert
        metrics = breaker.get_metrics()
        assert metrics.state == CircuitState.OPEN
        assert metrics.failure_count == 3
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_circuit_rejects_calls_when_open(self, mock_db):
        """Test that circuit rejects calls when open."""
        # Arrange
        breaker = MCPCircuitBreaker(
            circuit_key="test:circuit",
            db=mock_db,
            failure_threshold=1,
            cooldown_seconds=60
        )
        
        async def failing_func():
            raise Exception("Test failure")
        
        # Open the circuit
        try:
            await breaker.call(failing_func)
        except Exception:
            pass
        
        # Act & Assert
        async def success_func():
            return "success"
        
        with pytest.raises(CircuitOpenError):
            await breaker.call(success_func)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_circuit_transitions_to_half_open(self, mock_db):
        """Test that circuit transitions to HALF_OPEN after cooldown."""
        # Arrange
        breaker = MCPCircuitBreaker(
            circuit_key="test:circuit",
            db=mock_db,
            failure_threshold=1,
            cooldown_seconds=0  # Immediate cooldown for testing
        )
        
        async def failing_func():
            raise Exception("Test failure")
        
        # Open the circuit
        try:
            await breaker.call(failing_func)
        except Exception:
            pass
        
        # Wait for cooldown
        await asyncio.sleep(0.1)
        
        # Act - check state transition
        async def success_func():
            return "success"
        
        result = await breaker.call(success_func)
        
        # Assert
        assert result == "success"
        metrics = breaker.get_metrics()
        assert metrics.state == CircuitState.CLOSED  # Should close after success
```

### Testing MCP Integration Service

```python
# tests/unit/services/test_mcp_integration.py

import pytest
from unittest.mock import Mock, AsyncMock, patch
from omoi_os.services.mcp_integration import (
    MCPIntegrationService,
    MCPInvocationRequest,
    ToolNotFoundError,
    ToolDisabledError
)
from omoi_os.services.mcp_authorization import PolicyDecision

class TestMCPIntegrationService:
    """Unit tests for MCP integration service."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_invoke_tool_success(self, mcp_integration, mock_db):
        """Test successful tool invocation."""
        # Arrange
        request = MCPInvocationRequest(
            correlation_id="test-123",
            agent_id="agent-001",
            server_id="test-server",
            tool_name="create_ticket",
            params={"title": "Test", "description": "Test desc"}
        )
        
        # Mock registry to return a tool
        mock_tool = Mock()
        mock_tool.enabled = True
        mcp_integration.registry.get_tool = Mock(return_value=mock_tool)
        
        # Mock authorization to allow
        mock_auth_result = Mock()
        mock_auth_result.decision = PolicyDecision.ALLOW
        mock_auth_result.cached = False
        mcp_integration.authorization.authorize = Mock(return_value=mock_auth_result)
        
        # Mock the actual tool call
        with patch.object(mcp_integration, '_call_mcp_server', new_callable=AsyncMock) as mock_call:
            mock_call.return_value = {"ticket_id": "ticket-123"}
            
            # Act
            result = await mcp_integration.invoke_tool(request)
        
        # Assert
        assert result.success is True
        assert result.result == {"ticket_id": "ticket-123"}
        assert result.attempts == 1
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_invoke_tool_not_found(self, mcp_integration):
        """Test that non-existent tools raise ToolNotFoundError."""
        # Arrange
        request = MCPInvocationRequest(
            correlation_id="test-123",
            agent_id="agent-001",
            server_id="test-server",
            tool_name="nonexistent_tool",
            params={}
        )
        
        mcp_integration.registry.get_tool = Mock(return_value=None)
        
        # Act & Assert
        with pytest.raises(ToolNotFoundError):
            await mcp_integration.invoke_tool(request)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_invoke_tool_disabled(self, mcp_integration):
        """Test that disabled tools raise ToolDisabledError."""
        # Arrange
        request = MCPInvocationRequest(
            correlation_id="test-123",
            agent_id="agent-001",
            server_id="test-server",
            tool_name="disabled_tool",
            params={}
        )
        
        mock_tool = Mock()
        mock_tool.enabled = False
        mcp_integration.registry.get_tool = Mock(return_value=mock_tool)
        
        # Act & Assert
        with pytest.raises(ToolDisabledError):
            await mcp_integration.invoke_tool(request)
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_invoke_tool_with_fallback(self, mcp_integration):
        """Test that fallback tools are used when primary fails."""
        # Arrange
        request = MCPInvocationRequest(
            correlation_id="test-123",
            agent_id="agent-001",
            server_id="primary-server",
            tool_name="unreliable_tool",
            params={"data": "test"}
        )
        
        # Configure fallback
        mcp_integration.fallback_config = {
            "primary-server:unreliable_tool": ["fallback-server:reliable_tool"]
        }
        
        # Mock primary tool exists but will fail
        mock_primary_tool = Mock()
        mock_primary_tool.enabled = True
        mcp_integration.registry.get_tool = Mock(side_effect=[
            mock_primary_tool,  # First call - primary tool
            mock_fallback_tool  # Second call - fallback tool
        ])
        
        mock_fallback_tool = Mock()
        mock_fallback_tool.enabled = True
        
        # Mock authorization
        mock_auth_result = Mock()
        mock_auth_result.decision = PolicyDecision.ALLOW
        mcp_integration.authorization.authorize = Mock(return_value=mock_auth_result)
        
        # Mock calls - primary fails, fallback succeeds
        with patch.object(mcp_integration, '_call_mcp_server', new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = [
                Exception("Primary failed"),  # First call fails
                {"result": "fallback success"}  # Fallback succeeds
            ]
            
            # Act
            result = await mcp_integration.invoke_tool(request)
        
        # Assert
        assert result.success is True
        assert result.result == {"result": "fallback success"}
```

---

## Integration Test Patterns

### Full MCP Server Integration Test

```python
# tests/integration/test_mcp_server_integration.py

import pytest
import httpx
from fastmcp import Client

class TestMCPServerIntegration:
    """Integration tests for MCP server."""
    
    @pytest.fixture
    async def mcp_client(self):
        """Create FastMCP client."""
        async with Client("http://localhost:18000/mcp") as client:
            yield client
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_list_tools_endpoint(self, mcp_client):
        """Test that tools/list endpoint returns tools."""
        # Act
        tools = await mcp_client.list_tools()
        
        # Assert
        assert len(tools) > 0
        tool_names = [t.name for t in tools]
        assert "create_ticket" in tool_names
        assert "get_ticket" in tool_names
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_create_ticket_tool(self, mcp_client):
        """Test create_ticket tool invocation."""
        # Act
        result = await mcp_client.call_tool("create_ticket", {
            "workflow_id": "test-workflow",
            "agent_id": "test-agent",
            "title": "Integration Test Ticket",
            "description": "Created by integration test"
        })
        
        # Assert
        assert result is not None
        assert "ticket_id" in result
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_tool_with_invalid_params_returns_error(self, mcp_client):
        """Test that invalid parameters return proper error."""
        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await mcp_client.call_tool("create_ticket", {
                "title": "Test"  # Missing required fields
            })
        
        assert "validation" in str(exc_info.value).lower() or "required" in str(exc_info.value).lower()
```

### HTTP/SSE Endpoint Testing

```python
# tests/integration/test_mcp_http_endpoints.py

import pytest
import httpx

class TestMCPHTTPEndpoints:
    """Test MCP HTTP/SSE endpoints directly."""
    
    @pytest.fixture
    async def http_client(self):
        """Create HTTP client."""
        async with httpx.AsyncClient(base_url="http://localhost:18000") as client:
            yield client
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_mcp_post_tools_list(self, http_client):
        """Test POST /mcp with tools/list method."""
        # Arrange
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 1
        }
        
        # Act
        response = await http_client.post(
            "/mcp",
            json=payload,
            headers={"Content-Type": "application/json", "Session-ID": "test-session"}
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "tools" in data["result"]
    
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_mcp_post_tools_call(self, http_client):
        """Test POST /mcp with tools/call method."""
        # Arrange
        payload = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "get_ticket",
                "arguments": {
                    "ticket_id": "test-ticket-123"
                }
            },
            "id": 2
        }
        
        # Act
        response = await http_client.post(
            "/mcp",
            json=payload,
            headers={"Content-Type": "application/json", "Session-ID": "test-session"}
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "result" in data or "error" in data
```

---

## Mock Strategies

### Mocking FastMCP Client

```python
# tests/mocks/mock_fastmcp.py

from unittest.mock import AsyncMock, MagicMock

class MockFastMCPClient:
    """Mock FastMCP client for testing."""
    
    def __init__(self, tools=None):
        self.tools = tools or []
        self.call_tool_mock = AsyncMock()
        self.list_tools_mock = AsyncMock(return_value=self.tools)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    async def list_tools(self):
        return await self.list_tools_mock()
    
    async def call_tool(self, name, arguments=None):
        return await self.call_tool_mock(name, arguments)
    
    def add_tool(self, tool):
        self.tools.append(tool)
    
    def set_tool_result(self, tool_name, result):
        """Set the return value for a specific tool call."""
        async def side_effect(name, args):
            if name == tool_name:
                return result
            raise Exception(f"Unexpected tool: {name}")
        
        self.call_tool_mock.side_effect = side_effect

@pytest.fixture
def mock_mcp_client():
    """Create mock MCP client."""
    return MockFastMCPClient()
```

### Mocking MCP Services

```python
# tests/mocks/mock_mcp_services.py

import pytest
from unittest.mock import Mock, MagicMock

def create_mock_mcp_services():
    """Create a complete set of mocked MCP services."""
    
    # Mock database
    mock_db = Mock()
    mock_session = MagicMock()
    mock_db.get_session.return_value.__enter__ = Mock(return_value=mock_session)
    mock_db.get_session.return_value.__exit__ = Mock(return_value=False)
    
    # Mock registry
    mock_registry = Mock()
    mock_registry.get_tool = Mock(return_value=Mock(enabled=True))
    mock_registry.list_tools = Mock(return_value=[])
    mock_registry.register_server = Mock()
    
    # Mock authorization
    mock_auth = Mock()
    mock_auth.authorize = Mock(return_value=Mock(
        decision=Mock(value="ALLOW"),
        cached=False,
        reason=None
    ))
    
    # Mock circuit breaker
    mock_breaker = Mock()
    mock_breaker.call = Mock()
    mock_breaker.get_metrics = Mock(return_value=Mock(
        state=Mock(value="CLOSED"),
        failure_count=0,
        last_failure_time=None,
        opened_at=None
    ))
    
    # Mock retry manager
    mock_retry = Mock()
    mock_retry.execute_with_retry = Mock()
    
    return {
        "db": mock_db,
        "registry": mock_registry,
        "authorization": mock_auth,
        "circuit_breaker": mock_breaker,
        "retry_manager": mock_retry
    }

@pytest.fixture
def mock_mcp_services():
    """Provide mocked MCP services."""
    return create_mock_mcp_services()
```

### Using Mocks in Tests

```python
# tests/unit/services/test_mcp_with_mocks.py

import pytest
from unittest.mock import patch
from omoi_os.services.mcp_integration import MCPIntegrationService

class TestMCPWithMocks:
    """Tests using mocked dependencies."""
    
    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_invoke_with_mocked_services(self, mock_mcp_services):
        """Test invocation with fully mocked services."""
        # Arrange
        service = MCPIntegrationService(
            db=mock_mcp_services["db"],
            registry=mock_mcp_services["registry"],
            authorization=mock_mcp_services["authorization"],
            retry_manager=mock_mcp_services["retry_manager"]
        )
        
        # Set up mock return values
        mock_mcp_services["retry_manager"].execute_with_retry = Mock(
            return_value={"success": True}
        )
        
        from omoi_os.services.mcp_integration import MCPInvocationRequest
        request = MCPInvocationRequest(
            correlation_id="test-123",
            agent_id="agent-001",
            server_id="test-server",
            tool_name="test_tool",
            params={}
        )
        
        # Act
        result = await service.invoke_tool(request)
        
        # Assert
        assert result.success is True
        mock_mcp_services["authorization"].authorize.assert_called_once()
```

---

## CI Configuration

### GitHub Actions Workflow

```yaml
# .github/workflows/mcp-tests.yml

name: MCP Tests

on:
  push:
    branches: [main, develop]
    paths:
      - 'backend/omoi_os/services/mcp*.py'
      - 'tests/**/test_mcp*.py'
  pull_request:
    paths:
      - 'backend/omoi_os/services/mcp*.py'
      - 'tests/**/test_mcp*.py'

jobs:
  mcp-unit-tests:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: omoios_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 15432:5432
      
      redis:
        image: redis:7
        ports:
          - 16379:6379
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh
      
      - name: Install dependencies
        run: uv sync --group test
        working-directory: ./backend
      
      - name: Run MCP unit tests
        run: uv run pytest tests/unit/services/test_mcp*.py -v --tb=short
        working-directory: ./backend
        env:
          DATABASE_URL_TEST: postgresql://postgres:postgres@localhost:15432/omoios_test
          REDIS_URL: redis://localhost:16379/1
          OMOIOS_ENV: test
          ENABLE_MCP_TOOLS: true
      
      - name: Run MCP integration tests
        run: uv run pytest tests/integration/test_mcp*.py -v --tb=short
        working-directory: ./backend
        env:
          DATABASE_URL_TEST: postgresql://postgres:postgres@localhost:15432/omoios_test
          REDIS_URL: redis://localhost:16379/1
          OMOIOS_ENV: test
          ENABLE_MCP_TOOLS: true
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./backend/coverage.xml
          flags: mcp-tests
```

### Test Configuration File

```yaml
# backend/config/test.yaml

# Test-specific MCP configuration
mcp:
  enabled: true
  server_url: http://localhost:18000/mcp
  
  # Fast timeouts for tests
  circuit_breaker:
    failure_threshold: 2
    cooldown_seconds: 1
    half_open_max_requests: 1
  
  retry:
    max_retries: 2
    base_delay: 0.1
    max_delay: 0.5
    exponential_base: 2
  
  # Test fallbacks
  fallbacks:
    "primary-server:unreliable_tool": ["fallback-server:reliable_tool"]

# Disable external calls in tests
features:
  enable_mcp_tools: true
  enable_external_calls: false
```

---

## Testing Individual Tools

### Using Python Script

```python
# scripts/test_mcp_tool.py

import asyncio
import argparse
from fastmcp import Client

async def test_tool(server_url: str, tool_name: str, params: dict):
    """Test a specific MCP tool."""
    async with Client(server_url) as client:
        # List available tools
        tools = await client.list_tools()
        print(f"Available tools: {[t.name for t in tools]}")
        
        # Call specific tool
        print(f"\nCalling tool: {tool_name}")
        print(f"Parameters: {params}")
        
        try:
            result = await client.call_tool(tool_name, params)
            print(f"Result: {result}")
            return result
        except Exception as e:
            print(f"Error: {e}")
            raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test MCP tool")
    parser.add_argument("--url", default="http://localhost:18000/mcp")
    parser.add_argument("--tool", required=True)
    parser.add_argument("--params", type=str, help="JSON params string")
    
    args = parser.parse_args()
    
    import json
    params = json.loads(args.params) if args.params else {}
    
    asyncio.run(test_tool(args.url, args.tool, params))
```

### Using curl (HTTP/SSE)

```bash
# List tools
curl -X POST http://localhost:18000/mcp \
  -H "Content-Type: application/json" \
  -H "Session-ID: test-123" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/list",
    "id": 1
  }'

# Call a tool
curl -X POST http://localhost:18000/mcp \
  -H "Content-Type: application/json" \
  -H "Session-ID: test-123" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "create_ticket",
      "arguments": {
        "workflow_id": "test-001",
        "agent_id": "agent-001",
        "title": "Test Ticket",
        "description": "Test description"
      }
    },
    "id": 2
  }'

# Test with verbose output
curl -v -X POST http://localhost:18000/mcp \
  -H "Content-Type: application/json" \
  -H "Session-ID: test-123" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "get_ticket",
      "arguments": {
        "ticket_id": "test-ticket-id"
      }
    },
    "id": 3
  }' 2>&1 | grep -E "(HTTP|jsonrpc|result|error)"
```

---

## Agent Configuration

Agents automatically connect to the FastMCP server when `ENABLE_MCP_TOOLS=true` (default).

To disable MCP tools:

```bash
export ENABLE_MCP_TOOLS=false
```

To use a different MCP server URL:

```bash
export MCP_SERVER_URL=http://localhost:18000/mcp
```

### Environment Variables for Testing

```bash
# Test configuration
export OMOIOS_ENV=test
export ENABLE_MCP_TOOLS=true
export MCP_SERVER_URL=http://localhost:18000/mcp
export MCP_TEST_MODE=true  # Enable test endpoints
export MCP_MOCK_RESPONSES=true  # Use mock responses
```

---

## Troubleshooting Tests

### Common Issues

#### 1. Connection Refused

```
httpx.ConnectError: [Errno 111] Connection refused
```

**Solution**: Ensure the API server is running:
```bash
uv run uvicorn omoi_os.api.main:app --host 0.0.0.0 --port 18000 --reload
```

#### 2. Database Not Initialized

```
sqlalchemy.exc.ProgrammingError: relation "mcp_server" does not exist
```

**Solution**: Run migrations:
```bash
uv run alembic upgrade head
```

#### 3. Circuit Breaker Open

```
omoi_os.services.mcp_circuit_breaker.CircuitOpenError: Circuit is OPEN
```

**Solution**: Wait for cooldown or reset circuit breaker state in database.

#### 4. Tool Not Found

```
omoi_os.services.mcp_integration.ToolNotFoundError: Tool not found: server:tool
```

**Solution**: Register the tool first:
```python
registry.register_server(
    server_id="server",
    version="1.0.0",
    capabilities=["tools"],
    tools=[{"name": "tool", "schema": {}}]
)
```

### Debug Mode

Enable debug logging for MCP tests:

```python
# tests/conftest.py

import logging

def pytest_configure(config):
    """Configure logging for tests."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Set specific loggers to DEBUG
    logging.getLogger('omoi_os.services.mcp').setLevel(logging.DEBUG)
    logging.getLogger('fastmcp').setLevel(logging.DEBUG)
```

### Test Debugging Script

```python
# scripts/debug_mcp.py

import asyncio
import httpx

async def debug_mcp_connection():
    """Debug MCP server connection."""
    
    # Test health endpoint
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get("http://localhost:18000/health")
            print(f"Health check: {response.status_code}")
            print(f"Response: {response.text}")
        except Exception as e:
            print(f"Health check failed: {e}")
    
    # Test MCP endpoint
    try:
        response = await client.post(
            "http://localhost:18000/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": 1
            },
            headers={"Session-ID": "debug-session"}
        )
        print(f"\nMCP tools/list: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"MCP call failed: {e}")

if __name__ == "__main__":
    asyncio.run(debug_mcp_connection())
```

---

## Available Tools

See `docs/mcp/fastmcp_integration.md` for complete documentation on available MCP tools and their schemas.

### Core Tools

| Tool Name | Description | Test Example |
|-----------|-------------|--------------|
| `create_ticket` | Create a new ticket | `tests/integration/test_mcp_server_integration.py::test_create_ticket_tool` |
| `get_ticket` | Retrieve ticket by ID | `tests/integration/test_mcp_server_integration.py::test_get_ticket_tool` |
| `update_ticket` | Update ticket fields | `tests/integration/test_mcp_server_integration.py::test_update_ticket_tool` |
| `list_tickets` | List tickets with filters | `tests/integration/test_mcp_server_integration.py::test_list_tickets_tool` |
| `create_task` | Create a task for a ticket | `tests/integration/test_mcp_server_integration.py::test_create_task_tool` |
| `get_task` | Retrieve task by ID | `tests/integration/test_mcp_server_integration.py::test_get_task_tool` |

---

## Related Documentation

- FastMCP Integration Guide - Complete MCP integration documentation
- [MCP Server Architecture](../../docs/architecture/09-mcp-integration.md) - Architecture overview
- [Backend Testing Guide](../../backend/CLAUDE.md#testing-strategy) - General backend testing
- [FastMCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) - Official SDK documentation
- [MCP Specification](https://spec.modelcontextprotocol.io/) - Protocol specification

---

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2025-01-20 | Initial testing guide | @kivo360 |
| 2025-04-22 | Expanded with unit/integration patterns, mock strategies, CI config | Documentation Team |

---

**Last Updated**: 2025-04-22  
**Document Owner**: Backend Team  
**Review Cycle**: Monthly
