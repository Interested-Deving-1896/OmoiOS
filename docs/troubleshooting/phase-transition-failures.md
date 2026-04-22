# Phase Transition Failures Troubleshooting Guide

**Status**: Active | **Last Updated**: 2025-04-22 | **Applies To**: OmoiOS v1.0+

**Source Files**:
- `backend/omoi_os/services/phase_manager.py` - Phase transition orchestration
- `backend/omoi_os/services/spec_task_execution.py` - Spec task execution
- `backend/omoi_os/services/phase_gate.py` - Phase gate validation
- `backend/omoi_os/models/ticket.py` - Ticket state management

**Related Documentation**:
- [Architecture: Planning System](../architecture/01-planning-system.md)
- [Design: Phase Manager](../design/services/phase_manager.md)
- **Page Flows: Spec Workflow**

---

## Overview

OmoiOS uses a phase-based workflow system where tickets progress through phases: `PHASE_BACKLOG` → `PHASE_REQUIREMENTS` → `PHASE_DESIGN` → `PHASE_IMPLEMENTATION` → `PHASE_TESTING` → `PHASE_DEPLOYMENT` → `PHASE_DONE`. Each phase transition is validated by gate criteria and can fail due to missing artifacts, incomplete tasks, or invalid state transitions.

### Phase State Machine

```
PHASE_BACKLOG ──→ PHASE_REQUIREMENTS ──→ PHASE_DESIGN ──→ PHASE_IMPLEMENTATION
      │                    │                    │                    │
      │                    ↓                    ↓                    ↓
      └─────────────→ PHASE_BLOCKED ←────────────┴────────────────────┘
                           │
                           ↓ (when unblocked)
                    Any previous phase
```

---

## Common Errors Table

| Error Message | Cause | Fix |
|--------------|-------|-----|
| `Transition validation failed` | Gate criteria not met | Complete required artifacts and tasks |
| `Phase gate requirements not met. Missing: [...]` | Missing required artifacts | Create the missing documents/outputs |
| `Not all phase tasks are completed` | Tasks still pending/running | Wait for or complete pending tasks |
| `Ticket is blocked. Can only transition to: (...)` | Ticket in blocked state | Unblock ticket first or transition to allowed phase |
| `Transition from X to Y not allowed` | Invalid state transition | Use allowed transitions only |
| `Unknown target phase: X` | Phase ID doesn't exist | Check phase ID spelling |
| `No next phase available` | Already in terminal phase | Ticket is complete or blocked |
| `Ticket already in X` | Redundant transition request | Check current phase before transitioning |
| `Spec design must be approved before executing tasks` | Missing design approval | Approve spec design first |
| `spec_task_blocked_on_failure` | Task failed during execution | Review failure and retry or adjust |

---

## Diagnostic Commands

### Check Phase Configuration

```bash
# View all configured phases
cd backend && uv run python -c "
from omoi_os.services.phase_manager import PHASE_CONFIGS, ExecutionMode

for phase_id, config in PHASE_CONFIGS.items():
    print(f'{phase_id}:')
    print(f'  Name: {config.name}')
    print(f'  Allowed transitions: {config.allowed_transitions}')
    print(f'  Execution mode: {config.execution_mode}')
    print(f'  Terminal: {config.is_terminal}')
    print()
"

# Check phase gate criteria
cd backend && uv run python -c "
from omoi_os.services.phase_manager import PHASE_CONFIGS

for phase_id, config in PHASE_CONFIGS.items():
    if config.gate_criteria:
        print(f'{phase_id} gate criteria:')
        print(f'  Required artifacts: {config.gate_criteria.required_artifacts}')
        print(f'  All tasks completed: {config.gate_criteria.all_tasks_completed}')
        print(f'  Min test coverage: {config.gate_criteria.min_test_coverage}')
        print()
"
```

### Monitor Phase Transitions

```bash
# Watch for phase transition events
tail -f backend/logs/api.log | grep -E "phase_transition|Phase transition"

# Check for gate failures
tail -f backend/logs/api.log | grep -E "gate_failure|Phase gate"

# Monitor ticket status changes
tail -f backend/logs/api.log | grep "TICKET_STATUS_CHANGED"
```

### Check Ticket State

```bash
# Query ticket phase and status
cd backend && uv run python -c "
from omoi_os.services.database import get_db_service
from omoi_os.models.ticket import Ticket

db = get_db_service()
with db.get_session() as session:
    ticket = session.get(Ticket, 'ticket-id-here')
    print(f'Phase: {ticket.phase_id}')
    print(f'Status: {ticket.status}')
    print(f'Blocked: {ticket.is_blocked}')
    print(f'Previous phase: {ticket.previous_phase_id}')
"
```

