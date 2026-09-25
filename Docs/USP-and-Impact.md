# Paytm Pulse — USP, Impact & Benefits

### The AI workforce for Paytm

> **Give AI a job, not a prompt.**

Companion to the [Proposed Solution](Proposed-Solution.md) ·
[Architecture](Architecture.md) · [Design system](Design.md)

---

## 1. USP — Unique Selling Proposition

**In one line:**

> Pulse is not an assistant that talks about work. It is an AI workforce that
> **owns a mission end-to-end inside a permission boundary it cannot argue with,
> and proves the outcome by reading the ledger back.**

Most AI products for support and sales stop one step short of the outcome —
they answer, summarise or draft, and a human still does the thing. Pulse closes
that last step, and makes closing it *safe enough to trust with money*.

### 1.1 The five differentiators

| # | Differentiator | Why nobody else ships it | Where it lives |
|---|---|---|---|
| **1** | **Missions, not conversations** | Chat is the default UI for AI. Pulse has **no chat box anywhere** — the central object is a mission with an owner, a policy verdict and a measurable outcome. | `backend/app/services/mission_service.py`, the three screens |
| **2** | **Autonomy governed by deterministic code, not a prompt** | "Be careful with refunds" in a system prompt is not a control. Pulse's policy engine is plain Python evaluating **five named rules**. The model cannot see it, reach it, or override it. | `backend/app/policy/risk.py` |
| **3** | **Verified outcomes, not claimed ones** | Assistants say *"I've processed your refund."* Pulse **re-reads the transaction ledger** after execution. No matching row → the mission moves to *needs attention*, not to green. | verification step in the mission loop |
| **4** | **Explainable escalation** | Most agents escalate on an opaque confidence score. Every Pulse stop names the **rule that fired, the evidence, and the exact impact of approving**. | Approval Queue |
| **5** | **Counted metrics, not asserted ones** | Every tile on the Outcomes screen renders the query it was counted from. Before any mission runs the screen reads zero — and autonomy rate reads `—`, not a flattering `0%`. | `backend/app/services/` outcome aggregation |

### 1.2 The structural insight

The bottleneck on agentic AI in a payments org is not capability — it is
**trust**. Nobody hands a language model the ability to move ₹2,000 until three
questions have answers:

1. **What may it do alone?** → a deterministic engine, printed on screen.
2. **How do I know it did it?** → execution and verification are separate steps.
3. **Why did it stop?** → rule + evidence + impact, on the approval card.

Pulse answers these **architecturally**. Each answer is a layer with a hard
boundary, not a paragraph of prompt text:

| Layer | Owns | Never does |
|---|---|---|
| LLM | The narrative — which action fits, how to word it | Authorise itself; set an amount |
| Policy engine | Permission | Guess; call a model |
| n8n | Execution across systems | Decide whether an action is allowed |
| Verification | Truth | Assume success |
| Human | Judgement at the boundary | Operate every step |

The model may write *"refund the debited amount"* — but **the amount comes from
the ledger**, and the payments boundary rejects a refund that doesn't match the
record. The narrative is the model's. The numbers never are.

### 1.3 The demo moment that proves it

Three scenarios, three different verdicts, same agent:

| Scenario | Amount | Sentiment | Outcome |
|---|---|---|---|
| **A** | ₹500 | neutral | **Autonomous** — refunded, verified, customer notified. No human touched it. |
| **B** | ₹2,000 | neutral | **Escalated** on `MONEY_MOVEMENT_THRESHOLD`. |
| **C** | ₹800 | strongly negative | **Escalated** on `NEGATIVE_SENTIMENT_REVIEW`. |

Scenario C is the sharpest: **₹800 is *under* the money threshold** — the same
band that runs autonomously in A. It stops purely on how the customer is
writing, plus two prior unresolved cases in the database. That is *"escalate
only when needed"* made concrete: not a blanket rule about refunds, but
independent conditions any one of which can pull a human in.

### 1.4 Assistant vs. teammate

