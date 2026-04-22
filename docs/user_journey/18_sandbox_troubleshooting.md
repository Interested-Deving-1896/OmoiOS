# 18 Sandbox Troubleshooting

**Part of**: [User Journey Documentation](./README.md)

**Created**: 2026-04-22
**Status**: Active
**Purpose**: Document the complete user journey for debugging and resolving sandbox issues in OmoiOS

---

## Overview

Sandbox troubleshooting helps users diagnose and resolve issues when AI agents encounter problems during execution. The system provides comprehensive monitoring, logging, and intervention tools to identify root causes and apply fixes.

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Sandbox State** | Current status: pending, running, completed, failed, stuck |
| **Event Stream** | Real-time log of all sandbox activities |
| **Health Check** | Automated monitoring of sandbox vitals |
| **Agent Intervention** | Manual or automated guidance to correct course |
| **Session Transcript** | Complete conversation history for debugging |
| **Recovery Mode** | Special mode for rescuing stuck sandboxes |

---

## 18.1 Accessing Sandbox Monitoring

```
User navigates to sandbox monitoring:
   ↓
1. From sidebar → Box icon (Sandboxes)
   ↓
2. Arrives at /sandboxes
   ↓
3. Sandbox list shows:
   - All sandboxes with status indicators
   - Quick filters (Running, Failed, Completed)
   - Search and sort options
   ↓
4. Click any sandbox → /sandboxes/:id for detailed view
```

---

## 18.2 Sandbox Status Overview

```
/sandboxes list view:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  Sandboxes                                                   │
│  Monitor and manage AI agent execution environments          │
│                                                              │
│  [🔍 Search...]  [Filter: All ▼]  [Sort: Recent ▼]          │
│                                                              │
│  Running (3)                                                │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ 🔵 auth-system-7f3a    │ Running  │ 2h 15m │ [View]   ││
│  │ Feature: JWT Auth      │ 45 turns │ $12.50 │          ││
│  │ Worker: worker-3       │ ✅ Healthy│        │          ││
│  ├─────────────────────────────────────────────────────────┤│
│  │ 🔵 payment-gw-9b2e     │ Running  │ 1h 42m │ [View]   ││
│  │ Feature: Stripe Int    │ 38 turns │ $8.20  │          ││
│  │ Worker: worker-1       │ ⚠️ Slow  │        │          ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  Failed (2)                                                 │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ 🔴 db-migration-4c1d   │ Failed   │ 45m    │ [View]   ││
│  │ Error: Timeout         │ 12 turns │ $3.50  │ [Retry]  ││
│  │ Worker: worker-2       │ ❌ Error │        │          ││
│  ├─────────────────────────────────────────────────────────┤│
│  │ 🔴 api-tests-8f2a      │ Failed   │ 1h 5m  │ [View]   ││
│  │ Error: Test failed     │ 28 turns │ $7.80  │ [Retry]  ││
│  │ Worker: worker-5       │ ❌ Error │        │          ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  Completed (5)                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ 🟢 user-profile-2a9b   │ Completed│ 3h 20m │ [View]   ││
│  │ Feature: Profile Page  │ 67 turns │ $18.50 │ [PR #42] ││
│  │ Worker: worker-4       │ ✅ Success│        │          ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### Status Indicators

| Status | Icon | Color | Meaning |
|--------|------|-------|---------|
| Running | 🔵 | Blue | Actively executing |
| Completed | 🟢 | Green | Finished successfully |
| Failed | 🔴 | Red | Error or crash |
| Stuck | 🟡 | Yellow | No progress detected |
| Pending | ⏳ | Gray | Queued for execution |
| Degraded | ⚠️ | Orange | Running but issues detected |

---

## 18.3 Sandbox Detail View

```
/sandboxes/:id detail page:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  ← Back to Sandboxes                                         │
│  🔵 Sandbox: auth-system-7f3a                               │
│  Feature: Implement JWT Authentication System                │
│                                                              │
│  Status: Running ●  |  Duration: 2h 15m  |  Cost: $12.50     │
│  Worker: worker-3  |  Turns: 45  |  Health: ✅ Healthy      │
│                                                              │
│  Actions: [💬 Send Message] [⏸ Pause] [🛑 Stop] [🔄 Restart]│
│                                                              │
│  Tabs: [Overview] [Events] [Logs] [Files] [Transcript] [Debug]│
│                                                              │
│  ─────────────────────────────────────────────────────────  │
│  Overview Tab                                                │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ Progress                                                │  │
│  │ ████████████████████████████████░░░░░░ 80%            │  │
│  │                                                         │  │
│  │ Current Phase: Implementation                           │  │
│  │ Task: "Add refresh token rotation"                      │  │
│  │                                                         │  │
│  │ Test Results: 45/50 passing (90%)                       │  │
│  │ Coverage: 78%                                            │  │
│  │                                                         │  │
│  │ Recent Commits:                                         │  │
│  │ • a1b2c3d "Implement JWT middleware" (3h ago)          │  │
│  │ • e4f5g6h "Add refresh token rotation" (2h ago)        │  │
│  │ • i7j8k9l "Fix token expiration bug" (1h ago)        │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ Agent Activity Timeline                                 │  │
│  │                                                         │  │
│  │ 10:23 AM - Started task "Implement JWT"               │  │
│  │ 10:25 AM - Read 12 files from codebase                │  │
│  │ 10:28 AM - Committed changes (+450 lines)             │  │
│  │ 10:30 AM - Running tests...                           │  │
│  │ 10:32 AM - Tests passed (45/50)                       │  │
│  │ 10:35 AM - [GUARDIAN] Focus on edge cases             │  │
│  │ 10:40 AM - Committed fix for edge case                │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 18.4 Event Stream Analysis