---

## Symptom 1: SpecStateMachine Stuck in a Phase

**Error Message**: `Phase gate requirements not met. Missing: ["requirements_document"]` or similar

**Root Cause**: The ticket cannot advance because phase gate criteria are not satisfied - missing artifacts, incomplete tasks, or unmet validation rules.

### Diagnostic Steps

1. **Check Current Phase Configuration**:
   ```python
   from omoi_os.services.phase_manager import get_phase_manager
   
   pm = get_phase_manager()
   config = pm.get_phase_config(ticket.phase_id)
   print(f"Current phase: {config.name}")
   print(f"Gate criteria: {config.gate_criteria}")
   print(f"Allowed transitions: {config.allowed_transitions}")
   ```

2. **Verify Gate Requirements**:
   ```python
   # Check if gate service reports requirements met
   can_transition, reasons = pm.can_transition(ticket_id, "PHASE_IMPLEMENTATION")
   print(f"Can transition: {can_transition}")
   print(f"Blocking reasons: {reasons}")
   ```

3. **Check Task Completion Status**:
   ```python
   from omoi_os.models.task import Task
   
   with db.get_session() as session:
       tasks = session.query(Task).filter(
           Task.ticket_id == ticket_id,
           Task.phase_id == ticket.phase_id
       ).all()
       
       for task in tasks:
           print(f"Task {task.id}: {task.status}")
   ```

### Fix Procedure

1. **Complete Missing Artifacts**:
   ```python
   # For PHASE_REQUIREMENTS, create requirements document
   # For PHASE_DESIGN, create design document
   # For PHASE_IMPLEMENTATION, ensure code_changes artifact exists
   
   # Manually mark artifacts as collected (if appropriate)
   pm.transition_to_phase(
       ticket_id=ticket_id,
       to_phase="PHASE_IMPLEMENTATION",
       force=True,  # Skip validation (use with caution)
       reason="Manual override - artifacts verified"
   )
   ```

2. **Complete Pending Tasks**:
   ```bash
   # Wait for tasks to complete, or mark as completed if done externally
   cd backend && uv run python -c "
   from omoi_os.services.task_queue import get_task_queue
   tq = get_task_queue()
   
   # Mark task as completed
   tq.update_task_status('task-id', 'completed', result={'output': 'done'})
   "
   ```

3. **Force Transition (Emergency)**:
   ```python
   # Use force=True to bypass gate validation
   result = pm.transition_to_phase(
       ticket_id=ticket_id,
       to_phase="PHASE_IMPLEMENTATION",
       force=True,
       reason="Emergency bypass"
   )
   print(f"Transition result: {result.success}")
   ```

---

## Symptom 2: Evaluator Failures

**Error Message**: `Spec design must be approved before executing tasks` or phase evaluator rejection

**Root Cause**: Phase evaluators (LLM-based quality gates) have rejected the phase output as insufficient quality.

### Diagnostic Steps

1. **Check Spec Approval Status**:
   ```python
   from omoi_os.models.spec import Spec
   
   with db.get_session() as session:
       spec = session.get(Spec, spec_id)
       print(f"Design approved: {spec.design_approved}")
       print(f"Current phase: {spec.phase}")
       print(f"Phase data keys: {spec.phase_data.keys() if spec.phase_data else None}")
   ```

2. **Review Phase Data**:
   ```python
   # Check what data was collected in the phase
   phase_data = spec.phase_data or {}
   requirements = phase_data.get("requirements", {})
   design = phase_data.get("design", {})
   
   print(f"Requirements present: {bool(requirements)}")
   print(f"Design present: {bool(design)}")
   ```

3. **Check Evaluator Output**:
   ```bash
   # Look for evaluator rejection reasons
   grep -E "evaluator|evaluation|rejected" backend/logs/api.log | tail -20
   ```

### Fix Procedure

1. **Approve Design Manually**:
   ```python
   # If design is complete but not auto-approved
   with db.get_session() as session:
       spec = session.get(Spec, spec_id)
       spec.design_approved = True
       session.commit()
   ```

2. **Re-run Phase**:
   ```python
   # Reset phase and re-run tasks
   with db.get_session() as session:
       ticket = session.get(Ticket, ticket_id)
       ticket.phase_id = "PHASE_REQUIREMENTS"  # Go back to previous phase
       ticket.status = "analyzing"
       session.commit()
   
   # Spawn new tasks for the phase
   pm._spawn_phase_tasks(ticket_id, "PHASE_REQUIREMENTS")
   ```

