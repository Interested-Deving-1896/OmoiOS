# 16 API Keys Management

**Part of**: [User Journey Documentation](./README.md)

**Created**: 2026-04-22
**Status**: Active
**Purpose**: Document the complete user journey for managing API keys and credentials in OmoiOS

---

## Overview

API key management in OmoiOS enables users to bring their own LLM provider credentials (BYO keys), allowing unlimited workflow execution while paying providers directly. The system securely stores encrypted credentials and injects them into sandboxes at runtime.

### Key Concepts

| Concept | Description |
|---------|-------------|
| **BYO Keys** | Bring Your Own API keys from supported providers |
| **Provider** | LLM service (Anthropic, OpenAI, Z.AI, Fireworks.ai) |
| **Sandbox Injection** | Credentials automatically injected into agent sandboxes |
| **Secure Storage** | Encrypted at rest with field-level encryption |
| **Default Credential** | One default per provider per user |

---

## 16.1 Accessing API Key Management

```
User navigates to settings:
   ↓
1. From sidebar → Settings → "API Keys" or "Credentials" tab
   ↓
2. Arrives at /settings/credentials or /settings/api-keys
   ↓
3. Credentials dashboard loads showing:
   - Connected providers
   - Active credentials count
   - Last used timestamps
   - Provider status indicators
```

---

## 16.2 Viewing Existing Keys

```
Credentials Dashboard:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  API Credentials & Keys                                      │
│  Manage your LLM provider credentials for BYO key usage     │
│                                                              │
│  Connected Providers (3)                                     │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ 🔑 Anthropic                                            ││
│  │    Status: ✅ Active  |  Last used: 2 hours ago          ││
│  │    Model: claude-sonnet-4-5-20250929                     ││
│  │    [Edit] [Set Default] [Delete]                        ││
│  ├─────────────────────────────────────────────────────────┤│
│  │ 🔑 OpenAI                                               ││
│  │    Status: ✅ Active  |  Last used: 1 day ago             ││
│  │    Model: gpt-4o                                        ││
│  │    [Edit] [Set Default] [Delete]                        ││
│  ├─────────────────────────────────────────────────────────┤│
│  │ 🔑 Z.AI                                                 ││
│  │    Status: ⚠️ Expired  |  Last used: 2 weeks ago         ││
│  │    Model: claude-3-5-sonnet                             ││
│  │    [Edit] [Set Default] [Delete]                        ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  [+ Add New Provider]                                        │
└─────────────────────────────────────────────────────────────┘
```

### Provider Status Indicators

| Status | Icon | Meaning |
|--------|------|---------|
| Active | ✅ | Credential validated and ready |
| Expired | ⚠️ | API key rejected by provider |
| Inactive | ⏸️ | Manually disabled |
| Default | ⭐ | Used when no specific credential requested |

---

## 16.3 Adding New API Keys

```
User clicks [+ Add New Provider]:
   ↓
Add Credential Dialog opens:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  Add New API Credential                                      │
│                                                              │
│  Provider:                                                   │
│  [Select provider...                    ▼]                  │
│  Options: Anthropic | OpenAI | Z.AI | Fireworks.ai | GitHub │
│                                                              │
│  Credential Name (optional):                                 │
│  [My Production Key________________]                        │
│                                                              │
│  API Key:                                                    │
│  [sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx]  │
│  🔒 Encrypted and stored securely                            │
│                                                              │
│  Base URL (optional - for proxies):                         │
│  [https://api.anthropic.com________________]                │
│                                                              │
│  Default Model:                                              │
│  [claude-sonnet-4-5-20250929              ▼]                  │
│                                                              │
│  [✓] Set as default for this provider                       │
│                                                              │
│  Advanced Options:                                           │
│  ┌────────────────────────────────────────────────────────┐│
│  │ Config Data (JSON):                                    ││
│  │ {"temperature": 0.7, "max_tokens": 4096}              ││
│  └────────────────────────────────────────────────────────┘│
│                                                              │
│  [Cancel]                              [Validate & Save]    │
└─────────────────────────────────────────────────────────────┘
   ↓
On [Validate & Save]:
   ↓
┌─ Validation Success
│   ↓
│   POST /api/v1/credentials
│   ↓
│   System validates key with provider (test API call)
│   ↓
│   ✓ Key valid → Saved to user_credentials table
│   ↓
│   Toast: "Anthropic credential added successfully"
│   ↓
│   Dashboard updates with new credential
│
└─ Validation Failed
    ↓
    ✗ Key rejected → Shows error message
    ↓
    "Invalid API key. Please check and try again."
    ↓
    User can retry or cancel
```

### Supported Providers

