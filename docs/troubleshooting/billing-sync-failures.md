# Billing Sync Failures Troubleshooting Guide

**Last Updated**: 2026-04-22  
**Applies To**: OmoiOS Billing Service v1.0+  
**Related Services**: `BillingService`, `SubscriptionService`, `StripeService`

---

## Overview

This guide covers troubleshooting for billing synchronization failures between OmoiOS and Stripe. The billing system handles invoice generation, payment processing, subscription management, and usage tracking. Failures can occur at multiple integration points including webhook processing, payment intent creation, subscription sync, and usage record reconciliation.

---

## Common Error Scenarios

### 1. Stripe Customer Creation Failure

**Error Message**:
```
Failed to create Stripe customer: <stripe.error.StripeError message>
```

**Root Causes**:
- Missing or invalid `STRIPE_SECRET_KEY` environment variable
- Invalid organization email format
- Stripe API rate limiting
- Network connectivity issues to Stripe API

**Diagnosis Steps**:

1. Check Stripe configuration:
```python
from omoi_os.services.stripe_service import load_stripe_settings
settings = load_stripe_settings()
print(f"Secret key configured: {bool(settings.secret_key)}")
print(f"Webhook secret configured: {bool(settings.webhook_secret)}")
```

2. Verify Stripe API key validity:
```bash
curl https://api.stripe.com/v1/account \
  -H "Authorization: Bearer $STRIPE_SECRET_KEY"
```

3. Check billing service initialization:
```python
from omoi_os.services.billing_service import get_billing_service
from omoi_os.services.database import DatabaseService
from omoi_os.config import get_app_settings

db = DatabaseService(connection_string=get_app_settings().database.url)
service = get_billing_service(db)
print(f"Stripe configured: {service.stripe.is_configured}")
```

**Fix**:
```python
# In backend/.env or .env.local
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PUBLISHABLE_KEY=pk_live_...

# Restart the API server after updating environment variables
# The StripeService reads configuration at initialization time
```

---

### 2. Payment Processing Failure

**Error Message**:
```
Payment failed for invoice INV-202504-ABC123: <error_details>
billing.payment_failed event published
```

**Root Causes**:
- Expired or invalid payment method
- Insufficient funds
- Card declined by issuer
- Missing default payment method on customer
- `stripe_customer_id` not set on billing account

**Diagnosis Steps**:

1. Check billing account status:
```python
from omoi_os.services.billing_service import get_billing_service
from omoi_os.models.billing import BillingAccountStatus

account = service.get_billing_account(organization_id)
print(f"Account status: {account.status}")
print(f"Stripe customer ID: {account.stripe_customer_id}")
print(f"Credit balance: ${account.credit_balance}")
```

2. Verify payment method in Stripe:
```python
from omoi_os.services.stripe_service import get_stripe_service

stripe = get_stripe_service()
methods = stripe.list_payment_methods(customer_id)
print(f"Available payment methods: {len(methods)}")
for m in methods:
    print(f"  - {m.id}: {m.card.brand} ending in {m.card.last4}")
```

3. Check for specific card errors:
```python
from stripe import CardError

try:
    stripe.charge_customer_directly(
        customer_id="cus_...",
        amount_cents=1000,
        description="Test charge"
    )
except CardError as e:
    print(f"Card declined: {e.user_message}")
    print(f"Decline code: {e.code}")  # e.g., 'insufficient_funds', 'expired_card'
```

**Fix**:
```python
# Option 1: Add credits to bypass payment
from omoi_os.services.billing_service import get_billing_service

service.add_credits(
    billing_account_id=account.id,
    amount_usd=50.0,
    reason="manual_credit_for_failed_payment"
)

# Option 2: Update payment method via customer portal
portal_url = service.create_customer_portal_url(organization_id)
# Redirect user to portal_url to update their payment method

# Option 3: Reactivate suspended account after payment method updated
service.update_billing_account_status(
    billing_account_id=account.id,
    status=BillingAccountStatus.ACTIVE
)
```

---

### 3. Subscription Sync Failure from Stripe Webhook

