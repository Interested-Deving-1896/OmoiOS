# 17 Organization Management

**Part of**: [User Journey Documentation](./README.md)

**Created**: 2026-04-22
**Status**: Active
**Purpose**: Document the complete user journey for organization and team management in OmoiOS

---

## Overview

Organization management in OmoiOS enables teams to collaborate on AI-driven engineering projects. Organizations provide scoped billing, role-based access control (RBAC), member management, and resource isolation.

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Organization** | Top-level container for teams, projects, and billing |
| **Membership** | User or Agent association with an organization |
| **Role** | Permission set defining what members can do |
| **System Roles** | Built-in roles (Owner, Admin, Member) |
| **Custom Roles** | Organization-defined roles with specific permissions |
| **Billing Scope** | All billing attached to an organization |

---

## 17.1 Accessing Organization Management

```
User navigates to organizations:
   ↓
1. From IconRail → Building2 icon (Organizations)
   ↓
2. Arrives at /organizations
   ↓
3. Organization list loads showing:
   - Organizations user is member of
   - Current role in each
   - Member count
   - Quick actions
```

---

## 17.2 Organization List View

```
/organizations page:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  Organizations                                               │
│  Manage your teams and collaborate on projects              │
│                                                              │
│  [+ Create Organization]                                    │
│                                                              │
│  Your Organizations (3)                                     │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ 🏢 Acme Inc                                             ││
│  │    omoios.dev/o/acme-inc                                ││
│  │    👑 Owner  •  12 members  •  8 projects                ││
│  │    [View] [Settings] [Billing]                          ││
│  ├─────────────────────────────────────────────────────────┤│
│  │ 🏢 Personal Projects                                    ││
│  │    omoios.dev/o/personal                                ││
│  │    👑 Owner  •  1 member  •  3 projects                ││
│  │    [View] [Settings] [Billing]                          ││
│  ├─────────────────────────────────────────────────────────┤│
│  │ 🏢 StartupXYZ (invited)                                 ││
│  │    omoios.dev/o/startupxyz                              ││
│  │    🛡 Member  •  5 members  •  2 projects               ││
│  │    [Accept Invite] [Decline]                            ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  [Join Organization] — Enter invite code or organization slug│
└─────────────────────────────────────────────────────────────┘
```

---

## 17.3 Creating an Organization

```
User clicks [+ Create Organization]:
   ↓
Create Organization Form:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  ← Back to Organizations                                     │
│                                                              │
│  Create Organization                                         │
│  Set up a new organization to collaborate with your team     │
│                                                              │
│  Organization Name *                                         │
│  [Acme Inc________________________________]                 │
│                                                              │
│  URL Slug *                                                  │
│  omoios.dev/o/ [acme-inc________]                           │
│  Only lowercase letters, numbers, and hyphens                │
│                                                              │
│  Description (optional)                                      │
│  [Tell us about your organization...                ]       │
│                                                              │
│  Billing Email *                                             │
│  [billing@acme.com____________________]                     │
│  For invoices and payment notifications                      │
│                                                              │
│                          [Cancel] [Create Organization]      │
└─────────────────────────────────────────────────────────────┘
   ↓
On submit:
   ↓
POST /api/v1/organizations
{
  "name": "Acme Inc",
  "slug": "acme-inc",
  "description": "...",
  "billing_email": "billing@acme.com"
}
   ↓
System actions:
   1. Validates slug uniqueness
   2. Creates organization record
   3. Assigns Owner role to creator
   4. Creates billing account
   5. Sets up default project
   ↓
Redirect to /organizations/:id
Toast: "Organization created successfully"
```

---

## 17.4 Organization Detail View

