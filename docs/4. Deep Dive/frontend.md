# Frontend Deep Dive

## Overview

The OmoiOS frontend is a Next.js 15 application using the App Router architecture. It provides a spec-driven development interface where users describe features, review generated plans, and monitor autonomous agent execution in real-time. The UI follows a three-column shell pattern: a persistent IconRail for primary navigation, a ContextualPanel that adapts to the current route, and a main content area for feature-specific interfaces.

## Architecture

The frontend architecture centers on a provider stack that wraps all routes with authentication, state management, real-time event streaming, and analytics. The layout system uses a hierarchical composition where the root layout establishes global providers, route group layouts handle authentication boundaries, and page-level components implement domain-specific features.

```mermaid
graph TB
    subgraph "Root Layer"
        RL[layout.tsx]
        RP[RootProvider]
        TP[ThemeProvider]
        PHP[PostHogProvider]
    end
    
    subgraph "Data Layer"
        QP[QueryProvider]
        AP[AuthProvider]
        WP[WebSocketProvider]
        SP[StoreProvider]
    end
    
    subgraph "Shell Layer"
        ML[MainLayout.tsx]
        IR[IconRail]
        CP[ContextualPanel]
        MH[MinimalHeader]
    end
    
    subgraph "Route Groups"
        AUTH["(auth)/"]
        APP["(app)/"]
        DASH["(dashboard)/"]
    end
    
    subgraph "Domain Pages"
        CMD[command/page.tsx]
        SBX[sandbox/[id]/page.tsx]
        BRD[board/[projectId]/page.tsx]
        PRJ[projects/page.tsx]
    end
    
    RL --> RP --> TP --> PHP --> QP --> AP --> WP --> SP --> ML
    ML --> IR
    ML --> CP
    ML --> MH
    SP --> AUTH
    SP --> APP
    SP --> DASH
    APP --> CMD
    APP --> SBX
    APP --> BRD
    APP --> PRJ
```

The provider initialization order is deliberate: React Query must be available before AuthProvider attempts token validation, and WebSocketProvider needs the authenticated context to establish secure connections. StoreProvider wraps everything to ensure Zustand hydration happens after all async providers have initialized.

## Key Files

| File | Purpose | Lines |
|------|---------|-------|
| `/Users/kevinhill/Coding/Experiments/senior-sandbox/omoi_os/frontend/app/layout.tsx` | Root layout with provider stack and SEO metadata | 155 |
| `/Users/kevinhill/Coding/Experiments/senior-sandbox/omoi_os/frontend/app/(app)/layout.tsx` | Authenticated route wrapper with MainLayout | 45 |
| `/Users/kevinhill/Coding/Experiments/senior-sandbox/omoi_os/frontend/components/layout/MainLayout.tsx` | Three-column shell with keyboard shortcuts | 103 |
| `/Users/kevinhill/Coding/Experiments/senior-sandbox/omoi_os/frontend/components/layout/IconRail.tsx` | Left navigation rail with section icons | 89 |
| `/Users/kevinhill/Coding/Experiments/senior-sandbox/omoi_os/frontend/components/layout/ContextualPanel.tsx` | Route-aware sidebar with dynamic content | 156 |
| `/Users/kevinhill/Coding/Experiments/senior-sandbox/omoi_os/frontend/providers/WebSocketProvider.tsx` | Real-time event streaming with auto-reconnect | 194 |
| `/Users/kevinhill/Coding/Experiments/senior-sandbox/omoi_os/frontend/providers/AuthProvider.tsx` | JWT authentication with refresh token rotation | 178 |
| `/Users/kevinhill/Coding/Experiments/senior-sandbox/omoi_os/frontend/providers/QueryProvider.tsx` | React Query client with default stale times | 67 |
| `/Users/kevinhill/Coding/Experiments/senior-sandbox/omoi_os/frontend/lib/api/client.ts` | Centralized API client with token refresh | 454 |
| `/Users/kevinhill/Coding/Experiments/senior-sandbox/omoi_os/frontend/hooks/useSpecs.ts` | Spec management hooks with optimistic updates | 650 |
| `/Users/kevinhill/Coding/Experiments/senior-sandbox/omoi_os/frontend/hooks/useProjects.ts` | Project CRUD with pagination support | 234 |
| `/Users/kevinhill/Coding/Experiments/senior-sandbox/omoi_os/frontend/hooks/useSandbox.ts` | Sandbox monitoring with event streaming | 189 |
| `/Users/kevinhill/Coding/Experiments/senior-sandbox/omoi_os/frontend/components/sandbox/EventRenderer.tsx` | Multi-card event visualization system | 1800+ |
| `/Users/kevinhill/Coding/Experiments/senior-sandbox/omoi_os/frontend/app/(app)/command/page.tsx` | Command center for spec initiation | 312 |
| `/Users/kevinhill/Coding/Experiments/senior-sandbox/omoi_os/frontend/app/(app)/sandbox/[sandboxId]/page.tsx` | Live sandbox monitoring interface | 267 |

