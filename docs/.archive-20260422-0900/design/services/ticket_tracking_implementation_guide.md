# Hephaestus Ticket Tracking — Implementation Guide (PostgreSQL + SQLAlchemy)

**Created:** 2025-11-20  
**Status:** Active  
**Source File:** `backend/omoi_os/ticketing/services/ticket_service.py`, `backend/omoi_os/ticketing/models.py`  
**Related Docs:** [Ticket Tracking PostgreSQL Design](./ticket_tracking_postgres.md), [Database Schema](../../architecture/11-database-schema.md), [Ticket Workflow](./ticket_workflow.md)

---

## 1. Architecture Overview

This guide provides step-by-step instructions for implementing and operating the Hephaestus Ticket Tracking System with PostgreSQL and SQLAlchemy. It covers setup, migration patterns, query optimization, and operational best practices.

### 1.1 Implementation Architecture

```mermaid
flowchart TB
    subgraph "Setup Phase"
        INIT[init_db.py]
        ENV[Environment Config]
        ALEMBIC[Alembic Migrations]
    end
    
    subgraph "Core Implementation"
        MODELS[SQLAlchemy Models]
        SERVICES[Service Layer]
        ROUTES[API Routes]
    end
    
    subgraph "Query Patterns"
        CRUD[CRUD Operations]
        SEARCH[Hybrid Search]
        HISTORY[Audit Logging]
        BLOCK[Blocker Management]
    end
    
    subgraph "Production Ops"
        INDEX[Index Management]
        BACKUP[Backup Strategy]
        MONITOR[Performance Monitoring]
    end
    
    ENV --> INIT
    INIT --> MODELS
    ALEMBIC --> MODELS
    MODELS --> SERVICES
    SERVICES --> ROUTES
    SERVICES --> CRUD
    SERVICES --> SEARCH
    SERVICES --> HISTORY
    SERVICES --> BLOCK
    CRUD --> INDEX
    SEARCH --> INDEX
    HISTORY --> BACKUP
    INDEX --> MONITOR
```

### 1.2 Module Structure

```
backend/omoi_os/ticketing/
├── __init__.py
├── models.py                    # SQLAlchemy declarative models
├── services/
│   ├── __init__.py
│   ├── ticket_service.py        # Core CRUD and lifecycle
│   ├── ticket_history_service.py # Audit trail operations
│   └── ticket_search_service.py # Hybrid search implementation
└── scripts/
    └── init_db.py               # Database initialization
```

---

## 2. Setup and Installation

### 2.1 Prerequisites

- PostgreSQL 14+ with pgvector extension
- Python 3.12+
- SQLAlchemy 2.x
- psycopg (psycopg3 driver)

### 2.2 Database Initialization

```python
# backend/omoi_os/ticketing/scripts/init_db.py
"""Initialize ticket tracking database schema."""

from sqlalchemy import create_engine
from omoi_os.ticketing.models import Base
from omoi_os.config import get_app_settings

def init_database():
    """Create all tables and indexes."""
    settings = get_app_settings()
    engine = create_engine(settings.database.url)
    
    # Create pgvector extension first
    with engine.connect() as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.commit()
    
    # Create all tables
    Base.metadata.create_all(engine)
    
    # Create additional indexes
    with engine.connect() as conn:
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_tickets_workflow_status 
            ON tickets(workflow_id, status)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_ticket_changed 
            ON ticket_history(ticket_id, changed_at)
        """)
        conn.commit()
    
    print("Database initialized successfully")

if __name__ == "__main__":
    init_database()
```

### 2.3 Environment Configuration

```python
# Environment variables (.env)
DB_HOST=localhost
DB_PORT=15432
DB_NAME=omoios
DB_USER=omoios
DB_PASSWORD=secure_password
DB_SSLMODE=prefer

# Optional: Qdrant for semantic search
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=optional_api_key

# Optional: Embedding configuration
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_DIM=1536
EMBEDDING_PROVIDER=openai
```

### 2.4 Connection Setup

```python
# Database session management
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from omoi_os.config import get_app_settings

# Create engine
settings = get_app_settings()
engine = create_engine(
    settings.database.url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Verify connections before use
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_session() -> Session:
    """Get database session."""
    return SessionLocal()

# Context manager for safe session handling
from contextlib import contextmanager

@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
```

---

## 3. Migration Patterns

### 3.1 Alembic Setup

