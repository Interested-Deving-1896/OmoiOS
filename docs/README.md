# OmoiOS Documentation Hub

> **Last Updated**: 2026-04-22 | **Total Docs**: 384+ files | **Purpose**: Complete reference for OmoiOS architecture, design, development, and operations

OmoiOS is a spec-driven, multi-agent orchestration system. Users describe a feature, OmoiOS plans it, executes it with autonomous AI agents in isolated sandboxes, and creates a PR. This documentation covers every aspect of the system.

## Quick Navigation

| Start Here | Purpose |
|------------|---------|
| [ARCHITECTURE.md](../ARCHITECTURE.md) | System design, service map, data flow (start here for backend work) |
| [UI.md](../UI.md) | Frontend routes, components, state, design system (start here for frontend work) |
| [AGENTS.md](../AGENTS.md) | AI coding agent guide — read before any contribution |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | Branch conventions, PR process, testing requirements |
| [CLAUDE.md](../CLAUDE.md) | Monorepo structure, dev commands, port configuration |

## Documentation Tree

### Architecture (21 files)

System design deep-dives covering every major subsystem, starting with the C4 model.
| Doc | Description |
| [00_c4_model.md](architecture/00_c4_model.md) | C4 architecture model: System Context → Container → Component → Code |
| [01-planning-system.md](architecture/01-planning-system.md) | Spec State Machine: EXPLORE → PRD → REQUIREMENTS → DESIGN → TASKS → SYNC |
| [02-execution-system.md](architecture/02-execution-system.md) | OrchestratorWorker, sandbox dispatch, task lifecycle |
| [03-discovery-system.md](architecture/03-discovery-system.md) | Adaptive branching when agents find new requirements |
| [04-readjustment-system.md](architecture/04-readjustment-system.md) | Guardian, Conductor, Health Check subsystems |
| [05-frontend-architecture.md](architecture/05-frontend-architecture.md) | Next.js 15 App Router, component structure, state management |
| [06-realtime-events.md](architecture/06-realtime-events.md) | Redis pub/sub, SSE/WebSocket, event types |
| [07-auth-and-security.md](architecture/07-auth-and-security.md) | JWT + OAuth2, session management, RBAC |
| [08-billing-and-subscriptions.md](architecture/08-billing-and-subscriptions.md) | Stripe integration, subscriptions, credits, cost tracking |
| [09-mcp-integration.md](architecture/09-mcp-integration.md) | Model Context Protocol, circuit breakers, tool registry |
| [10-github-integration.md](architecture/10-github-integration.md) | GitHub OAuth, repo operations, webhook handling |
| [11-database-schema.md](architecture/11-database-schema.md) | PostgreSQL 16 + pgvector, 77 model classes, migration strategy |
| [12-configuration-system.md](architecture/12-configuration-system.md) | YAML + env, OmoiBaseSettings, Pydantic validation |
| [13-api-route-catalog.md](architecture/13-api-route-catalog.md) | 38 route modules, REST API overview, endpoint catalog |
| [14-integration-gaps.md](architecture/14-integration-gaps.md) | Known integration issues and resolved gaps |
| [15-llm-service.md](architecture/15-llm-service.md) | Multi-provider LLM abstraction, structured output, caching |
| [16-service-catalog.md](architecture/16-service-catalog.md) | Complete catalog of 119 backend service classes |
| [17-monitoring-replay.md](architecture/17-monitoring-replay.md) | Monitoring replay and trajectory analysis |
| [18-llm-service-internals.md](architecture/18-llm-service-internals.md) | LLM service internals, prompt templates, token tracking |
| [19-git-provider-abstraction.md](architecture/19-git-provider-abstraction.md) | Git provider abstraction layer |

### Page Flows (25 files)

Page-by-page UI flow documentation for every route in the application.