| | Typical AI assistant | **Paytm Pulse** |
|---|---|---|
| Primary object | Conversation | Mission with an owner and an outcome |
| Decides | Suggests; human executes | Decides, then executes within policy |
| Permission | Prompt says "be careful" | Deterministic engine the model cannot reach |
| Acts | Returns text | Refunds, notifies, updates CRM, books meetings |
| Proof | "I've processed that" | Re-reads the ledger; fails loudly if it didn't |
| Escalation | Confidence threshold | Five named rules, independently configurable |
| Why it stopped | Opaque | Rule + evidence + impact, on screen |
| Metrics | Claimed | Counted from records, with the query shown |
| Failure | Silent or hallucinated | *Needs attention* state, with retry |

### 1.5 Defensible engineering choices

- **Governance is agent-agnostic.** The policy engine, approval queue and outcome
  ledger sit *under* both Resolve and Grow. A third teammate inherits all of it.
- **Zero-key demo.** Every third-party service (Sarvam, Cognee, LLM, n8n) sits
  behind an adapter with a deterministic local fallback, and the header shows
  which mode each is in. The full demo runs with **no API keys**.
- **Honest degradation.** A configured-but-unreachable LLM **pauses the mission**
  rather than silently substituting a different reasoner — because that
  substitution would be a lie.
- **Explicit state machines, no agent framework.** An agent that hits an approval
  boundary *ends its task*; a continuation resumes when a human decides. The
  boundary is a real stop, not a blocked thread.
- **Autonomy is configuration, not code.** Ship at `REFUND_APPROVAL_THRESHOLD=0`
  — everything needs a human — then raise it as the escalation-precision metric
  earns it.

---

## 2. Impact & Benefits

### 2.1 What the prototype measurably produces

Running Scenario A, then Scenario B with an approval, then the Grow mission —
every figure counted from records, none hardcoded:

```
RESOLVE
Processed              2     missions in a terminal state
Resolved autonomously  1     missions with result resolved_autonomously
Escalated              1     missions that created an approval request
Human approvals        1     approval records marked approved
Failed                 0     missions in a failed state
Autonomy rate         50%    1 autonomous of 2 processed

GROW
Merchants evaluated   12     lead records scored by Grow
Qualified              4     leads at stage qualified or beyond
Contacted              3     leads that received outreach
Sales-ready            1     leads qualified from a reply
Meetings booked        1     leads with a booked meeting
```

The Grow figures fall out of the formula in `backend/app/agents/scoring.py`, not a constant
— change a merchant's estimated volume and they change.

**A deliberate non-claim:** we do not assert deflection percentages or
conversion lift. A prototype on a seeded dataset cannot honestly produce those.
What it ships is **the instrumentation that would measure exactly that on real
traffic** — which is the more valuable artifact.

### 2.2 Impact per stakeholder

**For the customer**

| Benefit | Mechanism |
|---|---|
| Resolution in seconds, not days | Low-risk disputes resolve autonomously end-to-end |
| Answered in their own language | Sarvam handles language ID, translation and intent — the Hindi case is notified back in Hindi |
| No repeating themselves | Context memory and support history load before the decision |
| Never told a refund happened when it didn't | Ledger read-back gates mission completion |

**For the support / ops team**

| Benefit | Mechanism |
|---|---|
| Humans see only the decisions that need judgement | Five-rule escalation boundary |
| Every stop arrives pre-briefed | Rule + evidence + impact on the approval card — decide in seconds, not after an investigation |
| "No" is a real path, not a dead end | Reject routes to a human specialist, notifies the customer, and closes as `rejected_by_human` |
| Full manual control preserved | **Take over** stops the agent immediately |
| Repetitive settlement triage disappears | The high-volume, low-variance work is what runs autonomously |

**For the sales / merchant-acquisition team**

| Benefit | Mechanism |
|---|---|
| Territory sweep without manual research | 14 matched → 2 skipped as already onboarded → 12 scored |
| Ranking a salesperson will actually trust | Every point traceable — e.g. Mumbai Brew House **91/100**, broken into volume 26/35, category 20/20, digital presence 20/20, territory 15/15, availability 10/10 |
| Outreach through to a booked meeting | Personalised draft → send → reply qualification → meeting booked |
| Reps start at the conversation, not the list | The pipeline arrives pre-qualified |