```bash
# Initialize Alembic
cd backend
uv run alembic init migrations

# Create first migration
uv run alembic revision -m "create ticket tracking tables"
```

### 3.2 Migration Script Template

```python
# migrations/versions/001_create_ticket_tracking.py
"""Create ticket tracking tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = '001_ticket_tracking'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Create extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    
    # tickets table
    op.create_table(
        'tickets',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('workflow_id', sa.String(), index=True),
        sa.Column('created_by_agent_id', sa.String(), nullable=False),
        sa.Column('assigned_agent_id', sa.String(), nullable=True, index=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('ticket_type', sa.String(50), nullable=False, index=True),
        sa.Column('priority', sa.String(20), nullable=False, index=True),
        sa.Column('status', sa.String(50), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('parent_ticket_id', sa.String(), 
                  sa.ForeignKey('tickets.id'), nullable=True),
        sa.Column('related_task_ids', JSONB, nullable=True),
        sa.Column('related_ticket_ids', JSONB, nullable=True),
        sa.Column('tags', JSONB, nullable=True),
        sa.Column('embedding', JSONB, nullable=True),
        sa.Column('embedding_id', sa.String(), nullable=True),
        sa.Column('embedding_vector', sa.Vector(1536), nullable=True),
        sa.Column('blocked_by_ticket_ids', JSONB, nullable=True),
        sa.Column('is_resolved', sa.Boolean(), nullable=False, default=False, index=True),
    )
    
    # ticket_comments table
    op.create_table(
        'ticket_comments',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('ticket_id', sa.String(), 
                  sa.ForeignKey('tickets.id', ondelete='CASCADE'), 
                  index=True),
        sa.Column('agent_id', sa.String(), index=True),
        sa.Column('comment_text', sa.Text(), nullable=False),
        sa.Column('comment_type', sa.String(50), nullable=True),
        sa.Column('mentions', JSONB, nullable=True),
        sa.Column('attachments', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_edited', sa.Boolean(), nullable=False, default=False),
    )
    
    # ticket_history table
    op.create_table(
        'ticket_history',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('ticket_id', sa.String(),
                  sa.ForeignKey('tickets.id', ondelete='CASCADE'),
                  index=True),
        sa.Column('agent_id', sa.String(), index=True),
        sa.Column('change_type', sa.String(50), nullable=False, index=True),
        sa.Column('field_name', sa.String(100), nullable=True),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('change_description', sa.Text(), nullable=True),
        sa.Column('change_metadata', JSONB, nullable=True),
        sa.Column('changed_at', sa.DateTime(timezone=True), nullable=False, index=True),
    )
    
    # ticket_commits table
    op.create_table(
        'ticket_commits',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('ticket_id', sa.String(),
                  sa.ForeignKey('tickets.id', ondelete='CASCADE'),
                  index=True),
        sa.Column('agent_id', sa.String(), index=True),
        sa.Column('commit_sha', sa.String(64), nullable=False, index=True),
        sa.Column('commit_message', sa.Text(), nullable=False),
        sa.Column('commit_timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('files_changed', sa.Integer(), nullable=True),
        sa.Column('insertions', sa.Integer(), nullable=True),
        sa.Column('deletions', sa.Integer(), nullable=True),
        sa.Column('files_list', JSONB, nullable=True),
        sa.Column('linked_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('link_method', sa.String(50), nullable=True),
        sa.UniqueConstraint('ticket_id', 'commit_sha'),
    )
    
    # board_configs table
    op.create_table(
        'board_configs',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('workflow_id', sa.String(), unique=True, index=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('columns', JSONB, nullable=False),
        sa.Column('ticket_types', JSONB, nullable=False),
        sa.Column('default_ticket_type', sa.String(50), nullable=True),
        sa.Column('initial_status', sa.String(50), nullable=False),
        sa.Column('settings', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    
    # Additional indexes
    op.create_index('idx_tickets_workflow_status', 'tickets', 
                    ['workflow_id', 'status'])
    op.create_index('idx_history_ticket_changed', 'ticket_history',
                    ['ticket_id', 'changed_at'])

def downgrade():
    op.drop_table('ticket_commits')
    op.drop_table('ticket_history')
    op.drop_table('ticket_comments')
    op.drop_table('tickets')
    op.drop_table('board_configs')
```

### 3.3 Zero-Downtime Migration Strategy