```
/organizations/:id page:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  ← Back to Organizations                                     │
│  🏢 Acme Inc                                    [Settings ⚙️]│
│  omoios.dev/o/acme-inc                                       │
│                                                              │
│  Tabs: [Overview] [Members] [Projects] [Billing] [Audit]   │
│                                                              │
│  ─────────────────────────────────────────────────────────  │
│  Overview Tab                                                │
│                                                              │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐          │
│  │ Members      │ │ Projects     │ │ Workflows    │          │
│  │ 12           │ │ 8            │ │ 247 this mo  │          │
│  └──────────────┘ └──────────────┘ └──────────────┘          │
│                                                              │
│  Recent Activity                                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Today, 10:23 AM    👤 Alice created project "API v2"  ││
│  │ Today, 9:45 AM     🤖 worker-3 completed task #452    ││
│  │ Yesterday, 4:30 PM 👤 Bob invited charlie@acme.com    ││
│  │ Yesterday, 2:15 PM 💳 Invoice paid: $150.00           ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  Active Sandboxes (3 running)                               │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ 🔵 Payment API Feature    │ Running │ 2h 15m elapsed ││
│  │ 🔵 Auth System Refactor   │ Running │ 1h 42m elapsed ││
│  │ 🟡 Database Migration     │ Pending │ Queued         ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

---

## 17.5 Member Management

### Viewing Members

```
User clicks [Members] tab:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  Members                                       [+ Add Member]│
│  Manage team members and their permissions                   │
│                                                              │
│  [Search members...]  [Filter by role ▼]  [Export CSV]      │
│                                                              │
│  Team Members (12)                                           │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Member          │ Role           │ Joined    │ Actions  ││
│  │ ────────────────────────────────────────────────────────││
│  │ 👤 Alice Smith   │ 👑 Owner       │ Jan 2026  │ [⋮]      ││
│  │    alice@acme.com│ (Full control) │           │          ││
│  ├─────────────────────────────────────────────────────────┤│
│  │ 👤 Bob Johnson   │ 🛡 Admin       │ Feb 2026  │ [⋮]      ││
│  │    bob@acme.com  │ (Manage)       │           │          ││
│  ├─────────────────────────────────────────────────────────┤│
│  │ 🤖 worker-1      │ 🤖 Agent       │ Feb 2026  │ [⋮]      ││
│  │    (system)      │ (Execute)      │           │          ││
│  ├─────────────────────────────────────────────────────────┤│
│  │ 👤 Charlie Brown │ 🛡 Member      │ Mar 2026  │ [⋮]      ││
│  │    charlie@acme  │ (Read/Create)  │           │          ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  Pending Invites (2)                                         │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ dave@acme.com    │ Member         │ Invited   │ [Resend]││
│  │                  │                │ 2 days ago│ [Cancel]││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### Adding Members

```
User clicks [+ Add Member]:
   ↓
Add Member Dialog:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  Add Member to Acme Inc                                      │
│                                                              │
│  Email Address *                                             │
│  [newmember@acme.com____________________]                   │
│                                                              │
│  Role *                                                      │
│  [Select role...                        ▼]                  │
│  ├─ System Roles                                            ││
│  │  👑 Owner — Full control (billing, deletion, settings)    ││
│  │  🛡 Admin — Manage members, projects, agents             ││
│  │  🛡 Member — Create and work on projects                 ││
│  ├─ Custom Roles                                            ││
│  │  🔬 Researcher — Read-only + memory access              ││
│  │  🔧 Developer — Member + agent spawning                ││
│  └─────────────────────────────────────────────────────────│
│                                                              │
│  Message (optional):                                         │
│  [Join our team on OmoiOS! We're building...        ]       │
│                                                              │
│  [✓] Send invite email                                       │
│                                                              │
│  [Cancel]                              [Send Invite]         │
└─────────────────────────────────────────────────────────────┘
   ↓
POST /api/v1/organizations/:id/members
{
  "user_id": "...",
  "role_id": "...",
  "invited_by": "..."
}
   ↓
System actions:
   1. Creates membership record
   2. Sends invite email (if checked)
   3. Creates notification for user
   4. Logs to audit trail
   ↓
Toast: "Invite sent to newmember@acme.com"
```

### Managing Member Roles

```
User clicks [⋮] → "Change Role" on a member:
   ↓
Change Role Dialog:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  Change Role for Bob Johnson                                 │
│                                                              │
│  Current Role: 🛡 Admin                                      │
│                                                              │
│  New Role:                                                   │
│  [🛡 Admin                              ▼]                   │
│                                                              │
│  Permission Preview:                                         │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ ✅ Create projects                                      ││
│  │ ✅ Manage agents                                        ││
│  │ ✅ Invite members                                       ││
│  │ ❌ Delete organization                                    ││
│  │ ❌ Manage billing                                         ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  [Cancel]                              [Update Role]         │
└─────────────────────────────────────────────────────────────┘
   ↓
PATCH /api/v1/organizations/:id/members/:member_id
   ↓
System:
   - Updates role_id in membership
   - Logs role change to audit
   - Notifies affected user
   ↓
Toast: "Role updated to Admin"
```

### Removing Members

```
User clicks [⋮] → "Remove Member":
   ↓
Destructive Confirmation:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  ⚠️ Remove Member?                                           │
│                                                              │
│  This will remove Charlie Brown from Acme Inc.              │
│                                                              │
│  Impact:                                                     │
│  • Charlie will lose access to all organization projects     │
│  • Any running sandboxes owned by Charlie will be stopped  │
│  • Charlie's contributions remain in project history        │
│                                                              │
│  [Cancel]                              [Remove Member]       │
└─────────────────────────────────────────────────────────────┘
   ↓
DELETE /api/v1/organizations/:id/members/:member_id
   ↓
System:
   - Soft deletes membership
   - Stops member's active sandboxes
   - Transfers owned projects to organization owner
   - Logs to audit trail
   ↓
Toast: "Member removed from organization"
```