**For the business and its risk owners**

| Benefit | Mechanism |
|---|---|
| Autonomy dialled by evidence, not intuition | Escalation precision (approved ÷ raised) shows whether humans are a rubber stamp |
| A model can never move unauthorised money | Amounts come from the ledger; the boundary rejects mismatches; an unrecognised action type is treated as unauthorised and routed to a human |
| Browsers can't move money | Mutating `/paytm/*` endpoints require an internal service key only the execution layer holds |
| Approval integrity | A decided approval can't be re-decided; an approval can't be applied to a mission that moved on |
| No secret reaches the client | The only `NEXT_PUBLIC_*` value is the API URL |
| Auditable by construction | Every mission emits a durable, typed event stream |

### 2.3 What the instrumentation unlocks in production

Because every mission emits typed events, these become computable with **no new
plumbing**:

| Metric | Derived from |
|---|---|
| Autonomy rate | Missions resolved without a human ÷ missions processed |
| **Escalation precision** | Approvals approved ÷ approvals raised |
| Time to resolution | `MISSION_CREATED` → `MISSION_COMPLETED` |
| Human minutes per mission | Time spent in `waiting_approval` |
| Verification failure rate | `ACTION_EXECUTED` without a matching `ACTION_VERIFIED` |
| Policy rule frequency | Which of the five rules fires most — where to tune the envelope |
| Lead conversion | `LEAD_CONTACTED` → `LEAD_QUALIFIED` → `MEETING_BOOKED` |

Escalation precision is the operationally interesting one: approvals approved
98% of the time means the threshold is too low and humans are being used as a
rubber stamp. Pulse gives you the data to move that threshold **deliberately**.

### 2.4 Cost of adoption — low by design

| Step | Effort |
|---|---|
| Replace `MockPaytmAdapter` with production | Interface exists — **no agent code changes** |
| Point `DATABASE_URL` at PostgreSQL | One environment variable |
| Move thresholds to a governed config service | The engine already reads from settings |
| Add authentication and reviewer identity | Approvals already record `reviewed_by` |
| Harden n8n credentials, per-workflow scoping | Workflows already authenticate to the boundary |
| Add per-agent rate limits and spend caps | A new rule in the same policy engine |

### 2.5 Verifiable, not asserted

Every claim above is checkable:

```bash
cd backend && .venv/Scripts/python scripts/smoke_test.py
```

62 checks drive the **public API only** through reset → autonomous resolution →
escalation → approve → sentiment escalation → reject → Grow → takeover →
outcomes → reset — asserting that the ledger is untouched before approval, that
a refund without the service key is refused, that a double approval is
rejected, and that a rejected action never executes.

---

## 3. Boundaries on these claims

Stated plainly, because it is part of the proposition:

- This prototype uses a **simulated Paytm integration boundary** and has **no
  access to Paytm production systems**.
- All customers, merchants, transactions, policies and support cases are
  **fictional demo data**; the dataset makes no claim about which real
  businesses accept Paytm. Lead scores come from seeded attributes, not real
  acquisition signals.
- The ₹1,000 approval threshold is a **configurable hackathon demo policy**
  (`REFUND_APPROVAL_THRESHOLD`), not a statement about Paytm's production policy.
- Sentiment classification **routes workflows**; it is not a psychological
  assessment, and a calm customer with a serious problem won't trigger it.
- Scoring and classification are tuned to demo data. Without Sarvam, fallback
  classifiers are keyword-based — accurate on the demo messages, not
  production-grade.

The distinction that matters: this is **real workflow execution against
simulated external systems**, not a mock-up. Click a button and something
genuinely happens behind it — including when it fails.

---

## 4. In one line

Most AI products give a support or sales team another thing to talk to.

Pulse gives them **two teammates with a job, a permission boundary, tools, and
an outcome they can be held to.**

> **We don't give AI another chat box. We give it a job.**