```python
# migrations/versions/002_add_ticket_priority_index.py
"""Add index on priority for performance."""

from alembic import op

revision = '002_add_priority_index'
down_revision = '001_ticket_tracking'

def upgrade():
    # Create index concurrently (PostgreSQL 11+)
    # Note: Run outside transaction for CONCURRENTLY
    op.execute("COMMIT")  # End transaction
    op.execute("""
        CREATE INDEX CONCURRENTLY idx_tickets_priority 
        ON tickets(priority)
    """)

def downgrade():
    op.execute("COMMIT")
    op.execute("DROP INDEX CONCURRENTLY idx_tickets_priority")
```

---

## 4. Query Patterns

### 4.1 CRUD Operations

```python
# Create ticket with validation
def create_ticket_example(session: Session, workflow_id: str, agent_id: str):
    from omoi_os.ticketing.services.ticket_service import TicketService
    
    service = TicketService(session)
    
    result = service.create_ticket(
        workflow_id=workflow_id,
        agent_id=agent_id,
        title="Implement user authentication",
        description="Add JWT-based auth to the API",
        ticket_type="feature",
        priority="HIGH",
        initial_status=None,  # Uses board config default
        assigned_agent_id=None,
        parent_ticket_id=None,
        blocked_by_ticket_ids=[],
        tags=["auth", "api", "security"],
        related_task_ids=[],
    )
    
    return result["ticket_id"]

# Update with history tracking
def update_ticket_example(session: Session, ticket_id: str, agent_id: str):
    from omoi_os.ticketing.services.ticket_service import TicketService
    
    service = TicketService(session)
    
    result = service.update_ticket(
        ticket_id=ticket_id,
        agent_id=agent_id,
        updates={
            "priority": "CRITICAL",
            "assigned_agent_id": "agent-123"
        },
        update_comment="Escalating due to security concerns"
    )
    
    return result

# Status transition with blocker check
def change_status_example(session: Session, ticket_id: str, agent_id: str):
    from omoi_os.ticketing.services.ticket_service import TicketService
    
    service = TicketService(session)
    
    result = service.change_status(
        ticket_id=ticket_id,
        agent_id=agent_id,
        new_status="in_progress",
        comment="Starting implementation",
        commit_sha=None
    )
    
    if not result["success"] and result.get("blocked"):
        print(f"Blocked by: {result['blocking_ticket_ids']}")
    
    return result
```

### 4.2 Search Patterns

```python
# Keyword search
def keyword_search_example(session: Session, workflow_id: str):
    from omoi_os.ticketing.services.ticket_search_service import TicketSearchService
    
    service = TicketSearchService(session)
    
    results = service.search_by_keywords(
        keywords="authentication bug",
        workflow_id=workflow_id,
        filters={"status": "open"}
    )
    
    return results["results"]

# Hybrid search with RRF
def hybrid_search_example(session: Session, workflow_id: str):
    from omoi_os.ticketing.services.ticket_search_service import TicketSearchService
    
    service = TicketSearchService(session)
    
    results = service.hybrid_search(
        query_text="user login failing",
        workflow_id=workflow_id,
        limit=10,
        filters={"priority": "HIGH"},
        include_comments=True,
        semantic_weight=0.6,
        keyword_weight=0.4
    )
    
    # Results include RRF score
    for r in results["results"]:
        print(f"{r['ticket_id']}: {r['title']} (score: {r['relevance_score']:.3f})")
    
    return results
```

### 4.3 Blocker Management

```python
# Check if ticket is blocked
def is_blocked(session: Session, ticket_id: str) -> bool:
    from omoi_os.ticketing.models import Ticket
    
    ticket = session.get(Ticket, ticket_id)
    if not ticket:
        return False
    
    blocked_ids = (ticket.blocked_by_ticket_ids or {}).get("ids", [])
    return len(blocked_ids) > 0

# Resolve and unblock dependents
def resolve_and_unblock(session: Session, ticket_id: str, agent_id: str):
    from omoi_os.ticketing.services.ticket_service import TicketService
    
    service = TicketService(session)
    
    result = service.resolve_ticket(
        ticket_id=ticket_id,
        agent_id=agent_id,
        resolution_comment="Fixed in commit abc123",
        commit_sha="abc123"
    )
    
    if result["unblocked_tickets"]:
        print(f"Unblocked {len(result['unblocked_tickets'])} dependent tickets")
    
    return result
```

