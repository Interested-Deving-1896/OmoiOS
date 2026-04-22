# OmoiOS E2E Testing Guide

**Created**: 2025-04-22  
**Updated**: 2025-04-22  
**Status**: Active  
**Purpose**: Authoritative guide for end-to-end testing OmoiOS using Playwright, covering authentication flows, critical user journeys, and CI/CD integration

---

## Table of Contents

1. [Testing Philosophy](#testing-philosophy)
2. [Environment Setup](#environment-setup)
3. [Authentication Testing](#authentication-testing)
4. [Critical User Flows](#critical-user-flows)
5. [Page Object Model](#page-object-model)
6. [API Integration Testing](#api-integration-testing)
7. [Visual Regression Testing](#visual-regression-testing)
8. [Performance Testing](#performance-testing)
9. [CI/CD Integration](#cicd-integration)
10. [Debugging and Troubleshooting](#debugging-and-troubleshooting)
11. [Related Documentation](#related-documentation)

---

## Testing Philosophy

E2E tests in OmoiOS verify complete user workflows from the browser through the backend to the database. These tests are:

1. **Expensive but Critical** — Slower than unit tests, but catch integration issues
2. **User-Focused** — Test what users actually do, not internal implementation
3. **Deterministic** — Same test always produces same result (no flaky tests)
4. **Isolated** — Each test creates and cleans up its own data
5. **Parallelizable** — Tests can run concurrently without interference

### E2E Test Scope

```
┌─────────────────────────────────────────────────────────────┐
│                     E2E Test Boundary                        │
├─────────────────────────────────────────────────────────────┤
│  Browser (Playwright)                                        │
│    → Frontend (Next.js)                                     │
│      → API Calls (REST/WebSocket)                           │
│        → Backend (FastAPI)                                  │
│          → Database (PostgreSQL)                            │
│            → External Services (GitHub, Stripe, etc.)        │
└─────────────────────────────────────────────────────────────┘
```

### When to Write E2E Tests

| Scenario | Test Type | Reason |
|----------|-----------|--------|
| User authentication flow | E2E | Critical path, multiple systems involved |
| Project creation wizard | E2E | Multi-step form, state management |
| Payment processing | E2E | External integration (Stripe) |
| API endpoint logic | Unit/Integration | Faster, more focused |
| Component rendering | Unit | Faster, easier to debug |

---

## Environment Setup

### Installation

```bash
# Install Playwright
pnpm add -D @playwright/test

# Install browsers
pnpm exec playwright install

# Install additional dependencies for auth testing
pnpm add -D @faker-js/faker
```

### Configuration

```typescript
// playwright.config.ts
import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['html', { open: 'never' }],
    ['list'],
    ['junit', { outputFile: 'test-results/junit.xml' }],
  ],
  
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    
    // Authentication state
    storageState: 'e2e/.auth/user.json',
  },

  projects: [
    {
      name: 'setup',
      testMatch: /.*\.setup\.ts/,
    },
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
      dependencies: ['setup'],
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
      dependencies: ['setup'],
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
      dependencies: ['setup'],
    },
    {
      name: 'Mobile Chrome',
      use: { ...devices['Pixel 5'] },
      dependencies: ['setup'],
    },
    {
      name: 'Mobile Safari',
      use: { ...devices['iPhone 12'] },
      dependencies: ['setup'],
    },
  ],

  // Local dev server
  webServer: {
    command: 'pnpm dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },
})
```

### Test Directory Structure

```
e2e/
├── .auth/                    # Authentication state storage
│   └── user.json            # Logged-in user state
├── fixtures/                 # Test data and utilities
│   ├── users.ts            # User factory functions
│   ├── projects.ts         # Project factory functions
│   └── api.ts              # API helpers for test setup
├── pages/                   # Page Object Models
│   ├── LoginPage.ts
│   ├── DashboardPage.ts
│   ├── ProjectPage.ts
│   └── components/
│       ├── Navigation.ts
│       └── Modal.ts
├── specs/                   # Test specifications
│   ├── auth/
│   │   ├── login.spec.ts
│   │   ├── register.spec.ts
│   │   └── oauth.spec.ts
│   ├── projects/
│   │   ├── create.spec.ts
│   │   ├── list.spec.ts
│   │   └── delete.spec.ts
│   ├── tickets/
│   │   ├── create.spec.ts
│   │   └── workflow.spec.ts
│   └── billing/
│       └── subscription.spec.ts
├── setup/                   # Test setup files
│   ├── auth.setup.ts       # Authentication setup
│   └── global.setup.ts     # Global test setup
└── utils/                   # Test utilities
    ├── test-helpers.ts
    └── selectors.ts
```

---

## Authentication Testing

### Setup: Authenticated State

```typescript
// e2e/setup/auth.setup.ts
import { test as setup, expect } from '@playwright/test'
import { LoginPage } from '../pages/LoginPage'

const authFile = 'e2e/.auth/user.json'

setup('authenticate', async ({ page }) => {
  const loginPage = new LoginPage(page)
  
  // Navigate and login
  await loginPage.goto()
  await loginPage.login('test@example.com', 'password123')
  
  // Verify successful login
  await expect(page).toHaveURL('/dashboard')
  await expect(page.getByText('Welcome back')).toBeVisible()
  
  // Save authentication state
  await page.context().storageState({ path: authFile })
})
```

### Login Flow Test

```typescript
// e2e/specs/auth/login.spec.ts
import { test, expect } from '@playwright/test'
import { LoginPage } from '../../pages/LoginPage'
import { DashboardPage } from '../../pages/DashboardPage'

test.describe('Authentication', () => {
  test('user can login with valid credentials', async ({ page }) => {
    const loginPage = new LoginPage(page)
    const dashboardPage = new DashboardPage(page)
    
    await loginPage.goto()
    await loginPage.login('test@example.com', 'password123')
    
    // Verify redirect to dashboard
    await expect(page).toHaveURL('/dashboard')
    await expect(dashboardPage.welcomeMessage).toBeVisible()
  })

  test('user sees error with invalid credentials', async ({ page }) => {
    const loginPage = new LoginPage(page)
    
    await loginPage.goto()
    await loginPage.login('test@example.com', 'wrongpassword')
    
    // Verify error message
    await expect(loginPage.errorMessage).toBeVisible()
    await expect(loginPage.errorMessage).toContainText('Invalid credentials')
    
    // Verify still on login page
    await expect(page).toHaveURL('/login')
  })

  test('user can logout', async ({ page }) => {
    const dashboardPage = new DashboardPage(page)
    const loginPage = new LoginPage(page)
    
    // Start logged in
    await dashboardPage.goto()
    
    // Logout
    await dashboardPage.navigation.openUserMenu()
    await dashboardPage.navigation.clickLogout()
    
    // Verify redirect to login
    await expect(page).toHaveURL('/login')
    await expect(loginPage.loginButton).toBeVisible()
  })
})
```

### OAuth Testing

```typescript
// e2e/specs/auth/oauth.spec.ts
import { test, expect } from '@playwright/test'
import { LoginPage } from '../../pages/LoginPage'

test.describe('OAuth Authentication', () => {
  test('user can login with GitHub', async ({ page }) => {
    const loginPage = new LoginPage(page)
    
    await loginPage.goto()
    
    // Click GitHub OAuth button
    await loginPage.clickGitHubOAuth()
    
    // Handle OAuth popup
    const popupPromise = page.waitForEvent('popup')
    const popup = await popupPromise
    
    // In test environment, mock OAuth provider
    // In production tests, use test credentials
    await popup.fill('[name="login"]', 'test-github-user')
    await popup.fill('[name="password"]', 'test-password')
    await popup.click('[name="commit"]')
    
    // Wait for redirect back to app
    await expect(page).toHaveURL('/dashboard', { timeout: 30000 })
    await expect(page.getByText('Welcome')).toBeVisible()
  })

  test('OAuth error handling', async ({ page }) => {
    const loginPage = new LoginPage(page)
    
    await loginPage.goto()
    await loginPage.clickGitHubOAuth()
    
    // Simulate OAuth error by closing popup
    const popupPromise = page.waitForEvent('popup')
    const popup = await popupPromise
    await popup.close()
    
    // Verify error handling
    await expect(loginPage.oauthErrorMessage).toBeVisible()
  })
})
```

### Registration Flow

```typescript
// e2e/specs/auth/register.spec.ts
import { test, expect } from '@playwright/test'
import { RegisterPage } from '../../pages/RegisterPage'
import { faker } from '@faker-js/faker'

test.describe('User Registration', () => {
  test('new user can register', async ({ page }) => {
    const registerPage = new RegisterPage(page)
    
    const userData = {
      name: faker.person.fullName(),
      email: faker.internet.email(),
      password: 'SecurePass123!',
    }
    
    await registerPage.goto()
    await registerPage.register(userData)
    
    // Verify success message
    await expect(registerPage.successMessage).toBeVisible()
    await expect(registerPage.successMessage).toContainText(
      'Check your email'
    )
  })

  test('registration validates email format', async ({ page }) => {
    const registerPage = new RegisterPage(page)
    
    await registerPage.goto()
    await registerPage.fillEmail('invalid-email')
    await registerPage.submit()
    
    await expect(registerPage.emailError).toBeVisible()
    await expect(registerPage.emailError).toContainText('valid email')
  })

  test('registration prevents duplicate emails', async ({ page }) => {
    const registerPage = new RegisterPage(page)
    
    // Use existing user email
    await registerPage.goto()
    await registerPage.register({
      name: 'Test User',
      email: 'existing@example.com',
      password: 'Password123!',
    })
    
    await expect(registerPage.errorMessage).toBeVisible()
    await expect(registerPage.errorMessage).toContainText('already exists')
  })
})
```

---

## Critical User Flows

### Project Creation Flow

```typescript
// e2e/specs/projects/create.spec.ts
import { test, expect } from '@playwright/test'
import { DashboardPage } from '../../pages/DashboardPage'
import { ProjectCreatePage } from '../../pages/ProjectCreatePage'
import { ProjectDetailPage } from '../../pages/ProjectDetailPage'
import { createTestUser, cleanupTestData } from '../../fixtures/api'

test.describe('Project Creation', () => {
  test.beforeEach(async ({ page }) => {
    // Ensure clean state
    await cleanupTestData()
  })

  test('user can create a new project', async ({ page }) => {
    const dashboard = new DashboardPage(page)
    const createPage = new ProjectCreatePage(page)
    const detailPage = new ProjectDetailPage(page)
    
    // Navigate to project creation
    await dashboard.goto()
    await dashboard.clickCreateProject()
    
    // Fill project details
    await createPage.fillProjectDetails({
      name: 'E2E Test Project',
      description: 'Created by automated test',
      repository: 'https://github.com/test/repo',
    })
    
    // Submit
    await createPage.submit()
    
    // Verify project created
    await expect(page).toHaveURL(/\/projects\/[\w-]+/)
    await expect(detailPage.projectName).toHaveText('E2E Test Project')
    await expect(detailPage.successToast).toBeVisible()
  })

  test('project creation validates required fields', async ({ page }) => {
    const createPage = new ProjectCreatePage(page)
    
    await createPage.goto()
    await createPage.submit()
    
    // Verify validation errors
    await expect(createPage.nameError).toBeVisible()
    await expect(createPage.nameError).toContainText('required')
  })

  test('user can cancel project creation', async ({ page }) => {
    const createPage = new ProjectCreatePage(page)
    
    await createPage.goto()
    await createPage.fillProjectDetails({
      name: 'Cancelled Project',
    })
    await createPage.cancel()
    
    // Verify return to dashboard
    await expect(page).toHaveURL('/dashboard')
  })
})
```

### Ticket Workflow Flow

```typescript
// e2e/specs/tickets/workflow.spec.ts
import { test, expect } from '@playwright/test'
import { ProjectPage } from '../../pages/ProjectPage'
import { TicketCreatePage } from '../../pages/TicketCreatePage'
import { TicketDetailPage } from '../../pages/TicketDetailPage'
import { createTestProject, createTestTicket } from '../../fixtures/api'

test.describe('Ticket Workflow', () => {
  let projectId: string

  test.beforeEach(async () => {
    // Create test project and ticket
    projectId = await createTestProject('Workflow Test Project')
  })

  test('ticket progresses through phases', async ({ page }) => {
    const projectPage = new ProjectPage(page, projectId)
    const ticketDetail = new TicketDetailPage(page)
    
    // Navigate to project
    await projectPage.goto()
    
    // Create new ticket
    await projectPage.clickNewTicket()
    await ticketDetail.createTicket({
      title: 'Test Feature Request',
      description: 'As a user, I want...',
      type: 'feature',
    })
    
    // Verify ticket in backlog
    await expect(ticketDetail.statusBadge).toHaveText('Backlog')
    
    // Move to in progress
    await ticketDetail.moveToInProgress()
    await expect(ticketDetail.statusBadge).toHaveText('In Progress')
    
    // Move to done
    await ticketDetail.moveToDone()
    await expect(ticketDetail.statusBadge).toHaveText('Done')
  })

  test('ticket shows spec generation progress', async ({ page }) => {
    const ticketDetail = new TicketDetailPage(page)
    const ticketId = await createTestTicket(projectId, {
      title: 'Spec Test Ticket',
      autoGenerateSpec: true,
    })
    
    await ticketDetail.goto(ticketId)
    
    // Verify spec generation indicator
    await expect(ticketDetail.specProgressIndicator).toBeVisible()
    
    // Wait for completion (with timeout)
    await expect(ticketDetail.specCompleteBadge).toBeVisible({
      timeout: 60000,
    })
  })
})
```

### Billing and Subscription Flow

```typescript
// e2e/specs/billing/subscription.spec.ts
import { test, expect } from '@playwright/test'
import { BillingPage } from '../../pages/BillingPage'
import { createTestUserWithStripe } from '../../fixtures/api'

test.describe('Billing and Subscriptions', () => {
  test('user can view billing dashboard', async ({ page }) => {
    const billingPage = new BillingPage(page)
    
    await billingPage.goto()
    
    // Verify billing sections
    await expect(billingPage.currentPlanCard).toBeVisible()
    await expect(billingPage.usageChart).toBeVisible()
    await expect(billingPage.invoicesList).toBeVisible()
  })

  test('user can upgrade subscription', async ({ page }) => {
    const billingPage = new BillingPage(page)
    
    await billingPage.goto()
    await billingPage.clickUpgradePlan()
    
    // Select Pro plan
    await billingPage.selectPlan('pro')
    
    // Fill payment details (Stripe test card)
    await billingPage.fillPaymentDetails({
      cardNumber: '4242424242424242',
      expiry: '12/25',
      cvc: '123',
    })
    
    // Confirm upgrade
    await billingPage.confirmUpgrade()
    
    // Verify success
    await expect(billingPage.upgradeSuccessMessage).toBeVisible()
    await expect(billingPage.currentPlanBadge).toHaveText('Pro')
  })

  test('user can cancel subscription', async ({ page }) => {
    const billingPage = new BillingPage(page)
    
    await billingPage.goto()
    await billingPage.openPlanSettings()
    await billingPage.clickCancelSubscription()
    
    // Confirm cancellation
    await billingPage.confirmCancellation()
    
    // Verify cancellation scheduled
    await expect(billingPage.cancellationNotice).toBeVisible()
    await expect(billingPage.cancellationNotice).toContainText(
      'Subscription will end'
    )
  })
})
```

---

## Page Object Model

### Base Page Class

```typescript
// e2e/pages/BasePage.ts
import { Page, Locator, expect } from '@playwright/test'

export abstract class BasePage {
  constructor(protected page: Page) {}

  abstract goto(): Promise<void>
  abstract waitForReady(): Promise<void>

  async waitForUrl(url: string | RegExp, timeout = 10000) {
    await expect(this.page).toHaveURL(url, { timeout })
  }

  async waitForToast(message?: string) {
    const toast = this.page.getByRole('alert')
    await expect(toast).toBeVisible()
    if (message) {
      await expect(toast).toContainText(message)
    }
  }

  async dismissToast() {
    await this.page.getByRole('alert').getByRole('button').click()
  }

  async takeScreenshot(name: string) {
    await this.page.screenshot({
      path: `test-results/screenshots/${name}.png`,
      fullPage: true,
    })
  }
}
```

### Login Page Object

```typescript
// e2e/pages/LoginPage.ts
import { Page, Locator } from '@playwright/test'
import { BasePage } from './BasePage'

export class LoginPage extends BasePage {
  readonly emailInput: Locator
  readonly passwordInput: Locator
  readonly loginButton: Locator
  readonly errorMessage: Locator
  readonly githubOAuthButton: Locator
  readonly googleOAuthButton: Locator

  constructor(page: Page) {
    super(page)
    this.emailInput = page.getByLabel('Email')
    this.passwordInput = page.getByLabel('Password')
    this.loginButton = page.getByRole('button', { name: 'Sign in' })
    this.errorMessage = page.getByRole('alert')
    this.githubOAuthButton = page.getByRole('button', { name: /github/i })
    this.googleOAuthButton = page.getByRole('button', { name: /google/i })
  }

  async goto() {
    await this.page.goto('/login')
    await this.waitForReady()
  }

  async waitForReady() {
    await this.emailInput.waitFor({ state: 'visible' })
  }

  async login(email: string, password: string) {
    await this.emailInput.fill(email)
    await this.passwordInput.fill(password)
    await this.loginButton.click()
  }

  async clickGitHubOAuth() {
    await this.githubOAuthButton.click()
  }

  async clickGoogleOAuth() {
    await this.googleOAuthButton.click()
  }
}
```

### Dashboard Page Object

```typescript
// e2e/pages/DashboardPage.ts
import { Page, Locator } from '@playwright/test'
import { BasePage } from './BasePage'
import { Navigation } from './components/Navigation'

export class DashboardPage extends BasePage {
  readonly navigation: Navigation
  readonly welcomeMessage: Locator
  readonly createProjectButton: Locator
  readonly projectsList: Locator
  readonly recentActivity: Locator

  constructor(page: Page) {
    super(page)
    this.navigation = new Navigation(page)
    this.welcomeMessage = page.getByText(/welcome back/i)
    this.createProjectButton = page.getByRole('button', {
      name: /create project/i,
    })
    this.projectsList = page.getByTestId('projects-list')
    this.recentActivity = page.getByTestId('recent-activity')
  }

  async goto() {
    await this.page.goto('/dashboard')
    await this.waitForReady()
  }

  async waitForReady() {
    await this.welcomeMessage.waitFor({ state: 'visible' })
  }

  async clickCreateProject() {
    await this.createProjectButton.click()
  }

  async getProjectCount(): Promise<number> {
    const projects = await this.projectsList
      .getByTestId('project-card')
      .count()
    return projects
  }

  async openProject(name: string) {
    await this.projectsList.getByText(name).click()
  }
}
```

### Navigation Component

```typescript
// e2e/pages/components/Navigation.ts
import { Page, Locator } from '@playwright/test'

export class Navigation {
  readonly page: Page
  readonly userMenuButton: Locator
  readonly logoutButton: Locator
  readonly projectsLink: Locator
  readonly settingsLink: Locator
  readonly billingLink: Locator

  constructor(page: Page) {
    this.page = page
    this.userMenuButton = page.getByRole('button', { name: /user menu/i })
    this.logoutButton = page.getByRole('menuitem', { name: /logout/i })
    this.projectsLink = page.getByRole('link', { name: /projects/i })
    this.settingsLink = page.getByRole('link', { name: /settings/i })
    this.billingLink = page.getByRole('link', { name: /billing/i })
  }

  async openUserMenu() {
    await this.userMenuButton.click()
  }

  async clickLogout() {
    await this.openUserMenu()
    await this.logoutButton.click()
  }

  async navigateToProjects() {
    await this.projectsLink.click()
  }

  async navigateToSettings() {
    await this.settingsLink.click()
  }

  async navigateToBilling() {
    await this.billingLink.click()
  }
}
```

---

## API Integration Testing

### Test Data Helpers

```typescript
// e2e/fixtures/api.ts
import { request, APIRequestContext } from '@playwright/test'

let apiContext: APIRequestContext

export async function initializeApi(baseURL: string) {
  apiContext = await request.newContext({
    baseURL,
  })
}

export async function createTestUser(email: string, password: string) {
  const response = await apiContext.post('/api/v1/auth/register', {
    data: { email, password, name: 'Test User' },
  })
  
  if (!response.ok() && response.status() !== 409) {
    throw new Error(`Failed to create test user: ${await response.text()}`)
  }
  
  return { email, password }
}

export async function createTestProject(name: string, ownerId?: string) {
  const response = await apiContext.post('/api/v1/projects', {
    data: {
      name,
      description: 'Test project created by E2E test',
      ownerId,
    },
  })
  
  if (!response.ok()) {
    throw new Error(`Failed to create project: ${await response.text()}`)
  }
  
  const data = await response.json()
  return data.id
}

export async function createTestTicket(
  projectId: string,
  options: { title?: string; autoGenerateSpec?: boolean } = {}
) {
  const response = await apiContext.post('/api/v1/tickets', {
    data: {
      projectId,
      title: options.title || 'Test Ticket',
      description: 'Test ticket description',
      autoGenerateSpec: options.autoGenerateSpec || false,
    },
  })
  
  if (!response.ok()) {
    throw new Error(`Failed to create ticket: ${await response.text()}`)
  }
  
  const data = await response.json()
  return data.id
}

export async function cleanupTestData() {
  // Clean up test data created during tests
  await apiContext.post('/api/v1/test/cleanup', {
    data: { prefix: 'E2E Test' },
  })
}

export async function createTestUserWithStripe(email: string) {
  const user = await createTestUser(email, 'password123')
  
  // Attach Stripe test customer
  await apiContext.post('/api/v1/test/stripe/attach-customer', {
    data: { email },
  })
  
  return user
}
```

### API Authentication Helper

```typescript
// e2e/fixtures/auth.ts
import { APIRequestContext, request } from '@playwright/test'

export async function authenticateApiContext(
  apiContext: APIRequestContext,
  email: string,
  password: string
) {
  const response = await apiContext.post('/api/v1/auth/login', {
    data: { email, password },
  })
  
  if (!response.ok()) {
    throw new Error('API authentication failed')
  }
  
  const { accessToken } = await response.json()
  
  // Create new context with auth header
  return request.newContext({
    extraHTTPHeaders: {
      Authorization: `Bearer ${accessToken}`,
    },
  })
}
```

---

## Visual Regression Testing

### Screenshot Comparison

```typescript
// e2e/specs/visual/dashboard.spec.ts
import { test, expect } from '@playwright/test'
import { DashboardPage } from '../../pages/DashboardPage'

test.describe('Visual Regression: Dashboard', () => {
  test('dashboard matches baseline', async ({ page }) => {
    const dashboard = new DashboardPage(page)
    
    await dashboard.goto()
    await dashboard.waitForReady()
    
    // Take screenshot and compare
    await expect(page).toHaveScreenshot('dashboard.png', {
      fullPage: true,
      threshold: 0.2,
    })
  })

  test('project card hover state', async ({ page }) => {
    const dashboard = new DashboardPage(page)
    
    await dashboard.goto()
    
    const projectCard = page.getByTestId('project-card').first()
    await projectCard.hover()
    
    await expect(projectCard).toHaveScreenshot('project-card-hover.png')
  })

  test('mobile dashboard layout', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 })
    
    const dashboard = new DashboardPage(page)
    await dashboard.goto()
    
    await expect(page).toHaveScreenshot('dashboard-mobile.png', {
      fullPage: true,
    })
  })
})
```

### Updating Baselines

```bash
# Update all baselines
pnpm exec playwright test --update-snapshots

# Update specific test
pnpm exec playwright test e2e/specs/visual/dashboard.spec.ts --update-snapshots
```

---

## Performance Testing

### Core Web Vitals

```typescript
// e2e/specs/performance/core-web-vitals.spec.ts
import { test, expect } from '@playwright/test'

test.describe('Performance: Core Web Vitals', () => {
  test('LCP should be under 2.5s', async ({ page }) => {
    await page.goto('/dashboard')
    
    // Wait for largest contentful paint
    const lcp = await page.evaluate(() => {
      return new Promise<number>((resolve) => {
        const observer = new PerformanceObserver((list) => {
          const entries = list.getEntries()
          const lastEntry = entries[entries.length - 1]
          resolve(lastEntry.startTime)
        })
        observer.observe({ entryTypes: ['largest-contentful-paint'] })
      })
    })
    
    expect(lcp).toBeLessThan(2500)
  })

  test('FID should be under 100ms', async ({ page }) => {
    await page.goto('/dashboard')
    
    // Measure first input delay
    const fid = await page.evaluate(() => {
      return new Promise<number>((resolve) => {
        const observer = new PerformanceObserver((list) => {
          const entries = list.getEntries()
          const firstEntry = entries[0] as PerformanceEventTiming
          resolve(firstEntry.processingStart - firstEntry.startTime)
        })
        observer.observe({ entryTypes: ['first-input'] })
      })
    })
    
    expect(fid).toBeLessThan(100)
  })

  test('CLS should be under 0.1', async ({ page }) => {
    await page.goto('/dashboard')
    
    // Measure cumulative layout shift
    const cls = await page.evaluate(() => {
      return new Promise<number>((resolve) => {
        let clsValue = 0
        const observer = new PerformanceObserver((list) => {
          for (const entry of list.getEntries()) {
            if (!(entry as any).hadRecentInput) {
              clsValue += (entry as any).value
            }
          }
        })
        observer.observe({ entryTypes: ['layout-shift'] })
        
        // Report after 5 seconds
        setTimeout(() => resolve(clsValue), 5000)
      })
    })
    
    expect(cls).toBeLessThan(0.1)
  })
})
```

### Load Testing Integration

```typescript
// e2e/specs/performance/load.spec.ts
import { test, expect } from '@playwright/test'

test.describe('Performance: Load Testing', () => {
  test('dashboard loads within 3 seconds', async ({ page }) => {
    const startTime = Date.now()
    
    await page.goto('/dashboard')
    await page.waitForLoadState('networkidle')
    
    const loadTime = Date.now() - startTime
    expect(loadTime).toBeLessThan(3000)
  })

  test('API response times under 500ms', async ({ page }) => {
    const responseTimes: number[] = []
    
    // Intercept API calls
    page.on('response', async (response) => {
      if (response.url().includes('/api/v1/')) {
        const timing = await response.request().timing()
        responseTimes.push(timing.responseEnd)
      }
    })
    
    await page.goto('/dashboard')
    await page.waitForLoadState('networkidle')
    
    // Verify all API calls were fast
    for (const time of responseTimes) {
      expect(time).toBeLessThan(500)
    }
  })
})
```

---

## CI/CD Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/e2e.yml
name: E2E Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: omoi_os_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432
      
      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v4

      - name: Setup Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '22'
          cache: 'pnpm'

      - name: Install dependencies
        run: pnpm install

      - name: Install Playwright browsers
        run: pnpm exec playwright install --with-deps

      - name: Setup backend
        run: |
          cd backend
          uv sync --group test
          uv run alembic upgrade head

      - name: Start backend
        run: |
          cd backend
          uv run uvicorn omoi_os.main:app --port 18000 &
          sleep 5

      - name: Build frontend
        run: pnpm build

      - name: Run E2E tests
        run: pnpm exec playwright test
        env:
          BASE_URL: http://localhost:3000
          API_URL: http://localhost:18000
          DATABASE_URL: postgresql://test:test@localhost:5432/omoi_os_test
          REDIS_URL: redis://localhost:6379

      - name: Upload test results
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: playwright-report
          path: |
            playwright-report/
            test-results/
          retention-days: 30

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: ./coverage/lcov.info
          flags: e2e
```

### Local CI Simulation

```bash
# Run full CI simulation locally
just e2e-ci

# Or manually:
# 1. Start services
just docker-up

# 2. Setup database
just db-migrate

# 3. Run tests
pnpm exec playwright test
```

---

## Debugging and Troubleshooting

### Common Issues

#### Issue: Flaky Tests

```typescript
// ❌ Flaky - no waiting for element
await page.click('.button')
await expect(page.locator('.result')).toBeVisible()

// ✅ Stable - wait for element first
await page.waitForSelector('.button')
await page.click('.button')
await expect(page.locator('.result')).toBeVisible({ timeout: 10000 })
```

#### Issue: Race Conditions

```typescript
// ❌ Race condition - two operations without sequencing
await Promise.all([
  page.click('.save'),
  page.waitForResponse('**/api/**'),
])

// ✅ Proper sequencing
await page.click('.save')
await page.waitForResponse('**/api/**')
await page.waitForSelector('.success-message')
```

#### Issue: Test Isolation

```typescript
// ✅ Ensure clean state before each test
test.beforeEach(async ({ page }) => {
  // Clear cookies and storage
  await page.context().clearCookies()
  await page.evaluate(() => localStorage.clear())
  
  // Reset database state
  await fetch('/api/v1/test/reset', { method: 'POST' })
})
```

### Debug Tools

```typescript
// Enable debug logging
test('debug example', async ({ page }) => {
  // Log all console messages
  page.on('console', msg => console.log('PAGE LOG:', msg.text()))
  
  // Log all network requests
  page.on('request', request => 
    console.log('REQUEST:', request.method(), request.url())
  )
  
  // Log all failures
  page.on('pageerror', error => 
    console.log('PAGE ERROR:', error.message)
  )
  
  await page.goto('/')
})
```

### Trace Viewer

```bash
# Run tests with tracing
pnpm exec playwright test --trace on

# Open trace viewer
pnpm exec playwright show-trace test-results/trace.zip
```

### Screenshot on Failure

```typescript
// playwright.config.ts
export default defineConfig({
  use: {
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'on-first-retry',
  },
})
```

---

## Related Documentation

- [OmoiOS Frontend Testing Guide](./frontend-testing-guide.md) — Unit and integration testing
- [OmoiOS Backend Testing](../CLAUDE.md) — Backend test patterns
- [Playwright Documentation](https://playwright.dev/)
- [Playwright Best Practices](https://playwright.dev/docs/best-practices)
- [Testing Library](https://testing-library.com/)

---

**Last Updated**: 2025-04-22  
**Document Owner**: QA Team  
**Review Cycle**: Quarterly
