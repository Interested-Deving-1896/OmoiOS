# OmoiOS User Journey Documentation

Complete end-to-end user flow documentation covering the entire OmoiOS experience — from first landing to ongoing optimization.

---

## Overview for AI Agents

This documentation system captures how users experience OmoiOS across their entire journey. Unlike the page_flows documentation (which documents individual pages), these documents trace complete user workflows across multiple pages and systems.

### What These Documents Contain

- **User personas**: Who uses OmoiOS and their goals
- **Journey phases**: Step-by-step flows from onboarding to feature completion
- **Decision points**: Where users make choices and what influences them
- **System interactions**: How backend systems manifest in the UI
- **Error handling**: Recovery paths when things go wrong

### How to Use These Documents

**When implementing features:**
1. Find the journey phase that matches your feature (e.g., feature planning → `02_feature_planning.md`)
2. Understand the user context: what came before, what comes after
3. Check `09_design_principles.md` for UX patterns to follow
4. Reference `08_user_personas.md` to understand who you're building for

**When debugging issues:**
1. Trace the user journey to understand expected behavior
2. Check `10_additional_flows.md` for edge cases and error handling
3. Review `06a_monitoring_system.md` for Guardian intervention patterns

**When writing documentation:**
1. Follow the established structure: context → flow → decisions → outcomes
2. Cross-reference related page_flows documents
3. Update this CLAUDE.md index when adding new journey documents

---

## Document Structure

### Demo & Overview
- **[00_overview.md](./00_overview.md)** — The 60-Second Story, Core Promise, Dashboard Layout
- **[00a_demo_flow.md](./00a_demo_flow.md)** — Video Demo Script (90 seconds)

### Core Journey (Phases 1-5)
- **[01_onboarding.md](./01_onboarding.md)** — Phase 1: Onboarding & First Project Setup
- **[02_feature_planning.md](./02_feature_planning.md)** — Phase 2: Feature Request & Planning
- **[03_execution_monitoring.md](./03_execution_monitoring.md)** — Phase 3: Autonomous Execution & Monitoring
- **[04_approvals_completion.md](./04_approvals_completion.md)** — Phase 4: Approval Gates & Phase Transitions
- **[05_optimization.md](./05_optimization.md)** — Phase 5: Ongoing Monitoring & Optimization

### System Documentation
- **[06_key_interactions.md](./06_key_interactions.md)** — Command Palette, Real-Time Updates, Intervention Tools
- **[06a_monitoring_system.md](./06a_monitoring_system.md)** — Guardian & Monitoring System
- **[07_phase_system.md](./07_phase_system.md)** — Phase System Overview
- **[08_user_personas.md](./08_user_personas.md)** — User Personas & Use Cases
- **[09_design_principles.md](./09_design_principles.md)** — Visual Design Principles

### Cost, Billing & Settings
- **[11_cost_memory_management.md](./11_cost_memory_management.md)** — Cost Dashboard, Budget Management, Agent Memory
- **[12_billing_subscription.md](./12_billing_subscription.md)** — Subscription Tiers, Credit Purchases, Invoices
- **[13_public_marketing_pages.md](./13_public_marketing_pages.md)** — Landing Page, Pricing, Blog, Docs
- **[14_settings_personalization.md](./14_settings_personalization.md)** — Appearance, Notifications, Security, Activity

### Advanced Topics
- **[15_prototype_diagnostic.md](./15_prototype_diagnostic.md)** — Prototype Workspace & Diagnostic Reasoning
- **[10_additional_flows.md](./10_additional_flows.md)** — Edge Cases, Error Handling, Collaboration

---

## Key Decision Points Documented

### User Decisions

| Decision | Location | Impact | Document |
|----------|----------|--------|----------|
| Select workflow mode | Command Center | Determines execution strategy | `02_feature_planning.md` |
| Approve requirements | Spec Viewer | Unlocks DESIGN phase | `04_approvals_completion.md` |
| Approve design | Spec Viewer | Unlocks TASKS phase | `04_approvals_completion.md` |
| Intervene on stuck agent | Health Dashboard | Redirects or restarts agent | `06a_monitoring_system.md` |
| Set budget threshold | Cost Dashboard | Triggers alerts | `11_cost_memory_management.md` |
| Choose subscription tier | Pricing Page | Determines feature access | `12_billing_subscription.md` |

### System Decisions

| Decision | Trigger | Outcome | Document |
|----------|---------|---------|----------|
| Advance spec phase | Phase evaluator passes | Unlocks next phase | `07_phase_system.md` |
| Spawn discovery task | Agent finds new requirement | Creates Phase 1 task from Phase 3 | `03_execution_monitoring.md` |
| Trigger Guardian intervention | Trajectory score < threshold | Redirects or stops agent | `06a_monitoring_system.md` |
| Merge agent branches | Tasks complete | Creates PR | `03_execution_monitoring.md` |

---

## Agent Guidance

### When Implementing Frontend Features

1. **Check the journey context**: What phase is the user in? What information do they have?
2. **Follow design principles**: Progressive disclosure, clear feedback, error recovery (`09_design_principles.md`)
3. **Match persona needs**: Engineering managers need overview; ICs need detail (`08_user_personas.md`)
4. **Handle errors gracefully**: Every flow has failure modes documented (`10_additional_flows.md`)

### When Implementing Backend Features

1. **Understand the user impact**: How does this API change manifest in the UI?
2. **Consider phase transitions**: Does this affect spec state machine behavior?
3. **Monitor system health**: Guardian and Conductor patterns (`06a_monitoring_system.md`)
4. **Track costs**: Every operation has cost implications (`11_cost_memory_management.md`)

### When Writing Tests

1. **Test the full journey**: Unit tests for components, integration tests for flows
2. **Cover decision points**: Test both choices at each decision
3. **Include error paths**: Test recovery flows, not just happy paths
4. **Verify real-time behavior**: WebSocket events, polling fallbacks

### When Debugging Issues

1. **Trace the user journey**: Where in the flow did things go wrong?
2. **Check system interactions**: Which backend services are involved?
3. **Review monitoring patterns**: What would Guardian/Conductor do?
4. **Examine edge cases**: Is this covered in `10_additional_flows.md`?

---

## The Core Promise

> **Start a feature before bed. Wake up to a PR.**

Let AI run overnight and finish your software for you. Describe what you want, approve a plan, go to sleep. Wake up to a completed PR ready for review.

---

## Related Documentation

- [Page Flows Documentation](../page_flows/README.md) — Detailed page-by-page navigation flows
- Page Architecture — Complete page architecture specifications
- Design System — UI/UX design system guide

<claude-mem-context>
# Recent Activity

<!-- This section is auto-generated by claude-mem. Edit content outside the tags. -->

*No recent activity*
</claude-mem-context>