### 4.4 History and Audit

```python
# Get full ticket history
def get_ticket_timeline(session: Session, ticket_id: str):
    from omoi_os.ticketing.services.ticket_history_service import TicketHistoryService
    
    service = TicketHistoryService(session)
    
    history = service.get_ticket_history(ticket_id=ticket_id)
    
    # Group by change type
    grouped = {}
    for entry in history:
        ct = entry["change_type"]
        if ct not in grouped:
            grouped[ct] = []
        grouped[ct].append(entry)
    
    return grouped

# Record custom change
def record_custom_change(session: Session, ticket_id: str, agent_id: str):
    from omoi_os.ticketing.services.ticket_history_service import TicketHistoryService
    
    service = TicketHistoryService(session)
    
    service.record_change(
        ticket_id=ticket_id,
        agent_id=agent_id,
        change_type="security_review",
        old_value=None,
        new_value="approved",
        change_metadata={"reviewer": "security-team", "findings": []},
        field_name=None,
        change_description="Security review completed - no issues found"
    )
```

---

## 5. Service Implementation Guide

### 5.1 TicketService Implementation

```python
# backend/omoi_os/ticketing/services/ticket_service.py
from __future__ import annotations
from typing import Any, Optional
from uuid import uuid4
from omoi_os.utils.datetime import utc_now
from sqlalchemy import select
from sqlalchemy.orm import Session
from omoi_os.ticketing.models import (
    BoardConfig, Ticket, TicketComment, TicketCommit, TicketHistory
)

def _ticket_id() -> str:
    return f"ticket-{uuid4()}"

def _comment_id() -> str:
    return f"comment-{uuid4()}"

def _commit_id() -> str:
    return f"tc-{uuid4()}"

class TicketService:
    """Core ticket lifecycle management."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def create_ticket(
        self,
        *,
        workflow_id: str,
        agent_id: str,
        title: str,
        description: str,
        ticket_type: str,
        priority: str,
        initial_status: Optional[str],
        assigned_agent_id: Optional[str],
        parent_ticket_id: Optional[str],
        blocked_by_ticket_ids: list[str] | None,
        tags: list[str] | None,
        related_task_ids: list[str] | None,
    ) -> dict[str, Any]:
        """Create new ticket with board config validation."""
        # Validate board config
        board_cfg = self.session.scalar(
            select(BoardConfig).where(BoardConfig.workflow_id == workflow_id)
        )
        if not board_cfg:
            raise ValueError("Board configuration not found for workflow")
        
        status = initial_status or board_cfg.initial_status
        
        # Create ticket
        ticket = Ticket(
            id=_ticket_id(),
            workflow_id=workflow_id,
            created_by_agent_id=agent_id,
            assigned_agent_id=assigned_agent_id,
            title=title,
            description=description,
            ticket_type=ticket_type,
            priority=priority,
            status=status,
            parent_ticket_id=parent_ticket_id,
            related_task_ids={"ids": related_task_ids or []},
            related_ticket_ids=None,
            tags={"values": tags or []},
            blocked_by_ticket_ids={"ids": blocked_by_ticket_ids or []} if blocked_by_ticket_ids else None,
            created_at=utc_now(),
            updated_at=utc_now(),
            is_resolved=False,
        )
        
        self.session.add(ticket)
        
        # Record creation in history
        self.session.add(
            TicketHistory(
                ticket_id=ticket.id,
                agent_id=agent_id,
                change_type="created",
                field_name=None,
                old_value=None,
                new_value=None,
                change_description="Ticket created",
                change_metadata=None,
                changed_at=utc_now(),
            )
        )
        
        return {"success": True, "ticket_id": ticket.id, "status": ticket.status}
    
    # ... additional methods (update_ticket, change_status, etc.)
```

### 5.2 TicketSearchService Implementation