## Implementation Details

### Three-Column Shell Layout

The MainLayout component implements a persistent three-column interface that remains stable across route transitions. This pattern eliminates layout shift when users navigate between sections and provides immediate access to primary navigation regardless of scroll position.

`file:13-34`
```tsx
export function MainLayout({ children }: MainLayoutProps) {
  const pathname = usePathname();
  const [activeSection, setActiveSection] = useState<NavSection>("command");
  const [isPanelCollapsed, setIsPanelCollapsed] = useState(false);

  // Sync active section with current route
  useEffect(() => {
    if (pathname.startsWith("/command")) setActiveSection("command");
    else if (pathname.startsWith("/projects") || pathname.startsWith("/board"))
      setActiveSection("projects");
    else if (
      pathname.startsWith("/sandboxes") ||
      pathname.startsWith("/sandbox/")
    )
      setActiveSection("sandboxes");
    // ... additional route mappings
  }, [pathname]);
```

The layout includes keyboard shortcuts for power users: Cmd+1 through Cmd+4 navigate to primary sections, and Cmd+B toggles the contextual panel collapse state. These shortcuts are registered in a useEffect that cleans up on unmount to prevent event listener leakage.

The IconRail occupies a fixed 14-width column on the left, displaying seven primary navigation sections with active state indicators. The ContextualPanel renders route-specific sidebar content through a switch statement on the activeSection prop, allowing each domain to define its own navigation tree and quick actions.

### Real-Time Event Streaming

WebSocketProvider establishes a persistent connection to the backend event stream, handling authentication token injection, automatic reconnection with exponential backoff, and integration with React Query for cache invalidation.

`file:62-179`
```tsx
export function WebSocketProvider({ children }: { children: React.ReactNode }) {
  const [socket, setSocket] = useState<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout>();
  const socketRef = useRef<WebSocket | null>(null);
  const queryClient = useQueryClient();
  const replayPath = process.env.NEXT_PUBLIC_EVENT_REPLAY;

  useEffect(() => {
    if (replayPath) return; // Skip WebSocket when replaying

    let isMounted = true;
    let reconnectAttempts = 0;
    const MAX_RECONNECT_ATTEMPTS = 5;
    const RECONNECT_DELAY = 3000;

    const connect = () => {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:18000";
      const baseWsUrl = apiUrl.replace("http://", "ws://").replace("https://", "wss://") + "/api/v1/ws/events";
      const token = getAccessToken();
      const wsUrl = token ? `${baseWsUrl}?token=${encodeURIComponent(token)}` : baseWsUrl;

      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        if (!isMounted) {
          ws.close();
          return;
        }
        setIsConnected(true);
        reconnectAttempts = 0;
      };

      ws.onmessage = (event) => {
        if (!isMounted) return;
        try {
          const data = JSON.parse(event.data);
          if (data.type && data.payload) {
            if (data.type === "ticket_updated" || data.type === "ticket_created") {
              queryClient.invalidateQueries({ queryKey: ["tickets"] });
            }
            if (data.type === "agent_updated" || data.type === "agent_created") {
              queryClient.invalidateQueries({ queryKey: ["agents"] });
            }
          }
        } catch (error) {
          console.error("Failed to parse WebSocket message:", error);
        }
      };

      ws.onclose = (event) => {
        if (!isMounted) return;
        setIsConnected(false);

        const shouldReconnect =
          event.code !== 1008 &&
          event.code !== 1003 &&
          event.code !== 1000 &&
          event.code !== 4401 &&
          reconnectAttempts < MAX_RECONNECT_ATTEMPTS;

        if (shouldReconnect) {
          reconnectAttempts++;
          reconnectTimeoutRef.current = setTimeout(connect, RECONNECT_DELAY);
        }
      };

      socketRef.current = ws;
      setSocket(ws);
    };

    connect();

    return () => {
      isMounted = false;
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      socketRef.current?.close();
    };
  }, [queryClient, replayPath]);
```

