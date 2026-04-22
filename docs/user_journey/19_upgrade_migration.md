# 19 Upgrade & Migration

**Part of**: [User Journey Documentation](./README.md)

**Created**: 2026-04-22
**Status**: Active
**Purpose**: Document the complete user journey for upgrading from free tier to paid plans in OmoiOS

---

## Overview

The upgrade and migration journey guides users from the free tier through plan selection, payment setup, and feature unlock. The process is designed to be frictionless while clearly communicating value at each step.

### Pricing Tiers

| Tier | Price | Agents | Workflows | BYO Keys | Best For |
|------|-------|--------|-----------|----------|----------|
| **Free** | $0 | 1 | 5/mo | No | Evaluation |
| **Pro** | $50/mo | 5 | 100/mo | Yes | Individual developers |
| **Team** | $150/mo | 10 | 500/mo | Yes | Growing teams |
| **BYO** | $19/mo | Unlimited* | Unlimited* | Required | Power users |
| **Lifetime** | $299-499 | 5 | 50/mo | Yes | Early adopters |
| **Enterprise** | Custom | Unlimited | Unlimited | Yes | Large orgs |

*Limited by user's API key budget

---

## 19.1 Free Tier Experience

```
Free Tier User Journey:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  Free Tier Dashboard                                          │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Usage This Month                                         ││
│  │ Workflows: 3/5 used  ████████████████░░░░░░░░░░  60%    ││
│  │                                                          ││
│  │ 🎉 2 workflows remaining this month                      ││
│  │ Resets on May 1, 2026                                    ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  Active Projects                                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Payment API Feature                                     ││
│  │ Status: Running  |  Workflows used: 2                   ││
│  │                                                          ││
│  │ ⚠️ Approaching limit — Upgrade for unlimited workflows   ││
│  │ [Compare Plans]                                          ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  Upgrade Prompt (appears at 4/5 workflows):                  │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ 🚀 Ready to ship more?                                   ││
│  │                                                          ││
│  │ You've used 4 of 5 free workflows. Upgrade to Pro:       ││
│  │ • 100 workflows/month                                    ││
│  │ • 5 concurrent agents                                    │
│  │ • Bring your own API keys                                │
│  │ • Priority support                                       │
│  │                                                          │
│  │ [Upgrade to Pro — $50/mo]  [View All Plans]              ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### Free Tier Limits

| Resource | Limit | Reset |
|----------|-------|-------|
| Workflows | 5/month | 1st of month |
| Concurrent Agents | 1 | N/A |
| Projects | 1 | N/A |
| Storage | 2GB | N/A |
| Support | Community | N/A |

---

## 19.2 Upgrade Triggers

```
Automatic Upgrade Prompts:
   ↓