```python
# backend/omoi_os/ticketing/services/ticket_search_service.py
from __future__ import annotations
from typing import Any, Optional
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from omoi_os.ticketing.models import Ticket

class TicketSearchService:
    """Hybrid search combining semantic and keyword search."""
    
    def __init__(self, session: Session):
        self.session = session
    
    def semantic_search(
        self, *, query_text: str, workflow_id: str, limit: int, filters: Optional[dict]
    ) -> dict[str, Any]:
        """Placeholder for Qdrant semantic search."""
        # TODO: Integrate with Qdrant client
        return {"results": [], "total_found": 0}
    
    def search_by_keywords(
        self, *, keywords: str, workflow_id: str, filters: Optional[dict]
    ) -> dict[str, Any]:
        """Basic keyword search using ILIKE."""
        stmt = select(Ticket).where(Ticket.workflow_id == workflow_id)
        kw = f"%{keywords}%"
        stmt = stmt.where(or_(Ticket.title.ilike(kw), Ticket.description.ilike(kw)))
        
        rows = list(self.session.scalars(stmt.limit(50)))
        
        results = [
            {
                "ticket_id": t.id,
                "title": t.title,
                "description": t.description[:280],
                "status": t.status,
                "priority": t.priority,
                "ticket_type": t.ticket_type,
                "relevance_score": 0.5,
                "matched_in": ["title" if keywords.lower() in (t.title or "").lower() else "description"],
                "preview": (t.description or "")[:200],
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "assigned_agent_id": t.assigned_agent_id,
            }
            for t in rows
        ]
        
        return {"results": results, "total_found": len(results)}
    
    def hybrid_search(
        self,
        *,
        query_text: str,
        workflow_id: str,
        limit: int = 10,
        filters: Optional[dict] = None,
        include_comments: bool = True,
        semantic_weight: float = 0.6,
        keyword_weight: float = 0.4,
    ) -> dict[str, Any]:
        """Combine semantic and keyword using RRF."""
        # Run both searches
        sem = self.semantic_search(
            query_text=query_text,
            workflow_id=workflow_id,
            limit=limit * 2,
            filters=filters,
        )
        kw = self.search_by_keywords(
            keywords=query_text, workflow_id=workflow_id, filters=filters
        )
        
        # Merge using RRF
        merged = self._merge_results_rrf(
            sem.get("results", []),
            kw.get("results", []),
            semantic_weight,
            keyword_weight,
        )
        
        return {
            "success": True,
            "query": query_text,
            "results": merged[:limit],
            "total_found": len(merged),
        }
    
    def _merge_results_rrf(
        self,
        semantic_results: list[dict[str, Any]],
        keyword_results: list[dict[str, Any]],
        semantic_weight: float,
        keyword_weight: float,
    ) -> list[dict[str, Any]]:
        """Reciprocal Rank Fusion algorithm."""
        k = 60  # RRF constant
        
        # Create rank maps (1-indexed)
        semantic_ranks = {
            r.get("ticket_id"): idx + 1
            for idx, r in enumerate(semantic_results)
            if r.get("ticket_id")
        }
        keyword_ranks = {
            r.get("ticket_id"): idx + 1
            for idx, r in enumerate(keyword_results)
            if r.get("ticket_id")
        }
        
        all_ids = set(semantic_ranks.keys()) | set(keyword_ranks.keys())
        semantic_map = {r.get("ticket_id"): r for r in semantic_results if r.get("ticket_id")}
        keyword_map = {r.get("ticket_id"): r for r in keyword_results if r.get("ticket_id")}
        
        # Calculate combined scores
        combined = []
        for ticket_id in all_ids:
            sem_rank = semantic_ranks.get(ticket_id, len(semantic_results) + 10)
            kw_rank = keyword_ranks.get(ticket_id, len(keyword_results) + 10)
            
            rrf_score = semantic_weight * (1.0 / (k + sem_rank)) + keyword_weight * (1.0 / (k + kw_rank))
            
            result = semantic_map.get(ticket_id) or keyword_map.get(ticket_id)
            if result:
                merged = result.copy()
                merged["relevance_score"] = rrf_score
                merged["semantic_score"] = result.get("relevance_score") if ticket_id in semantic_map else None
                merged["keyword_score"] = result.get("relevance_score") if ticket_id in keyword_map else None
                combined.append(merged)
        
        # Sort by RRF score
        combined.sort(key=lambda x: x.get("relevance_score", 0.0), reverse=True)
        return combined
```

---

## 6. API Route Integration

### 6.1 FastAPI Routes