3. **Bypass Evaluator**:
   ```python
   # For development/testing, skip evaluator
   # Set force=True on transition
   pm.fast_track_to_implementation(ticket_id, force=True)
   ```

---

## Symptom 3: Phase Gate Rejections

**Error Message**: `Transition from X to Y not allowed. Allowed transitions: [...]`

**Root Cause**: Attempting an invalid state transition not defined in the phase configuration.

### Diagnostic Steps

1. **Check Allowed Transitions**:
   ```python
   from omoi_os.services.phase_manager import PHASE_CONFIGS
   
   current_config = PHASE_CONFIGS.get(current_phase)
   print(f"Current phase: {current_phase}")
   print(f"Allowed transitions: {current_config.allowed_transitions}")
   print(f"Is terminal: {current_config.is_terminal}")
   ```

2. **Validate Transition Path**:
   ```python
   # Check if transition path is valid
   is_valid, reasons = pm.validate_transition_path(from_phase, to_phase)
   print(f"Valid: {is_valid}, Reasons: {reasons}")
   ```

3. **Check Blocked Status**:
   ```python
   with db.get_session() as session:
       ticket = session.get(Ticket, ticket_id)
       if ticket.is_blocked:
           blocked_config = PHASE_CONFIGS.get("PHASE_BLOCKED")
           print(f"Ticket blocked. Allowed transitions: {blocked_config.allowed_transitions}")
   ```

### Fix Procedure

1. **Use Allowed Transition**:
   ```python
   # Transition to an allowed phase first
   if current_phase == "PHASE_BACKLOG":
       result = pm.transition_to_phase(ticket_id, "PHASE_REQUIREMENTS")
   elif current_phase == "PHASE_REQUIREMENTS":
       result = pm.transition_to_phase(ticket_id, "PHASE_DESIGN")
   # etc.
   ```

2. **Fast-Track to Implementation**:
   ```python
   # Skip intermediate phases if allowed
   result = pm.fast_track_to_implementation(ticket_id)
   print(f"Fast-track result: {result.success}")
   if not result.success:
       print(f"Reason: {result.reason}")
   ```

3. **Force Invalid Transition**:
   ```python
   # Only for emergency/debugging
   result = pm.transition_to_phase(
       ticket_id,
       to_phase="PHASE_IMPLEMENTATION",
       force=True,
       reason="Forced transition for testing"
   )
   ```

---

## Symptom 4: Transition Timeout

**Error Message**: Transition hangs or takes excessive time

**Root Cause**: Phase transition involves callbacks, artifact collection, or task spawning that is slow or blocking.

### Diagnostic Steps

1. **Enable Debug Logging**:
   ```bash
   # Increase log level for phase manager
   export LOG_LEVEL=DEBUG
   
   # Watch transition progress
   tail -f backend/logs/api.log | grep -E "Phase transition|transition_to_phase"
   ```

2. **Check Callback Execution**:
   ```python
   # Review pre/post transition callbacks
   # In phase_manager.py, check:
   # - _pre_transition_callbacks
   # - _post_transition_callbacks
   # - _on_gate_failure_callbacks
   ```

3. **Monitor Task Spawning**:
   ```bash
   # Check if task spawning is the bottleneck
   tail -f backend/logs/api.log | grep "Spawned phase tasks"
   ```

### Fix Procedure

1. **Disable Task Spawning**:
   ```python
   # Transition without spawning tasks
   result = pm.transition_to_phase(
       ticket_id,
       to_phase="PHASE_IMPLEMENTATION",
       spawn_tasks=False  # Skip task spawning
   )
   ```

2. **Simplify Transition**:
   ```python
   # Use move_to_done for direct completion
   pm.move_to_done(
       ticket_id,
       reason="Direct completion - bypassing phases"
   )
   ```

3. **Check Database Performance**:
   ```bash
   # Monitor DB query times
   tail -f backend/logs/api.log | grep -E "query|transaction|commit"
   ```

---

## Symptom 5: Duplicate Transitions

**Error Message**: Multiple phase transition events for same ticket, or `Ticket already in X`

**Root Cause**: Race conditions causing duplicate transition attempts, or event reprocessing.

### Diagnostic Steps

1. **Check Phase History**:
   ```python
   from omoi_os.models.phase_history import PhaseHistory
   
   with db.get_session() as session:
       history = session.query(PhaseHistory).filter(
           PhaseHistory.ticket_id == ticket_id
       ).order_by(PhaseHistory.created_at).all()
       
       for h in history:
           print(f"{h.created_at}: {h.from_phase} -> {h.to_phase}")
   ```