| Doc | Description |
|-----|-------------|
| [00_index.md](page_flows/00_index.md) | Master index of all 68+ page flows |
| [01_authentication.md](page_flows/01_authentication.md) | Authentication, login, registration, OAuth |
| [02_projects_specs.md](page_flows/02_projects_specs.md) | Projects, specs, creation wizard |
| [03_agents_workspaces.md](page_flows/03_agents_workspaces.md) | Agent management, workspaces, kanban |
| [04_kanban_tickets.md](page_flows/04_kanban_tickets.md) | Kanban board, ticket lifecycle, filtering |
| [05_organizations_api.md](page_flows/05_organizations_api.md) | Organizations, teams, API keys |
| [06_visualizations.md](page_flows/06_visualizations.md) | React Flow DAGs, phase overview graphs |
| [07_phases.md](page_flows/07_phases.md) | Phase progression, configuration, monitoring |
| [14_billing.md](page_flows/14_billing.md) | Subscription management, credits, invoices |
| [16_public_pages.md](page_flows/16_public_pages.md) | Landing, pricing, compare, onboarding |
| [17_activity_timeline.md](page_flows/17_activity_timeline.md) | Activity feed, notifications, event timeline |
| [18_prototype_system.md](page_flows/18_prototype_system.md) | Prototype workspace, demo replay |

### User Journey (25 files)

End-to-end user journey documentation from signup to feature completion.

| Doc | Description |
|-----|-------------|
| [00_overview.md](user_journey/00_overview.md) | Journey overview and navigation |
| [01_onboarding.md](user_journey/01_onboarding.md) | First-time user experience |
| [02_feature_planning.md](user_journey/02_feature_planning.md) | Creating and configuring a project |
| [03_execution_monitoring.md](user_journey/03_execution_monitoring.md) | Writing and submitting a feature spec |
| [04_approvals_completion.md](user_journey/04_approvals_completion.md) | Monitoring agent execution |
| [05_optimization.md](user_journey/05_optimization.md) | Reviewing and merging results |
| [09_design_principles.md](user_journey/09_design_principles.md) | UI/UX design principles |
| [16_api_keys_management.md](user_journey/16_api_keys_management.md) | API key lifecycle |
| [17_organization_management.md](user_journey/17_organization_management.md) | Organizations, teams, RBAC |
| [18_sandbox_troubleshooting.md](user_journey/18_sandbox_troubleshooting.md) | Sandbox issue resolution |
| [19_upgrade_migration.md](user_journey/19_upgrade_migration.md) | Upgrading and migrating |

### Design Docs (42 files)

Comprehensive design documentation organized by domain.

#### Service Design (`design/services/`)

Backend service architecture docs — each covers responsibilities, data models, API surface, integration points.

| Doc | Description | Lines |
|-----|-------------|-------|
| [orchestrator_service.md](design/services/orchestrator_service.md) | Main orchestration engine | 822 |
| [guardian_monitoring.md](design/services/guardian_monitoring.md) | Trajectory analysis and intervention | 1,042 |
| [discovery_service.md](design/services/discovery_service.md) | Adaptive requirement discovery | 954 |
| [conductor_coherence.md](design/services/conductor_coherence.md) | Multi-agent coherence detection | 992 |
| [sandbox_spawner.md](design/services/sandbox_spawner.md) | Daytona sandbox lifecycle management | 1,166 |
| [phase_manager.md](design/services/phase_manager.md) | Spec phase state machine | 662 |
| [agent_registry.md](design/services/agent_registry.md) | Agent registration and capabilities | 539 |
| [monitor_service.md](design/services/monitor_service.md) | System health monitoring | 521 |
| [embedding_service.md](design/services/embedding_service.md) | Vector embeddings for semantic search | 530 |
| [event_bus.md](design/services/event_bus.md) | Redis pub/sub event system | 458 |
| [spec_task_execution.md](design/services/spec_task_execution.md) | Spec-to-task execution pipeline | 480 |
| [llm_service_guide.md](design/services/llm_service_guide.md) | LLM service usage guide | 236 |
| [task_queue.md](design/services/task_queue.md) | Priority task queue system | — |
| [auth_service.md](design/services/auth_service.md) | Authentication service | — |
| [diagnostic_service.md](design/services/diagnostic_service.md) | Diagnostic service | — |
| [result_submission.md](design/services/result_submission.md) | Result submission system | — |
| [ticket_workflow.md](design/services/ticket_workflow.md) | Ticket workflow management | — |
| [coordination_service.md](design/services/coordination_service.md) | Coordination service | — |
| [context-validation-system.md](design/services/context-validation-system.md) | Context validation system | — |
| [monitoring-observability-system.md](design/services/monitoring-observability-system.md) | Monitoring and observability | — |
| [branch-management-system.md](design/services/branch-management-system.md) | Branch management | — |
| [sandbox-provisioning-system.md](design/services/sandbox-provisioning-system.md) | Sandbox provisioning | — |
| [authentication-authorization-system.md](design/services/authentication-authorization-system.md) | Auth and authorization | — |
| [agent-execution-system.md](design/services/agent-execution-system.md) | Agent execution | — |
| [ace-system.md](design/services/ace-system.md) | ACE system | — |
| [billing-cost-management-system.md](design/services/billing-cost-management-system.md) | Billing and cost management | — |