The provider supports an event replay mode for development and debugging. When NEXT_PUBLIC_EVENT_REPLAY is set, it loads a recorded event stream from disk and plays it back through the same message handling pipeline, allowing developers to reproduce specific agent execution sequences without running live sandboxes.

### Spec-Driven Workflow Hooks

The useSpecs hook implements comprehensive spec lifecycle management with optimistic updates, cache invalidation, and polling strategies for long-running operations. It exposes 25+ query and mutation hooks covering the full spec state machine from creation through execution.

`file:95-114`
```tsx
export function useProjectSpecs(
  projectId: string | undefined,
  options?: {
    status?: string;
    refetchInterval?:
      | number
      | false
      | ((query: {
          state: { data: SpecListResponse | undefined };
        }) => number | false);
  },
) {
  const { status, refetchInterval } = options || {};
  return useQuery<SpecListResponse>({
    queryKey: specsKeys.project(projectId!),
    queryFn: () => listProjectSpecs(projectId!, { status }),
    enabled: !!projectId,
    refetchInterval: refetchInterval as any,
  });
}
```

The refetchInterval callback pattern enables intelligent polling that adapts to execution state. When any spec in the list has status "executing", the hook polls every 5 seconds to capture progress updates. When all specs are idle, polling stops to conserve bandwidth and battery.

`file:396-414`
```tsx
export function useExecuteSpecTasks(specId: string) {
  const queryClient = useQueryClient();

  return useMutation<
    ExecuteTasksResponse,
    Error,
    ExecuteTasksRequest | undefined
  >({
    mutationFn: (request) => executeSpecTasks(specId, request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: specsKeys.detail(specId) });
      queryClient.invalidateQueries({
        queryKey: specsKeys.executionStatus(specId),
      });
    },
  });
}
```

Mutations follow a consistent pattern: execute the API call, then invalidate affected query keys to trigger refetches. The specsKeys factory ensures cache keys remain consistent across the 650-line hook file and any components that need to manually invalidate specific queries.

### Sandbox Event Visualization

EventRenderer.tsx implements a card-based visualization system for sandbox execution events. It supports 12 distinct event types including agent messages, file operations, tool usage, and MCP server calls. Each event type has a specialized card component with appropriate syntax highlighting, diff visualization, and collapsible sections.

`file:144-193`
```tsx
const extensionToLanguage: Record<string, string> = {
  py: "python",
  js: "javascript",
  jsx: "jsx",
  ts: "typescript",
  tsx: "tsx",
  rs: "rust",
  go: "go",
  rb: "ruby",
  java: "java",
  c: "c",
  cpp: "cpp",
  cs: "csharp",
  php: "php",
  swift: "swift",
  kt: "kotlin",
  scala: "scala",
  sql: "sql",
  sh: "bash",
  bash: "bash",
  zsh: "bash",
  json: "json",
  yaml: "yaml",
  yml: "yaml",
  xml: "xml",
  html: "html",
  css: "css",
  scss: "scss",
  less: "less",
  md: "markdown",
  dockerfile: "docker",
  makefile: "makefile",
  toml: "toml",
  ini: "ini",
  env: "bash",
  gitignore: "git",
};
```

The FileWriteCard component implements a cursor-style diff display with syntax highlighting via react-syntax-highlighter. It parses unified diff format to extract line numbers and change types, then renders additions in green and deletions in red with full Prism.js language support.