2. **Review Event Bus Events**:
   ```bash
   # Check for duplicate events
   tail -f backend/logs/api.log | grep "ticket.phase_transitioned" | grep $TICKET_ID
   ```

3. **Check Current Phase**:
   ```python
   with db.get_session() as session:
       ticket = session.get(Ticket, ticket_id)
       print(f"Current phase: {ticket.phase_id}")
       print(f"Previous phase: {ticket.previous_phase_id}")
   ```

### Fix Procedure

1. **Idempotent Transition**:
   ```python
   # Check current phase before transitioning
   with db.get_session() as session:
       ticket = session.get(Ticket, ticket_id)
       if ticket.phase_id != target_phase:
           result = pm.transition_to_phase(ticket_id, target_phase)
       else:
           print(f"Already in {target_phase}")
   ```

2. **Clear Duplicate History**:
   ```python
   # Remove duplicate history entries (if needed)
   with db.get_session() as session:
       # Keep only the latest transition for each phase pair
       # This is advanced - usually not needed
       pass
   ```

---

## Symptom 6: Invalid State Transitions

**Error Message**: `Unknown source phase: X` or `Unknown target phase: Y`

**Root Cause**: Phase ID doesn't exist in the phase configuration registry.

### Diagnostic Steps

1. **List Valid Phases**:
   ```python
   from omoi_os.services.phase_manager import PHASE_CONFIGS
   
   print("Valid phase IDs:")
   for phase_id in PHASE_CONFIGS.keys():
       print(f"  - {phase_id}")
   ```

2. **Check Phase Status Map**:
   ```python
   from omoi_os.services.phase_manager import PHASE_STATUS_MAP, STATUS_PHASE_MAP
   
   print("Phase to status mapping:")
   for phase, status in PHASE_STATUS_MAP.items():
       print(f"  {phase} -> {status}")
   ```

3. **Validate Phase ID**:
   ```python
   def is_valid_phase(phase_id):
       return phase_id in PHASE_CONFIGS
   
   print(f"Is 'PHASE_FOO' valid? {is_valid_phase('PHASE_FOO')}")
   print(f"Is 'PHASE_BACKLOG' valid? {is_valid_phase('PHASE_BACKLOG')}")
   ```

### Fix Procedure

1. **Use Correct Phase ID**:
   ```python
   # Valid phase IDs
   VALID_PHASES = [
       "PHASE_BACKLOG",
       "PHASE_REQUIREMENTS",
       "PHASE_DESIGN",
       "PHASE_IMPLEMENTATION",
       "PHASE_TESTING",
       "PHASE_DEPLOYMENT",
       "PHASE_DONE",
       "PHASE_BLOCKED",
   ]
   ```

2. **Fix Data Migration**:
   ```python
   # If ticket has invalid phase_id, reset to valid one
   with db.get_session() as session:
       ticket = session.get(Ticket, ticket_id)
       if ticket.phase_id not in PHASE_CONFIGS:
           ticket.phase_id = "PHASE_BACKLOG"
           session.commit()
   ```

---

## Configuration Reference

### Phase Configuration

| Phase ID | Name | Allowed Transitions | Terminal | Skippable |
|----------|------|---------------------|----------|-----------|
| `PHASE_BACKLOG` | Backlog | REQUIREMENTS, IMPLEMENTATION | No | Yes |
| `PHASE_REQUIREMENTS` | Requirements | DESIGN, IMPLEMENTATION | No | Yes |
| `PHASE_DESIGN` | Design | IMPLEMENTATION | No | Yes |
| `PHASE_IMPLEMENTATION` | Implementation | TESTING, DONE | No | No |
| `PHASE_TESTING` | Testing | DEPLOYMENT, IMPLEMENTATION, DONE | No | No |
| `PHASE_DEPLOYMENT` | Deployment | DONE | No | Yes |
| `PHASE_DONE` | Done | (none) | Yes | No |
| `PHASE_BLOCKED` | Blocked | BACKLOG, REQUIREMENTS, DESIGN, IMPLEMENTATION, TESTING | Yes | No |

### Gate Criteria by Phase

| Phase | Required Artifacts | Min Test Coverage | All Tasks Completed |
|-------|-------------------|-------------------|---------------------|
| `PHASE_REQUIREMENTS` | requirements_document | - | Yes |
| `PHASE_DESIGN` | design_document | - | Yes |
| `PHASE_IMPLEMENTATION` | code_changes | 80.0% | Yes |
| `PHASE_TESTING` | test_results | - | Yes |
| `PHASE_DEPLOYMENT` | deployment_evidence | - | Yes |