```
Events Tab:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  Event Stream — Real-time sandbox activity                   │
│                                                              │
│  [🔍 Filter events...]  [Auto-scroll ✓]  [Export]           │
│                                                              │
│  10:45:32  🤖 agent.tool_use    │ bash                      │
│            Command: npm test                                 │
│            Duration: 12.5s                                   │
│            Status: success                                   │
│                                                              │
│  10:45:18  🤖 agent.tool_result │ test_output               │
│            Tests: 45/50 passed                               │
│            Coverage: 78%                                     │
│            Failures: 5                                       │
│                                                              │
│  10:44:55  🤖 agent.message     │ assistant                 │
│            "I see 5 tests are failing. Let me analyze..."   │
│                                                              │
│  10:44:30  🛡️ guardian.intervention                         │
│            Type: trajectory_correction                       │
│            Message: "Focus on fixing the 5 failing tests    │
│                     before adding new features"              │
│            Alignment Score: 65% → 85%                        │
│                                                              │
│  10:43:12  🤖 agent.tool_use    │ Write                    │
│            File: src/auth/jwt.ts                             │
│            Lines: +45 -8                                     │
│                                                              │
│  10:42:00  💾 system.checkpoint  │ auto_commit               │
│            Commit: a1b2c3d                                   │
│            Message: "WIP: JWT implementation"                │
│                                                              │
│  [Load More...]  |  Showing 50 of 234 events                 │
└─────────────────────────────────────────────────────────────┘
```

### Event Types

| Category | Event | Description |
|----------|-------|-------------|
| **Agent** | agent.started | Agent initialized |
| | agent.tool_use | Tool execution |
| | agent.tool_result | Tool output |
| | agent.message | LLM response |
| | agent.error | Error occurred |
| | agent.completed | Task finished |
| **System** | system.checkpoint | Auto-save |
| | system.heartbeat | Health ping |
| | system.phase_change | Phase transition |
| **Guardian** | guardian.intervention | Steering applied |
| | guardian.warning | Issue detected |
| **Task** | task.assigned | Task claimed |
| | task.completed | Task done |
| | task.failed | Task error |

---

## 18.5 Common Error Patterns

### Timeout Errors

```
┌─ Sandbox Timeout
│
│  Error Display:
│  ┌─────────────────────────────────────────┐
│  │ 🔴 Sandbox Timeout                       │
│  │                                          │
│  │ Sandbox: db-migration-4c1d              │
│  │ Duration: 4h 0m (exceeded 4h limit)      │
│  │                                          │
│  │ Likely Causes:                           │
│  │ • Infinite loop in migration script      │
│  │ • Large dataset processing               │
│  │ • External API dependency hanging        │
│  │                                          │
│  │ Recovery Options:                        │
│  │ [View Logs] [Extend Timeout] [Retry]     │
│  │ [Clone & Debug] [Mark Failed]            │
│  └─────────────────────────────────────────┘
│
│  Troubleshooting Steps:
│  1. Check Logs tab for last activity
│  2. Look for hanging processes (npm, docker)
│  3. Review Files tab for partial changes
│  4. Clone sandbox to debug locally
│  5. Extend timeout if legitimate long task
│
│  Resolution:
│  • Extend timeout → Adds 2 hours
│  • Retry → Restarts from last checkpoint
│  • Clone → Creates debug copy
│  • Mark failed → Ends sandbox, logs reason
```

### Test Failures

