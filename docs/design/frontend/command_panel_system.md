# OmoiOS Command + Panel System Design

## Overview

The Command + Panel system is the primary user interaction surface for OmoiOS. It provides a three-column layout consisting of:

1. **Icon Rail** — Navigation sidebar with section icons
2. **Contextual Panel** — Route-aware sidebar showing relevant information
3. **Main Content Area** — Primary workspace for the active page

This document describes the component architecture, data flow, and interaction patterns.

---

## Component Hierarchy

```
MainLayout (layout shell)
├── IconRail (navigation)
├── ContextualPanel (route-aware sidebar)
│   └── [Dynamic Panel Component]
└── Main Content Area
    ├── MinimalHeader
    └── Page Content (e.g., CommandCenterPage)
        └── Command Components
```

---

## Core Components

### 1. MainLayout

**File:** `frontend/components/layout/MainLayout.tsx`

The root layout shell that orchestrates the three-column structure.

| Prop | Type | Description |
|------|------|-------------|
| `children` | `React.ReactNode` | Page content to render in main area |

**State Management:**
- `activeSection`: Current navigation section (`NavSection`)
- `isPanelCollapsed`: Boolean for panel visibility

**Keyboard Shortcuts:**
| Shortcut | Action |
|----------|--------|
| `Cmd/Ctrl + 1` | Navigate to Command |
| `Cmd/Ctrl + 2` | Navigate to Projects |
| `Cmd/Ctrl + 3` | Navigate to Sandboxes |
| `Cmd/Ctrl + 4` | Navigate to Analytics |
| `Cmd/Ctrl + B` | Toggle panel collapse |

**Route-to-Section Mapping:**
```typescript
/command → "command"
/projects, /board → "projects"
/sandboxes, /sandbox/* → "sandboxes"
/phases → "phases"
/analytics → "analytics"
/organizations → "organizations"
/settings → "settings"
```

---

### 2. IconRail

**File:** `frontend/components/layout/IconRail.tsx`

A 56px-wide vertical navigation bar with icon buttons.

| Prop | Type | Description |
|------|------|-------------|
| `activeSection` | `NavSection` | Currently active section |
| `onSectionChange` | `(section: NavSection) => void` | Section change callback |

**Navigation Sections (`NavSection`):**
```typescript
type NavSection = 
  | "command"      // Terminal icon
  | "projects"     // FolderGit2 icon
  | "phases"       // Workflow icon (disabled)
  | "sandboxes"    // Box icon
  | "analytics"    // BarChart3 icon (disabled)
  | "organizations" // Building2 icon
  | "settings";     // Settings icon (bottom)
```

**Features:**
- Tooltips on hover showing section labels
- Active state highlighting with primary color
- Badge support for notification counts
- OmoiOS logo at top linking to `/command`

---

### 3. ContextualPanel

**File:** `frontend/components/layout/ContextualPanel.tsx`

A 256px-wide (or 40px when collapsed) sidebar that renders contextually based on route.

| Prop | Type | Description |
|------|------|-------------|
| `activeSection` | `NavSection` | Current section from IconRail |
| `pathname` | `string` | Current URL path |
| `isCollapsed` | `boolean` | Panel collapsed state |
| `onToggleCollapse` | `() => void` | Toggle callback |

**Panel Selection Logic:**

The panel is selected via a two-tier priority system:

**Tier 1: Route-Specific Panels** (checked first)
| Route Pattern | Panel Component |
|---------------|-----------------|
| `/projects/*/settings` | `ProjectSettingsPanel` |
| `/health*` | `HealthPanel` |
| `/graph*` | `GraphFiltersPanel` |
| `/diagnostic*` | `DiagnosticContextPanel` |
| `/activity*` | `ActivityFiltersPanel` |
| `/board*` | `ProjectsPanel` |
| `/phases*` | `PhasesPanel` |
| `/sandbox*` | `TasksPanel` (with pathname) |

**Tier 2: Section-Based Panels** (fallback)
| Section | Panel Component |
|---------|-----------------|
| `command`, `sandboxes` | `TasksPanel` |
| `projects` | `ProjectsPanel` |
| `phases` | `PhasesPanel` |
| `analytics` | `AnalyticsPanel` |
| `settings` | `SettingsPanel` |
| `organizations` | `OrganizationsPanel` |
| default | `TasksPanel` |

