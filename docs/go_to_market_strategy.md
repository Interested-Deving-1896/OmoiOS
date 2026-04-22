# OmoiOS Go-to-Market Strategy

**Created**: 2026-04-22
**Status**: Draft
**Owner**: Kevin Hill
**Purpose**: Launch and customer acquisition strategy for OmoiOS

---

## Executive Summary

OmoiOS enters the market as the **only open-source, spec-driven autonomous engineering platform** that runs in the cloud. While competitors like Kiro (AWS), OpenAI Codex, and Claude Code require users to be present at their desks, OmoiOS executes full feature lifecycles overnight—delivering tested PRs while users sleep.

**Core Launch Thesis**: Position OmoiOS not as "another AI coding tool" but as **infrastructure for autonomous engineering execution**—the layer that turns specs into shipped code without human babysitting.

---

## Target Audience Segments

### Primary: Engineering Managers & CTOs (10–100 Engineers)

**Pain Point**: Roadmap moves faster than hiring. Backlog grows while recruiting takes months.

**OmoiOS Value**: Add agent capacity tonight, wake up to shipped work tomorrow. No headcount required.

**Acquisition Channel**: Hacker News, technical blogs, GitHub discovery, word-of-mouth in engineering leadership circles

**Conversion Trigger**: Free tier (10 workflows) → Hit limit → Upgrade to Pro ($50/mo) for 5 concurrent agents

---

### Secondary: Senior IC Engineers

**Pain Point**: Repetitive planning and boilerplate implementation drain energy from high-value architecture work.

**OmoiOS Value**: Offload implementation to agents; focus on system design and review.

**Acquisition Channel**: GitHub trending, developer Twitter, technical podcasts

**Conversion Trigger**: Individual Pro plan for personal projects; advocate for Team plan at work

---

### Tertiary: Solo Developers & Startups (2–5 People)

**Pain Point**: Limited resources, need to move fast without burning budget.

**OmoiOS Value**: Lifetime access ($299 one-time) or BYO keys ($19/mo + their own API costs) for unlimited execution.

**Acquisition Channel**: Product Hunt, Indie Hackers, Hacker News "Show HN" launches

**Conversion Trigger**: Lifetime deal urgency (first 100 founding members)

---

## Competitive Positioning

### The OmoiOS Difference

| Competitor | What They Do | What OmoiOS Does Differently |
|------------|--------------|------------------------------|
| **Kiro** (AWS) | Spec-driven IDE for interactive coding | Cloud autonomous execution—no IDE required, runs overnight |
| **OpenAI Codex** | Cloud coding agent for individual tasks | Full spec-to-PR pipeline with validation and self-healing |
| **Claude Code** | Terminal-based pair programming | Autonomous orchestration—you write the spec, agents execute while you're away |
| **Cursor** | AI-powered code editor | No IDE at all—spec-driven execution in isolated sandboxes |
| **OpenCode** (sst) | Local CLI for AI-assisted coding | Cloud infrastructure with multi-agent orchestration |

### Unique Combination (No Competitor Has All 5)

1. ✅ **Open source** (Apache 2.0)
2. ✅ **Cloud autonomous execution** (runs without you)
3. ✅ **Spec-driven pipeline** (not just prompts)
4. ✅ **Self-hostable** (your infrastructure, your data)
5. ✅ **Multi-model BYOK** (Anthropic, OpenAI, not locked to one vendor)

---

## Launch Strategy

### Phase 1: Developer Community Validation (Months 1–2)

**Goal**: Prove product-market fit with early adopters, gather feedback, iterate

**Tactics**:
- **Hacker News "Show HN" launch** with tight narrative (see `docs/hn-launch-post.md`)
- **GitHub open source** with clear README, quickstart, and architecture docs
- **Free tier** (10 workflows/month) for tire-kicking without commitment
- **Founding Member lifetime deal** ($299) for first 100 users—creates urgency and early revenue