#### Frontend Design (`design/frontend/`)

Frontend system architecture — hooks, state, components, flows.

| Doc | Description | Lines |
|-----|-------------|-------|
| [authentication_system.md](design/frontend/authentication_system.md) | JWT + OAuth flows, session management | 591 |
| [onboarding_flow.md](design/frontend/onboarding_flow.md) | 6-step onboarding wizard | 816 |
| [billing_subscriptions.md](design/frontend/billing_subscriptions.md) | Stripe UI, pricing tiers, credits | 977 |
| [organizations_multi_tenancy.md](design/frontend/organizations_multi_tenancy.md) | Org management, RBAC UI | 1,041 |
| [realtime_events_architecture.md](design/frontend/realtime_events_architecture.md) | WebSocket system, reconnection | 1,097 |
| [project_management_dashboard.md](design/frontend/project_management_dashboard.md) | Project management dashboard | — |
| [command_panel_system.md](design/frontend/command_panel_system.md) | Command input, panel sidebar, keyboard shortcuts | 587 |
| [spec_phase_system.md](design/frontend/spec_phase_system.md) | Spec state machine UI, phase progression, evaluators | 489 |
| [sandbox_preview_prototype.md](design/frontend/sandbox_preview_prototype.md) | Sandbox lifecycle, preview panels, prototype workspace | 468 |
| [agent_monitoring_system.md](design/frontend/agent_monitoring_system.md) | Agent execution dashboard, trajectory monitoring | 680 |

#### Integration Design (`design/integration/`)

External service integration architecture.

| Doc | Description |
|-----|-------------|
| [oauth.md](design/integration/oauth.md) | OAuth2 provider configuration |
| [github.md](design/integration/github.md) | GitHub integration |
| [stripe.md](design/integration/stripe.md) | Stripe integration |
| [daytona.md](design/integration/daytona.md) | Daytona sandbox integration |
| [llm_provider.md](design/integration/llm_provider.md) | LLM provider integration |
| [websocket.md](design/integration/websocket.md) | WebSocket integration |

### Troubleshooting (23 files)

Operational guides for diagnosing and fixing issues. See [troubleshooting/README.md](troubleshooting/README.md) for categorized navigation.

| Doc | Description |
|-----|-------------|
| [README.md](troubleshooting/README.md) | Troubleshooting navigation hub with categories |
| [detached_instance_fixes.md](troubleshooting/detached_instance_fixes.md) | SQLAlchemy detached instance errors |
| [database-connections.md](troubleshooting/database-connections.md) | PostgreSQL connection pooling, timeouts, SSL |
| [database-issues.md](troubleshooting/database-issues.md) | PostgreSQL problems, migration failures, pgvector |
| [redis-issues.md](troubleshooting/redis-issues.md) | Redis connection errors, pub/sub, cache invalidation |
| [auth-jwt-troubleshooting.md](troubleshooting/auth-jwt-troubleshooting.md) | JWT token expiration, refresh, session, RBAC |
| [oauth-token-refresh.md](troubleshooting/oauth-token-refresh.md) | OAuth token refresh failures, expired tokens |
| [oauth_redirect_uri_fix.md](troubleshooting/oauth_redirect_uri_fix.md) | OAuth redirect URI misconfigurations |
| [llm-service-failures.md](troubleshooting/llm-service-failures.md) | API key issues, rate limiting, structured output |
| [sandbox-provisioning.md](troubleshooting/sandbox-provisioning.md) | Daytona sandbox provisioning, resource limits |
| [sandbox-lifecycle-errors.md](troubleshooting/sandbox-lifecycle-errors.md) | Sandbox creation, startup, health check failures |
| [sandbox-agent-timeouts.md](troubleshooting/sandbox-agent-timeouts.md) | Agent execution timeouts, infinite loops |
| [phase-transition-failures.md](troubleshooting/phase-transition-failures.md) | SpecStateMachine stuck phases, evaluator failures |
| [websocket-events.md](troubleshooting/websocket-events.md) | WebSocket connection drops, event deduplication |
| [websocket-disconnections.md](troubleshooting/websocket-disconnections.md) | Connection drops, reconnection loops, event loss |
| [billing-sync-failures.md](troubleshooting/billing-sync-failures.md) | Stripe webhook failures, subscription state drift |
| [github-webhook-errors.md](troubleshooting/github-webhook-errors.md) | Webhook validation, payload parsing, rate limiting |
| [embedding-indexing-failures.md](troubleshooting/embedding-indexing-failures.md) | Embedding generation, vector index, search quality |
| [docker-setup.md](troubleshooting/docker-setup.md) | Docker Compose, networking, volumes |
| [migration-issues.md](troubleshooting/migration-issues.md) | Alembic conflicts, schema drift, rollbacks |

