# Part 16: Service Catalog

> Complete catalog of all backend services (119 service classes across 119 files).

## Overview

This is the comprehensive catalog of all 119 services in `backend/omoi_os/services/`.

## Core (1)

| File | Class | Description |
| :--- | :--- | :--- |
| database.py | DatabaseService | Manages database connections and provides session context manager |

## Auth (5)

| File | Class | Description |
| :--- | :--- | :--- |
| oauth_service.py | OAuthService | OAuth authentication flows |
| authorization_service.py | AuthorizationService | RBAC and permission checking |
| credentials.py | CredentialsService | User credentials for managing external API keys |
| auth_service.py | AuthService | Authentication service for user management and token generation |
| token_blacklist.py | TokenBlacklistService | Redis-based token blacklist for JWT invalidation |

## Billing (4)

| File | Class | Description |
| :--- | :--- | :--- |
| billing_service.py | BillingService | Invoice and payment management |
| subscription_service.py | SubscriptionService | Tier-based subscription management |
| cost_tracking.py | CostTrackingService | LLM API cost tracking and analysis |
| budget_enforcer.py | BudgetEnforcerService | Budget limit enforcement and alerts |

## Execution (4)

| File | Class | Description |
| :--- | :--- | :--- |
| daytona_spawner.py | DaytonaSpawnerService | Manages Daytona sandbox lifecycle |
| agent_executor.py | AgentExecutor | DEPRECATED — OpenHands SDK wrapper |
| sandbox_git_operations.py | SandboxGitOperations | Git merge operations in sandboxes |
| convergence_merge_service.py | ConvergenceMergeService | DAG convergence point merge orchestration |

## Monitoring (11)

| File | Class | Description |
| :--- | :--- | :--- |
| monitor.py | MonitorService | Metrics collection and anomaly detection |
| guardian.py | GuardianService | Emergency intervention for critical failures |
| watchdog.py | WatchdogService | Meta-monitoring of monitor agents |
| intelligent_guardian.py | IntelligentGuardian | LLM-powered trajectory analysis |
| monitoring_loop.py | MonitoringLoop | Complete monitoring workflow orchestration |
| conductor.py | ConductorService | System coherence analysis and duplicate detection |
| heartbeat_protocol.py | HeartbeatProtocolService | Heartbeat with sequence tracking and gap detection |
| agent_status_manager.py | AgentStatusManager | Agent status state machine |
| composite_anomaly_scorer.py | CompositeAnomalyScorer | Agent-level anomaly scoring |
| baseline_learner.py | BaselineLearner | EMA-based baseline learning for anomaly detection |
| agent_registry.py | AgentRegistryService | Agent CRUD, capability updates, discovery |

## Memory & Discovery (3)

| File | Class | Description |
| :--- | :--- | :--- |
| memory.py | MemoryService | Task execution history and pattern learning |
| discovery.py | DiscoveryService | Adaptive workflow branching |
| discovery_analyzer.py | DiscoveryAnalyzer | LLM-powered discovery pattern analysis |

## MCP Integration (6)

| File | Class | Description |
| :--- | :--- | :--- |
| mcp_integration.py | MCPIntegrationService | MCP tool invocation orchestration |
| mcp_authorization.py | MCPAuthorizationService | Per-agent, per-tool MCP authorization |
| mcp_retry.py | MCPRetryManager | Exponential backoff retry with idempotency |
| mcp_circuit_breaker.py | MCPCircuitBreaker | Per-server+tool circuit breaker |
| mcp_client.py | MCPClientService | Remote MCP tool invocation client |
| mcp_registry.py | MCPRegistryService | MCP tool registry for server discovery and tool registration |

## Git & GitHub (3)

| File | Class | Description |
| :--- | :--- | :--- |
| github_integration.py | GitHubIntegrationService | Repository integration and webhooks |
| github_api.py | GitHubAPIService | GitHub API wrapper |
| repository_service.py | RepositoryService | Repository operations |

## Coordination & DAG (4)

| File | Class | Description |
| :--- | :--- | :--- |
| coordination.py | CoordinationService | Multi-agent sync/split/join/merge patterns |
| orchestrator_coordination.py | OrchestratorCoordination | Pattern-based task generation |
| dependency_graph.py | DependencyGraphService | DAG visualization and critical path |
| pattern_loader.py | PatternLoader | YAML coordination pattern config |

## Phase Management (5)