| Provider | Models | Use Case |
|----------|--------|----------|
| **Anthropic** | Claude Sonnet, Opus, Haiku | Primary OmoiOS agent |
| **OpenAI** | GPT-4, GPT-4o, GPT-3.5 | Alternative LLM option |
| **Z.AI** | Claude-compatible | Cost-effective proxy |
| **Fireworks.ai** | Various OSS models | Open source models |
| **GitHub** | N/A | Repository access |

---

## 16.4 Editing and Rotating Keys

```
User clicks [Edit] on existing credential:
   ↓
Edit Credential Dialog:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  Edit Anthropic Credential                                   │
│                                                              │
│  Name: [Production Anthropic Key________]                   │
│                                                              │
│  Current API Key:                                            │
│  [sk-ant-api03-...••••••••••••••••••••••••••••••••••••]   │
│                                                              │
│  New API Key (leave blank to keep current):                 │
│  [________________________________________]                 │
│                                                              │
│  Model: [claude-sonnet-4-5-20250929       ▼]                │
│                                                              │
│  [✓] Active                                                  │
│  [✓] Default for Anthropic                                  │
│                                                              │
│  [Cancel]                              [Save Changes]        │
└─────────────────────────────────────────────────────────────┘
   ↓
Key Rotation Flow:
   ↓
1. User enters new API key
   ↓
2. System validates new key with provider
   ↓
3. On success:
   - Old key archived (for audit trail)
   - New key encrypted and stored
   - Active sandboxes continue with old key
   - New sandboxes use new key
   ↓
4. Toast: "API key rotated successfully"
```

---

## 16.5 Setting Default Credentials

```
User clicks [Set Default] on a credential:
   ↓
Confirmation Dialog:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  Set as Default?                                             │
│                                                              │
│  This will become the default Anthropic credential.         │
│  All new sandboxes will use this key unless specified.        │
│                                                              │
│  Current default: "Development Key"                         │
│  New default: "Production Key"                              │
│                                                              │
│  [Cancel]                              [Confirm]             │
└─────────────────────────────────────────────────────────────┘
   ↓
On confirm:
   ↓
PATCH /api/v1/credentials/:id/default
   ↓
System updates is_default flag:
   - Clears default on other Anthropic credentials
   - Sets is_default=true on selected credential
   ↓
Toast: "Default credential updated"
```

---

## 16.6 Revoking and Deleting Keys

```
User clicks [Delete] on a credential:
   ↓
Destructive Confirmation Dialog:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  ⚠️ Delete Credential?                                       │
│                                                              │
│  This action cannot be undone.                               │
│                                                              │
│  Credential: "Production Anthropic Key"                     │
│  Provider: Anthropic                                         │
│                                                              │
│  Impact:                                                     │
│  • Active sandboxes using this key will fail on next request │
│  • 3 running sandboxes currently using this key             │
│                                                              │
│  [Cancel]                              [Delete Credential]  │
└─────────────────────────────────────────────────────────────┘
   ↓
On confirm:
   ↓
DELETE /api/v1/credentials/:id
   ↓
System actions:
   1. Soft delete (marks is_active=false)
   2. Notifies running sandboxes (if possible)
   3. Logs deletion for audit trail
   4. Updates dashboard
   ↓
Toast: "Credential deleted"
```

---

## 16.7 Key Permissions and Security

### Permission Model

```
┌─────────────────────────────────────────────────────────────┐
│  Credential Access Control                                   │
│                                                              │
│  Who can use this credential?                               │
│  ○ Only me (owner)                                          │
│  ● Organization members                                       │
│  ○ Specific projects only                                   │
│                                                              │
│  Sandbox Access Restrictions:                               │
│  [✓] Allow code execution                                    │
│  [✓] Allow file system access                               │
│  [✓] Allow network requests                                  │
│  [ ] Allow credential export (dangerous)                    │
│                                                              │
│  Rate Limiting:                                             │
│  Max requests per minute: [1000________]                    │
│  Daily spend limit: $[500________]                         │
│                                                              │
│  [Save Permissions]                                          │
└─────────────────────────────────────────────────────────────┘
```

### Security Best Practices

| Practice | Implementation |
|----------|----------------|
| **Encryption at Rest** | AES-256-GCM field-level encryption |
| **Key Rotation** | Automatic 90-day rotation reminders |
| **Access Logging** | Every credential use logged |
| **Sandbox Isolation** | Keys never exposed in logs or UI |
| **Rate Limiting** | Per-credential request throttling |
| **Spend Alerts** | Daily/weekly spend notifications |

---

## 16.8 Sandbox Key Injection