---

## Command Components

### CommandCenterPage

**File:** `frontend/app/(app)/command/page.tsx`

The main command input interface where users submit feature requests.

**State Machine (`LaunchState`):**
```typescript
type LaunchState =
  | { status: "idle" }
  | { status: "creating_ticket"; prompt: string }
  | { status: "launching_spec"; prompt: string }
  | { status: "waiting_for_sandbox"; ticketId: string; prompt: string; mode: WorkflowMode; projectId: string }
  | { status: "redirecting"; destination: string };
```

**Workflow Modes:**
| Mode | Description | Redirect Target |
|------|-------------|-----------------|
| `quick` | Immediate implementation | `/sandbox/{id}` |
| `spec_driven` | Plan first, then build | `/projects/{id}/specs/{specId}` |

**Key Hooks:**
- `useProjects()` — Fetch available projects
- `useGitHubRepos()` — Fetch user's GitHub repositories
- `useCreateTicket()` — Create ticket for quick mode
- `useLaunchSpec()` — Launch spec-driven workflow
- `useEvents()` — Listen for sandbox creation events

---

### PromptInput

**File:** `frontend/components/command/PromptInput.tsx`

The primary text input for command entry.

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `onSubmit` | `(prompt: string) => void` | — | Submit callback |
| `isLoading` | `boolean` | `false` | Loading state |
| `placeholder` | `string` | "Ask Cursor to build..." | Input placeholder |
| `submitLabel` | `string` | — | Custom submit button text |

**Features:**
- Auto-resizing textarea (max 200px height)
- Enter to submit, Shift+Enter for new line
- File attachment button (placeholder)
- Loading spinner during submission

---

### RepoSelector

**File:** `frontend/components/command/RepoSelector.tsx`

Project and repository selection with branch picker.

| Prop | Type | Description |
|------|------|-------------|
| `projects` | `Project[]` | Available OmoiOS projects |
| `repositories` | `Repository[]` | Available GitHub repos |
| `selectedProject` | `Project \| null` | Currently selected project |
| `selectedRepo` | `string \| null` | Selected repo (owner/repo) |
| `selectedBranch` | `string` | Selected git branch |
| `onProjectSelect` | `(project: Project) => void` | Project selection callback |
| `onRepoSelect` | `(repo: string) => void` | Repo selection callback |
| `onBranchChange` | `(branch: string) => void` | Branch change callback |

**Interfaces:**
```typescript
interface Project {
  id: string;
  name: string;
  repo?: string;        // GitHub owner/repo format
  ticketCount: number;
}

interface Repository {
  fullName: string;     // "owner/repo" format
  isPrivate: boolean;
}
```

---

### WorkflowModeSelector

**File:** `frontend/components/command/WorkflowModeSelector.tsx`

Toggle between quick and spec-driven execution modes.

| Prop | Type | Description |
|------|------|-------------|
| `value` | `WorkflowMode` | Current mode |
| `onValueChange` | `(value: WorkflowMode) => void` | Change callback |

**Mode Configuration:**
```typescript
type WorkflowMode = "quick" | "spec_driven";

interface WorkflowModeOption {
  id: WorkflowMode;
  name: string;
  description: string;
  icon: React.ComponentType;
  placeholder: string;
  helperText: string;
  submitLabel: string;
}
```

---

### CommandPalette

**File:** `frontend/components/command/CommandPalette.tsx`

Global command palette for quick navigation and actions.

| Prop | Type | Description |
|------|------|-------------|
| `open` | `boolean` | Visibility state |
| `onOpenChange` | `(open: boolean) => void` | Visibility callback |

**Command Groups:**
1. **Navigation** — Quick links to main pages
2. **Projects** — Recent projects (filtered by search)
3. **Agents** — Active agents
4. **Tickets** — Recent tickets (search-only)
5. **Quick Actions** — Create project, spawn agent
6. **Tools** — Graph, diagnostic, commits
7. **Settings** — All settings subpages

---

## Panel Components

### TasksPanel

