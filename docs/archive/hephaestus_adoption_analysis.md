# Hephaestus Phase System Adoption Analysis

**Created**: 2025-01-30  
**Status**: Analysis Document  
**Purpose**: Determine what OmoiOS should adopt from Hephaestus phase system best practices

---

## Executive Summary

OmoiOS has **already adopted ~80% of Hephaestus concepts** (done_definitions, discovery tracking, workflow branching). However, there are **key interconnection patterns** from Hephaestus that would significantly enhance OmoiOS's adaptive capabilities.

**Recommendation**: Adopt **selective interconnection patterns** while maintaining OmoiOS's structured approval workflow model.

---

## Current OmoiOS Implementation Status

### ✅ Already Implemented (Hephaestus-Inspired)

1. **Enhanced Phase Model**
   - ✅ `done_definitions` - Concrete completion criteria
   - ✅ `expected_outputs` - Required artifacts
   - ✅ `phase_prompt` - Phase-level instructions
   - ✅ `next_steps_guide` - What happens next

2. **Discovery Tracking System**
   - ✅ `TaskDiscovery` model
   - ✅ `DiscoveryService` with branching
   - ✅ Discovery types (bug, optimization, security, etc.)
   - ✅ Workflow graph visualization

3. **Workflow Branching**
   - ✅ Agents can spawn tasks via `DiscoveryService.record_discovery_and_branch()`
   - ✅ Parent-child task relationships
   - ✅ Discovery → Task creation flow

### ❌ Missing (Hephaestus Best Practices)

1. **Free-Form Phase Spawning**
   - ❌ OmoiOS has `allowed_transitions` restriction
   - ❌ Cannot spawn tasks in arbitrary phases
   - ❌ Phase transitions are controlled/restricted

2. **Ticket Threading Through Phases**
   - ⚠️ Tickets exist but not explicitly threaded through phases
   - ❌ No explicit "pass ticket to next phase" pattern
   - ❌ No ticket status transitions tied to phase progress

3. **Interconnection Patterns**
   - ⚠️ Discovery branching exists but not all patterns
   - ❌ No explicit feedback loops (validation → fix → revalidate)
   - ❌ No explicit phase jumping (implementation → requirements clarification)

---

## Hephaestus Best Practices Analysis

### Pattern 1: Free-Form Phase Spawning ⭐ HIGH VALUE

**Hephaestus Approach:**
```
Phase 3 agent (validation) discovers optimization
  ↓
Spawns Phase 1 task (investigation) immediately
  ↓
No restrictions - workflow adapts automatically
```

**Current OmoiOS:**
```python
# PhaseModel has allowed_transitions restriction
allowed_transitions: List[str] = ["PHASE_TESTING", "PHASE_BLOCKED"]
```

**Gap**: OmoiOS restricts phase transitions, preventing free-form discovery branching.

**Recommendation**:
- **Option A (Recommended)**: Allow discovery-based phase spawning to bypass `allowed_transitions`
  - Normal phase transitions: Enforce `allowed_transitions`
  - Discovery-based spawning: Allow any phase (via DiscoveryService)

- **Option B**: Make `allowed_transitions` optional/advisory
  - Use as guidance, not restriction
  - Log when agents spawn outside allowed transitions

**Implementation:**
```python
# In DiscoveryService.record_discovery_and_branch()
# Allow spawning in any phase when discovery-based
def record_discovery_and_branch(
    self,
    spawn_phase_id: str,  # Can be ANY phase
    ...
):
    # Bypass allowed_transitions check for discoveries
    # This enables free-form branching
```

### Pattern 2: Ticket Threading Through Phases ⭐ HIGH VALUE

**Hephaestus Approach:**
```
Phase 1: Create ticket → Pass to Phase 2
Phase 2: Move ticket to 'building' → Pass to Phase 3
Phase 3: Move ticket to 'testing' → Pass to Phase 2 (if fails)
```

**Current OmoiOS:**
- ✅ Tickets exist
- ✅ Tasks link to tickets
- ❌ No explicit ticket status transitions tied to phases
- ❌ No "pass ticket to next phase" pattern

**Recommendation**:
- Add ticket status transitions tied to phase progress
- Add explicit "pass ticket" pattern in phase prompts
- Track ticket movement through Kanban columns