┌─ Workflow Limit Warning (4/5 used)
│   ↓
│   In-app banner + email notification
│   ↓
│   "You're almost out of workflows"
│
├─ Workflow Limit Reached (5/5 used)
│   ↓
│   Modal appears on next feature request
│   ↓
│   "Upgrade to continue building"
│   [Upgrade Now] [I'll wait until next month]
│
├─ Concurrent Agent Limit
│   ↓
│   "You have 1 agent running. Upgrade to run multiple agents."
│   ↓
│   Shown when trying to spawn 2nd agent
│
├─ Storage Limit
│   ↓
│   "Storage 90% full (1.8GB/2GB)"
│   ↓
│   Cleanup suggestions + upgrade prompt
│
└─ Feature Gate
    ↓
    "BYO API Keys requires Pro or higher"
    ↓
    Shown when clicking "Add API Key" on free tier
```

---

## 19.3 Plan Selection

```
User clicks [Upgrade] or [View All Plans]:
   ↓
Pricing Page (/pricing or modal):
   ↓
┌─────────────────────────────────────────────────────────────┐
│  Choose Your Plan                                            │
│  Scale your engineering output with AI agents                │
│                                                              │
│  Monthly  [Yearly — Save 20%]                              │
│                                                              │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │   STARTER    │ │     PRO      │ │     TEAM     │        │
│  │              │ │   Popular    │ │              │        │
│  │   Free       │ │   $50/mo     │ │  $150/mo     │        │
│  │   $0         │ │   $40/mo     │ │  $120/mo     │        │
│  │              │ │   yearly     │ │  yearly      │        │
│  ├──────────────┤ ├──────────────┤ ├──────────────┤        │
│  │ 1 agent      │ │ 5 agents     │ │ 10 agents    │        │
│  │ 5 workflows  │ │ 100 workflows│ │ 500 workflows│        │
│  │ Community    │ │ BYO Keys ✓  │ │ BYO Keys ✓  │        │
│  │ support      │ │ Priority     │ │ Priority     │        │
│  │              │ │ support      │ │ support      │        │
│  │              │ │              │ │ Team collab  │        │
│  │ [Current]    │ │ [Upgrade]    │ │ [Upgrade]    │        │
│  └──────────────┘ └──────────────┘ └──────────────┘        │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  🔑 BYO Keys Plan                                        ││
│  │  $19/mo — Bring your own API keys for unlimited usage   ││
│  │  [Learn More]                                            ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  💎 Lifetime Access                                      ││
│  │  $499 one-time — Permanent Pro access                    ││
│  │  [Limited availability]                                  ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  Enterprise? [Contact Sales] for custom pricing             │
└─────────────────────────────────────────────────────────────┘
```

### Plan Comparison Helper

```
Interactive Plan Selector:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  Find Your Perfect Plan                                      │
│                                                              │
│  How many team members?                                      │
│  [1-5 ▼]  [6-15 ▼]  [16-50 ▼]  [50+ ▼]                     │
│                                                              │
│  Expected monthly workflows?                                 │
│  [Slider: 0 ———●——— 1000]                                   │
│  ~50 workflows/month                                       │
│                                                              │
│  Do you have your own API keys?                              │
│  [Yes, I have Anthropic/OpenAI keys]                       │
│  [No, I need OmoiOS to provide them]                        │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  💡 Recommended: Pro Plan ($50/mo)                      ││
│  │                                                          ││
│  │  Based on your answers:                                  ││
│  │  • 50 workflows fits in 100 workflow limit              ││
│  │  • 5 agents enough for 1-5 team members                   ││
│  │  • BYO keys available for cost savings                    ││
│  │                                                          ││
│  │  [Select Pro Plan]  [Compare All]                       ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

---

## 19.4 Checkout Flow

```
User selects Pro Plan:
   ↓
Checkout Process:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  Upgrade to Pro Plan                                         │
│  Step 1 of 3: Confirm Plan                                   │
│                                                              │
│  Selected Plan: Pro ($50/month)                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ What's included:                                         ││
│  │ ✓ 5 concurrent agents                                    ││
│  │ ✓ 100 workflows/month                                  ││
│  │ ✓ BYO API key support                                    ││
│  │ ✓ Priority email support                                 ││
│  │ ✓ Unlimited projects                                     ││
│  │ ✓ 50GB storage                                           ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  Billing Cycle:                                            │
│  ○ Monthly — $50/month                                       │
│  ● Yearly — $480/year (Save $60)                           │
│                                                              │
│  Organization: Acme Inc                                     │
│  [Change organization ▼]                                    │
│                                                              │
│  [Cancel]                              [Continue →]          │
└─────────────────────────────────────────────────────────────┘
   ↓
Step 2: Payment Method
   ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 2 of 3: Payment Method                                   │
│                                                              │
│  Pay with:                                                   │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ 💳 Credit Card                                          ││
│  │                                                         ││
│  │ Card number: [•••• •••• •••• 4242________________]    ││
│  │ Expiry: [12/26____]  CVC: [•••___]                     ││
│  │ Name: [Alice Smith________________]                      ││
│  │                                                         ││
│  │ [✓] Save card for future payments                       ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  Or pay with:                                               │
│  [PayPal] [Apple Pay] [Google Pay]                         │
│                                                              │
│  Promo Code:                                                 │
│  [EARLY2026________]  [Apply]  ✓ 20% off first 3 months    │
│                                                              │
│  Order Summary:                                              │
│  Pro Plan (Yearly)                              $480.00    │
│  Discount (EARLY2026)                           -$96.00     │
│  ─────────────────────────────────────────────────────────  │
│  Total due today                                $384.00    │
│                                                              │
│  [← Back]                              [Pay $384.00 →]       │
└─────────────────────────────────────────────────────────────┘
   ↓
Step 3: Confirmation
   ↓
┌─────────────────────────────────────────────────────────────┐
│  Step 3 of 3: Confirmation                                     │
│                                                              │
│  🎉 Welcome to Pro!                                          │
│                                                              │
│  Your upgrade is complete. Here's what's unlocked:         │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Immediate Access:                                        ││
│  │ • 5 concurrent agents (was 1)                           ││
│  │ • 100 workflows this month (was 5)                      ││
│  │ • BYO API key configuration enabled                     ││
│  │ • Priority support queue                                  ││
│  │                                                          ││
│  │ Next Steps:                                              ││
│  │ 1. [Configure API Keys] — Use your own LLM keys          ││
│  │ 2. [Invite Team Members] — Add up to 5 members           ││
│  │ 3. [Create New Project] — Unlimited projects now         ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  Receipt sent to: billing@acme.com                           │
│  Invoice #: INV-2026-0422-001                              │
│                                                              │
│  [Go to Dashboard]  [View Billing Settings]                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 19.5 Feature Unlock

```
Post-Upgrade Feature Activation:
   ↓
┌─ Concurrent Agents
│   ↓
│   Before: 1 agent slot
│   After: 5 agent slots immediately available
│   ↓
│   User can spawn up to 5 agents simultaneously
│   Existing running agent continues unaffected
│
├─ Workflow Limit
│   ↓
│   Before: 0 remaining (5/5 used)
│   After: 95 remaining (5/100 used)
│   ↓
│   Counter resets on upgrade, not billing cycle
│   Usage bar updates in real-time
│
├─ BYO API Keys
│   ↓
│   Before: Feature gated, shows upgrade prompt
│   After: Settings → API Keys menu unlocked
│   ↓
│   User can add Anthropic, OpenAI, Z.AI credentials
│   Sandboxes can use BYO keys immediately
│
├─ Projects
│   ↓
│   Before: 1 project limit
│   After: Unlimited projects
│   ↓
│   [+ New Project] button always available
│   Existing project preserved
│
└─ Support
    ↓
    Before: Community support only
    After: Priority email support
    ↓
    Support widget shows "Pro" badge
    Faster response time SLA
```

---

## 19.6 Data Migration

```
Free → Paid Data Migration:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  Data Migration Status                                       │
│  Your data is being transferred to Pro plan                 │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ ✅ Projects        │ 3 projects  │ Migrated          ││
│  │ ✅ Sandboxes       │ 12 history  │ Migrated          ││
│  │ ✅ Specs           │ 8 specs     │ Migrated          ││
│  │ ✅ Memories        │ 45 patterns │ Migrated          ││
│  │ ✅ Billing History │ 5 records   │ Migrated          ││
│  │ ⏳ Agent States    │ 1 running   │ Preserving...     ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  Migration completed in 2.3 seconds                          │
│  All data preserved, no action needed                         │
└─────────────────────────────────────────────────────────────┘
```

### What Migrates

| Data Type | Migration | Notes |
|-----------|-----------|-------|
| Projects | ✅ All | Preserved with history |
| Sandboxes | ✅ History | Logs and transcripts kept |
| Specs | ✅ All | Requirements, design, tasks |
| Memories | ✅ All | Learned patterns preserved |
| Billing | ✅ History | Free tier usage visible |
| Agents | ✅ Running | Continue uninterrupted |
| Settings | ✅ All | Preferences maintained |

---

## 19.7 Billing Management

```
Organization → Billing Tab:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  Billing & Subscription                                        │
│  Acme Inc — Pro Plan                                         │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Current Plan                                             ││
│  │ Pro — $50/month                                         ││
│  │ Next billing date: May 22, 2026                         ││
│  │ Payment method: Visa ending in 4242                    ││
│  │                                                          ││
│  │ [Change Plan] [Cancel Subscription] [Update Payment]    ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  Usage This Period                                           │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Workflows: 23/100 used  ████████░░░░░░░░░░░░░░░░░░ 23% ││
│  │ Agents: 2/5 active       ████████░░░░░░░░░░░░░░░░░░ 40% ││
│  │ Storage: 8.2GB/50GB      ███░░░░░░░░░░░░░░░░░░░░░░░ 16% ││
│  │                                                          ││
│  │ Projected usage: 67 workflows (within limit)          ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  Recent Invoices                                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Date       │ Description    │ Amount  │ Status │ Action ││
│  │ 2026-04-22 │ Pro Plan       │ $50.00  │ Paid   │ [PDF]  ││
│  │ 2026-03-22 │ Pro Plan       │ $50.00  │ Paid   │ [PDF]  ││
│  │ 2026-02-22 │ Upgrade prorate│ $25.00  │ Paid   │ [PDF]  ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### Plan Changes

```
Upgrade Flow (Pro → Team):
   ↓
┌─────────────────────────────────────────────────────────────┐
│  Upgrade to Team Plan                                        │
│                                                              │
│  Current: Pro ($50/mo)                                       │
│  New: Team ($150/mo)                                        │
│  Difference: +$100/mo                                       │
│                                                              │
│  Prorated charge today: $50.00                              │
│  (Credit for unused Pro time: $25, Team for 15 days: $75)  │
│                                                              │
│  New limits effective immediately:                          │
│  • Agents: 5 → 10                                            │
│  • Workflows: 100 → 500/month                               │
│  • Team collaboration features unlocked                      │
│                                                              │
│  [Keep Pro]  [Upgrade to Team — $50 today]                  │
└─────────────────────────────────────────────────────────────┘

Downgrade Flow (Team → Pro):
   ↓
┌─────────────────────────────────────────────────────────────┐
│  Change to Pro Plan                                          │
│                                                              │
│  ⚠️ Your new limits will be lower                            │
│                                                              │
│  Current usage (Team):                                        │
│  • 7 agents active (Pro limit: 5)                           │
│  • 340 workflows this month (Pro limit: 100)               │
│                                                              │
│  Options:                                                    │
│  ○ Effective next billing cycle (May 22)                   │
│    - Keep current limits until then                         │
│                                                              │
│  ● Effective immediately                                     │
│    - Excess agents will be stopped                          │
│    - Workflow limit applies immediately                     │
│                                                              │
│  [Cancel]  [Schedule Downgrade]                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 19.8 Cancellation Flow

```
User clicks [Cancel Subscription]:
   ↓
Cancellation Flow:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  Cancel Subscription                                         │
│  We're sorry to see you go                                   │
│                                                              │
│  Before you cancel, would you tell us why?                   │
│  (This helps us improve)                                     │
│                                                              │
│  [ ] Too expensive                                           │
│  [ ] Not using it enough                                     │
│  [ ] Missing features I need                                 │
│  [ ] Switched to alternative                                 │
│  [ ] Technical issues                                        │
│  [ ] Other: [________________]                              │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ 💡 Alternative to cancelling:                           ││
│  │                                                          ││
│  │ Switch to BYO Keys plan ($19/mo)                       ││
│  │ • Keep unlimited workflows                               ││
│  │ • Use your own API keys for LLM costs                   ││
│  │ • Same agent limits                                      ││
│  │ • Save $31/month                                        ││
│  │                                                          ││
│  │ [Consider BYO Plan]                                      ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  Cancellation Terms:                                         │
│  • Access continues until May 22, 2026 (end of period)     │
│  • No partial refunds for unused time                        │
│  • Data retained for 30 days, then archived                │
│  • Can reactivate anytime before period end                  │
│                                                              │
│  [Never Mind]  [Confirm Cancellation]                       │
└─────────────────────────────────────────────────────────────┘
   ↓
On Confirm:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  Subscription Cancelled                                        │
│                                                              │
│  Your Pro subscription will end on May 22, 2026           │
│                                                              │
│  Until then, you keep:                                       │
│  • Full Pro access                                           │
│  • All your data                                             │
│  • Ability to reactivate                                     │
│                                                              │
│  After May 22:                                               │
│  • Downgrade to Free tier (5 workflows/month)              │
│  • Projects preserved but limited to 1 active              │
│  • Sandboxes archived (retrievable for 30 days)             │
│                                                              │
│  [Reactivate Now]  [Export Data]  [Contact Support]          │
└─────────────────────────────────────────────────────────────┘
```

---

## 19.9 Upgrade Journey Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    Upgrade Journey Flow                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
│                   │   Free Tier       │
│                   │   (5 workflows)   │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
       ┌──────────┐  ┌──────────┐  ┌──────────┐
       │ Workflow │  │ Feature  │  │ Manual   │
       │ Limit    │  │ Gate     │  │ Upgrade  │
       │ Reached  │  │ Blocked  │  │ Click    │
       └────┬─────┘  └────┬─────┘  └────┬─────┘
            │             │             │
            └──────────────┼─────────────┘
                           ▼
                    ┌─────────────────┐
                    │  Plan Selection   │
                    │  /pricing page    │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
       ┌──────────┐  ┌──────────┐  ┌──────────┐
       │ Pro      │  │ Team     │  │ BYO      │
       │ $50/mo   │  │ $150/mo  │  │ $19/mo   │
       └────┬─────┘  └────┬─────┘  └────┬─────┘
            │             │             │
            └──────────────┼─────────────┘
                           ▼
                    ┌─────────────────┐
                    │  Stripe Checkout  │
                    │  Payment flow     │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Confirmation     │
                    │  Features unlock  │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  Active Paid      │
                    │  Subscription     │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
       ┌──────────┐  ┌──────────┐  ┌──────────┐
       │ Continue │  │ Upgrade  │  │ Cancel   │
       │ Using    │  │ Further  │  │ (retain  │
       │          │  │          │  │ access)  │
       └──────────┘  └──────────┘  └──────────┘
```

---

## 19.10 Error States and Recovery

```
┌─ Payment Failed
│   ↓
│   Error: "Card declined (insufficient funds)"
│   ↓
│   Options:
│   • Try different payment method
│   • Contact bank
│   • Retry in 24 hours
│   ↓
│   Account remains on free tier
│   Upgrade can be retried anytime
│
├─ Proration Confusion
│   ↓
│   User: "Why am I charged $75 for mid-month upgrade?"
│   ↓
│   Explanation shown:
│   "Credit for unused Starter: -$25
│    Charge for Pro (15 days): +$50
│    ─────────────────────────────
│    Total due today: $25"
│   ↓
│   Clear breakdown with tooltip explanations
│
├─ Organization Not Found
│   ↓
│   User tries to upgrade without org
│   ↓
│   System: "Create an organization first"
│   ↓
│   Redirected to /organizations/new
│   ↓
│   After creation, return to upgrade flow
│
└─ Promo Code Invalid
    ↓
    Error: "Code EARLY2026 expired"
    ↓
    Suggestions:
    • "Try NEWYEAR2026 for 15% off"
    • "Student? Use STUDENT50 for 50% off"
    ↓
    User can continue without code
```

---

## Upgrade Journey Summary

```
Key Touchpoints:
    │
    ├── Awareness
    │   ├── Usage bar at 80%
    │   ├── Feature gate messages
    │   └── "Upgrade" buttons in UI
    │
    ├── Consideration
    │   ├── /pricing page visit
    │   ├── Plan comparison
    │   └── Cost calculator
    │
    ├── Decision
    │   ├── Plan selection
    │   ├── Billing cycle choice
    │   └── Promo code entry
    │
    ├── Purchase
    │   ├── Stripe checkout
    │   ├── Payment confirmation
    │   └── Receipt email
    │
    └── Activation
        ├── Immediate feature unlock
        ├── Data migration
        ├── Welcome email
        └── Onboarding tips

Retention:
    ├── Usage alerts (approaching limits)
    ├── Value metrics (workflows saved)
    ├── Feature announcements
    └── Support engagement
```

---

## Related Documentation

- [12_billing_subscription.md](./12_billing_subscription.md) - Detailed billing flows
- [16_api_keys_management.md](./16_api_keys_management.md) - BYO keys setup
- docs/design/billing/pricing_strategy.md - Pricing details
- [backend/omoi_os/api/routes/billing.py](../../backend/omoi_os/api/routes/billing.py) - Billing API

---

**Next**: See [README.md](./README.md) for complete user journey documentation index.