**File:** `frontend/components/panels/TasksPanel.tsx`

Displays sandbox tasks grouped by status.

| Prop | Type | Description |
|------|------|-------------|
| `pathname` | `string` | Optional pathname for sandbox selection |

**Features:**
- Search filtering by title, type, or ID
- Sort options: status (grouped), newest, oldest, name
- Status groups: Running, Validating, Pending Validation, Pending, Completed, Failed
- Task selection highlighting based on current sandbox
- "Mark as failed" action for running/pending tasks

**Task Status Mapping:**
```typescript
type TaskStatus = 
  | "pending" 
  | "assigned" 
  | "running" 
  | "completed" 
  | "failed"
  | "pending_validation"
  | "validating";
```

---

### ProjectsPanel

**File:** `frontend/components/panels/ProjectsPanel.tsx`

Project list with current project context.

**Features:**
- Current project indicator with quick navigation links (Board, Specs, Graph, Settings)
- Favorites section (first 2 active projects)
- Active projects list with status indicators
- Paused/archived projects section
- Search filtering
- "New Project" button

**Route-Aware Selection:**
Extracts project ID from `/projects/[id]`, `/board/[projectId]`, or `/graph/[projectId]` routes.

---

### AgentsPanel

**File:** `frontend/components/panels/AgentsPanel.tsx`

Agent list grouped by status.

**Features:**
- Search by agent type or ID
- Status groups: Running, Completed, Errored
- Time ago formatting for agent creation
- "New Agent" button linking to `/agents/spawn`

---

### SettingsPanel

**File:** `frontend/components/panels/SettingsPanel.tsx`

Settings navigation with grouped sections.

**Navigation Groups:**
| Group | Items |
|-------|-------|
| Account | Profile, Security, Notifications, Appearance |
| Developer | API Keys, Integrations (disabled) |
| Organization | Team, Billing (disabled) |

**Features:**
- Active state highlighting based on current route
- Disabled item badges ("Soon")
- Sign out button
- Help & Support link

---

## Data Flow

### Command Submission Flow

```
User Input
    ↓
PromptInput.onSubmit()
    ↓
CommandCenterPage.handleSubmit()
    ↓
[Spec-Driven Mode]
    └── launchSpecMutation.mutateAsync()
        └── Redirect to /projects/{id}/specs/{specId}
[Quick Mode]
    └── createTicketMutation.mutateAsync()
        └── setLaunchState("waiting_for_sandbox")
            └── WebSocket Event: SANDBOX_CREATED
                └── handleSandboxReady()
                    └── Redirect to /sandbox/{id} or /board/{id}
```

### Panel Selection Flow

```
Route Change
    ↓
MainLayout useEffect()
    ↓
setActiveSection() based on pathname
    ↓
ContextualPanel renderPanel()
    ↓
[Route-Specific Check]
    ├── /projects/*/settings → ProjectSettingsPanel
    ├── /health* → HealthPanel
    ├── /graph* → GraphFiltersPanel
    └── ...etc
[Fallback to Section-Based]
    ├── command/sandboxes → TasksPanel
    ├── projects → ProjectsPanel
    └── ...etc
```

---

## Key Interfaces

### Layout Components

```typescript
// IconRail
interface IconRailProps {
  activeSection?: NavSection;
  onSectionChange?: (section: NavSection) => void;
  className?: string;
}

// ContextualPanel
interface ContextualPanelProps {
  activeSection: NavSection;
  pathname?: string;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
  className?: string;
}

// MainLayout
interface MainLayoutProps {
  children: React.ReactNode;
}
```

### Command Components

```typescript
// PromptInput
interface PromptInputProps {
  onSubmit?: (prompt: string) => void;
  isLoading?: boolean;
  placeholder?: string;
  submitLabel?: string;
  className?: string;
}

// RepoSelector
interface RepoSelectorProps {
  projects?: Project[];
  repositories?: Repository[];
  selectedProject?: Project | null;
  selectedRepo?: string | null;
  selectedBranch?: string;
  onProjectSelect?: (project: Project) => void;
  onRepoSelect?: (repo: string) => void;
  onBranchChange?: (branch: string) => void;
  className?: string;
}

// WorkflowModeSelector
interface WorkflowModeSelectorProps {
  value?: WorkflowMode;
  onValueChange?: (value: WorkflowMode) => void;
  className?: string;
}

// CommandPalette
interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}
```

