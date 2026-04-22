# Sandbox Agent Architecture

**Created**: 2025-12-12  
**Updated**: 2025-12-12  
**Status**: Design Document  
**Purpose**: Comprehensive architecture for spawning AI agents in sandboxed environments with real-time bidirectional communication

---

> **🎉 UPDATE (2025-12-12)**: Upon further codebase analysis, we discovered that **most of the WebSocket infrastructure already exists!**
> 
> **What's already built:**
> - ✅ `/api/v1/ws/events` WebSocket endpoint with filters
> - ✅ `WebSocketEventManager` with Redis pub/sub bridge
> - ✅ Frontend hooks: `useEvents()`, `useEntityEvents()`, `WebSocketProvider`
> - ✅ Full test coverage
>
> **What we actually need to build:**
> - ❌ Sandbox event callback endpoint (~2-3 hours)
> - ❌ Message injection endpoints (~4-6 hours)  
> - ❌ Worker script updates (~4 hours)
>
> **See **Sandbox System Gap Analysis** for the revised implementation plan.**

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [High-Level Architecture](#high-level-architecture)
3. [Component Deep-Dive](#component-deep-dive)
4. [Database Schema](#database-schema)
5. [API Endpoints](#api-endpoints)
6. [WebSocket Communication](#websocket-communication)
7. [Event Flow Diagrams](#event-flow-diagrams)
8. [SDK Comparison](#sdk-comparison)
9. [Implementation Plan](#implementation-plan)

---

## Executive Summary

This document describes the architecture for spawning AI coding agents (using **Claude Agent SDK**) inside isolated **Daytona Cloud sandboxes**, with **real-time bidirectional communication** via WebSockets that allows users to:

1. **See what's happening inside sandboxes** (file changes, commands, agent thoughts)
2. **Control conversations** (send messages, interrupt, provide guidance)
3. **Monitor progress** (task status, cost tracking, tool usage)
4. **Observe Guardian interventions** (when agents get stuck or drift)

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                   USER LAYER                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                         Next.js Frontend                                │   │
│   │                                                                         │   │
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │   │
│   │  │ Agent Spawn  │  │ Sandbox View │  │ Conversation │  │  Terminal  │  │   │
│   │  │    Panel     │  │   Monitor    │  │   Control    │  │   Output   │  │   │
│   │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └─────┬──────┘  │   │
│   │         │                 │                 │                │         │   │
│   │         └─────────────────┴─────────────────┴────────────────┘         │   │
│   │                                    │                                    │   │
│   │                              WebSocket + REST                           │   │
│   └────────────────────────────────────┼────────────────────────────────────┘   │
│                                        │                                        │
└────────────────────────────────────────┼────────────────────────────────────────┘
                                         │
┌────────────────────────────────────────┼────────────────────────────────────────┐
│                               ORCHESTRATION LAYER                               │
├────────────────────────────────────────┼────────────────────────────────────────┤
│                                        ▼                                        │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                        FastAPI Backend                                  │   │
│   │                                                                         │   │
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │   │
│   │  │  Sandbox     │  │  WebSocket   │  │   Guardian   │  │   Event    │  │   │
│   │  │  Spawner     │  │   Manager    │  │   Service    │  │    Bus     │  │   │
│   │  │  Service     │  │              │  │              │  │  (Redis)   │  │   │
│   │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └─────┬──────┘  │   │
│   │         │                 │                 │                │         │   │
│   │         │    ┌────────────┴─────────────────┴────────────────┘         │   │
│   │         │    │                                                         │   │
│   │  ┌──────┴────┴──────────────────────────────────────────────────────┐  │   │
│   │  │                    Sandbox Session Manager                        │  │   │
│   │  │                                                                   │  │   │
│   │  │  • Tracks active sandboxes (sandbox_id → connection info)        │  │   │
│   │  │  • Routes WebSocket messages to/from sandboxes                   │  │   │
│   │  │  • Manages conversation state                                     │  │   │
│   │  │  • Buffers events for reconnection                               │  │   │
│   │  └───────────────────────────────┬───────────────────────────────────┘  │   │
│   │                                  │                                      │   │
│   └──────────────────────────────────┼──────────────────────────────────────┘   │
│                                      │                                          │
│                          Daytona API │ + HTTP Callbacks                         │
│                                      │                                          │
└──────────────────────────────────────┼──────────────────────────────────────────┘
                                       │
┌──────────────────────────────────────┼──────────────────────────────────────────┐
│                               EXECUTION LAYER                                    │
├──────────────────────────────────────┼──────────────────────────────────────────┤
│                                      ▼                                          │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                      Daytona Cloud Sandbox                              │   │
│   │                                                                         │   │
│   │  ┌─────────────────────────────────────────────────────────────────┐   │   │
│   │  │                   Agent Runtime (Choice)                         │   │   │
│   │  │                                                                  │   │   │
│   │  │   ┌─────────────────────┐                                        │   │   │
│   │  │   │  Claude Agent SDK   │                                        │   │   │
│   │  │   │                     │                                        │   │   │
│   │  │   │ • ClaudeSDKClient   │                                        │   │   │
│   │  │   │ • @tool decorator   │                                        │   │   │
│   │  │   │ • Pre/PostToolUse   │                                        │   │   │
│   │  │   │ • Streaming msgs    │                                        │   │   │
│   │  │   └──────────┬──────────┘                                        │   │   │
│   │  │              │                                                    │   │   │
│   │  │                               │                                  │   │   │
│   │  └───────────────────────────────┼──────────────────────────────────┘   │   │
│   │                                  │                                      │   │
│   │                    ┌─────────────┴─────────────┐                        │   │
│   │                    │     Sandbox Worker        │                        │   │
│   │                    │                           │                        │   │
│   │                    │  • Fetches task from API  │                        │   │
│   │                    │  • Runs agent loop        │                        │   │
│   │                    │  • Reports events (HTTP)  │                        │   │
│   │                    │  • Receives messages      │                        │   │
│   │                    │  • Sends heartbeats       │                        │   │
│   │                    └─────────────┬─────────────┘                        │   │
│   │                                  │                                      │   │
│   │  ┌───────────────────────────────┼───────────────────────────────────┐  │   │
│   │  │                    Sandbox Filesystem                             │  │   │
│   │  │                                                                   │  │   │
│   │  │  /workspace/        ← Agent working directory                     │  │   │
│   │  │  /tmp/worker.log    ← Agent logs                                  │  │   │
│   │  │  /tmp/events/       ← Buffered events (if connection lost)        │  │   │
│   │  └───────────────────────────────────────────────────────────────────┘  │   │
│   │                                                                         │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Deep-Dive

### 1. Sandbox Session Manager

The **SandboxSessionManager** is the central hub that maintains live connections to sandboxes:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Sandbox Session Manager                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  In-Memory State:                                                           │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                                                                       │  │
│  │  sessions: Dict[sandbox_id, SandboxSession]                          │  │
│  │                                                                       │  │
│  │  SandboxSession:                                                      │  │
│  │    ├─ sandbox_id: str                                                │  │
│  │    ├─ task_id: str                                                   │  │
│  │    ├─ agent_id: str                                                  │  │
│  │    ├─ conversation_id: str                                           │  │
│  │    ├─ status: "creating" | "running" | "paused" | "completed"        │  │
│  │    ├─ created_at: datetime                                           │  │
│  │    ├─ last_event_at: datetime                                        │  │
│  │    ├─ event_buffer: List[SandboxEvent]  (for reconnection)           │  │
│  │    ├─ connected_clients: Set[WebSocket] (frontend connections)       │  │
│  │    └─ daytona_sandbox: DaytonaSandbox  (API handle)                  │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  WebSocket Subscriptions:                                                   │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                                                                       │  │
│  │  ws_connections: Dict[user_id, Set[WebSocket]]                       │  │
│  │  sandbox_subscriptions: Dict[sandbox_id, Set[WebSocket]]             │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2. Event Types

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            Sandbox Event Types                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  FROM SANDBOX → SERVER → FRONTEND:                                          │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                                                                       │  │
│  │  agent.started        - Agent began processing task                   │  │
│  │  agent.thinking       - Agent reasoning (extended thinking block)     │  │
│  │  agent.message        - Agent produced text response                  │  │
│  │  agent.tool_use       - Agent using a tool                           │  │
│  │  agent.tool_result    - Tool execution result                        │  │
│  │  agent.completed      - Agent finished task                          │  │
│  │  agent.error          - Agent encountered error                      │  │
│  │                                                                       │  │
│  │  file.created         - New file created in workspace                │  │
│  │  file.modified        - File content changed                         │  │
│  │  file.deleted         - File removed                                 │  │
│  │                                                                       │  │
│  │  command.started      - Shell command began                          │  │
│  │  command.output       - Command stdout/stderr (streaming)            │  │
│  │  command.completed    - Command finished with exit code              │  │
│  │                                                                       │  │
│  │  sandbox.heartbeat    - Health check                                 │  │
│  │  sandbox.metrics      - Cost, tokens, duration                       │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  FROM FRONTEND → SERVER → SANDBOX:                                          │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                                                                       │  │
│  │  user.message         - User sends message to agent                  │  │
│  │  user.interrupt       - Stop current operation                       │  │
│  │  user.guidance        - Provide hint/direction                       │  │
│  │  user.approve         - Approve pending action                       │  │
│  │  user.reject          - Reject pending action                        │  │
│  │                                                                       │  │
│  │  guardian.intervention - Guardian sends steering message             │  │
│  │                                                                       │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Sandbox Lifecycle State Machine

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SANDBOX STATE TRANSITIONS                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                              ┌────────────────────┐                         │
│                              │                    │                         │
│                              ▼                    │                         │
│  ┌──────────┐  spawn()  ┌──────────┐  ready   ┌──────────┐                  │
│  │ PENDING  │ ────────► │ CREATING │ ───────► │ RUNNING  │                  │
│  └──────────┘           └──────────┘          └──────────┘                  │
│       │                      │                     │  │                     │
│       │                      │ error               │  │ task_done           │
│       │                      ▼                     │  ▼                     │
│       │                ┌──────────┐                │ ┌──────────┐           │
│       │                │  FAILED  │ ◄──────────────┤ │COMPLETING│           │
│       │                └──────────┘   crash/       │ └──────────┘           │
│       │                      ▲        timeout      │      │                 │
│       │ cancel               │                     │      │ pr_created      │
│       │                      │                     │      ▼                 │
│       │                      │                     │ ┌──────────┐           │
│       └──────────────────────┴─────────────────────┴►│COMPLETED │           │
│                                                      └──────────┘           │
│                                                           │                 │
│                                                           │ cleanup         │
│                                                           ▼                 │
│                                                      ┌──────────┐           │
│                                                      │TERMINATED│           │
│                                                      └──────────┘           │
│                                                                             │
│  TRANSITION TRIGGERS:                                                       │
│  ────────────────────                                                       │
│  PENDING → CREATING    : DaytonaSpawnerService.spawn_sandbox() called       │
│  CREATING → RUNNING    : Worker script starts, registers conversation       │
│  CREATING → FAILED     : Daytona API error, provision timeout (5 min)       │
│  RUNNING → COMPLETING  : Agent calls update_task_status(done)               │
│  RUNNING → FAILED      : Agent crash, heartbeat timeout (60s), Guardian     │
│  COMPLETING → COMPLETED: PR created, branch pushed                          │
│  COMPLETING → FAILED   : GitHub API error, merge conflicts                  │
│  * → TERMINATED        : Cleanup after completion or manual termination     │
│                                                                             │
│  STATUS FIELD VALUES:                                                       │
│  ────────────────────                                                       │
│  'pending'    - Task queued, sandbox not yet requested                      │
│  'creating'   - Daytona sandbox provisioning in progress                    │
│  'running'    - Agent actively working in sandbox                           │
│  'completing' - Agent done, PR/commit in progress                           │
│  'completed'  - All work done, PR created                                   │
│  'failed'     - Error occurred, see error_message                           │
│  'terminated' - Sandbox destroyed (normal cleanup or forced)                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Database Schema

### New Tables

```sql
-- Tracks sandbox instances
CREATE TABLE sandbox_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sandbox_id VARCHAR(255) UNIQUE NOT NULL,
    task_id UUID REFERENCES tasks(id),
    agent_id UUID REFERENCES agents(id),
    conversation_id VARCHAR(255),
    
    -- Runtime configuration
    runtime VARCHAR(50) NOT NULL DEFAULT 'claude',  -- 'claude'
    status VARCHAR(50) NOT NULL DEFAULT 'creating',    -- creating | running | paused | completed | failed | terminated
    
    -- Daytona metadata
    daytona_sandbox_id VARCHAR(255),
    preview_url VARCHAR(512),
    
    -- Timing
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    last_heartbeat_at TIMESTAMP WITH TIME ZONE,
    
    -- Metrics
    total_cost_usd DECIMAL(10, 6) DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    tool_calls_count INTEGER DEFAULT 0,
    
    -- Error handling
    error_message TEXT,
    retry_count INTEGER DEFAULT 0
);

-- Stores events from sandboxes for audit/replay
CREATE TABLE sandbox_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sandbox_id VARCHAR(255) NOT NULL REFERENCES sandbox_sessions(sandbox_id),
    
    -- Event details
    event_type VARCHAR(100) NOT NULL,
    event_data JSONB NOT NULL,
    
    -- Source
    source VARCHAR(50) NOT NULL,  -- 'agent' | 'user' | 'guardian' | 'system'
    
    -- Timing
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Indexing
    sequence_number SERIAL
);

-- Index for fast event retrieval
CREATE INDEX idx_sandbox_events_sandbox_id ON sandbox_events(sandbox_id);
CREATE INDEX idx_sandbox_events_created_at ON sandbox_events(created_at);
CREATE INDEX idx_sandbox_events_type ON sandbox_events(event_type);

-- Stores file snapshots for "see what's inside sandbox"
CREATE TABLE sandbox_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sandbox_id VARCHAR(255) NOT NULL REFERENCES sandbox_sessions(sandbox_id),
    
    file_path VARCHAR(1024) NOT NULL,
    file_content TEXT,
    file_size_bytes INTEGER,
    file_hash VARCHAR(64),  -- SHA-256 for change detection
    
    -- Metadata
    is_directory BOOLEAN DEFAULT FALSE,
    last_modified_at TIMESTAMP WITH TIME ZONE,
    
    -- Snapshotting
    snapshot_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(sandbox_id, file_path, snapshot_at)
);

-- Active WebSocket connections (for multi-server scaling)
CREATE TABLE sandbox_ws_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sandbox_id VARCHAR(255) NOT NULL REFERENCES sandbox_sessions(sandbox_id),
    user_id UUID REFERENCES users(id),
    
    -- Connection metadata
    connection_id VARCHAR(255) NOT NULL,
    server_instance VARCHAR(255),  -- For load balancing
    connected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_ping_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│     tasks       │       │     agents      │       │     users       │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id (PK)         │       │ id (PK)         │       │ id (PK)         │
│ description     │       │ agent_type      │       │ email           │
│ phase_id        │       │ status          │       │ ...             │
│ status          │       │ ...             │       └────────┬────────┘
└────────┬────────┘       └────────┬────────┘                │
         │                         │                         │
         │    ┌────────────────────┴─────────────────────────┘
         │    │
         ▼    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        sandbox_sessions                             │
├─────────────────────────────────────────────────────────────────────┤
│ id (PK)                                                             │
│ sandbox_id (UNIQUE)                                                 │
│ task_id (FK → tasks)                                                │
│ agent_id (FK → agents)                                              │
│ conversation_id                                                     │
│ runtime ('claude')                                                   │
│ status                                                              │
│ daytona_sandbox_id                                                  │
│ preview_url                                                         │
│ total_cost_usd, total_tokens, tool_calls_count                      │
│ created_at, started_at, completed_at, last_heartbeat_at             │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
           ┌──────────────────┼──────────────────┐
           │                  │                  │
           ▼                  ▼                  ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐
│ sandbox_events  │  │ sandbox_files   │  │ sandbox_ws_connections  │
├─────────────────┤  ├─────────────────┤  ├─────────────────────────┤
│ id (PK)         │  │ id (PK)         │  │ id (PK)                 │
│ sandbox_id (FK) │  │ sandbox_id (FK) │  │ sandbox_id (FK)         │
│ event_type      │  │ file_path       │  │ user_id (FK)            │
│ event_data      │  │ file_content    │  │ connection_id           │
│ source          │  │ file_hash       │  │ server_instance         │
│ created_at      │  │ snapshot_at     │  │ connected_at            │
└─────────────────┘  └─────────────────┘  └─────────────────────────┘
```

---

## API Endpoints

### Sandbox Management

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Sandbox API Endpoints                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  POST /api/v1/sandboxes                                                     │
│  ├─ Description: Spawn a new sandbox for a task                            │
│  ├─ Body: {                                                                 │
│  │     task_id: string,                                                    │
│  │     runtime: "claude",                                                  │
│  │     agent_type?: string,                                                │
│  │     env?: Record<string, string>                                        │
│  │  }                                                                       │
│  └─ Response: { sandbox_id, status, preview_url }                          │
│                                                                             │
│  GET /api/v1/sandboxes                                                      │
│  ├─ Description: List all active sandboxes                                 │
│  ├─ Query: ?status=running&task_id=xxx                                     │
│  └─ Response: { sandboxes: SandboxSession[] }                              │
│                                                                             │
│  GET /api/v1/sandboxes/{sandbox_id}                                         │
│  ├─ Description: Get sandbox details                                       │
│  └─ Response: { sandbox: SandboxSession, recent_events: Event[] }          │
│                                                                             │
│  DELETE /api/v1/sandboxes/{sandbox_id}                                      │
│  ├─ Description: Terminate a sandbox                                       │
│  └─ Response: { status: "terminated" }                                     │
│                                                                             │
│  POST /api/v1/sandboxes/{sandbox_id}/pause                                  │
│  ├─ Description: Pause agent execution                                     │
│  └─ Response: { status: "paused" }                                         │
│                                                                             │
│  POST /api/v1/sandboxes/{sandbox_id}/resume                                 │
│  ├─ Description: Resume paused agent                                       │
│  └─ Response: { status: "running" }                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Sandbox Events & Files

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Sandbox Events & Files Endpoints                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  GET /api/v1/sandboxes/{sandbox_id}/events                                  │
│  ├─ Description: Get historical events                                     │
│  ├─ Query: ?limit=50&since=timestamp&type=agent.tool_use                   │
│  └─ Response: { events: SandboxEvent[] }                                   │
│                                                                             │
│  POST /api/v1/sandboxes/{sandbox_id}/events                                 │
│  ├─ Description: Send event to sandbox (user message, interrupt)           │
│  ├─ Body: {                                                                 │
│  │     event_type: "user.message" | "user.interrupt" | ...,                │
│  │     event_data: { content: string, ... }                                │
│  │  }                                                                       │
│  └─ Response: { event_id, status }                                         │
│                                                                             │
│  GET /api/v1/sandboxes/{sandbox_id}/files                                   │
│  ├─ Description: List files in sandbox workspace                           │
│  ├─ Query: ?path=/workspace&recursive=true                                 │
│  └─ Response: { files: FileInfo[] }                                        │
│                                                                             │
│  GET /api/v1/sandboxes/{sandbox_id}/files/{path}                            │
│  ├─ Description: Get file content                                          │
│  └─ Response: { content: string, size: number, hash: string }              │
│                                                                             │
│  GET /api/v1/sandboxes/{sandbox_id}/terminal                                │
│  ├─ Description: Get recent terminal output                                │
│  ├─ Query: ?lines=100                                                      │
│  └─ Response: { output: string, timestamp: string }                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## WebSocket Communication

### WebSocket Endpoint

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         WebSocket Architecture                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Endpoint: ws://api.omoios.dev/ws/sandboxes/{sandbox_id}                   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Connection Lifecycle                            │   │
│  │                                                                     │   │
│  │  1. Client connects with JWT token in query param:                  │   │
│  │     ws://api.omoios.dev/ws/sandboxes/sb-123?token=eyJ...            │   │
│  │                                                                     │   │
│  │  2. Server authenticates, subscribes to sandbox events              │   │
│  │                                                                     │   │
│  │  3. Server sends buffered events (if reconnecting)                  │   │
│  │                                                                     │   │
│  │  4. Bidirectional messages flow                                     │   │
│  │                                                                     │   │
│  │  5. Heartbeat every 30s to keep alive                              │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      Message Format                                 │   │
│  │                                                                     │   │
│  │  Server → Client:                                                   │   │
│  │  {                                                                  │   │
│  │    "type": "event",                                                 │   │
│  │    "event_type": "agent.tool_use",                                  │   │
│  │    "sandbox_id": "sb-123",                                          │   │
│  │    "timestamp": "2025-12-12T16:30:00Z",                             │   │
│  │    "data": {                                                        │   │
│  │      "tool_name": "Bash",                                           │   │
│  │      "tool_input": { "command": "npm install" },                    │   │
│  │      "status": "running"                                            │   │
│  │    }                                                                │   │
│  │  }                                                                  │   │
│  │                                                                     │   │
│  │  Client → Server:                                                   │   │
│  │  {                                                                  │   │
│  │    "type": "command",                                               │   │
│  │    "command": "send_message",                                       │   │
│  │    "payload": {                                                     │   │
│  │      "content": "Try using async/await instead"                     │   │
│  │    }                                                                │   │
│  │  }                                                                  │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### WebSocket Message Types

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    WebSocket Server → Client Messages                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  { type: "connected", sandbox_id, status, buffered_events_count }          │
│  { type: "event", event_type: "agent.*", data: {...} }                     │
│  { type: "event", event_type: "file.*", data: { path, action, diff } }     │
│  { type: "event", event_type: "command.*", data: { command, output } }     │
│  { type: "event", event_type: "sandbox.*", data: { metrics, status } }     │
│  { type: "heartbeat", timestamp }                                          │
│  { type: "error", code, message }                                          │
│                                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                    WebSocket Client → Server Messages                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  { type: "command", command: "send_message", payload: { content } }        │
│  { type: "command", command: "interrupt" }                                 │
│  { type: "command", command: "pause" }                                     │
│  { type: "command", command: "resume" }                                    │
│  { type: "command", command: "request_files", payload: { path } }          │
│  { type: "command", command: "request_terminal" }                          │
│  { type: "ping" }                                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Event Flow Diagrams

### 1. Spawn Sandbox Flow

```
┌──────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐
│ Frontend │      │  API     │      │ Spawner  │      │ Daytona  │      │ Sandbox  │
│          │      │  Server  │      │ Service  │      │   API    │      │ Worker   │
└────┬─────┘      └────┬─────┘      └────┬─────┘      └────┬─────┘      └────┬─────┘
     │                 │                 │                 │                 │
     │ POST /sandboxes │                 │                 │                 │
     │ {task_id, ...}  │                 │                 │                 │
     │────────────────>│                 │                 │                 │
     │                 │                 │                 │                 │
     │                 │ spawn_for_task()│                 │                 │
     │                 │────────────────>│                 │                 │
     │                 │                 │                 │                 │
     │                 │                 │ CREATE sandbox  │                 │
     │                 │                 │────────────────>│                 │
     │                 │                 │                 │                 │
     │                 │                 │  sandbox_id +   │                 │
     │                 │                 │  preview_url    │                 │
     │                 │                 │<────────────────│                 │
     │                 │                 │                 │                 │
     │                 │                 │           Upload worker script    │
     │                 │                 │───────────────────────────────────│
     │                 │                 │                 │                 │
     │                 │                 │           Set env vars + start    │
     │                 │                 │───────────────────────────────────│
     │                 │                 │                 │                 │
     │                 │  sandbox_id     │                 │                 │
     │                 │<────────────────│                 │                 │
     │                 │                 │                 │                 │
     │ {sandbox_id,    │                 │                 │                 │
     │  status,        │                 │                 │                 │
     │  preview_url}   │                 │                 │                 │
     │<────────────────│                 │                 │                 │
     │                 │                 │                 │                 │
     │                 │                 │                 │   Worker boots  │
     │                 │                 │                 │   & registers   │
     │                 │                 │   ←─────────────│────────────────>│
     │                 │                 │                 │                 │
     │ WS: connected   │ Event: sandbox.started           │                 │
     │<═══════════════════════════════════════════════════│                 │
     │                 │                 │                 │                 │
```

### 2. Real-Time Event Flow

```
┌──────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐
│ Frontend │      │    WS    │      │  Event   │      │ Sandbox  │
│          │      │ Manager  │      │   Bus    │      │ Worker   │
└────┬─────┘      └────┬─────┘      └────┬─────┘      └────┬─────┘
     │                 │                 │                 │
     │                 │                 │  Agent uses     │
     │                 │                 │  Bash tool      │
     │                 │                 │<────────────────│
     │                 │                 │                 │
     │                 │  Publish:       │                 │
     │                 │  agent.tool_use │                 │
     │                 │<────────────────│                 │
     │                 │                 │                 │
     │ WS Event:       │                 │                 │
     │ {type: "event", │                 │                 │
     │  event_type:    │                 │                 │
     │  "agent.tool_use"│                │                 │
     │  data: {...}}   │                 │                 │
     │<════════════════│                 │                 │
     │                 │                 │                 │
     │ UI Updates:     │                 │                 │
     │ - Tool panel    │                 │                 │
     │ - Activity log  │                 │                 │
     │                 │                 │                 │
     │                 │                 │  Command output │
     │                 │                 │  (streaming)    │
     │                 │                 │<────────────────│
     │                 │                 │                 │
     │ WS: command.output               │                 │
     │<══════════════════════════════════│                 │
     │                 │                 │                 │
     │ Terminal view   │                 │                 │
     │ updates live    │                 │                 │
     │                 │                 │                 │
```

### 3. User Sends Message to Agent

```
┌──────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐
│ Frontend │      │    WS    │      │ Sandbox  │      │  Agent   │
│          │      │ Manager  │      │ Worker   │      │ Runtime  │
└────┬─────┘      └────┬─────┘      └────┬─────┘      └────┬─────┘
     │                 │                 │                 │
     │ WS: {type:      │                 │                 │
     │  "command",     │                 │                 │
     │  command:       │                 │                 │
     │  "send_message" │                 │                 │
     │  payload: {...}}│                 │                 │
     │════════════════>│                 │                 │
     │                 │                 │                 │
     │                 │ HTTP POST       │                 │
     │                 │ /sandbox-input  │                 │
     │                 │────────────────>│                 │
     │                 │                 │                 │
     │                 │                 │ Inject into     │
     │                 │                 │ conversation    │
     │                 │                 │────────────────>│
     │                 │                 │                 │
     │                 │                 │                 │ Agent
     │                 │                 │                 │ responds
     │                 │                 │                 │
     │                 │                 │ agent.message   │
     │                 │                 │<────────────────│
     │                 │                 │                 │
     │ WS: agent.message                │                 │
     │<════════════════│<────────────────│                 │
     │                 │                 │                 │
```

### 4. Guardian Intervention Flow

> **⚠️ IMPORTANT**: The Guardian has TWO intervention paths depending on agent execution mode:
> - **Sandbox Mode**: Uses HTTP message injection API
> - **Legacy Mode**: Uses local filesystem via `ConversationInterventionService`

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     GUARDIAN INTERVENTION FLOW (UPDATED)                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Guardian Service                                                           │
│       │                                                                     │
│       │ Monitoring loop detects:                                           │
│       │ - Agent drift                                                      │
│       │ - Stuck state                                                      │
│       │ - Off-track trajectory                                             │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  execute_steering_intervention(intervention, task)                  │   │
│  │                                                                     │   │
│  │       ┌───────────────────────────────────────────────────────┐    │   │
│  │       │   Is task.sandbox_id present?                         │    │   │
│  │       └───────────────────┬───────────────────────────────────┘    │   │
│  │                           │                                        │   │
│  │              YES ─────────┼───────── NO                            │   │
│  │                           │                                        │   │
│  │    ┌──────────────────────┴──────────────────────┐                 │   │
│  │    │                      │                      │                 │   │
│  │    ▼                      │                      ▼                 │   │
│  │  SANDBOX PATH             │             LEGACY PATH                │   │
│  │  ────────────             │             ────────────               │   │
│  │  POST /api/v1/sandboxes   │             ConversationIntervention   │   │
│  │    /{sandbox_id}/messages │             Service.send_intervention() │   │
│  │                           │                      │                 │   │
│  │  Body:                    │             Uses:                      │   │
│  │  {                        │             - task.conversation_id     │   │
│  │    "content": "...",      │             - task.persistence_dir     │   │
│  │    "message_type":        │               (LOCAL filesystem)       │   │
│  │      "guardian_           │                      │                 │   │
│  │       intervention"       │                      │                 │   │
│  │  }                        │                      │                 │   │
│  │         │                 │                      │                 │   │
│  │         ▼                 │                      ▼                 │   │
│  │  Worker polls             │             Claude Agent SDK            │   │
│  │  GET /messages            │             client receives message     │   │
│  │  and receives it          │             and processes it             │   │
│  │                           │                                        │   │
│  └───────────────────────────┴────────────────────────────────────────┘   │
│                                                                             │
│  BOTH PATHS:                                                               │
│  ───────────                                                               │
│  • Agent receives intervention message                                     │
│  • Agent course-corrects behavior                                         │
│  • Event published for frontend visibility                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Sequence Diagram (Sandbox Mode)**:

```
┌──────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐
│ Guardian │      │  HTTP    │      │ Sandbox  │      │  Agent   │
│ Service  │      │   API    │      │ Worker   │      │ Runtime  │
└────┬─────┘      └────┬─────┘      └────┬─────┘      └────┬─────┘
     │                 │                 │                 │
     │ Monitoring loop │                 │                 │
     │ detects drift   │                 │                 │
     │                 │                 │                 │
     │ _is_sandbox_task() → TRUE        │                 │
     │                 │                 │                 │
     │ POST /sandboxes/{id}/messages    │                 │
     │ {type: "guardian_intervention"}  │                 │
     │────────────────>│                 │                 │
     │                 │                 │                 │
     │                 │ Queue message   │                 │
     │                 │                 │                 │
     │                 │                 │ Poll GET        │
     │                 │                 │ /messages       │
     │                 │<────────────────│                 │
     │                 │                 │                 │
     │                 │ Return messages │                 │
     │                 │────────────────>│                 │
     │                 │                 │                 │
     │                 │                 │ Inject as       │
     │                 │                 │ system msg      │
     │                 │                 │────────────────>│
     │                 │                 │                 │
     │                 │                 │                 │ Agent
     │                 │                 │                 │ course-
     │                 │                 │                 │ corrects
     │                 │                 │                 │
```

### 5. Hook-Based Intervention Architecture

> **🚀 Performance Enhancement**: This pattern reduces intervention latency from seconds to milliseconds.

**Current (Polling-Based) vs. Proposed (Hook-Based):**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│             INTERVENTION INJECTION: POLLING vs HOOK-BASED                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  POLLING-BASED (Current):                                                   │
│  ────────────────────────                                                   │
│  Guardian enqueues → Worker finishes turn → Polls → Gets message → Injects │
│                                          ↑                                   │
│                                   DELAY (seconds)                           │
│                                                                             │
│  HOOK-BASED (Proposed):                                                     │
│  ──────────────────────                                                     │
│  Guardian enqueues → Poll loop detects → client.query(message) → New turn  │
│                                       ↑                                      │
│                              ~500ms polling interval                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**SDK-Specific Implementation:**

| SDK | Message Injection | Latency | Pattern |
|-----|-------------------|---------|---------|
| Claude Agent SDK | `client.query(new_message)` | ~500ms | Multi-turn conversation |

**Worker Script Multi-Turn Pattern (Claude SDK - CORRECTED):**

```python
# FIXED: Multi-turn pattern matching Claude Code web behavior
async with ClaudeSDKClient(options=options) as client:
    # Start with initial task
    await client.query(task_description)
    
    # Stream messages indefinitely (not receive_response which stops at ResultMessage)
    async def message_stream():
        async for msg in client.receive_messages():  # Indefinite streaming
            # Map SDK messages to events
            if isinstance(msg, AssistantMessage):
                # Process text, tool use, thinking blocks...
                pass
    
    # Poll for interventions and inject as NEW USER MESSAGES
    async def intervention_handler():
        while True:
            messages = await poll_messages()
            if messages:
                for msg in messages:
                    # Real message injection: call client.query() with new message
                    await client.query(msg["content"])  # ← Like Claude Code web
    
    # Run both concurrently
    await asyncio.gather(message_stream(), intervention_handler())
```

**Key Fix**: Hooks cannot inject messages. Real injection requires `client.query(new_message)`.


---

## SDK Comparison

> **SDK Documentation References:**
> - **Claude Agent SDK**: `docs/libraries/claude-agent-sdk-python-clean.md`
>   - GitHub: https://github.com/anthropics/claude-agent-sdk-python
### Claude Agent SDK

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Claude Agent SDK Features                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ARCHITECTURE:                                                              │  │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ ClaudeSDKClient                                                    │   │
│  │   └── Claude CLI                                                   │   │
│  │       └── Tool Use                                                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  STREAMING:                                                                 │
│  • async for in receive_*()                                                 │
│  • StreamEvent messages                                                     │
│  • Partial message updates                                                 │
│                                                                             │
│  HOOKS:                                                                     │
│  • PreToolUse (modify tool execution, NOT message injection)               │
│  • PostToolUse (track tool usage)                                          │
│  • can_use_tool callback (permission control)                               │
│  NOTE: Hooks cannot inject new user messages - use client.query() instead  │
│                                                                             │
│  TOOLS:                                                                     │
│  • @tool decorator                                                          │
│  • create_sdk_mcp_server()                                                  │
│  • mcp_servers={} option                                                    │
│                                                                             │
│  CONVERSATION CONTROL:                                                      │
│  • client.query(message) - Send new user message (for message injection)  │
│  • client.receive_messages() - Stream indefinitely (not receive_response) │
│  • client.interrupt() - Stop current operation                             │
│  • Multi-turn sessions - Maintain conversation state                       │
│                                                                             │
│  COST TRACKING:                                                             │
│  • max_budget_usd option                                                    │
│  • ResultMessage.total_cost_usd                                             │
│                                                                             │
│  SETUP:                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ options = ClaudeAgentOptions(...)                                   │   │
│  │ client = ClaudeSDKClient(options)                                   │   │
│  │ client.query(prompt)                                                │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Plan

> **⚠️ REVISED**: The original 4-week plan has been significantly reduced since we discovered 
> the existing WebSocket infrastructure. See **Gap Analysis** for details.

### ~~Phase 1: Core Infrastructure (Week 1)~~ → Mostly Exists!

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Phase 1: REVISED - Minimal New Work                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ✅ ALREADY EXISTS:                                                         │
│      ✓ DaytonaSpawnerService with in-memory tracking                       │
│      ✓ EventBusService with Redis pub/sub                                  │
│      ✓ WebSocketEventManager with filters                                  │
│                                                                             │
│  ❌ STILL NEEDED (2-3 hours):                                               │
│      □ POST /api/v1/sandboxes/{id}/events (event callback)                 │
│                                                                             │
│  ⏳ OPTIONAL (can defer):                                                   │
│      □ Database persistence for sandbox_sessions                           │
│      □ Database persistence for sandbox_events (audit trail)               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### ~~Phase 2: WebSocket Layer (Week 2)~~ → Already Exists!

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     Phase 2: NOTHING TO BUILD!                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ✅ ALREADY EXISTS in backend/omoi_os/api/routes/events.py:                 │
│      ✓ WebSocket endpoint: /api/v1/ws/events                               │
│      ✓ WebSocketEventManager class                                         │
│      ✓ Redis Pub/Sub listener (pattern: events.*)                          │
│      ✓ Filter by event_types, entity_types, entity_ids                     │
│      ✓ Dynamic subscription via WebSocket messages                         │
│      ✓ Ping/keepalive every 30s                                            │
│                                                                             │
│  ✅ ALREADY EXISTS in frontend/hooks/useEvents.ts:                          │
│      ✓ useEvents() hook with filters                                       │
│      ✓ useEntityEvents(entityType, entityId) hook                          │
│      ✓ useEventTypes(eventTypes) hook                                      │
│      ✓ Auto-reconnection                                                   │
│      ✓ Event buffer (max 100)                                              │
│                                                                             │
│  ✅ ALREADY EXISTS in frontend/providers/WebSocketProvider.tsx:             │
│      ✓ WebSocketProvider context                                           │
│      ✓ useWebSocket() hook                                                 │
│      ✓ Reconnection with backoff                                           │
│                                                                             │
│  HOW TO USE:                                                                │
│      Backend: event_bus.publish(SystemEvent(                               │
│          entity_type="sandbox", entity_id=sandbox_id, ...                  │
│      ))                                                                     │
│      Frontend: useEntityEvents("sandbox", sandboxId)                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Phase 3: Message Injection (4-6 hours)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Phase 3: Message Injection                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  3.1 Message Queue Endpoints (NEW)                                          │
│      □ POST /api/v1/sandboxes/{id}/messages (queue message)                │
│      □ GET /api/v1/sandboxes/{id}/messages (worker polls)                  │
│                                                                             │
│  3.2 Worker Polling                                                         │
│      □ Worker polls for messages after each agent turn                     │
│      □ Handle interrupt commands                                           │
│      □ Inject user messages into conversation                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Phase 4: Worker Script Updates (4 hours)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      Phase 4: Worker Script Updates                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  4.1 Event Reporting                                                        │
│      □ POST events to /sandboxes/{id}/events (not tasks endpoint)          │
│      □ Report tool_use, thinking, message events                           │
│                                                                             │
│  4.2 Message Polling                                                        │
│      □ Poll GET /sandboxes/{id}/messages after agent turns                 │
│      □ Handle interrupt command                                            │
│      □ Inject user messages into agent                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Phase 5: Frontend UI (Optional - Separate Task)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Phase 5: Frontend UI (Optional)                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Once the backend is working, frontend just uses existing hooks:            │
│                                                                             │
│  const { events } = useEntityEvents("sandbox", sandboxId)                  │
│                                                                             │
│  UI Components (can build incrementally):                                   │
│      □ Real-time agent activity view                                        │
│      □ Message input box                                                    │
│      □ Interrupt button                                                     │
│      □ File tree view (via sandbox API)                                    │
│      □ Terminal output view                                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Summary

This architecture enables:

1. **Real-time visibility** into sandbox agent execution via WebSockets
2. **Bidirectional control** - users can send messages, interrupt, guide agents
3. **SDK integration** - using Claude Agent SDK
4. **Scalability** - Redis Pub/Sub for multi-server deployments
5. **Audit trail** - all events stored in database for replay
6. **Guardian integration** - interventions flow through the same event system

### Revised Timeline

| Original Plan | Revised Plan |
|---------------|--------------|
| Phase 1: 1 week | ~~Exists~~ + 2-3 hours |
| Phase 2: 1 week | ~~Exists~~ (0 hours) |
| Phase 3: 1 week | 4-6 hours |
| Phase 4: 1 week | 4 hours |
| **Total: 4 weeks** | **Total: 14-19 hours** |

---

## Related Documents

- ****Sandbox System Gap Analysis**** ← **Start here for implementation**
- [Product Vision](../../product_vision.md)
- [Architecture Comparison](../../architecture/services/architecture_comparison_current_vs_target.md)
- [Workspace Isolation System](../agents/workspace_isolation_system.md)
- [Daytona Spawner Service](../../backend/omoi_os/services/daytona_spawner.py)

## Existing Code References

**Backend WebSocket (ALREADY EXISTS):**
- `backend/omoi_os/api/routes/events.py` - WebSocket endpoint & WebSocketEventManager
- `backend/tests/test_websocket_events.py` - Full test coverage
- `backend/scripts/test_websocket_client.py` - Manual test client

**Frontend WebSocket (ALREADY EXISTS):**
- `frontend/providers/WebSocketProvider.tsx` - Context provider
- `frontend/hooks/useEvents.ts` - useEvents, useEntityEvents, useEventTypes hooks
