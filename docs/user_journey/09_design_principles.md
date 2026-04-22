# 9 Design Principles

**Part of**: [User Journey Documentation](./README.md)

---

## Core Design Philosophy

OmoiOS is built on three foundational principles that guide every design decision:

### Spec-Driven Development

Every feature starts with a specification that evolves through structured phases. The UI reflects this progression:

- **Phase-aware interfaces**: Each phase (EXPLORE → REQUIREMENTS → DESIGN → TASKS → SYNC) has dedicated UI patterns that match its purpose
- **Artifact visibility**: Requirements, designs, and tasks are always accessible, not buried in chat history
- **Versioned progression**: Users can see how specs evolved and compare versions
- **Approval gates**: Clear visual indicators when human input is required

### Autonomous Execution

The system runs independently, but users remain in control:

- **Fire-and-forget with oversight**: Start work, walk away, check in when convenient
- **Progress without polling**: Real-time updates push information to users, not the other way around
- **Intervention when needed**: Clear pathways to pause, redirect, or stop agents
- **Confidence through transparency**: Complete visibility into what agents are doing and why

### Radical Transparency

Nothing happens in a black box:

- **Complete event logs**: Every file edit, command, and decision is recorded
- **Live execution view**: Watch agents work in real-time with terminal output
- **Decision trails**: Understand why agents made specific choices
- **Cost visibility**: Real-time tracking of compute and token costs

---

## UX Principles

### Progressive Disclosure

Information is revealed as users need it, not all at once:

- **Command Center entry**: Simple prompt interface that expands to show advanced options (model selection, workflow mode, branch targeting)
- **Collapsible spec sections**: Requirements, designs, and tasks can be expanded/collapsed based on user focus
- **Contextual panels**: Sidebar content changes based on the active route and user context
- **Breadcrumb navigation**: Deep hierarchies (projects → specs → tasks → sandboxes) remain navigable

**Implementation**: The IconRail + ContextualPanel layout provides persistent navigation while keeping the main content area focused.

### Clear Feedback Loops

Users always know the system state:

- **Status badges**: Live indicators for agent health, spec phase, and sandbox state
- **Progress indicators**: Animated progress bars for long-running operations
- **Toast notifications**: Non-intrusive updates for completed actions
- **Connection status**: WebSocket health indicator shows real-time connectivity
- **Agent heartbeat**: Visual pulse showing active agent work

**Pattern**: Use the `--color-success`, `--color-warning`, `--color-info` semantic tokens consistently across all status indicators.

### Error Recovery

When things go wrong, recovery is clear:

- **Graceful degradation**: If WebSocket fails, polling takes over automatically
- **Retry with backoff**: Failed operations show countdown to next attempt
- **Intervention tools**: One-click buttons to redirect stuck agents
- **Sandbox restart**: Clear option to respawn failed sandboxes
- **Rollback visibility**: See previous versions and revert when needed

**Pattern**: Error states use `--color-destructive` with clear action buttons, never just red text.

### Consistency Across Contexts

Similar actions work similarly everywhere:

- **Command palette**: `Cmd+K` available on every page for quick actions
- **Keyboard shortcuts**: `Cmd+1-4` for main sections, `Cmd+B` for sidebar toggle
- **Card patterns**: Spec cards, task cards, and sandbox cards share interaction patterns
- **Form layouts**: Consistent label positioning, validation messages, and submit patterns

---

## Visual Design Principles

### Linear/Arc Aesthetic

- Clean, minimal, white-space-heavy
- Modern SaaS look
- Smooth animations
- Gentle shadows and subtle gradients

### Notion-Style Structured Blocks

- Spec workspace uses structured blocks for requirements/design
- Collapsible sections
- Rich text editing
- Block-level comments

### Obsidian-Style Sidebar

- Collapsible sidebar for spec navigation
- Quick access to all specs
- Search within sidebar
- Recent specs list

### Real-Time Indicators

- Live status badges
- Animated progress indicators
- WebSocket connection status
- Agent heartbeat indicators