### Testing (7 files)

Test strategies, plans, and comprehensive testing guides.

| Doc | Description |
|-----|-------------|
| [frontend-testing-guide.md](testing/frontend-testing-guide.md) | Frontend testing with Vitest, React Testing Library, mocks (1,436 lines) |
| [e2e-testing-guide.md](testing/e2e-testing-guide.md) | End-to-end testing with Playwright, auth fixtures, CI/CD (1,580 lines) |
| [API_TEST_REPORT.md](testing/API_TEST_REPORT.md) | API test coverage report |
| [local_claude_code_testing.md](testing/local_claude_code_testing.md) | Local testing with Claude Code |
| [phase_progression_testing_plan.md](testing/phase_progression_testing_plan.md) | Phase progression test plan |
| [SANDBOX_MONITORING_TEST_PLAN.md](testing/SANDBOX_MONITORING_TEST_PLAN.md) | Sandbox monitoring test plan |
| [file_diff_tracking_test_plan.md](testing/file_diff_tracking_test_plan.md) | File diff tracking test plan |

### Proposals (11 files)

OmoiOS Improvement Proposals (OIPs).

| Doc | Status | Description |
|-----|--------|-------------|
| [README.md](proposals/README.md) | — | OIP process and lifecycle |
| [TEMPLATE.md](proposals/TEMPLATE.md) | — | Proposal template |
| [oip-0001-landing-demo-replay.md](proposals/oip-0001-landing-demo-replay.md) | Proposed | Landing page demo replay |
| [oip-0002-public-prototype-workspace.md](proposals/oip-0002-public-prototype-workspace.md) | Proposed | Public prototype workspace |
| [oip-0003-streamlined-onboarding.md](proposals/oip-0003-streamlined-onboarding.md) | Proposed | Streamlined onboarding flow |
| [oip-0004-live-demo-sandbox.md](proposals/oip-0004-live-demo-sandbox.md) | Proposed | Live demo sandbox |
| [oip-0005-bring-your-own-keys.md](proposals/oip-0005-bring-your-own-keys.md) | Proposed | Bring your own API keys |
| [oip-0006-local-orchestration-dev-mode.md](proposals/oip-0006-local-orchestration-dev-mode.md) | Proposed | Local orchestration dev mode |
| [oip-0007-local-dev-service-abstraction.md](proposals/oip-0007-local-dev-service-abstraction.md) | Proposed | Local dev service abstraction |

### Requirements (16 files)

Feature requirements organized by domain.

| Directory | Files | Description |
|-----------|-------|-------------|
| [agents/](requirements/agents/) | 5 | Agent lifecycle, orchestration, validation |
| [workflows/](requirements/workflows/) | 4 | Workflow requirements, task queue, ticket flow |
| [monitoring/](requirements/monitoring/) | 2 | Fault tolerance, monitoring architecture |
| [auth/](requirements/auth/) | 1 | Authentication system requirements |
| [memory/](requirements/memory/) | 1 | Memory system requirements |
| [projects/](requirements/projects/) | 1 | Project creation requirements |
| [integration/](requirements/integration/) | 1 | MCP server integration requirements |

### Guides (9 files)

Developer and operational guides.