**Implementation:**
```python
# In PhaseModel.phase_prompt
"""
STEP 6: Move ticket to 'building' status
  change_ticket_status(ticket_id="ticket-xxx", new_status="building")

STEP 7: Create Phase 3 validation task with ticket link
  create_task({
      "description": "Phase 3: Validate [Component] - TICKET: ticket-xxx",
      "phase_id": 3,
      "ticket_id": "ticket-xxx"
  })
"""
```

### Pattern 3: Branching on Discoveries ✅ MOSTLY IMPLEMENTED

**Hephaestus Approach:**
```
Phase 3 agent discovers CWE → Spawns Phase 1 investigation
Continues validation work (doesn't stop)
```

**Current OmoiOS:**
- ✅ DiscoveryService supports this
- ✅ Agents can spawn tasks via discovery
- ⚠️ Need to ensure agents continue original work

**Recommendation**:
- ✅ Already implemented
- Add guidance in phase prompts: "Continue your work after spawning discovery task"

### Pattern 4: Feedback Loops ⚠️ PARTIALLY IMPLEMENTED

**Hephaestus Approach:**
```
Phase 3: Validation fails → Spawns Phase 2 fix → Spawns Phase 3 revalidation
Loop until tests pass
```

**Current OmoiOS:**
- ✅ DiscoveryService can spawn fix tasks
- ❌ No explicit feedback loop pattern
- ❌ No "loop until success" guidance

**Recommendation**:
- Add explicit feedback loop pattern in Phase 3 prompts
- Guide agents to spawn fix tasks when validation fails
- Track retry loops in DiscoveryService

**Implementation:**
```python
# In PHASE_INTEGRATION phase_prompt
"""
If tests FAIL:
  - Create Phase 2 bug fix task:
    discovery_service.record_discovery_and_branch(
        discovery_type=DiscoveryType.BUG_FOUND,
        spawn_phase_id="PHASE_IMPLEMENTATION",
        spawn_description="Fix bugs in [Component] - [Specific errors]"
    )
  - Mark your validation task as done (validation complete, found issues)
  - Fix task will spawn new validation task when complete
"""
```

### Pattern 5: Parallel Branching ✅ IMPLEMENTED

**Hephaestus Approach:**
```
Phase 1: Identifies 10 components → Spawns 10 Phase 2 tasks in parallel
```

**Current OmoiOS:**
- ✅ TaskQueueService supports parallel execution
- ✅ Multiple agents can work in parallel
- ✅ DiscoveryService can spawn multiple tasks

**Status**: ✅ Already supported

### Pattern 6: Phase Jumping ⚠️ PARTIALLY IMPLEMENTED

**Hephaestus Approach:**
```
Phase 2: Implementation discovers missing requirements
  ↓
Spawns Phase 1 clarification task
  ↓
Marks implementation task as blocked
```

**Current OmoiOS:**
- ✅ DiscoveryService can spawn tasks in any phase
- ❌ No explicit "phase jumping" guidance
- ❌ No task blocking pattern

**Recommendation**:
- Add phase jumping guidance in phase prompts
- Add task blocking when waiting for clarification
- Track phase jumps in DiscoveryService

**Implementation:**
```python
# In PHASE_IMPLEMENTATION phase_prompt
"""
If you discover:
  - Requirements are unclear
  - Design decision needed
  - Need more analysis

  JUMP BACK to Phase 1:
  discovery_service.record_discovery_and_branch(
      discovery_type=DiscoveryType.CLARIFICATION_NEEDED,
      spawn_phase_id="PHASE_INITIAL",  # Jump back
      spawn_description="Clarify [What's unclear] - Needed for [Component]"
  )

  Mark your task as blocked until clarification received
"""
```

---

## Recommended Adoption Strategy

### Phase 1: High-Value Quick Wins (Immediate)

**1. Enable Discovery-Based Free-Phase Spawning**
```python
# Modify DiscoveryService to bypass allowed_transitions
def record_discovery_and_branch(
    self,
    spawn_phase_id: str,  # Can be ANY phase
    ...
):
    # Discovery-based spawning bypasses phase restrictions
    # This enables Hephaestus-style free-form branching
```

**2. Add Ticket Threading Pattern**
```python
# Add to phase prompts
"""
STEP 6: Move ticket to '[phase-status]' status
  change_ticket_status(ticket_id="ticket-xxx", new_status="building")

STEP 7: Pass ticket to next phase
  create_task({
      "ticket_id": "ticket-xxx",
      "description": "Phase X: [Work] - TICKET: ticket-xxx"
  })
"""
```

