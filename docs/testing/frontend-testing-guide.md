# OmoiOS Frontend Testing Guide

**Created**: 2025-04-22  
**Updated**: 2025-04-22  
**Status**: Active  
**Purpose**: Authoritative guide for testing OmoiOS frontend components, hooks, and pages using Vitest, React Testing Library, and Next.js 15 patterns

---

## Table of Contents

1. [Testing Philosophy](#testing-philosophy)
2. [Test Environment Setup](#test-environment-setup)
3. [Component Testing](#component-testing)
4. [Hook Testing](#hook-testing)
5. [Next.js 15 Async Patterns](#nextjs-15-async-patterns)
6. [Mocking Strategies](#mocking-strategies)
7. [Test Utilities](#test-utilities)
8. [Coverage Requirements](#coverage-requirements)
9. [Debugging Tests](#debugging-tests)
10. [Related Documentation](#related-documentation)

---

## Testing Philosophy

OmoiOS frontend testing follows these core principles:

1. **Test Behavior, Not Implementation** — Tests should verify what users see and interact with, not internal implementation details
2. **Isolation** — Each test should be independent and not rely on state from other tests
3. **Realistic Data** — Use factory functions to generate realistic test data that matches API response shapes
4. **Accessibility First** — Prefer querying by role, label, or text content over test IDs
5. **Async Awareness** — Properly handle React's async rendering and state updates

### Test Pyramid for Frontend

```
    /\
   /  \
  / E2E \     <- Playwright (critical flows)
 /________\
/          \
/ Integration \  <- Component + Hook tests (Vitest)
/______________\
/               \
/    Unit Tests   \ <- Utilities, helpers (Vitest)
/__________________\
```

---

## Test Environment Setup

### Dependencies

OmoiOS uses Vitest as the test runner with React Testing Library for component testing:

```json
{
  "scripts": {
    "test": "vitest",
    "test:run": "vitest run",
    "test:coverage": "vitest run --coverage"
  },
  "devDependencies": {
    "@testing-library/react": "^15.0.0",
    "@testing-library/jest-dom": "^6.4.0",
    "@testing-library/user-event": "^14.5.0",
    "vitest": "^1.5.0",
    "@vitest/coverage-v8": "^1.5.0",
    "jsdom": "^24.0.0"
  }
}
```

### Vitest Configuration

```typescript
// vitest.config.ts
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./__tests__/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      exclude: [
        'node_modules/',
        '__tests__/',
        '**/*.d.ts',
        '**/*.config.*',
        '**/mock*/**',
      ],
      thresholds: {
        lines: 80,
        functions: 80,
        branches: 75,
        statements: 80,
      },
    },
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './'),
      '@components': path.resolve(__dirname, './components'),
      '@hooks': path.resolve(__dirname, './hooks'),
      '@lib': path.resolve(__dirname, './lib'),
    },
  },
})
```

### Test Setup File

```typescript
// __tests__/setup.ts
import '@testing-library/jest-dom'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// Clean up after each test
afterEach(() => {
  cleanup()
})

// Mock Next.js navigation
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    refresh: vi.fn(),
    back: vi.fn(),
  }),
  useSearchParams: () => ({
    get: vi.fn(),
    has: vi.fn(),
  }),
  usePathname: () => '/',
}))

// Mock next/headers for async header/cookie access
vi.mock('next/headers', () => ({
  headers: vi.fn(() => Promise.resolve(new Headers())),
  cookies: vi.fn(() => Promise.resolve({ get: vi.fn(), set: vi.fn() })),
}))
```

---

## Component Testing

### Basic Component Test Pattern

```typescript
// __tests__/components/ui/Button.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { Button } from '@/components/ui/button'

describe('Button', () => {
  it('renders with correct text', () => {
    render(<Button>Click me</Button>)
    expect(screen.getByRole('button', { name: /click me/i })).toBeInTheDocument()
  })

  it('handles click events', () => {
    const handleClick = vi.fn()
    render(<Button onClick={handleClick}>Click me</Button>)
    
    fireEvent.click(screen.getByRole('button'))
    expect(handleClick).toHaveBeenCalledTimes(1)
  })

  it('is disabled when loading', () => {
    render(<Button isLoading>Loading</Button>)
    expect(screen.getByRole('button')).toBeDisabled()
  })

  it('applies variant classes correctly', () => {
    const { rerender } = render(<Button variant="default">Default</Button>)
    expect(screen.getByRole('button')).toHaveClass('bg-primary')

    rerender(<Button variant="destructive">Delete</Button>)
    expect(screen.getByRole('button')).toHaveClass('bg-destructive')
  })
})
```

### Testing Complex Components with Providers

```typescript
// __tests__/components/providers/QueryProvider.test.tsx
import { describe, it, expect } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ProjectList } from '@/components/projects/ProjectList'

// Create a test wrapper with all required providers
function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        staleTime: 0,
      },
    },
  })
}

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = createTestQueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      {ui}
    </QueryClientProvider>
  )
}

describe('ProjectList', () => {
  it('displays loading state initially', () => {
    renderWithProviders(<ProjectList />)
    expect(screen.getByText(/loading/i)).toBeInTheDocument()
  })

  it('displays projects after loading', async () => {
    renderWithProviders(<ProjectList />)
    
    await waitFor(() => {
      expect(screen.queryByText(/loading/i)).not.toBeInTheDocument()
    })
    
    expect(screen.getByRole('list')).toBeInTheDocument()
  })
})
```

### Testing Form Components

```typescript
// __tests__/components/forms/LoginForm.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { LoginForm } from '@/components/forms/LoginForm'

describe('LoginForm', () => {
  it('validates required fields', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    
    render(<LoginForm onSubmit={onSubmit} />)
    
    // Try submitting empty form
    await user.click(screen.getByRole('button', { name: /sign in/i }))
    
    expect(await screen.findByText(/email is required/i)).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('submits with valid data', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    
    render(<LoginForm onSubmit={onSubmit} />)
    
    // Fill in the form
    await user.type(
      screen.getByLabelText(/email/i),
      'test@example.com'
    )
    await user.type(
      screen.getByLabelText(/password/i),
      'password123'
    )
    
    // Submit
    await user.click(screen.getByRole('button', { name: /sign in/i }))
    
    await waitFor(() => {
      expect(onSubmit).toHaveBeenCalledWith({
        email: 'test@example.com',
        password: 'password123',
      })
    })
  })

  it('displays server errors', async () => {
    render(
      <LoginForm 
        onSubmit={vi.fn()} 
        error="Invalid credentials"
      />
    )
    
    expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument()
  })
})
```

---

## Hook Testing

### Testing Custom Hooks

```typescript
// __tests__/hooks/useProjects.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useProjects } from '@/hooks/useProjects'

// Mock the API client
vi.mock('@/lib/api/client', () => ({
  fetchProjects: vi.fn(),
}))

import { fetchProjects } from '@/lib/api/client'

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })
  
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    )
  }
}

describe('useProjects', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('returns loading state initially', () => {
    const { result } = renderHook(() => useProjects(), {
      wrapper: createWrapper(),
    })
    
    expect(result.current.isLoading).toBe(true)
    expect(result.current.data).toBeUndefined()
  })

  it('returns projects after successful fetch', async () => {
    const mockProjects = [
      { id: '1', name: 'Project A', status: 'active' },
      { id: '2', name: 'Project B', status: 'archived' },
    ]
    
    vi.mocked(fetchProjects).mockResolvedValueOnce(mockProjects)
    
    const { result } = renderHook(() => useProjects(), {
      wrapper: createWrapper(),
    })
    
    await waitFor(() => {
      expect(result.current.isLoading).toBe(false)
    })
    
    expect(result.current.data).toEqual(mockProjects)
    expect(result.current.error).toBeNull()
  })

  it('handles errors gracefully', async () => {
    vi.mocked(fetchProjects).mockRejectedValueOnce(
      new Error('Failed to fetch')
    )
    
    const { result } = renderHook(() => useProjects(), {
      wrapper: createWrapper(),
    })
    
    await waitFor(() => {
      expect(result.current.isError).toBe(true)
    })
    
    expect(result.current.error).toBeDefined()
  })
})
```

### Testing Hooks with Zustand

```typescript
// __tests__/hooks/useAuthStore.test.ts
import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useAuthStore } from '@/stores/authStore'

describe('useAuthStore', () => {
  beforeEach(() => {
    // Reset store state before each test
    act(() => {
      useAuthStore.setState({
        user: null,
        isAuthenticated: false,
        isLoading: false,
      })
    })
  })

  it('starts with unauthenticated state', () => {
    const { result } = renderHook(() => useAuthStore())
    
    expect(result.current.isAuthenticated).toBe(false)
    expect(result.current.user).toBeNull()
  })

  it('sets user on login', () => {
    const { result } = renderHook(() => useAuthStore())
    const mockUser = { id: '1', email: 'test@example.com', name: 'Test' }
    
    act(() => {
      result.current.login(mockUser)
    })
    
    expect(result.current.isAuthenticated).toBe(true)
    expect(result.current.user).toEqual(mockUser)
  })

  it('clears user on logout', () => {
    const { result } = renderHook(() => useAuthStore())
    
    // First login
    act(() => {
      result.current.login({ id: '1', email: 'test@example.com', name: 'Test' })
    })
    
    // Then logout
    act(() => {
      result.current.logout()
    })
    
    expect(result.current.isAuthenticated).toBe(false)
    expect(result.current.user).toBeNull()
  })
})
```

---

## Next.js 15 Async Patterns

### Testing Async Server Components

Next.js 15 introduces async server components. Here's how to test them:

```typescript
// __tests__/app/page.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import HomePage from '@/app/(app)/page'

// Mock the async headers/cookies functions
vi.mock('next/headers', () => ({
  headers: vi.fn(() => Promise.resolve(new Headers({
    'x-user-id': 'test-user-123',
  }))),
  cookies: vi.fn(() => Promise.resolve({
    get: vi.fn((name: string) => ({ value: `cookie-${name}` })),
  })),
}))

// Mock data fetching
vi.mock('@/lib/api/server', () => ({
  fetchDashboardData: vi.fn(() => Promise.resolve({
    projects: [],
    recentActivity: [],
    stats: { total: 0, completed: 0 },
  })),
}))

describe('HomePage (Server Component)', () => {
  it('renders dashboard with user data', async () => {
    // Server components are async, so we need to await the render
    const jsx = await HomePage()
    render(jsx)
    
    expect(screen.getByRole('heading', { name: /dashboard/i }))
      .toBeInTheDocument()
  })

  it('handles unauthenticated state', async () => {
    // Override the mock for this test
    const { headers } = await import('next/headers')
    vi.mocked(headers).mockResolvedValueOnce(new Headers())
    
    const jsx = await HomePage()
    render(jsx)
    
    expect(screen.getByText(/please sign in/i)).toBeInTheDocument()
  })
})
```

### Testing Client Components in Next.js 15

```typescript
// __tests__/components/client/ProjectCard.test.tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ProjectCard } from '@/components/projects/ProjectCard'

// Mark as client component test
describe('ProjectCard (Client Component)', () => {
  const mockProject = {
    id: '1',
    name: 'Test Project',
    description: 'A test project',
    status: 'active',
    updatedAt: new Date().toISOString(),
  }

  it('renders project information', () => {
    render(<ProjectCard project={mockProject} />)
    
    expect(screen.getByText(mockProject.name)).toBeInTheDocument()
    expect(screen.getByText(mockProject.description)).toBeInTheDocument()
  })

  it('navigates to project detail on click', async () => {
    const user = userEvent.setup()
    const push = vi.fn()
    
    // Mock Next.js router
    vi.mock('next/navigation', () => ({
      useRouter: () => ({ push }),
    }))
    
    render(<ProjectCard project={mockProject} />)
    
    await user.click(screen.getByRole('link'))
    
    expect(push).toHaveBeenCalledWith(`/projects/${mockProject.id}`)
  })
})
```

---

## Mocking Strategies

### Mocking API Calls

```typescript
// __tests__/mocks/handlers.ts
import { http, HttpResponse } from 'msw'

export const handlers = [
  http.get('/api/v1/projects', () => {
    return HttpResponse.json({
      projects: [
        { id: '1', name: 'Project A' },
        { id: '2', name: 'Project B' },
      ],
    })
  }),
  
  http.post('/api/v1/auth/login', async ({ request }) => {
    const body = await request.json()
    
    if (body.email === 'test@example.com') {
      return HttpResponse.json({
        accessToken: 'mock-token',
        user: { id: '1', email: body.email },
      })
    }
    
    return new HttpResponse(null, { status: 401 })
  }),
]
```

### Mocking WebSocket

```typescript
// __tests__/mocks/websocket.ts
export class MockWebSocket {
  static instances: MockWebSocket[] = []
  
  onopen: (() => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  onclose: (() => void) | null = null
  onerror: ((error: Error) => void) | null = null
  
  constructor(public url: string) {
    MockWebSocket.instances.push(this)
  }
  
  send(data: string) {
    // Mock implementation
  }
  
  close() {
    this.onclose?.()
  }
  
  // Test helper to simulate receiving messages
  simulateMessage(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) })
  }
  
  static clear() {
    MockWebSocket.instances = []
  }
}

// In setup.ts
global.WebSocket = MockWebSocket as unknown as typeof WebSocket
```

### Mocking Next.js App Router

```typescript
// __tests__/mocks/next-navigation.ts
import { vi } from 'vitest'

export function createMockRouter(overrides = {}) {
  return {
    push: vi.fn(),
    replace: vi.fn(),
    refresh: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    prefetch: vi.fn(),
    ...overrides,
  }
}

export function createMockSearchParams(params: Record<string, string>) {
  return {
    get: (key: string) => params[key] || null,
    has: (key: string) => key in params,
    getAll: (key: string) => params[key] ? [params[key]] : [],
    entries: () => Object.entries(params),
    keys: () => Object.keys(params),
    values: () => Object.values(params),
    toString: () => new URLSearchParams(params).toString(),
    forEach: (callback: (value: string, key: string) => void) => {
      Object.entries(params).forEach(([key, value]) => callback(value, key))
    },
    [Symbol.iterator]: function* () {
      yield* Object.entries(params)
    },
  }
}
```

---

## Test Utilities

### Factory Functions for Test Data

```typescript
// __tests__/factories/project.ts
import { faker } from '@faker-js/faker'

export function createProject(overrides = {}) {
  return {
    id: faker.string.uuid(),
    name: faker.company.name(),
    description: faker.lorem.paragraph(),
    status: faker.helpers.arrayElement(['active', 'archived', 'draft']),
    createdAt: faker.date.past().toISOString(),
    updatedAt: faker.date.recent().toISOString(),
    ownerId: faker.string.uuid(),
    ...overrides,
  }
}

export function createUser(overrides = {}) {
  return {
    id: faker.string.uuid(),
    email: faker.internet.email(),
    name: faker.person.fullName(),
    avatar: faker.image.avatar(),
    role: faker.helpers.arrayElement(['admin', 'member', 'viewer']),
    ...overrides,
  }
}

export function createTicket(overrides = {}) {
  return {
    id: faker.string.uuid(),
    title: faker.lorem.sentence(),
    description: faker.lorem.paragraphs(2),
    status: faker.helpers.arrayElement(['open', 'in_progress', 'completed']),
    priority: faker.helpers.arrayElement(['low', 'medium', 'high']),
    projectId: faker.string.uuid(),
    assigneeId: faker.string.uuid(),
    ...overrides,
  }
}
```

### Custom Render with All Providers

```typescript
// __tests__/utils/render.tsx
import { render as rtlRender } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from 'next-themes'
import { StoreProvider } from '@/providers/StoreProvider'

interface RenderOptions {
  queryClient?: QueryClient
  theme?: string
  initialStoreState?: Record<string, unknown>
}

export function render(
  ui: React.ReactElement,
  options: RenderOptions = {}
) {
  const {
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
      },
    }),
    theme = 'light',
    initialStoreState,
  } = options

  function AllProviders({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <ThemeProvider attribute="class" defaultTheme={theme}>
          <StoreProvider initialState={initialStoreState}>
            {children}
          </StoreProvider>
        </ThemeProvider>
      </QueryClientProvider>
    )
  }

  return {
    ...rtlRender(ui, { wrapper: AllProviders }),
    queryClient,
  }
}
```

---

## Coverage Requirements

OmoiOS frontend requires minimum coverage thresholds:

| Metric | Minimum |
|--------|---------|
| Lines | 80% |
| Functions | 80% |
| Branches | 75% |
| Statements | 80% |

### Running Coverage Reports

```bash
# Generate coverage report
pnpm test:coverage

# View HTML report
open coverage/index.html

# Coverage for specific files
pnpm vitest run --coverage --reporter=verbose src/components/ui
```

### Coverage Best Practices

1. **Focus on Critical Paths** — Prioritize testing user-facing features over internal utilities
2. **Test Edge Cases** — Empty states, error states, loading states
3. **Avoid Testing Implementation** — Don't test private functions or internal state
4. **Use Snapshot Testing Sparingly** — Only for stable UI components like icons

---

## Debugging Tests

### Common Issues and Solutions

#### Issue: "Unable to find element" with async components

```typescript
// ❌ Wrong - doesn't wait for async render
render(<AsyncComponent />)
expect(screen.getByText('Loaded')).toBeInTheDocument()

// ✅ Correct - wait for element to appear
render(<AsyncComponent />)
expect(await screen.findByText('Loaded')).toBeInTheDocument()
```

#### Issue: React Query cache pollution between tests

```typescript
// ✅ Solution - create new QueryClient for each test
import { cleanup } from '@testing-library/react'

afterEach(() => {
  cleanup()
  // Clear React Query cache
  queryClient.clear()
})
```

#### Issue: Mock not being reset between tests

```typescript
// ✅ Solution - clear mocks in beforeEach
import { vi } from 'vitest'

beforeEach(() => {
  vi.clearAllMocks()
})

// Or use mockReset for stricter reset
beforeEach(() => {
  vi.resetAllMocks()
})
```

### Debug Helpers

```typescript
// Log the rendered DOM for debugging
screen.debug()

// Log a specific element
screen.debug(screen.getByRole('button'))

// Pretty print the DOM
import { prettyDOM } from '@testing-library/react'
console.log(prettyDOM(container))
```

---

## Related Documentation

- [OmoiOS E2E Testing Guide](./e2e-testing-guide.md) — Playwright testing patterns
- [OmoiOS Backend Testing](../CLAUDE.md) — Backend test patterns
- [Vitest Documentation](https://vitest.dev/)
- [React Testing Library](https://testing-library.com/docs/react-testing-library/intro/)
- [Next.js Testing](https://nextjs.org/docs/app/building-your-application/testing)

---

**Last Updated**: 2025-04-22  
**Document Owner**: Frontend Team  
**Review Cycle**: Quarterly