| File | Class | Description |
| :--- | :--- | :--- |
| phase_manager.py | PhaseManager | Unified phase operations |
| phase_gate.py | PhaseGateService | Phase gate validation |
| phase_progression_service.py | PhaseProgressionService | Automatic ticket advancement |
| phase_loader.py | PhaseLoader | YAML phase configuration |
| fixture_phase_runner.py | FixturePhaseRunner | Runs spec phases using pre-recorded reference outputs |

## Task Management (7)

| File | Class | Description |
| :--- | :--- | :--- |
| task_queue.py | TaskQueueService | Task assignment and lifecycle |
| task_validator.py | TaskValidatorService | Validator agent spawning |
| task_context_builder.py | TaskContextBuilder | Sandbox execution context building |
| task_requirements_analyzer.py | TaskRequirementsAnalyzer | LLM-powered task analysis |
| task_dedup.py | TaskDeduplicationService | pgvector-based task dedup |
| task_scorer.py | TaskScorer | Dynamic task prioritization |
| spec_task_execution.py | SpecTaskExecutionService | SpecTask sandbox execution |

## Validation & Quality (6)

| File | Class | Description |
| :--- | :--- | :--- |
| validation_orchestrator.py | ValidationOrchestrator | Validation state machine |
| validation_agent.py | ValidationAgent | PydanticAI phase gate reviews |
| spec_acceptance_validator.py | SpecAcceptanceValidator | Acceptance criteria validation |
| quality_checker.py | QualityCheckerService | Code quality metrics |
| quality_predictor.py | QualityPredictorService | Memory-based quality prediction |
| validation_helpers.py | Module | File validation helpers for result submission |

## Events & Messaging (3)

| File | Class | Description |
| :--- | :--- | :--- |
| event_bus.py | EventBusService | Redis Pub/Sub event system |
| reasoning_listener.py | ReasoningListener | Event-to-reasoning chain |
| message_queue.py | RedisMessageQueue | Redis message queue for sandboxes |

## LLM & AI (7)

| File | Class | Description |
| :--- | :--- | :--- |
| llm_service.py | LLMService | LLM completion and structured output |
| pydantic_ai_service.py | PydanticAIService | PydanticAI/Fireworks.ai backend |
| embedding.py | EmbeddingService | Text embeddings for similarity search |
| llm_factory.py | create_llm_service | Factory for creating LLM services based on mode config |
| null_llm_service.py | NullLLMService | Returns placeholder responses without making API calls |
| recording_llm_service.py | RecordingLLMService | Records LLM calls to disk for later replay |
| replay_llm_service.py | ReplayLLMService | Replays cached responses from disk recordings |

## Workspace (3)

| File | Class | Description |
| :--- | :--- | :--- |
| workspace_manager.py | WorkspaceManager | Git-backed workspace management |
| prototype_manager.py | PrototypeManager | Rapid prompt-to-preview prototyping |
| idle_sandbox_monitor.py | IdleSandboxMonitor | Idle sandbox detection and termination |

## Spec & Ticket Processing (7)

| File | Class | Description |
| :--- | :--- | :--- |
| spec_sync.py | SpecSyncService | Phase data sync with deduplication |
| spec_completion_service.py | SpecCompletionService | Post-completion and PR creation |
| spec_dedup.py | SpecDeduplicationService | Multi-level spec deduplication |
| ticket_dedup.py | TicketDeduplicationService | Embedding-based ticket dedup |
| ticket_workflow.py | TicketWorkflowOrchestrator | Kanban state machine |
| board.py | BoardService | Kanban board operations |
| spec_driven_settings.py | SpecDrivenSettingsService | Spec-driven development settings |

## Agent Operations (7)

| File | Class | Description |
| :--- | :--- | :--- |
| restart_orchestrator.py | RestartOrchestrator | Automatic agent restart protocol |
| diagnostic.py | DiagnosticService | Stuck workflow detection |
| trajectory_context.py | TrajectoryContext | Agent trajectory thinking context |
| agent_output_collector.py | AgentOutputCollector | Agent conversation output collection |
| conversation_intervention.py | ConversationInterventionService | Guardian steering interventions |
| result_submission.py | ResultSubmissionService | Task/workflow result handling |
| collaboration.py | CollaborationService | Agent-to-agent messaging |

## Context (2)

| File | Class | Description |
| :--- | :--- | :--- |
| context_service.py | ContextService | Cross-phase context aggregation |
| context_summarizer.py | ContextSummarizer | PydanticAI context summarization |

## Other (14)