---

## 17.6 Role Management

### System Roles

| Role | Permissions | Use Case |
|------|-------------|----------|
| **Owner** | Full control including billing, deletion, settings | Organization creator |
| **Admin** | Manage members, projects, agents, settings | Team leads |
| **Member** | Create and work on projects, view analytics | Regular team members |
| **Agent** | Execute tasks, no UI access | System agents |

### Custom Roles

```
User navigates to Settings → Roles:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  Custom Roles                                                │
│  Create specialized roles for your organization              │
│                                                              │
│  [+ Create Custom Role]                                      │
│                                                              │
│  Existing Custom Roles (2)                                   │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ 🔬 Researcher                                            ││
│  │ Read-only access + memory search capabilities           ││
│  │ 3 members  •  Created Feb 2026                          ││
│  │ [Edit] [Delete]                                         ││
│  ├─────────────────────────────────────────────────────────┤│
│  │ 🔧 Senior Developer                                      ││
│  │ Member + agent spawning + deployment approval           ││
│  │ 5 members  •  Created Jan 2026                          ││
│  │ [Edit] [Delete]                                         ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### Creating Custom Role

```
Create Role Form:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  Create Custom Role                                          │
│                                                              │
│  Role Name *                                                 │
│  [Senior Developer________________________]                  │
│                                                              │
│  Description                                                 │
│  [Experienced devs who can spawn agents...          ]       │
│                                                              │
│  Inherits From                                               │
│  [Member______________________________▼]                    │
│  Start with Member permissions as base                      │
│                                                              │
│  Permissions:                                               │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Organization                                            ││
│  │ [✓] View organization details                           ││
│  │ [✓] View members                                        ││
│  │ [ ] Manage members                                      ││
│  │ [ ] Manage billing                                        ││
│  ├─────────────────────────────────────────────────────────┤│
│  │ Projects                                                ││
│  │ [✓] Create projects                                     ││
│  │ [✓] Edit own projects                                   ││
│  │ [✓] View all projects                                   ││
│  │ [ ] Delete projects                                     ││
│  ├─────────────────────────────────────────────────────────┤│
│  │ Agents & Sandboxes                                      ││
│  │ [✓] Spawn agents                                        ││
│  │ [✓] View sandboxes                                      ││
│  │ [✓] Send messages to agents                             ││
│  │ [ ] Manage agent pools                                  ││
│  ├─────────────────────────────────────────────────────────┤│
│  │ Approvals                                               ││
│  │ [✓] Approve phase transitions                           ││
│  │ [✓] Approve PR merges                                   ││
│  │ [ ] Override budget limits                              ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  [Cancel]                              [Create Role]         │
└─────────────────────────────────────────────────────────────┘
```

---

## 17.7 Organization Settings

```
/organizations/:id/settings:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  Organization Settings                                       │
│                                                              │
│  General                                                     │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ [Logo]  [Change Logo]                                   ││
│  │                                                         ││
│  │ Organization Name: [Acme Inc________________]          ││
│  │                                                         ││
│  │ Slug: acme-inc (read-only)                              ││
│  │ URL: omoios.dev/o/acme-inc                              ││
│  │                                                         ││
│  │ Description: [Building the future...            ]       ││
│  │                                                         ││
│  │ Billing Email: [billing@acme.com______________]        ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  Resource Limits                                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Max Concurrent Agents: [10________]                    ││
│  │ Max Agent Runtime: [24________] hours                   ││
│  │ Default Project Storage: [50________] GB                  ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  Member Settings                                             │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ [✓] Allow members to invite others                      ││
│  │ [✓] Allow members to create public projects             ││
│  │ [ ] Require approval for new member invites             ││
│  │ [✓] Allow members to spawn agents                       ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│                                        [Save Changes]        │
│                                                              │
│  ⚠️ Danger Zone                                               │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Delete Organization                                     ││
│  │ This will permanently delete Acme Inc and all data.     ││
│  │ This action cannot be undone.                           ││
│  │                                                         ││
│  │ [Delete Organization] — Requires owner confirmation     ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

---

## 17.8 Audit Log