| Doc | Description |
|-----|-------------|
| [BILLING_FRONTEND_DEVELOPMENT_GUIDE.md](guides/BILLING_FRONTEND_DEVELOPMENT_GUIDE.md) | Billing UI development guide |
| [DOCKER_CLOUD_AGENT.md](guides/DOCKER_CLOUD_AGENT.md) | Docker cloud agent deployment |
| [oauth_frontend_integration.md](guides/oauth_frontend_integration.md) | OAuth frontend integration guide |
| [fumadocs-documentation-system.md](guides/fumadocs-documentation-system.md) | Documentation system guide |
| [fumadocs-blog-system.md](guides/fumadocs-blog-system.md) | Blog system guide |
| [fumadocs-seo-guide.md](guides/fumadocs-seo-guide.md) | SEO configuration guide |
| [ticket-analysis-guide.md](guides/ticket-analysis-guide.md) | Ticket analysis guide |
| [PROJECT_RULES.md](guides/PROJECT_RULES.md) | Project coding rules |
| [README_AI_ORGANIZATION.md](guides/README_AI_ORGANIZATION.md) | AI organization guide |

### Other Directories

| Directory | Files | Description |
|-----------|-------|-------------|
| [implementation/](implementation/) | 30 | Implementation details and guides |
| [archive/](archive/) | 23 | Archived/historical documentation |
| [figma_prompts/](figma_prompts/) | 16 | Figma Make UI generation prompts |
| [security/](security/) | 1 | Security documentation |
| [deployment/](deployment/) | 1 | Deployment documentation |
| [memory/](memory/) | 1 | Memory system docs |
| [diagnostic/](diagnostic/) | 1 | Diagnostic agent docs |
| [guardian/](guardian/) | 1 | Guardian agent docs |
| [results/](results/) | 1 | Result submission docs |
| [cost_tracking/](cost_tracking/) | 1 | Cost tracking docs |
| [mcp/](mcp/) | 1 | MCP protocol docs |
| [comparisons/](comparisons/) | 2 | System comparisons |
| [libraries/](libraries/) | 2 | Library documentation |
| [plans/](plans/) | 4 | Planning documents |
| [experiments/](experiments/) | 3 | Experimental features |
| [features/](features/) | 1 | Feature specs |
| [tasks/](tasks/) | 1 | Task documentation |
| [diagrams/](diagrams/) | 1 | Architecture diagrams |

## Top-Level Reference Docs

| Doc | Description |
|-----|-------------|
| [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) | Comprehensive project overview — start here for new contributors |
| [go_to_market_strategy.md](go_to_market_strategy.md) | Go-to-market strategy |
| [marketing_overview.md](marketing_overview.md) | Marketing strategy overview |
| [frontend_implementation_guide.md](frontend_implementation_guide.md) | Frontend implementation guide |
| [OmoiOS_API_Reference.md](OmoiOS_API_Reference.md) | Complete backend API reference (300+ endpoints) |

## Documentation Statistics

| Category | Files | Primary Audience |
|----------|-------|-----------------|
| Architecture | 21 | Backend developers, architects |
| Page Flows | 25 | Frontend developers, designers |
| User Journey | 25 | Product managers, QA, designers |
| Design (all subdirs) | 42 | All developers |
| Troubleshooting | 23 | DevOps, developers |
| Testing | 7 | All developers |
| Proposals | 11 | Product, architects |
| Requirements | 16 | Product, architects |
| Guides | 9 | All developers |
| Implementation | 30 | Backend developers |
| Other | 120+ | Various |
| **Total** | **384+** | |

## Contributing to Documentation

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the full contribution guide. Key points:

1. **New features** → Write an OIP in `proposals/`
2. **New services** → Add a design doc in `design/services/`
3. **New pages** → Add a page flow in `page_flows/`
4. **Bug fixes** → Update troubleshooting if applicable
5. **Cross-link** → Add "Related Documentation" sections to new docs

### Documentation Standards

- Each doc should have a header with: Created date, Status, Purpose, Related docs
- Use Mermaid diagrams for architecture and flow visualizations
- Include API surface documentation with TypeScript/Python type signatures
- Cross-reference related docs with relative links
- Keep files under 800 lines — split if larger

## Documentation Audit Status
- **Architecture Docs**: Audited and literal markers resolved.
- **Frontend Components**: Deferred to tech debt proposal (`docs/proposals/frontend-component-documentation-debt.md`) to unblock the current release.
- **Missing Files**: `autonomous-execution-feature.md` and `kanban-board-yaml-phase-loader-complete.md` confirmed missing and removed from active tracking.