```python
# backend/omoi_os/api/routes/tickets.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from omoi_os.api.dependencies import get_db_session
from omoi_os.ticketing.services.ticket_service import TicketService
from omoi_os.ticketing.services.ticket_search_service import TicketSearchService

router = APIRouter(prefix="/tickets", tags=["tickets"])

@router.post("/")
def create_ticket(
    request: CreateTicketRequest,
    session: Session = Depends(get_db_session)
):
    """Create new ticket."""
    service = TicketService(session)
    try:
        result = service.create_ticket(
            workflow_id=request.workflow_id,
            agent_id=request.agent_id,
            title=request.title,
            description=request.description,
            ticket_type=request.ticket_type,
            priority=request.priority,
            initial_status=request.initial_status,
            assigned_agent_id=request.assigned_agent_id,
            parent_ticket_id=request.parent_ticket_id,
            blocked_by_ticket_ids=request.blocked_by_ticket_ids,
            tags=request.tags,
            related_task_ids=request.related_task_ids,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{ticket_id}/status")
def change_status(
    ticket_id: str,
    request: ChangeStatusRequest,
    session: Session = Depends(get_db_session)
):
    """Change ticket status."""
    service = TicketService(session)
    result = service.change_status(
        ticket_id=ticket_id,
        agent_id=request.agent_id,
        new_status=request.new_status,
        comment=request.comment,
        commit_sha=request.commit_sha,
    )
    if not result["success"] and result.get("blocked"):
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Ticket is blocked",
                "blocking_ticket_ids": result["blocking_ticket_ids"]
            }
        )
    return result

@router.post("/search")
def search_tickets(
    request: SearchRequest,
    session: Session = Depends(get_db_session)
):
    """Hybrid search tickets."""
    service = TicketSearchService(session)
    results = service.hybrid_search(
        query_text=request.query,
        workflow_id=request.workflow_id,
        limit=request.limit,
        filters=request.filters,
    )
    return results
```

---

## 7. Testing Strategy

### 7.1 Unit Tests

```python
# tests/unit/ticketing/test_ticket_service.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from omoi_os.ticketing.models import Base, BoardConfig
from omoi_os.ticketing.services.ticket_service import TicketService

@pytest.fixture
def session():
    engine = create_engine("postgresql://test:test@localhost/test")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Seed board config
    board = BoardConfig(
        id="board-1",
        workflow_id="wf-1",
        name="Test Board",
        columns={"backlog": {"name": "Backlog"}},
        ticket_types={"task": {"name": "Task"}},
        initial_status="backlog",
    )
    session.add(board)
    session.commit()
    
    yield session
    session.close()
    Base.metadata.drop_all(engine)

def test_create_ticket(session):
    service = TicketService(session)
    
    result = service.create_ticket(
        workflow_id="wf-1",
        agent_id="agent-1",
        title="Test Ticket",
        description="Test description",
        ticket_type="task",
        priority="MEDIUM",
        initial_status=None,
        assigned_agent_id=None,
        parent_ticket_id=None,
        blocked_by_ticket_ids=[],
        tags=["test"],
        related_task_ids=[],
    )
    
    assert result["success"] is True
    assert result["ticket_id"].startswith("ticket-")
    assert result["status"] == "backlog"

def test_blocked_ticket_cannot_change_status(session):
    service = TicketService(session)
    
    # Create blocker
    blocker = service.create_ticket(
        workflow_id="wf-1",
        agent_id="agent-1",
        title="Blocker",
        description="Blocking ticket",
        ticket_type="task",
        priority="HIGH",
        initial_status=None,
        assigned_agent_id=None,
        parent_ticket_id=None,
        blocked_by_ticket_ids=[],
        tags=[],
        related_task_ids=[],
    )
    
    # Create blocked ticket
    blocked = service.create_ticket(
        workflow_id="wf-1",
        agent_id="agent-1",
        title="Blocked",
        description="Blocked ticket",
        ticket_type="task",
        priority="MEDIUM",
        initial_status=None,
        assigned_agent_id=None,
        parent_ticket_id=None,
        blocked_by_ticket_ids=[blocker["ticket_id"]],
        tags=[],
        related_task_ids=[],
    )
    
    # Try to change status
    result = service.change_status(
        ticket_id=blocked["ticket_id"],
        agent_id="agent-1",
        new_status="in_progress",
        comment="Trying to start",
        commit_sha=None,
    )
    
    assert result["success"] is False
    assert result["blocked"] is True
```

### 7.2 Integration Tests