```
When sandbox spawns with BYO keys:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  Sandbox Environment Setup                                   │
│                                                              │
│  1. User initiates workflow with BYO key preference        │
│     ↓                                                        │
│  2. System retrieves default credentials for user          │
│     ↓                                                        │
│  3. CredentialsService.get_sandbox_env_vars(user_id)       │
│     ↓                                                        │
│  4. Environment variables prepared:                        │
│     ANTHROPIC_API_KEY=sk-ant-... (encrypted in transit)     │
│     OPENAI_API_KEY=sk-...                                   │
│     Z_AI_API_KEY=sk-...                                     │
│     ↓                                                        │
│  5. Sandbox spawned with env vars injected                 │
│     ↓                                                        │
│  6. Agent worker reads keys from environment               │
│     ↓                                                        │
│  7. Keys used for LLM API calls within sandbox              │
│     ↓                                                        │
│  8. Sandbox destroyed → Keys wiped from memory             │
└─────────────────────────────────────────────────────────────┘
```

---

## 16.9 Usage Tracking and Monitoring

```
Credentials Dashboard → Usage Tab:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  Credential Usage — Last 30 Days                             │
│                                                              │
│  Anthropic (Production Key)                                  │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Requests: 12,450  |  Tokens: 4.2M  |  Cost: $847.50     ││
│  │ ████████████████████████████████████████░░░░░░░░░░░░ ││
│  │ 0%        25%       50%       75%       100%          ││
│  │ Monthly budget: $1,000  |  85% utilized               ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  Daily Breakdown:                                            │
│  Date       | Requests | Tokens    | Cost      | Status     │
│  2026-04-22 | 1,245    | 420K      | $84.50    | ✅ Normal  │
│  2026-04-21 | 1,102    | 380K      | $76.20    | ✅ Normal  │
│  2026-04-20 | 1,567    | 520K      | $104.30   | ⚠️ High   │
│                                                              │
│  Top Workflows:                                              │
│  1. Feature: Payment API (2,340 requests)                   │
│  2. Feature: Auth System (1,890 requests)                   │
│  3. Bug Fix: Database Migration (987 requests)              │
└─────────────────────────────────────────────────────────────┘
```

---

## 16.10 Error States and Recovery

### Common Error Scenarios

```
┌─ API Key Expired
│   ↓
│   Sandbox event: agent.error
│   ↓
│   Error: "Anthropic API key expired (401)"
│   ↓
│   User notification:
│   ┌─────────────────────────────────────────┐
│   │ ⚠️ API Key Expired                       │
│   │ Your Anthropic credential has expired.   │
│   │ 3 sandboxes affected.                   │
│   │ [Update Key] [View Affected Sandboxes]  │
│   └─────────────────────────────────────────┘
│   ↓
│   User updates key → Sandboxes auto-retry
│
├─ Rate Limit Exceeded
│   ↓
│   Error: "Rate limit exceeded (429)"
│   ↓
│   System automatically:
│   - Backs off with exponential delay
│   - Retries after 60 seconds
│   - Switches to backup credential (if configured)
│   ↓
│   User sees: "Rate limited - retrying in 60s"
│
├─ Invalid API Key
│   ↓
│   Validation fails on save
│   ↓
│   Error shown immediately:
│   "Invalid API key format. Expected: sk-ant-..."
│   ↓
│   User corrects and retries
│
└─ Provider Outage
    ↓
    Multiple sandboxes failing
    ↓
    System detects pattern
    ↓
    Alert: "Anthropic API experiencing issues"
    ↓
    Auto-failover to backup provider (if BYO configured)
```

---

## API Keys Journey Summary

```
User Types:
    │
    ├── Free Tier User
    │   ├── Uses OmoiOS-provided API keys (limited)
    │   ├── No credential management needed
    │   └── Upgrade prompt to BYO for unlimited usage
    │
    ├── Pro/Team User (BYO Enabled)
    │   ├── Navigates to Settings → API Keys
    │   ├── Adds provider credentials
    │   ├── Sets default credentials
    │   ├── Monitors usage and costs
    │   └── Rotates keys periodically
    │
    └── Enterprise User
        ├── Multiple credential sets per provider
        ├── Project-specific key restrictions
        ├── Audit logging enabled
        └── Automated rotation policies

Security Flow:
    Key Added → Validation → Encryption → Storage
       ↓
    Sandbox Spawn → Key Injection → Usage → Destruction
       ↓
    Audit Log → Usage Tracking → Alerts → Rotation
```

---

## Related Documentation

- [12_billing_subscription.md](./12_billing_subscription.md) - Subscription tiers including BYO
- [14_settings_personalization.md](./14_settings_personalization.md) - General settings flow
- docs/design/billing/pricing_strategy.md - BYO pricing details
- [backend/omoi_os/services/credentials.py](../../backend/omoi_os/services/credentials.py) - Credentials service
- [backend/omoi_os/models/user_credentials.py](../../backend/omoi_os/models/user_credentials.py) - Data model

---

**Next**: See [17_organization_management.md](./17_organization_management.md) for team and organization workflows.