### Execution Modes

| Mode | Description | Phases |
|------|-------------|--------|
| `exploration` | Stops early, doesn't push code | BACKLOG, REQUIREMENTS, DESIGN, DONE, BLOCKED |
| `implementation` | Runs to completion, pushes code | IMPLEMENTATION, DEPLOYMENT |
| `validation` | Runs tests, validates functionality | TESTING |

---

## Step-by-Step Recovery Procedures

### Procedure 1: Reset Ticket to Initial Phase

1. **Check current state**:
   ```python
   with db.get_session() as session:
       ticket = session.get(Ticket, ticket_id)
       print(f"Current: {ticket.phase_id}, Status: {ticket.status}")
   ```

2. **Reset phase and status**:
   ```python
   with db.get_session() as session:
       ticket = session.get(Ticket, ticket_id)
       ticket.phase_id = "PHASE_BACKLOG"
       ticket.status = "backlog"
       ticket.is_blocked = False
       ticket.blocked_reason = None
       session.commit()
   ```

3. **Clear associated tasks**:
   ```python
   from omoi_os.models.task import Task
   
   with db.get_session() as session:
       tasks = session.query(Task).filter(Task.ticket_id == ticket_id).all()
       for task in tasks:
           task.status = "cancelled"
       session.commit()
   ```

### Procedure 2: Force Complete Ticket

1. **Move directly to done**:
   ```python
   from omoi_os.services.phase_manager import get_phase_manager
   
   pm = get_phase_manager()
   result = pm.move_to_done(
       ticket_id,
       initiated_by="admin",
       reason="Force completion"
   )
   print(f"Result: {result.success}")
   ```

2. **Mark all tasks complete**:
   ```python
   with db.get_session() as session:
       tasks = session.query(Task).filter(
           Task.ticket_id == ticket_id,
           Task.status.in_(["pending", "assigned", "running"])
       ).all()
       for task in tasks:
           task.status = "completed"
           task.completed_at = utc_now()
       session.commit()
   ```

---

## Prevention Strategies

1. **Validate Before Transition**:
   ```python
   # Always check can_transition before attempting
   can, reasons = pm.can_transition(ticket_id, target_phase)
   if not can:
       print(f"Cannot transition: {reasons}")
       return
   ```

2. **Use Auto-Advance**:
   ```python
   # Let phase manager check and advance automatically
   result = pm.check_and_advance(ticket_id)
   if not result.success:
       print(f"Cannot advance: {result.blocking_reasons}")
   ```

3. **Monitor Phase History**:
   - Log all phase transitions
   - Alert on rapid phase changes (possible loop)
   - Track time spent in each phase

4. **Gate Criteria Documentation**:
   - Document what each phase requires
   - Provide clear error messages for missing artifacts
   - Implement progress indicators for long phases

---

## Troubleshooting Flowchart

```
Phase transition failed?
├── Check gate criteria → Complete missing artifacts/tasks
├── Check blocked status → Unblock if needed
├── Check allowed transitions → Use valid target phase
└── Check phase exists → Use valid phase ID

Ticket stuck in phase?
├── Check task completion → Complete or cancel pending tasks
├── Check artifact collection → Create or manually add artifacts
├── Check evaluator status → Approve design or bypass
└── Force transition → Use force=True (emergency only)

Duplicate transitions?
├── Check phase history → Look for rapid changes
├── Check event bus → Deduplicate events
└── Add idempotency → Check current phase first

Invalid phase error?
├── List valid phases → Use correct phase ID
├── Check data integrity → Fix invalid phase_id in DB
└── Validate on entry → Reject invalid phases early
```

---

## Common Diagnostic Commands

```bash
# Check phase transitions for a ticket
grep "ticket-id-here" backend/logs/api.log | grep "phase"

# Monitor all phase transitions
tail -f backend/logs/api.log | grep "phase_transitioned"

# Check gate failures
tail -f backend/logs/api.log | grep -E "gate_failure|not met"

# View ticket status changes
tail -f backend/logs/api.log | grep "TICKET_STATUS_CHANGED"

# Check spec execution events
tail -f backend/logs/api.log | grep "SPEC_EXECUTION"

# Monitor task completion
tail -f backend/logs/api.log | grep "TASK_COMPLETED"
```

---

*End of Phase Transition Failures Troubleshooting Guide*

*This guide covers the OmoiOS phase state machine, gate criteria, transition validation, and recovery procedures.*