```
┌─ Test Failure Pattern
│
│  Error Display:
│  ┌─────────────────────────────────────────┐
│  │ 🔴 Tests Failed                            │
│  │                                          │
│  │ Sandbox: api-tests-8f2a                 │
│  │ Tests: 42/50 passed (84%)                │
│  │                                          │
│  │ Failed Tests:                            │
│  │ 1. auth.middleware.test.ts              │
│  │    - should reject expired tokens        │
│  │    - AssertionError: expected 401, got 200│
│  │                                          │
│  │ 2. user.controller.test.ts               │
│  │    - should validate email format        │
│  │    - ValidationError: invalid regex      │
│  │                                          │
│  │ [View Test Output] [Retry Tests]        │
│  │ [Send Message to Agent]                 │
│  └─────────────────────────────────────────┘
│
│  Troubleshooting Steps:
│  1. View detailed test output in Logs tab
│  2. Check if tests were passing before
│  3. Review recent commits for breaking changes
│  4. Send message: "Focus on fixing test #1 first"
│  5. Agent will retry with specific focus
│
│  Agent Self-Correction:
│  • Agent detects test failures automatically
│  • Analyzes failure patterns
│  • Attempts fixes (up to 3 retries)
│  • Escalates to user if unable to resolve
```

### Agent Stuck

```
┌─ Agent Stuck Detection
│
│  Detection:
│  • No heartbeat for 90 seconds
│  • No events for 5 minutes
│  • Alignment score drops below 40%
│
│  System Response:
│  ┌─────────────────────────────────────────┐
│  │ 🟡 Agent May Be Stuck                    │
│  │                                          │
│  │ Sandbox: payment-gw-9b2e                │
│  │ Last Activity: 6 minutes ago            │
│  │                                          │
│  │ Possible Causes:                         │
│  │ • Waiting for user input                 │
│  │ • Processing large file                  │
│  │ • Stuck in infinite loop                 │
│  │ • LLM API rate limited                   │
│  │                                          │
│  │ Actions:                                 │
│  │ [Send Ping] [View Transcript] [Restart] │
│  │ [Send Message] [Force Stop]             │
│  └─────────────────────────────────────────┘
│
│  Intervention Options:
│  1. Send Ping → Agent responds with status
│  2. Send Message → "What's your current progress?"
│  3. View Transcript → Check last conversation
│  4. Restart → Kill and respawn agent
│  5. Force Stop → End sandbox, preserve state
```

### Dependency Issues

```
┌─ Dependency Resolution Failure
│
│  Error Display:
│  ┌─────────────────────────────────────────┐
│  │ 🔴 Dependency Installation Failed          │
│  │                                          │
│  │ Sandbox: frontend-5d2e                  │
│  │ Command: npm install                     │
│  │ Exit Code: 1                             │
│  │                                          │
│  │ Error:                                   │
│  │ npm ERR! ERESOLVE unable to resolve     │
│  │ dependency tree                          │
│  │ npm ERR! Found: react@18.2.0            │
│  │ npm ERR! node_modules/react              │
│  │ npm ERR!   peer react@"^17.0.0" from      │
│  │ @old-lib/core@1.2.3                     │
│  │                                          │
│  │ Resolution Options:                      │
│  │ [Use --legacy-peer-deps] [Downgrade     │
│  │ React] [Update @old-lib] [Manual Fix]    │
│  └─────────────────────────────────────────┘
│
│  Agent Self-Healing:
│  • Detects npm install failure
│  • Tries --legacy-peer-deps flag
│  • If fails, analyzes package.json
│  • Attempts compatible version resolution
│  • Reports to user if manual intervention needed
```

---

## 18.6 Health Checks and Diagnostics

```
Debug Tab:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  Sandbox Diagnostics                                           │
│                                                              │
│  Health Status                                               │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Overall: ✅ Healthy                                      ││
│  │                                                         ││
│  │ Heartbeat:     ●●●●●●●●●○  Last: 15s ago               ││
│  │ CPU Usage:     ████████░░  78% (normal)                 ││
│  │ Memory:        ██████░░░░  45% (512MB / 1GB)            ││
│  │ Disk:          ███░░░░░░░  23% (2.3GB / 10GB)           ││
│  │ Network:       ●●●●●●●●●●  Connected                    ││
│  │ LLM API:       ●●●●●●●●●●  Responsive                  ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  Alignment Score History                                     │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ 100% ┤                                          ╭─╮    ││
│  │  80% ┤                              ╭────────╯   │    ││
│  │  60% ┤          ╭────╮    ╭────╯                  │    ││
│  │  40% ┤    ╭────╯    ╰────╯                       │    ││
│  │  20% ┤────╯                                      │    ││
│  │   0% ┼────┬────┬────┬────┬────┬────┬────┬────┬───┤    ││
│  │      0h   30m  1h   90m  2h   150m 3h   210m 4h        ││
│  │                                                         ││
│  │ Score: 85% (Good)  |  Interventions: 2 applied         ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  Active Processes                                            │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ PID  │ Name          │ CPU  │ Memory │ Status           ││
│  │ 1234 │ node          │ 12%  │ 128MB  │ Running        ││
│  │ 1235 │ npm test      │ 45%  │ 256MB  │ Running        ││
│  │ 1236 │ jest          │ 21%  │ 64MB   │ Running        ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  [Run Full Diagnostics] [Download Report] [Contact Support]  │
└─────────────────────────────────────────────────────────────┘
```