**3. Add Feedback Loop Guidance**
```python
# Add to PHASE_INTEGRATION phase_prompt
"""
If validation fails:
  - Spawn Phase 2 fix task (via DiscoveryService)
  - Fix task will spawn new validation task
  - Loop until validation passes
"""
```

**Impact**: Enables Hephaestus-style interconnection patterns while maintaining OmoiOS structure.

### Phase 2: Enhanced Interconnection (Short-Term)

**4. Add Phase Jumping Guidance**
- Update phase prompts with phase jumping instructions
- Add task blocking when waiting for clarification
- Track phase jumps in analytics

**5. Enhance Done Definitions with Interconnection**
```python
done_definitions = [
    "Component implemented",
    "Tests passing",
    "Phase 3 validation task created with ticket link",  # Interconnection
    "Ticket moved to 'building-done' status",  # Ticket threading
    "If discovered issues: investigation tasks created"  # Branching
]
```

**6. Add Interconnection Patterns to Phase Prompts**
- Explicit instructions for spawning discovery tasks
- Guidance on when to branch vs continue
- Patterns for feedback loops

### Phase 3: Advanced Patterns (Long-Term)

**7. Workflow Graph Analytics**
- Track interconnection patterns
- Analyze branching depth
- Identify common discovery → phase patterns

**8. Adaptive Phase Configuration**
- Learn from discovery patterns
- Suggest phase structure based on problem type
- Optimize interconnection patterns

---

## What NOT to Adopt

### ❌ Don't Remove Approval Gates

**Hephaestus**: Minimal user intervention, autonomous discovery

**OmoiOS**: Strategic approval gates are core value proposition

**Decision**: Keep approval gates. They provide strategic oversight that users need.

### ❌ Don't Remove Structured Spec Workflow

**Hephaestus**: Starts with PRD, agents discover structure

**OmoiOS**: Spec-driven workflow (Requirements → Design → Tasks → Execution) is core

**Decision**: Keep structured spec workflow. It provides clarity and approval points.

### ❌ Don't Remove Phase Restrictions Entirely

**Hephaestus**: No restrictions, agents spawn freely

**OmoiOS**: `allowed_transitions` provides structure

**Decision**: Keep `allowed_transitions` for normal transitions. Allow bypass for discovery-based spawning.

---

## Implementation Priority

### 🔴 Critical (Do First)

1. **Enable Discovery-Based Free-Phase Spawning**
   - Modify DiscoveryService to bypass `allowed_transitions`
   - Allows Phase 3 → Phase 1 spawning (Hephaestus pattern)
   - Enables free-form branching

2. **Add Ticket Threading Pattern**
   - Update phase prompts with ticket status transitions
   - Add "pass ticket" instructions
   - Track ticket movement through phases

### 🟡 High Priority (Do Soon)

3. **Add Feedback Loop Guidance**
   - Update Phase 3 prompts with retry loop pattern
   - Guide agents to spawn fix tasks when validation fails
   - Track retry loops

4. **Add Phase Jumping Guidance**
   - Update Phase 2 prompts with phase jumping instructions
   - Add task blocking pattern
   - Track phase jumps

### 🟢 Medium Priority (Do Later)

5. **Enhance Done Definitions**
   - Add interconnection requirements to done_definitions
   - Enforce ticket threading in completion criteria

6. **Add Interconnection Analytics**
   - Track discovery → phase patterns
   - Analyze branching depth
   - Identify common interconnection patterns

---

## Code Changes Required

### 1. DiscoveryService Enhancement

```python
# omoi_os/services/discovery.py

def record_discovery_and_branch(
    self,
    session: Session,
    source_task_id: str,
    discovery_type: DiscoveryType,
    description: str,
    spawn_phase_id: str,  # Can be ANY phase (bypasses allowed_transitions)
    spawn_description: str,
    priority_boost: bool = False,
) -> Tuple[TaskDiscovery, Task]:
    """
    Record discovery and spawn task in ANY phase.

    This bypasses PhaseModel.allowed_transitions for discovery-based
    spawning, enabling Hephaestus-style free-form branching.
    """
    # Create discovery record
    discovery = TaskDiscovery(...)

    # Spawn task in ANY phase (bypass phase restrictions)
    spawned_task = self._create_task_in_phase(
        phase_id=spawn_phase_id,  # No allowed_transitions check
        description=spawn_description,
        parent_task_id=source_task_id,
        priority_boost=priority_boost,
    )

    return discovery, spawned_task
```