### Panel Components

```typescript
// TasksPanel
interface TasksPanelProps {
  pathname?: string;
}

// All other panels currently have no required props
```

---

## File Inventory

### Command Components
| File | Lines | Purpose |
|------|-------|---------|
| `PromptInput.tsx` | 100 | Primary command text input |
| `CommandPalette.tsx` | 334 | Global command search |
| `RepoSelector.tsx` | 476 | Project/repo/branch selection |
| `WorkflowModeSelector.tsx` | 97 | Quick vs spec-driven toggle |
| `ModelSelector.tsx` | 66 | LLM model selection (disabled) |
| `RecentAgentsSidebar.tsx` | — | Recent agents display |
| `SpecDrivenSettingsPanel.tsx` | — | Spec configuration panel |

### Panel Components
| File | Lines | Purpose |
|------|-------|---------|
| `TasksPanel.tsx` | 409 | Sandbox task list |
| `ProjectsPanel.tsx` | 282 | Project navigation |
| `AgentsPanel.tsx` | 185 | Agent list |
| `SettingsPanel.tsx` | 187 | Settings navigation |
| `AnalyticsPanel.tsx` | — | Analytics filters |
| `OrganizationsPanel.tsx` | — | Organization list |
| `GraphFiltersPanel.tsx` | — | Graph view filters |
| `DiagnosticContextPanel.tsx` | — | Diagnostic context |
| `ActivityFiltersPanel.tsx` | — | Activity feed filters |
| `ProjectSettingsPanel.tsx` | — | Project configuration |
| `PhasesPanel.tsx` | — | Phase management |
| `HealthPanel.tsx` | — | System health |

### Layout Components
| File | Lines | Purpose |
|------|-------|---------|
| `MainLayout.tsx` | 103 | Three-column shell |
| `ContextualPanel.tsx` | 141 | Panel router/renderer |
| `IconRail.tsx` | 185 | Navigation rail |
| `MinimalHeader.tsx` | — | Top header bar |

---

## Design Patterns

### 1. Route-Aware Rendering
Panels use `usePathname()` to determine context and highlight active items. The `ContextualPanel` uses pathname to select the appropriate panel component.

### 2. Section Synchronization
`MainLayout` syncs `activeSection` state with the current route via `useEffect`, ensuring the IconRail and ContextualPanel stay in sync.

### 3. Collapsible Sidebar
The ContextualPanel supports collapse/expand with:
- Collapsed: 40px width with expand button
- Expanded: 256px width with content and collapse button
- State managed in `MainLayout`, passed via props

### 4. Status Grouping
List panels (Tasks, Agents) group items by status with visual headers:
- Running/Active (highlighted)
- Validating/Pending Validation
- Pending
- Completed
- Failed/Errored

### 5. Keyboard Accessibility
Global shortcuts for power users:
- Number keys (1-4) for main sections
- `B` for panel toggle
- Enter to submit in PromptInput

---

## Integration Points

### API Hooks Used
| Hook | Purpose |
|------|---------|
| `useProjects()` | Fetch project list |
| `useGitHubRepos()` | Fetch GitHub repositories |
| `useGitHubBranches()` | Fetch repo branches |
| `useCreateTicket()` | Create ticket (quick mode) |
| `useLaunchSpec()` | Launch spec-driven workflow |
| `useSandboxTasks()` | Fetch task list |
| `useAgents()` | Fetch agent list |
| `useEvents()` | WebSocket event subscription |

### External Services
- **GitHub API** — Repository and branch fetching
- **WebSocket** — Real-time sandbox events
- **Daytona** — Sandbox creation and management

---

## Future Considerations

1. **Analytics Panel** — Currently disabled, needs implementation
2. **Phases Panel** — Currently disabled, needs phase management UI
3. **Model Selector** — UI exists but is disabled pending backend support
4. **Command Palette Data** — Currently uses mock data, needs API integration
5. **Panel Persistence** — Remember collapsed state across sessions