```
User clicks [Audit] tab:
   ↓
┌─────────────────────────────────────────────────────────────┐
│  Audit Log                                                   │
│  Track all actions within your organization                   │
│                                                              │
│  [Search...]  [Filter by type ▼]  [Date range ▼]  [Export]  │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ Time           │ User        │ Action        │ Target  ││
│  │ ────────────────────────────────────────────────────────││
│  │ Today 10:23 AM │ Alice       │ project.create│ API v2  ││
│  │ Today 9:45 AM  │ system      │ task.complete │ #452    ││
│  │ Today 9:30 AM  │ Bob         │ member.invite │ charlie ││
│  │ Yesterday 4PM  │ Charlie     │ sandbox.start │ auth-12 ││
│  │ Yesterday 3PM  │ system      │ invoice.paid  │ $150    ││
│  │ Yesterday 2PM  │ Alice       │ role.update   │ Bob     ││
│  │ Mar 15 11AM    │ system      │ agent.spawn   │ worker-3││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
│  [Load More...]                                              │
└─────────────────────────────────────────────────────────────┘

Audit Event Types:
• organization.create, organization.update, organization.delete
• member.invite, member.join, member.remove, role.update
• project.create, project.update, project.delete
• sandbox.start, sandbox.stop, sandbox.complete
• billing.update, invoice.paid, subscription.change
• settings.update, limit.change
```

---

## 17.9 Organization Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    Organization Lifecycle                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  Create Org       │
                    │  POST /orgs       │
                    │  • Owner assigned │
                    │  • Billing created│
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
       ┌──────────┐  ┌──────────┐  ┌──────────┐
       │ Add      │  │ Create   │  │ Configure│
       │ Members  │  │ Projects │  │ Settings │
       └────┬─────┘  └────┬─────┘  └────┬─────┘
            │             │             │
            ▼             ▼             ▼
       ┌─────────────────────────────────────┐
       │         Daily Operations              │
       │  • Agents execute tasks              │
       │  • Members collaborate               │
       │  • Billing tracked                   │
       │  • Audit log grows                   │
       └──────────────────┬──────────────────┘
                          │
           ┌──────────────┼──────────────┐
           ▼              ▼              ▼
    ┌──────────┐  ┌──────────┐  ┌──────────┐
    │ Upgrade  │  │ Add      │  │ Archive  │
    │ Plan     │  │ More     │  │ (soft    │
    │          │  │ Members  │  │ delete)  │
    └──────────┘  └──────────┘  └──────────┘
```

---

## 17.10 Error States and Edge Cases

### Common Scenarios

```
┌─ Member Already Exists
│   ↓
│   User tries to invite existing member
│   ↓
│   Error: "User is already a member of this organization"
│   ↓
│   Option to update role instead
│
├─ Last Owner Removal
│   ↓
│   Attempt to remove sole owner
│   ↓
│   Error: "Cannot remove the only owner"
│   ↓
│   Must transfer ownership first or delete org
│
├─ Slug Conflict
│   ↓
│   Creating org with taken slug
│   ↓
│   Error: "Organization slug already exists"
│   ↓
│   Suggest alternatives: "acme-inc-2", "acme-inc-dev"
│
├─ Invite Expired
│   ↓
│   User clicks expired invite link
│   ↓
│   Error: "Invite expired (valid for 7 days)"
│   ↓
│   [Request New Invite] button
│
└─ Role Permission Denied
    ↓
    Member tries unauthorized action
    ↓
    Error: "You don't have permission to perform this action"
    ↓
    Shows required role, suggests contacting admin
```

---

## Organization Journey Summary

```
User Types:
    │
    ├── Individual User
    │   ├── Creates personal organization (auto-created)
    │   ├── Single member (owner)
    │   └── Uses for personal projects
    │
    ├── Team Lead
    │   ├── Creates organization for team
    │   ├── Invites members with appropriate roles
    │   ├── Sets up custom roles if needed
    │   ├── Configures resource limits
    │   └── Monitors audit log
    │
    └── Enterprise Admin
        ├── Multiple organizations
        ├── Strict RBAC with custom roles
        ├── Integration with SSO/SAML
        ├── Automated provisioning
        └── Compliance audit requirements

Permission Hierarchy:
    Owner (all permissions)
        ↓
    Admin (manage, no billing/org deletion)
        ↓
    Custom Roles (specialized permissions)
        ↓
    Member (create, edit own)
        ↓
    Agent (execute only)
```

---

## Related Documentation

- [10_additional_flows.md](./10_additional_flows.md) - Organization sub-pages detailed
- [12_billing_subscription.md](./12_billing_subscription.md) - Organization-scoped billing
- [backend/omoi_os/api/routes/organizations.py](../../backend/omoi_os/api/routes/organizations.py) - API routes
- [backend/omoi_os/models/organization.py](../../backend/omoi_os/models/organization.py) - Data models

---

**Next**: See [18_sandbox_troubleshooting.md](./18_sandbox_troubleshooting.md) for debugging sandbox issues.