### 2. Phase Prompt Updates

```python
# Update PHASE_IMPLEMENTATION phase_prompt
phase_prompt = """
YOU ARE A SOFTWARE ENGINEER IN THE IMPLEMENTATION PHASE

STEP 1: Extract ticket ID from task description
STEP 2: Move ticket to 'building' status
  change_ticket_status(ticket_id="ticket-xxx", new_status="building")
STEP 3: Implement component
STEP 4: Write tests (minimum 3)
STEP 5: Verify tests pass
STEP 6: Move ticket to 'building-done'
  change_ticket_status(ticket_id="ticket-xxx", new_status="building-done")
STEP 7: Create Phase 3 validation task with ticket link
  discovery_service.record_discovery_and_branch(
      discovery_type=DiscoveryType.NEW_COMPONENT,
      spawn_phase_id="PHASE_INTEGRATION",
      spawn_description="Phase 3: Validate [Component] - TICKET: ticket-xxx"
  )

IF you discover:
  - Missing requirements → Spawn Phase 1 clarification task
  - Optimization opportunity → Spawn Phase 1 investigation task
  - Security issue → Spawn Phase 1 investigation task

  Continue your implementation work after spawning discovery task.
"""
```

### 3. Phase Integration Prompt Updates

```python
# Update PHASE_INTEGRATION phase_prompt
phase_prompt = """
YOU ARE A VALIDATION AGENT IN THE INTEGRATION PHASE

STEP 1: Extract ticket ID from task description
STEP 2: Move ticket to 'testing' status
STEP 3: Run integration tests
STEP 4: Verify component meets requirements

IF tests PASS:
  - Move ticket to 'done' status
  - Mark task complete

IF tests FAIL:
  - Spawn Phase 2 fix task (via DiscoveryService)
  - Keep ticket in 'testing' status
  - Fix task will spawn new validation task when complete
  - Loop until validation passes

IF you discover:
  - Security issue → Spawn Phase 1 investigation
  - Optimization → Spawn Phase 1 investigation
  - Continue validation work after spawning discovery
"""
```

---

## Expected Impact

### Before (Current OmoiOS)
- Discovery branching exists but restricted by `allowed_transitions`
- Tickets exist but not explicitly threaded through phases
- Feedback loops not explicitly guided
- Phase jumping not encouraged

### After (With Hephaestus Patterns)
- ✅ Free-form phase spawning via discoveries
- ✅ Tickets thread through phases maintaining context
- ✅ Explicit feedback loops (validation → fix → revalidate)
- ✅ Phase jumping for clarification
- ✅ Maintains approval gates and structured workflow

**Result**: OmoiOS gains Hephaestus-style interconnection while keeping its strategic oversight model.

---

## Alignment Score

| Pattern | Before | After Adoption | Hephaestus |
|---------|--------|----------------|------------|
| Free-Form Phase Spawning | ❌ | ✅ | ✅ |
| Ticket Threading | ⚠️ | ✅ | ✅ |
| Discovery Branching | ✅ | ✅ | ✅ |
| Feedback Loops | ⚠️ | ✅ | ✅ |
| Phase Jumping | ⚠️ | ✅ | ✅ |
| Parallel Branching | ✅ | ✅ | ✅ |
| **Overall Alignment** | **60%** | **95%** | **100%** |

---

## Conclusion

**Recommendation**: Adopt **selective interconnection patterns** from Hephaestus:

1. ✅ **Enable discovery-based free-phase spawning** (bypass `allowed_transitions`)
2. ✅ **Add ticket threading pattern** (explicit ticket movement through phases)
3. ✅ **Add feedback loop guidance** (validation → fix → revalidate)
4. ✅ **Add phase jumping guidance** (implementation → requirements clarification)

**Keep OmoiOS Differentiators**:
- ✅ Approval gates (strategic oversight)
- ✅ Structured spec workflow (Requirements → Design → Tasks → Execution)
- ✅ Dashboard-driven product experience

**Result**: Best of both worlds - Hephaestus interconnection patterns with OmoiOS strategic oversight.

---

## Related Documents

- `./implementation/workflows/hephaestus_workflow_enhancements.md` - Current implementation
- `./user_journey.md` - Complete user flow
- `./product_vision.md` - Product concept