**Error Message**:
```
Subscription not found for Stripe ID: sub_...
ValueError: Subscription not found for Stripe ID: sub_...
```

**Root Causes**:
- Webhook received for subscription created outside OmoiOS
- Database inconsistency between Stripe and local state
- Missing `stripe_subscription_id` mapping
- Webhook processing failed before local record created

**Diagnosis Steps**:

1. Check subscription mapping:
```python
from sqlalchemy import select
from omoi_os.models.subscription import Subscription

result = session.execute(
    select(Subscription).where(
        Subscription.stripe_subscription_id == "sub_..."
    )
)
sub = result.scalar_one_or_none()
print(f"Local subscription: {sub}")
```

2. Verify webhook endpoint configuration:
```bash
# Check webhook endpoints in Stripe Dashboard
curl https://api.stripe.com/v1/webhook_endpoints \
  -H "Authorization: Bearer $STRIPE_SECRET_KEY"
```

3. Review webhook event types:
```python
# Required events per CLAUDE.md:
# - checkout.session.completed
# - customer.subscription.created
# - customer.subscription.updated
# - customer.subscription.deleted
# - invoice.paid
# - invoice.payment_failed
```

**Fix**:
```python
# Manually sync subscription from Stripe
from omoi_os.services.subscription_service import get_subscription_service

subscription = service.sync_from_stripe(
    stripe_subscription_id="sub_...",
    session=session
)

# Or create mapping if subscription exists locally but stripe_id is missing
subscription.stripe_subscription_id = "sub_..."
session.commit()
```

---

### 4. Invoice Generation Failure

**Error Message**:
```
No unbilled usage for account: <uuid>
Generated invoice INV-202504-ABC123 for $0.00 (0 workflow(s))
```

**Root Causes**:
- All usage records already billed
- Usage records marked with `free_tier_used=True`
- Missing usage records for completed workflows
- Billing account not found for organization

**Diagnosis Steps**:

1. Check unbilled usage:
```python
from omoi_os.services.billing_service import get_billing_service

unbilled = service.get_unbilled_usage(billing_account_id)
print(f"Unbilled records: {len(unbilled)}")
for record in unbilled:
    print(f"  - {record.id}: ${record.total_price} (ticket: {record.ticket_id})")
```

2. Verify usage record creation:
```python
from omoi_os.models.billing import UsageRecord
from sqlalchemy import select

result = session.execute(
    select(UsageRecord).where(
        UsageRecord.billing_account_id == account_id,
        UsageRecord.billed == False
    )
)
records = result.scalars().all()
print(f"Unbilled usage records: {len(records)}")
```

3. Check workflow usage tracking:
```python
# Verify usage is being recorded when workflows complete
usage_record = service.record_workflow_usage(
    organization_id=org_id,
    ticket_id=ticket_id,
    usage_details={"tokens": 1500, "duration_seconds": 120}
)
print(f"Recorded usage: {usage_record.id}")
```

**Fix**:
```python
# Force invoice generation even with minimal usage
from omoi_os.models.billing import Invoice, InvoiceStatus
from uuid import uuid4
from omoi_os.utils.datetime import utc_now

invoice = Invoice(
    id=uuid4(),
    invoice_number=f"INV-{utc_now().strftime('%Y%m')}-{str(uuid4())[:8].upper()}",
    billing_account_id=account_id,
    status=InvoiceStatus.DRAFT.value,
    period_start=utc_now() - timedelta(days=30),
    period_end=utc_now(),
    currency="usd",
    line_items=[],
    due_date=utc_now() + timedelta(days=7),
)
```

---

### 5. Workflow Execution Blocked Due to Billing

**Error Message**:
```
Workflow execution blocked for org <uuid>: Account suspended due to payment issues
billing.workflow_blocked event published
```

**Root Causes**:
- `BillingAccountStatus.SUSPENDED` due to failed payments
- No active subscription and free tier exhausted
- No prepaid credits available
- Monthly workflow limit reached on subscription

**Diagnosis Steps**:

1. Check execution permission:
```python
from omoi_os.services.billing_service import get_billing_service

can_execute, reason = service.can_execute_workflow(organization_id)
print(f"Can execute: {can_execute}")
print(f"Reason: {reason}")
# Possible reasons: 'new_account', 'subscription_quota', 'free_tier', 
#                   'prepaid_credits', 'enterprise_unlimited', 'overage_credits'
```

2. Get full usage summary:
```python
summary = service.get_usage_summary(organization_id)
print(f"Subscription tier: {summary['subscription_tier']}")
print(f"Workflows used: {summary['workflows_used']}/{summary['workflows_limit']}")
print(f"Free workflows remaining: {summary['free_workflows_remaining']}")
print(f"Credit balance: ${summary['credit_balance']}")
print(f"Can execute: {summary['can_execute']}")
```

3. Check subscription status:
```python
from omoi_os.services.subscription_service import get_subscription_service
from omoi_os.models.subscription import SubscriptionStatus

sub = sub_service.get_subscription(organization_id)
if sub:
    print(f"Status: {sub.status}")
    print(f"Is active: {sub.is_active}")
    print(f"Workflows remaining: {sub.workflows_remaining}")
```

**Fix**:
```python
# Option 1: Add prepaid credits
service.add_credits(billing_account_id, amount_usd=100.0)

# Option 2: Upgrade subscription tier
from omoi_os.models.subscription import SubscriptionTier

sub_service.upgrade_tier(
    subscription_id=sub.id,
    new_tier=SubscriptionTier.PRO,
    stripe_subscription_id="sub_...",
    stripe_price_id="price_..."
)

# Option 3: Reset free tier (if new month)
account.free_workflows_remaining = settings.free_workflows_per_month
account.free_workflows_reset_at = service._next_month_start()
```

---

## Prevention

### 1. Webhook Reliability

Configure webhook endpoint with retry logic:
```yaml
# In Stripe Dashboard:
# Endpoint URL: https://api.omoios.dev/api/v1/billing/webhooks/stripe
# Events: checkout.session.completed, customer.subscription.*, invoice.*
```

Implement idempotent webhook handlers:
```python
# Check for duplicate webhook processing
existing = session.execute(
    select(WebhookEvent).where(
        WebhookEvent.stripe_event_id == event.id
    )
).scalar_one_or_none()

if existing:
    logger.info(f"Webhook {event.id} already processed")
    return  # Skip duplicate
```

### 2. Monitoring and Alerting

Set up alerts for billing events:
```python
# Monitor these event types:
# - billing.payment_failed
# - billing.workflow_blocked
# - subscription.canceled
# - billing.invoice_generated (with amount_due > threshold)
```

### 3. Grace Periods for Failed Payments

Configure dunning management:
```python
# In billing_service.py, the process_invoice_payment method:
# - Sets account status to SUSPENDED on payment failure
# - Publishes billing.payment_failed event
# - Consider implementing retry logic with exponential backoff
```

### 4. Test Mode Validation

Always test billing flows in Stripe test mode:
```bash
# Use Stripe test cards:
# Success: 4242 4242 4242 4242
# Decline: 4000 0000 0000 0002
# Insufficient funds: 4000 0000 0000 9995
```

---

## Related Documentation

- [Stripe Integration Architecture](../../docs/architecture/08-billing-and-subscriptions.md)
- [Billing Service API](../../backend/omoi_os/api/routes/billing.py)
- [Subscription Service](../../backend/omoi_os/services/subscription_service.py)
- [Stripe Service](../../backend/omoi_os/services/stripe_service.py)
- [CLAUDE.md - Stripe Webhook Configuration](../../backend/CLAUDE.md)

---

## Quick Reference: Key Functions

| Function | Purpose | Location |
|----------|---------|----------|
| `get_or_create_billing_account()` | Initialize billing for organization | `billing_service.py:62` |
| `process_invoice_payment()` | Charge customer for invoice | `billing_service.py:449` |
| `can_execute_workflow()` | Check execution permission | `billing_service.py:691` |
| `sync_from_stripe()` | Sync subscription state | `subscription_service.py:746` |
| `verify_webhook()` | Validate Stripe webhook | `stripe_service.py:565` |
| `charge_customer_directly()` | Process payment | `stripe_service.py:437` |