**Success Metrics**:
- 500+ GitHub stars in first month
- 100+ signups with 20% conversion to paid
- 10+ organic HN/Reddit mentions

---

### Phase 2: Scale Early Adopters (Months 3–4)

**Goal**: Convert free users to paid, build case studies, establish pricing credibility

**Tactics**:
- **New Year Deal campaign**: $0.59 first month → $12.99 months 2–3 → normal pricing
- **Case study content**: "How [User] Shipped [Feature] Overnight with OmoiOS"
- **BYO API Keys launch**: Target power users who already pay for LLM APIs
- **Team plan trials**: 14-day free trial for Team tier ($150/mo)

**Success Metrics**:
- 50+ paid subscribers
- $5,000+ MRR
- 3+ published case studies

---

### Phase 3: Enterprise Pipeline (Months 5–6)

**Goal**: Establish enterprise credibility, build sales pipeline for larger deals

**Tactics**:
- **Enterprise landing page**: Self-hosted deployment, SSO, compliance, custom SLAs
- **Outbound to engineering leaders**: LinkedIn/email outreach to CTOs at 50–500 person companies
- **Security/compliance documentation**: SOC 2 preparation, data isolation guarantees
- **Partner integrations**: Daytona, Stripe, GitHub marketplace presence

**Success Metrics**:
- 5+ enterprise conversations
- 1–2 enterprise pilots
- $15,000+ MRR

---

## Channel Strategy

### Organic/Community (Primary)

| Channel | Strategy | Expected Impact |
|---------|----------|-----------------|
| **Hacker News** | "Show HN" launch + ongoing Show HN posts for major releases | Primary acquisition for technical early adopters |
| **GitHub** | Trending discovery, good first issues, clear contribution guide | Credibility and organic discovery |
| **Technical Blog** | Architecture deep-dives, "how we built X" posts | SEO and thought leadership |
| **Twitter/X** | Founder story, build-in-public updates, technical threads | Community building and launch amplification |
| **Reddit** (r/programming, r/webdev, r/SaaS) | Value-add comments, occasional product mentions | Secondary acquisition (requires karma building) |

### Paid/Performance (Secondary)

| Channel | Strategy | Timing |
|---------|----------|--------|
| **Google Ads** | "AI software development", "autonomous coding" keywords | Phase 2+ (after organic validation) |
| **Sponsored Newsletters** | TLDR, Pointer, other dev-focused newsletters | Phase 2+ |
| **Product Hunt** | Featured launch with founder story | Phase 2 (after initial HN traction) |

### Partnerships (Long-term)

| Partner | Opportunity |
|---------|-------------|
| **Daytona** | Co-marketing for sandbox infrastructure |
| **Anthropic** | Claude Agent SDK case study, potential partner credits |
| **GitHub** | Marketplace listing, OAuth app promotion |
| **Stripe** | Partner program for billing infrastructure |

---

## Messaging Framework

### Core Narrative

**Headline**: "Start a feature before bed. Wake up to a PR."

**Subhead**: "OmoiOS is autonomous engineering execution. Describe what you want, approve the plan, and agents deliver tested code overnight."

### Pain-Agitation-Solution

**Pain**: "Your roadmap moves faster than your hiring."

**Agitation**: "Recruiting takes months. Your backlog grows daily. You're stuck choosing between shipping slow or burning out your team."

**Solution**: "OmoiOS lets you add agent capacity tonight and wake up to shipped work tomorrow—no headcount required."

### Feature-Specific Messaging

| Feature | Benefit | Proof Point |
|---------|---------|-------------|
| Spec-driven pipeline | Requirements with machine-checkable acceptance criteria | "By the time agents code, they have a contract to code against" |
| Isolated sandboxes | Your local env is untouched | "Agents work in ephemeral containers with full git access" |
| Self-healing execution | No 3am pages when tests fail | "Agents diagnose, fix, and retry automatically" |
| Full traceability | Review with confidence | "Every change traced back to the original requirement" |
| Parallel orchestration | Scale without merge chaos | "5 agents working simultaneously without stepping on each other" |