| File | Class | Description |
| :--- | :--- | :--- |
| alerting.py | AlertingService | Alert rule evaluation and routing |
| approval.py | ApprovalService | Human-in-the-loop approval workflow |
| email_service.py | EmailService | Transactional emails via Resend |
| conflict_scorer.py | ConflictScorer | Least-conflicts-first merge ordering |
| agent_conflict_resolver.py | AgentConflictResolver | LLM-based git conflict resolution |
| template_service.py | TemplateService | Jinja2 template rendering |
| title_generation_service.py | TitleGenerationService | LLM title generation |
| resource_lock.py | ResourceLockService | Distributed resource locking |
| ownership_validation.py | OwnershipValidationService | File ownership conflict prevention |
| synthesis_service.py | SynthesisService | Result synthesis at sync points |
| preview_manager.py | PreviewManager | Manages preview session lifecycle and event publishing |
| stripe_service.py | StripeService | Stripe integration service for payment processing |
| claude_agent_worker.py | Module | Claude Agent SDK worker for sandbox execution |
| session_agent_config_restorer.py | SessionAgentConfigRestorer | Restores agent configuration from checkpoints |
## Git Providers (4)

| File | Class | Description |
| :--- | :--- | :--- |
| git_provider.py | GitProvider | Protocol for Git hosting operations |
| local_git_provider.py | LocalGitProvider | GitProvider using local bare Git repositories |
| git_factory.py | create_git_provider | Factory for creating GitProvider based on config |
| github_provider.py | GitHubProvider | GitProvider backed by GitHub API |

## Sandbox Providers (4)

| File | Class | Description |
| :--- | :--- | :--- |
| sandbox_provider.py | SandboxProvider | Protocol for sandbox lifecycle management |
| daytona_provider.py | DaytonaProvider | SandboxProvider backed by Daytona Cloud |
| local_docker_provider.py | LocalDockerProvider | SandboxProvider using local Docker containers |
| sandbox_factory.py | create_sandbox_provider | Factory for creating SandboxProvider based on config |

## Branch Management (3)

| File | Class | Description |
| :--- | :--- | :--- |
| branch_preview.py | BranchPreview | Branch strategy preview dataclasses |
| branch_strategy_preview.py | BranchStrategyPreviewService | Preview branch strategy without hitting GitHub/Daytona |
| branch_workflow.py | BranchWorkflowService | Branch workflow service for ticket-based development |

## Agent Health (2)

| File | Class | Description |
| :--- | :--- | :--- |
| agent_health.py | AgentHealthService | Service for monitoring agent health and managing heartbeats |
| monitoring_replay.py | MonitoringReplayService | Feeds recorded agent sessions to Guardian/Conductor for testing |

## ACE Workflow (4)

| File | Class | Description |
| :--- | :--- | :--- |
| ace_engine.py | ACEEngine | ACE workflow engine orchestrator |
| ace_executor.py | Executor | ACE Phase 1: memory record creation |
| ace_reflector.py | Reflector | ACE Phase 2: feedback error analysis |
| ace_curator.py | Curator | ACE Phase 3: playbook insight updates |

## Service Initialization

- API server (`api/main.py`): ~27 services initialized at startup
- Orchestrator worker (`workers/orchestrator_worker.py`): ~8 services initialized
- Some services are initialized per-request (noted in `14-integration-gaps.md`)


## Related Documentation

### Architecture Deep-Dives
- [Part 1: Planning System](01-planning-system.md) — Spec services
- [Part 2: Execution System](02-execution-system.md) — Execution services
- [Part 3: Discovery System](03-discovery-system.md) — Discovery services
- [Part 4: Readjustment System](04-readjustment-system.md) — Monitoring services
- [Part 7: Auth & Security](07-auth-and-security.md) — Auth services
- [Part 8: Billing & Subscriptions](08-billing-and-subscriptions.md) — Billing services
- [Part 9: MCP Integration](09-mcp-integration.md) — MCP services
- [Part 11: Database Schema](11-database-schema.md) — Data services
- [Part 12: Configuration System](12-configuration-system.md) — Config services
- [Part 13: API Route Catalog](13-api-route-catalog.md) — API services
- [Part 14: Integration Gaps](14-integration-gaps.md) — Service integration
- [Part 15: LLM Service](15-llm-service.md) — LLM services

### Design Docs
- [Monitoring Architecture](../requirements/monitoring/monitoring_architecture.md) — Monitoring services
- [Task Queue](../design/services/task_queue.md) — Task services
- [LLM Service Guide](../design/services/llm_service_guide.md) — LLM services

### Requirements
- [Monitoring](../requirements/monitoring/monitoring_architecture.md) — Monitoring requirements
- [Task Queue](../requirements/workflows/task_queue.md) — Task requirements