`file:195-260`
```tsx
interface DiffLine {
  type: "addition" | "deletion" | "context" | "header";
  content: string;
  oldLineNum?: number;
  newLineNum?: number;
}

function parseDiff(diffText: string): {
  lines: DiffLine[];
  addedCount: number;
  removedCount: number;
} {
  const rawLines = diffText.split("\n");
  const lines: DiffLine[] = [];
  let oldLine = 0;
  let newLine = 0;
  let addedCount = 0;
  let removedCount = 0;

  for (const line of rawLines) {
    if (
      line.startsWith("---") ||
      line.startsWith("+++") ||
      line.startsWith("diff ")
    ) {
      continue;
    }

    if (line.startsWith("@@")) {
      const match = line.match(/@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
      if (match) {
        oldLine = parseInt(match[1], 10);
        newLine = parseInt(match[2], 10);
      }
      continue;
    }

    if (line.startsWith("+")) {
      lines.push({
        type: "addition",
        content: line.slice(1),
        newLineNum: newLine++,
      });
      addedCount++;
    } else if (line.startsWith("-")) {
      lines.push({
        type: "deletion",
        content: line.slice(1),
        oldLineNum: oldLine++,
      });
      removedCount++;
    } else if (line.startsWith(" ") || line === "") {
      lines.push({
        type: "context",
        content: line.startsWith(" ") ? line.slice(1) : line,
        oldLineNum: oldLine++,
        newLineNum: newLine++,
      });
    }
  }

  return { lines, addedCount, removedCount };
}
```

### API Client with Token Refresh

The centralized API client in lib/api/client.ts handles authentication token management, automatic refresh on 401 responses, and comprehensive error handling with Sentry integration.

`file:56-145`
```tsx
export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEYS.ACCESS);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEYS.REFRESH);
}

export function getAccessTokenExpiresAt(): number | null {
  if (typeof window === "undefined") return null;
  const expiry = localStorage.getItem(TOKEN_KEYS.ACCESS_EXPIRES_AT);
  return expiry ? parseInt(expiry, 10) : null;
}

export function isAccessTokenValid(): boolean {
  const token = getAccessToken();
  if (!token) return false;

  const expiresAt = getAccessTokenExpiresAt();
  if (!expiresAt) return true;

  return Date.now() < expiresAt - TOKEN_REFRESH_BUFFER;
}
```

The client implements a dual-token strategy with JWT access tokens and opaque refresh tokens. Access tokens are decoded client-side to extract expiration timestamps, enabling proactive refresh 2 minutes before expiry. The refresh flow uses a promise-locking mechanism to prevent multiple simultaneous refresh attempts when multiple API calls fail with 401 simultaneously.

`file:233-277`
```tsx
let isRefreshing = false;
let refreshPromise: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  const refreshToken = getRefreshToken();

  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(refreshToken ? { refresh_token: refreshToken } : {}),
    });

    if (!response.ok) {
      clearTokens();
      return false;
    }

    const data = await response.json();
    if (data.access_token && data.refresh_token) {
      setTokens(data.access_token, data.refresh_token);
    }
    return true;
  } catch {
    clearTokens();
    return false;
  }
}

async function ensureValidToken(): Promise<boolean> {
  if (isRefreshing) {
    return refreshPromise || Promise.resolve(false);
  }

  const accessToken = getAccessToken();
  if (!accessToken) return false;

  return true;
}
```

## Dependencies

### External Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| next | ^16.0.10 | React framework with App Router |
| react | ^19.0.0 | UI library |
| @tanstack/react-query | ^5.0.0 | Server state management |
| zustand | ^4.5.0 | Client state management |
| @radix-ui/* | ^1.1.x | Headless UI primitives (32 packages) |
| tailwindcss | ^4.1.18 | Utility-first CSS |
| @xyflow/react | ^12.10.0 | React Flow graph visualization |
| @dnd-kit/* | ^6.3.x | Drag and drop for Kanban |
| framer-motion | ^11.0.0 | Animation library |
| react-syntax-highlighter | ^15.6.6 | Code syntax highlighting |
| @sentry/nextjs | ^10.32.1 | Error tracking |
| posthog-js | ^1.313.0 | Product analytics |

### Internal Dependencies

| System | Interface | Purpose |
|--------|-----------|---------|
| Backend API | REST + WebSocket | Data fetching and real-time events |
| Auth Service | JWT + OAuth | Authentication and session management |
| Spec Service | REST endpoints | Spec CRUD and execution |
| Sandbox Service | WebSocket events | Live execution monitoring |
| File Service | REST endpoints | File upload and download |

> From legacy `/Users/kevinhill/Coding/Experiments/senior-sandbox/omoi_os/UI.md` — verified accurate 2026-04-22.

The frontend consumes the backend API through a typed client layer in lib/api/. Each domain (specs, projects, sandboxes, agents) has its own API module with corresponding TypeScript interfaces. The WebSocket connection provides a secondary real-time channel for events that would be inefficient to poll, including sandbox execution progress and agent status changes.