---

## 18.7 Manual Intervention

```
User clicks [💬 Send Message]:
   ↓
Send Message Dialog:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  Send Message to Agent                                       │
│  Sandbox: auth-system-7f3a                                  │
│                                                              │
│  Message Type:                                             │
│  ○ General message                                          │
│  ● Guidance / Correction                                    │
│  ○ Interrupt (stop current action)                          │
│  ○ Question (request status)                                │
│                                                              │
│  Your Message:                                               │
│  [Focus on fixing the token expiration bug first. Don't     │
│   add new features until tests pass.________________]       │
│                                                              │
│  Priority:                                                   │
│  [Normal ▼]  Options: Low, Normal, High, Critical           │
│                                                              │
│  [Cancel]                              [Send Message]      │
└─────────────────────────────────────────────────────────────┘
   ↓
POST /api/v1/sandboxes/:id/messages
{
  "content": "Focus on fixing...",
  "message_type": "user_message",
  "priority": "high"
}
   ↓
System:
   1. Adds message to Redis queue
   2. Agent polls and receives message
   3. Agent adjusts behavior
   4. Event published: agent.intervention_received
   5. User sees confirmation toast
```

### Intervention Types

| Type | Use Case | Effect |
|------|----------|--------|
| **General** | Provide context | Agent incorporates into reasoning |
| **Guidance** | Correct course | Agent reprioritizes tasks |
| **Interrupt** | Stop action | Immediate halt, agent responds |
| **Question** | Check status | Agent reports current state |

---

## 18.8 Session Transcript Analysis

```
Transcript Tab:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  Session Transcript                                          │
│  Complete conversation history for debugging                 │
│                                                              │
│  [🔍 Search transcript...]  [Export JSON]  [Filter ▼]       │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Turn 45 — Assistant (10:45:32)                          ││
│  │                                                         ││
│  │ I'll analyze the failing tests. Looking at the output,  ││
│  │ the token expiration test is failing because...         ││
│  │                                                         ││
│  │ [Thinking] The JWT middleware isn't checking the exp     ││
│  │ claim properly. I need to add validation...             ││
│  │                                                         ││
│  │ <tool_use>                                              ││
│  │ Name: Read                                              ││
│  │ Input: {"file_path": "src/auth/jwt.ts"}                 ││
│  │ </tool_use>                                             ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Turn 46 — Tool Result (10:45:33)                          ││
│  │                                                         ││
│  │ File content: [syntax highlighted code]                 ││
│  │ Lines 1-50 of src/auth/jwt.ts                           ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Turn 47 — Assistant (10:45:35)                          ││
│  │                                                         ││
│  │ I see the issue. The verifyToken function doesn't       ││
│  │ check if the token is expired. Let me fix this:         ││
│  │                                                         ││
│  │ <tool_use>                                              ││
│  │ Name: Write                                             ││
│  │ Input: {"file_path": "src/auth/jwt.ts", ...}          ││
│  │ </tool_use>                                             ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  [Load More...]  |  234 turns total  |  Cost: $12.50        │
└─────────────────────────────────────────────────────────────┘
```

---

## 18.9 Recovery Procedures

### Sandbox Restart

```
User clicks [🔄 Restart]:
   ↓
Restart Options:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  Restart Sandbox                                             │
│  auth-system-7f3a                                            │
│                                                              │
│  Restart Mode:                                               │
│                                                              │
│  ○ Soft Restart (preserve state)                            │
│    - Keeps current files and changes                       │
│    - Restarts agent process only                           │
│    - Fast recovery (30 seconds)                            │
│                                                              │
│  ● Hard Restart (from checkpoint)                          │
│    - Rolls back to last checkpoint                         │
│    - Loses changes since checkpoint                        │
│    - Clean state, slower (2 minutes)                       │
│                                                              │
│  ○ Fresh Start (from scratch)                               │
│    - Complete reset, loses all progress                    │
│    - Use only if corrupted                                 │
│    - Slowest (5 minutes)                                   │
│                                                              │
│  [Cancel]                              [Confirm Restart]     │
└─────────────────────────────────────────────────────────────┘
```