---

## Pricing & Packaging Strategy

### Tier Positioning

| Tier | Positioning | Target |
|------|-------------|--------|
| **Free** | "Try it out" | Individual exploration, tire-kickers |
| **Pro ($50/mo)** | "Scale your personal output" | Solo developers, side projects |
| **Team ($150/mo)** | "Ship more with the team you have" | Engineering managers, small teams |
| **BYO ($19/mo)** | "Unlimited workflows, your API cost" | Power users with existing LLM keys |
| **Lifetime ($299)** | "Pay once, use forever" | Early adopters, cost-conscious buyers |
| **Enterprise (custom)** | "Deploy on your infrastructure" | Large orgs with compliance needs |

### Promotional Strategy

- **Founding Member urgency**: First 100 lifetime purchases get early access to BYO keys
- **New Year Deal**: $0.59 first month (teaser pricing) → $12.99 months 2–3 → normal pricing
- **Annual discount**: 2 months free for annual Pro/Team subscriptions

---

## Success Metrics & KPIs

### Acquisition

| Metric | Month 1 | Month 3 | Month 6 |
|--------|---------|---------|---------|
| GitHub Stars | 500 | 2,000 | 5,000 |
| Signups | 200 | 1,000 | 3,000 |
| Free→Paid Conversion | 10% | 15% | 20% |

### Revenue

| Metric | Month 1 | Month 3 | Month 6 |
|--------|---------|---------|---------|
| MRR | $1,000 | $5,000 | $15,000 |
| Paying Customers | 20 | 100 | 300 |
| ARPU | $50 | $50 | $50 |
| Lifetime Deals | 50 | 100 | 100 |

### Engagement

| Metric | Target |
|--------|--------|
| Workflows completed (monthly) | 1,000+ by Month 3 |
| Retention (monthly active) | 60%+ |
| NPS | 40+ |
| Support tickets per user | <0.5 |

---

## Risk Mitigation

### Risk: Solo founder bus factor

**Mitigation**: Open source (Apache 2.0) means community can fork and continue. Clear documentation and tests reduce dependency on founder.

### Risk: "Just a wrapper around Claude"

**Mitigation**: Emphasize orchestration layer—spec pipeline, validation loop, discovery branching, sandbox management. These are substantial engineering investments, not thin wrappers.

### Risk: LLM costs make unit economics unprofitable

**Mitigation**: BYO API Key tier shifts LLM costs to users. Usage-based pricing with margin on top. Free tier limited to 10 workflows to prevent abuse.

### Risk: Competition from well-funded players (Devin, etc.)

**Mitigation**: Differentiate on open source, self-hostability, and multi-model support. Community and transparency as moats against closed black-box solutions.

---

## Timeline & Milestones

| Date | Milestone |
|------|-----------|
| **Month 1** | HN launch, 500 GitHub stars, first 20 paying customers |
| **Month 2** | Founding Member lifetime deal closes (100 sold), BYO keys beta |
| **Month 3** | New Year Deal campaign, Product Hunt launch, first case studies |
| **Month 4** | Team plan traction, $5K MRR, enterprise conversations start |
| **Month 5** | Enterprise pilot program, SOC 2 preparation begins |
| **Month 6** | $15K MRR, 300 paying customers, first enterprise deal |

---

## Related Documents

- Pricing Strategy - Detailed pricing tiers and billing models
- [Marketing Overview](./marketing_overview.md) - Positioning, messaging, and brand strategy
- [HN Launch Post](./hn-launch-post.md) - Specific launch narrative and prepared answers
- [Website Copy](./website-copy.md) - Finalized website copy and conversion flows
- Product Vision - Core value proposition and target audience

---

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2026-04-22 | Initial GTM strategy document | Claude |