### Color System

Semantic tokens defined in CSS with light/dark variants:

- `--color-primary`, `--color-secondary`, `--color-destructive` — Actions
- `--color-muted`, `--color-accent` — UI accents
- `--color-background`, `--color-foreground`, `--color-border` — Layout
- `--color-success`, `--color-warning`, `--color-info` — Status
- `--color-sidebar`, `--color-sidebar-*` — Sidebar theming
- `--color-chart-1` through `--color-chart-5` — Data visualization

### Spacing and Radius

- `--radius-lg: 0.5rem` (cards, large buttons)
- `--radius-md: 6px` (medium elements)
- `--radius-sm: 4px` (small elements)

---

## Interaction Patterns

### Command Palette

The universal entry point for actions:

- **Trigger**: `Cmd+K` or click the search icon
- **Scope**: Context-aware suggestions based on current page
- **Recent actions**: Quick re-run of previous commands
- **Keyboard navigation**: Arrow keys + Enter for selection

**Usage**: Project switching, spec creation, agent spawning, settings access.

### Contextual Panels

The sidebar adapts to the active route:

- **ProjectsPanel**: Project list, recent specs, quick actions
- **TasksPanel**: Task filters, status breakdown, assignment view
- **HealthPanel**: Agent trajectories, intervention tools, system status
- **GraphFilters**: Dependency graph controls, layout options

**Pattern**: Panel content is route-aware via `ContextualPanel.tsx`.

### Real-Time Updates

WebSocket-powered live updates:

- **Event streaming**: Sandbox events appear as they happen
- **State synchronization**: Spec phases advance automatically
- **Cost tracking**: Live cost counters update per event
- **Agent status**: Health indicators reflect current state

**Fallback**: If WebSocket disconnects, the UI polls gracefully.

### Three-Column Layout

The authenticated app uses a consistent three-column layout:

```
┌──────────────────────────────────────────────────────┐
│ MinimalHeader (breadcrumbs, context, user menu)       │
├─────────┬──────────────────┬─────────────────────────┤
│ IconRail│ ContextualPanel  │ Main Content             │
│  (14w)  │   (16rem)        │   (flex-1)               │
│         │                  │                           │
│ Terminal│ Changes based on │ Route page content        │
│ Folder  │ active section   │                           │
│ Box     │                  │                           │
│ Building│                  │                           │
│         │                  │                           │
│ ─────── │                  │                           │
│ Settings│                  │                           │
└─────────┴──────────────────┴─────────────────────────┘
```

---

## Accessibility Principles

### Keyboard Navigation

- All interactive elements are keyboard accessible
- `Tab` order follows visual hierarchy
- `Escape` closes modals and panels
- `Cmd+K` opens command palette from anywhere
- Skip links for screen reader users

### Screen Reader Support

- Semantic HTML structure
- ARIA labels for icon-only buttons
- Live regions for real-time updates
- Status announcements for agent state changes

### Visual Accessibility

- Minimum contrast ratio 4.5:1 for text
- Focus indicators visible on all interactive elements
- Color is never the sole indicator (icons + text)
- Reduced motion support via `prefers-reduced-motion`

### Responsive Design

- Mobile-first breakpoints
- Touch targets minimum 44x44px
- Sidebar collapses to drawer on small screens
- Tables convert to cards on mobile

---

## Success Metrics

### User Experience Goals

- **Reduced monitoring time**: From hours to minutes per day
- **Faster delivery**: Agents work 24/7 autonomously
- **Clear visibility**: Complete transparency into agent activity
- **Confidence**: Trust system enough to approve PRs without manual review

### System Goals

- **Autonomous execution**: Agents handle 80%+ of work without intervention
- **Self-healing**: Guardian detects and fixes 90%+ of stuck workflows
- **Discovery-driven**: System adapts to new requirements automatically
- **Quality gates**: 95%+ of PRs pass on first approval

---

**Next**: See [README.md](./README.md) for complete documentation index.