### Clone for Debugging

```
User clicks [Clone & Debug] on failed sandbox:
   ↓
Clone Sandbox:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  Clone Sandbox for Debugging                                 │
│  Create a copy to investigate issues                          │
│                                                              │
│  Source: db-migration-4c1d (Failed)                        │
│                                                              │
│  Clone Options:                                            │
│                                                              │
│  [✓] Copy file system state                                 │
│  [✓] Copy environment variables                             │
│  [✓] Copy last checkpoint                                   │
│  [ ] Copy session transcript (large)                       │
│                                                              │
│  Clone Name:                                                 │
│  [db-migration-4c1d-debug____________]                     │
│                                                              │
│  Purpose:                                                    │
│  [Investigating timeout issue during migration...]          │
│                                                              │
│  [Cancel]                              [Create Clone]      │
└─────────────────────────────────────────────────────────────┘
   ↓
System:
   1. Creates new sandbox with same config
   2. Copies file system from source
   3. Sets up identical environment
   4. Does not start agent automatically
   5. User can inspect files, run commands
   6. Debug without affecting original
```

---

## 18.10 Troubleshooting Decision Tree

```
┌─────────────────────────────────────────────────────────────────┐
│                    Troubleshooting Flow                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Sandbox Issue?  │
                    └────────┬────────┘
                             │
           ┌─────────────────┼─────────────────┐
           ▼                 ▼                 ▼
    ┌──────────┐      ┌──────────┐      ┌──────────┐
    │ Not      │      │ Running  │      │ Failed/  │
    │ Starting │      │ but Slow │      │ Stuck    │
    └────┬─────┘      └────┬─────┘      └────┬─────┘
         │                 │                 │
         ▼                 ▼                 ▼
    ┌──────────┐      ┌──────────┐      ┌──────────┐
    │ Check    │      │ Check    │      │ View     │
    │ Logs for │      │ Resource │      │ Events   │
    │ startup  │      │ Usage    │      │ for      │
    │ errors   │      │          │      │ errors   │
    └────┬─────┘      └────┬─────┘      └────┬─────┘
         │                 │                 │
         ▼                 ▼                 ▼
    ┌──────────┐      ┌──────────┐      ┌──────────┐
    │ Fix      │      │ Send     │      │ Send     │
    │ Config   │      │ Message  │      │ Message  │
    │ or       │      │ to       │      │ or       │
    │ Retry    │      │ Optimize │      │ Restart  │
    └──────────┘      └──────────┘      └──────────┘
                             │                 │
                             ▼                 ▼
                    ┌─────────────────┐
                    │  Still Issues?   │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                               ▼
       ┌──────────┐                    ┌──────────┐
       │ Clone &  │                    │ Contact  │
       │ Debug    │                    │ Support  │
       │ Manually │                    │ with     │
       │          │                    │ Transcript│
       └──────────┘                    └──────────┘
```

---

## Sandbox Troubleshooting Summary

```
Common Issues → Solutions:

Timeout
  ├── Check last activity in Events
  ├── Identify hanging process
  ├── Extend timeout if legitimate
  └── Clone and debug locally

Test Failures
  ├── View detailed test output
  ├── Check which tests failed
  ├── Send guidance to agent
  └── Agent auto-retries fixes

Agent Stuck
  ├── Check heartbeat status
  ├── View last transcript entry
  ├── Send ping or message
  └── Restart if unresponsive

Dependencies
  ├── Check npm/pip logs
  ├── Try legacy peer deps
  ├── Update incompatible packages
  └── Manual package.json edit

High Cost
  ├── Review cost breakdown
  ├── Check token usage
  ├── Optimize prompts
  └── Set budget alerts

Permission Denied
  ├── Check sandbox logs
  ├── Verify file ownership
  ├── Review security policies
  └── Escalate to admin
```

---

## Related Documentation

- [03_execution_monitoring.md](./03_execution_monitoring.md) - Normal execution flow
- [06a_monitoring_system.md](./06a_monitoring_system.md) - Guardian and monitoring
- [backend/omoi_os/api/routes/sandbox.py](../../backend/omoi_os/api/routes/sandbox.py) - Sandbox API
- [backend/omoi_os/workers/sandbox_agent_worker.py](../../backend/omoi_os/workers/sandbox_agent_worker.py) - Agent worker

---

**Next**: See [19_upgrade_migration.md](./19_upgrade_migration.md) for upgrading from free to paid tiers.