```python
# tests/integration/test_ticket_workflow.py
import pytest

@pytest.mark.integration
def test_full_ticket_lifecycle(client, db_session):
    """Test complete ticket lifecycle."""
    # Create
    response = client.post("/tickets/", json={
        "workflow_id": "wf-1",
        "agent_id": "agent-1",
        "title": "Feature Request",
        "description": "Add dark mode",
        "ticket_type": "feature",
        "priority": "MEDIUM"
    })
    assert response.status_code == 200
    ticket_id = response.json()["ticket_id"]
    
    # Update
    response = client.post(f"/tickets/{ticket_id}/update", json={
        "agent_id": "agent-1",
        "updates": {"priority": "HIGH"},
        "update_comment": "Customer escalation"
    })
    assert response.status_code == 200
    
    # Change status
    response = client.post(f"/tickets/{ticket_id}/status", json={
        "agent_id": "agent-1",
        "new_status": "in_progress",
        "comment": "Starting work"
    })
    assert response.status_code == 200
    
    # Resolve
    response = client.post(f"/tickets/{ticket_id}/resolve", json={
        "agent_id": "agent-1",
        "resolution_comment": "Implemented in PR #123",
        "commit_sha": "abc123"
    })
    assert response.status_code == 200
    assert response.json()["success"] is True
```

---

## 8. Operational Guide

### 8.1 Performance Monitoring

```sql
-- Check table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
FROM pg_tables
WHERE schemaname = 'public'
AND tablename LIKE 'ticket%'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Check index usage
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE tablename LIKE 'ticket%'
ORDER BY idx_scan DESC;

-- Slow queries
SELECT 
    query,
    mean_exec_time,
    calls,
    total_exec_time
FROM pg_stat_statements
WHERE query LIKE '%ticket%'
ORDER BY mean_exec_time DESC
LIMIT 10;
```

### 8.2 Backup and Recovery

```bash
# Full backup
pg_dump -h localhost -p 15432 -U omoios -d omoios > backup.sql

# Schema only
pg_dump -h localhost -p 15432 -U omoios -d omoios --schema-only > schema.sql

# Data only (specific tables)
pg_dump -h localhost -p 15432 -U omoios -d omoios \
    --data-only \
    --table=tickets \
    --table=ticket_history > tickets_data.sql

# Restore
psql -h localhost -p 15432 -U omoios -d omoios < backup.sql
```

### 8.3 Maintenance Tasks

```sql
-- Reindex (after bulk operations)
REINDEX INDEX CONCURRENTLY idx_tickets_workflow_status;

-- Analyze tables for query planner
ANALYZE tickets;
ANALYZE ticket_history;

-- Vacuum to reclaim space
VACUUM ANALYZE tickets;

-- Update statistics
SELECT pg_stat_reset();  -- Reset stats for fresh monitoring
```

---

## 9. Troubleshooting

### 9.1 Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Slow search | Missing indexes | Check idx_tickets_workflow_status exists |
| Connection errors | Pool exhaustion | Increase pool_size in engine config |
| Deadlocks | Concurrent updates | Use SELECT FOR UPDATE or retry logic |
| Large table size | History bloat | Archive old history or partition |
| pgvector errors | Extension not installed | Run `CREATE EXTENSION vector` |

### 9.2 Debug Queries

```sql
-- Find blocking queries
SELECT 
    blocked_locks.pid AS blocked_pid,
    blocked_activity.usename AS blocked_user,
    blocking_locks.pid AS blocking_pid,
    blocking_activity.usename AS blocking_user,
    blocked_activity.query AS blocked_statement,
    blocking_activity.query AS blocking_statement
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;

-- Check long-running queries
SELECT 
    pid,
    usename,
    query_start,
    now() - query_start AS duration,
    query
FROM pg_stat_activity
WHERE state = 'active'
AND query LIKE '%ticket%'
AND now() - query_start > interval '5 minutes';
```

---

## 10. Related Documentation

- [Ticket Tracking PostgreSQL Design](./ticket_tracking_postgres.md) - Complete design specification
- [Database Schema](../../architecture/11-database-schema.md) - Full database documentation
- [Ticket Workflow](./ticket_workflow.md) - Workflow orchestration
- [API Route Catalog](../../architecture/13-api-route-catalog.md) - HTTP endpoints
- [Configuration System](../../architecture/12-configuration-system.md) - Settings management

---

*Document Version: 2.0*  
*Last Updated: 2026-04-22*  
*Maintainer: OmoiOS Core Team*
