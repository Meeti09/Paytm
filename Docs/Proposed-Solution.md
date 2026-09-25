# Paytm Pulse — Proposed Solution

### The AI workforce for Paytm

> **Give AI a job, not a prompt.**

---

## 1. The problem

> **Build AI teammates that don't just respond; they get the job done.**
>
> Design an AI teammate that can go beyond answering questions and deliver
> measurable outcomes in sales or customer service. The AI should understand
> context, make decisions, take actions, and work alongside human teams.
>
> *How might we build an AI teammate that can independently handle a
> customer-service or sales workflow end-to-end — resolving issues, taking
> actions across systems, and escalating to humans only when needed?*

The hard part of that sentence is not "AI". It is **"end-to-end"**, **"taking
actions across systems"**, and **"only when needed"**.

---

## 2. Why assistants don't close this gap

Almost every "AI agent" built for support or sales today stops one step short of
the outcome:

| What it does | What is still left for a human |
|---|---|
| Answers the customer's question | Someone still issues the refund |
| Summarises the ticket | Someone still decides what to do |
| Drafts the outreach email | Someone still sends it and logs the CRM entry |
| Says "I've processed your refund" | Nobody checked whether it actually happened |

The last row is the dangerous one. An assistant that *claims* an action is an
assistant that can be confidently wrong about money.

And the reason teams stop short is rarely capability — it is **trust**. You
cannot hand a language model the ability to move ₹2,000 unless you can answer
three questions first:

1. **What is it allowed to do on its own?**
2. **How do I know it actually did it?**
3. **When it stops and asks me, why did it stop?**

A teammate is not a smarter assistant. A teammate is an assistant **plus an
answer to those three questions**.

---

## 3. The solution

**Paytm Pulse** is a mission-based AI workforce with two specialised teammates.

| Teammate | Job |
|---|---|
| **Resolve** | Own a customer issue until it is **verified** as resolved. |
| **Grow** | Find, qualify and move high-potential merchants toward onboarding. |

The product's central object is a **Mission**, not a conversation. There is no
chat box anywhere in the interface. A mission is:

```
objective · agent · context · decision · policy verdict
actions · approvals · events · verified outcome
```

Everything a human sees is a window onto a mission that is genuinely executing.

### The three answers

Pulse answers the three trust questions structurally, not with a prompt:

**1. What is it allowed to do on its own?**
A deterministic policy engine — plain Python, no model call — evaluates every
proposed action against five named rules. The policy is printed on screen above
the approval queue. The model cannot see it, argue with it, or override it.

**2. How do I know it actually did it?**
Execution and verification are separate steps. After a refund executes, the
system **re-reads the transaction ledger**. If the ledger does not say
`refunded`, the mission does not complete — it moves to *needs attention*. The
UI never shows a green tick that isn't backed by a database row.

**3. When it stops and asks me, why did it stop?**
Every approval card names the policy rule that fired, the evidence behind the
decision, and exactly what will happen if you approve.

---

## 4. How a mission works

```
        Objective
            ▼
   Understand context        Sarvam → language, intent, sentiment
            ▼                Cognee → memory
       Load evidence         Ledger → customer, transaction, merchant, policy
            ▼
    Make a decision          LLM writes the rationale and the message
            ▼
      Check policy           Deterministic engine decides permission
            ▼
   ┌────────┴────────┐
 SAFE              RISKY
   │                 │
   ▼                 ▼
Execute        Ask a human ──► approve / reject / take over
   │                 │
   └────────┬────────┘
            ▼
         Verify              Read the ledger back
            ▼
    Measurable outcome       Counted, not claimed
```

**The separation that makes it safe:**

| Layer | Owns | Never does |
|---|---|---|
| LLM | The narrative — which action fits the evidence, how to word it | Authorise itself, set an amount |
| Policy engine | Permission | Guess, or call a model |
| n8n | Execution across systems | Decide whether an action is allowed |
| Verification | Truth | Assume success |
| Human | Judgement at the boundary | Operate every step |

Concretely: the model may write *"refund the debited amount"* — but the **amount
comes from the transaction ledger**, and the payments boundary rejects any
refund whose amount doesn't match the record. The narrative is the model's. The
numbers never are.

---

## 5. Resolve — customer resolution

### The walkthrough

A customer writes, in Hindi:

> "₹2,000 कट गया लेकिन merchant को नहीं मिला."

Resolve runs, and every line below is a real event written to the database:

```
✓ Mission accepted by Resolve
✓ Language detected: Hindi (Devanagari)
✓ Intent: Amount debited but not received by merchant · sentiment neutral
✓ Customer identified: Aarav Shah (CUST-001)
✓ Transaction TX-1004 found — ₹2,000 UPI, status debited not settled
⚠ Merchant Demo Cafe — settlement failed
✓ Context memory: 3 items
✓ Policy POL-REFUND-01 retrieved — Debited but not settled to merchant
✓ Support case CASE-003 opened
✓ Decision: Refund ₹2,000
✓ Action proposed: Refund ₹2,000
⚠ Policy check: MONEY_MOVEMENT_THRESHOLD — approval required
⚠ Human approval requested — ₹2,000 exceeds the ₹1,000 limit
```

Note what the agent was *not* given: the transaction. It discovered TX-1004 from
the customer and the amount in the message — the way it would from a real
inbound message.

A human approves. The mission resumes:

```
✓ Ops Lead approved: Refund ₹2,000
✓ Refund ₹2,000 executed via WF3
✓ Refund verified — TX-1004 is now 'refunded' in the ledger
✓ Customer notified on sms (Hindi)
✓ Mission complete — Resolved after human approval by Ops Lead
```

### Escalating *only when needed*

Three scenarios, three different policy outcomes — this is the heart of the
submission:

| Scenario | Amount | Sentiment | Outcome |
|---|---|---|---|
| **A** | ₹500 | neutral | **Autonomous.** Under the limit. Refunded, verified, customer notified. No human touched it. |
| **B** | ₹2,000 | neutral | **Escalated** on `MONEY_MOVEMENT_THRESHOLD`. |
| **C** | ₹800 | strongly negative | **Escalated** on `NEGATIVE_SENTIMENT_REVIEW`. |

Scenario C is the one worth pausing on. **₹800 is *under* the money threshold.**
The same amount in Scenario A runs autonomously. C stops purely because the
customer is writing in a way the system classifies as strongly negative — and
because the database confirms two prior unresolved cases from the same customer.

That is "escalate only when needed" made concrete: the boundary is not a blanket
rule about refunds, it is a set of independent conditions, any one of which can
pull a human in.

---

## 6. Grow — merchant acquisition

The same architecture, a sales workflow.

**Objective:** *"Find 5 high-potential merchants in Thane."*

```
14 merchants match the territory
 2 already accept Paytm — skipped
12 evaluated and scored
 4 qualified (score ≥ 75)
 3 ready for outreach (score ≥ 80 with a reachable contact)
```

Grow drafts personalised outreach, sends it on a simulated channel, and parks at
`WAITING_RESPONSE`. A merchant replies *"Interested. What do I need to do?"* —
Grow qualifies the reply, moves the lead to sales-ready, and books an onboarding
meeting.

### Explainable scoring

A sales teammate that can't justify its ranking is a black box a sales team will
ignore. Every point is traceable:

```
Mumbai Brew House

Transaction potential  26/35   ₹660,000 estimated monthly volume
Category fit           20/20   Cafe — digital-payment affinity
Digital presence       20/20   Website and direct contact available
Territory match        15/15   Thane West matches the mission territory
Availability           10/10   Not onboarded in the demo dataset
                       ─────
Lead score             91/100  High opportunity
```

The same policy engine governs Grow. Outreach and meeting booking move no money
and change no account, so they return `AUTONOMOUS · WITHIN_AUTONOMY` — which the
decision card shows. The governance layer is not bolted onto one agent; it sits
under both.

---

## 7. Working alongside human teams

Three controls, available wherever they are valid:

| Control | What it means |
|---|---|
| **Approve** | Proceed. The action executes, then verifies. |
| **Reject** | Don't. The mission takes the **alternative path** — reassign the case to a human specialist and tell the customer someone will follow up. It still closes with a recorded outcome. |
| **Take over** | The agent stops immediately. A human owns the mission from here. |

Rejection deserves emphasis. A rejected action in most agent demos is a dead end
— the mission just stops. Here it routes to the fallback that a real operations
team would want, and the outcome is recorded as `rejected_by_human` so the
metrics stay honest.

**Guardrails on the human side too.** An approval that has already been decided
cannot be decided again. An approval cannot be applied to a mission that has
moved on. And a browser cannot execute a refund directly even though the
endpoint exists — the money-moving endpoints require an internal service key
that only the execution layer holds.

---

## 8. What makes this a teammate, not a chatbot

| | Typical AI assistant | Paytm Pulse |
|---|---|---|
| **Primary object** | Conversation | Mission with an owner and an outcome |
| **Decides** | Suggests, human executes | Decides, then executes within policy |
| **Permission** | Prompt says "be careful" | Deterministic engine the model cannot reach |
| **Acts** | Returns text | Refunds, notifies, updates CRM, books meetings |
| **Proof** | "I've processed that" | Re-reads the ledger; fails loudly if it didn't |
| **Escalation** | Confidence threshold | Five named rules, each independently configurable |
| **Why it stopped** | Opaque | Rule + evidence + impact, on screen |
| **Metrics** | Claimed | Counted from records, with the query shown |
| **Failure** | Silent or hallucinated | Mission moves to *needs attention* with retry |

---

## 9. Measurable outcomes

The brief asks for **measurable** outcomes, so the honest thing to report is
what the system actually measures — and where those numbers come from.

### What the demo produces

Running Scenario A, then Scenario B with an approval, then the Grow mission:

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

Every tile renders the second column on screen — the records it was counted
from. Nothing is hardcoded. Before any mission runs, the screen reads zero, and
autonomy rate reads `—` rather than a misleading `0%`.

**We are deliberately not claiming business impact figures.** A prototype on a
seeded dataset cannot honestly tell you it deflects a percentage of contacts or
lifts conversion. What it *can* do is ship the instrumentation that would
measure exactly that on real traffic.

### What this instrumentation gives you in production

Because every mission emits a durable, typed event stream, these become
computable without new plumbing:

| Metric | Derived from |
|---|---|
| **Autonomy rate** | Missions resolved without a human ÷ missions processed |
| **Escalation precision** | Approvals *approved* ÷ approvals raised — is the policy escalating too much? |
| **Time to resolution** | `MISSION_CREATED` → `MISSION_COMPLETED` |
| **Human minutes per mission** | Time a mission spent in `waiting_approval` |
| **Verification failure rate** | `ACTION_EXECUTED` without a matching `ACTION_VERIFIED` |
| **Policy rule frequency** | Which of the five rules fires most — where to tune the envelope |
| **Lead conversion** | `LEAD_CONTACTED` → `LEAD_QUALIFIED` → `MEETING_BOOKED` |

The escalation-precision metric is the interesting one operationally: if
approvals are approved 98% of the time, the threshold is too low and humans are
being used as a rubber stamp. Pulse gives you the data to move that threshold
deliberately rather than by intuition.

---

## 10. Mapping to the problem statement

| The brief asks for | How Pulse delivers it |
|---|---|
| **Understand context** | Sarvam resolves language, intent and sentiment from a real Hindi/English message; the agent loads customer, transaction, merchant, settlement status, support history and the applicable policy before deciding — and discovers the disputed transaction itself. |
| **Make decisions** | The LLM proposes an action from a fixed catalogue with evidence; a deterministic engine rules on permission. Both are shown on the decision card. |
| **Take actions across systems** | n8n workflows execute refunds, notifications, case updates, CRM outreach and meeting booking against the payments boundary — then the result is verified against the ledger. |
| **Work alongside human teams** | Approve / reject / take over, with the reason for every stop stated, and an alternative path when a human says no. |
| **End-to-end** | Intake → context → decision → policy → execution → verification → customer notification → recorded outcome. No manual step in the middle. |
| **Escalate only when needed** | Five independent rules. ₹500 runs alone; ₹2,000 stops on amount; ₹800 stops on sentiment. |
| **Measurable outcomes** | Every figure counted from records, with its source shown on screen. |

---

## 11. System design

```
        Next.js — Live Mission · Approvals · Outcomes
                        │  REST + Server-Sent Events
                        ▼
                     FastAPI
         ┌──────────────┼──────────────┐
         ▼              ▼              ▼
     Resolve          Grow      Policy engine
      agent           agent     (deterministic)
         └──────┬───────┘              │
                ▼                      │
     Sarvam · Cognee · LLM             │
                                       ▼
                              n8n  (WF1–WF6)
                                       ▼
                        Simulated Paytm boundary
                                       ▼
                    verified outcome → event → metrics
```

Agents are **explicit state machines**, not open-ended loops — no agent
framework. An agent that hits an approval boundary *ends its task*; a
continuation task resumes when a human decides. The boundary is a real stop, not
a blocked thread.

Every third-party service sits behind an adapter with a deterministic local
fallback, so the complete demo runs with **zero API keys** and the UI shows
which mode each integration is in.

Full detail: [`Architecture.md`](Architecture.md). Visual system:
[`Design.md`](Design.md).

---

## 12. Technology

| Layer | Choice |
|---|---|
| Frontend | Next.js 16 · React 19 · TypeScript 5 · Tailwind CSS 4 · lucide-react |
| Backend | Python 3.14 · FastAPI · SQLAlchemy 2 · Pydantic 2 · httpx |
| Database | SQLite by default (zero setup); PostgreSQL by changing one env var |
| Execution | n8n — six workflows, importable, with an in-process fallback runner |
| Language | Sarvam — language ID, translation, intent and sentiment |
| Memory | Cognee — graph recall, falling back to database-derived context |
| Reasoning | Provider-agnostic: Anthropic, OpenAI, OpenAI-compatible or Sarvam |
| Live UI | Server-Sent Events — one connection, six channels |

---

## 13. What is real and what is simulated

Stating this plainly is part of the submission, not a footnote.

**Real — genuinely executing:**

- The mission state machines, from intake to verified outcome
- The policy engine and every escalation decision
- The agent tool permission model
- Execution through the workflow layer, and the verification read-back
- The event stream, and every metric computed from it
- The approval lifecycle and its server-side validation
- The security boundary on money-moving endpoints

**Simulated — clearly labelled in the product:**

- The Paytm integration boundary. There is **no production Paytm access.**
- All customers, merchants, transactions, policies and support cases are
  **fictional demo data**. The dataset makes no claim about which real
  businesses accept Paytm.
- Notification delivery, CRM outreach and meeting booking
- Lead scores are computed from seeded demo attributes, not real acquisition
  signals

The ₹1,000 threshold is a **configurable demo policy**, not Paytm's production
policy. Sentiment classification routes workflows; it is not a psychological
assessment.

The distinction we care about: this is **real workflow execution against
simulated external systems** — not a mock-up. Click a button and something
genuinely happens behind it, including when it fails.

---

## 14. Path to production

The prototype was built so this list is short and mostly boring:

| Step | Effort |
|---|---|
| Replace `MockPaytmAdapter` with a production implementation | The interface already exists; **no agent code changes** |
| Point `DATABASE_URL` at PostgreSQL | One environment variable |
| Move policy thresholds to a governed config service | The engine already reads them from settings |
| Add authentication and reviewer identity | Approvals already record `reviewed_by` |
| Harden n8n credentials and per-workflow scoping | Workflows already authenticate to the boundary |
| Add per-agent rate limits and spend caps | New rule in the same policy engine |

The architecture's most valuable property for production is that the autonomy
envelope is a **configuration decision, not a code change**. Launch with
`REFUND_APPROVAL_THRESHOLD=0` — every action needs a human. Watch the
escalation-precision metric. Raise the threshold as the evidence justifies it.
That is how you'd actually earn trust in a payments org.

---

## 15. Limitations

Stated honestly:

- **Seeded dataset.** Scoring and classification are tuned to demo data; real
  merchant and message distributions would need retuning.
- **Two agents, narrow scope.** Resolve handles settlement disputes; Grow
  handles greenfield acquisition. Neither covers its full real domain.
- **Fallback classifiers are keyword-based.** Without Sarvam, language and
  sentiment detection is deterministic and shallow — accurate on the demo
  messages, not production-grade.
- **Single-process orchestration.** Missions run as asyncio tasks in the API
  process. Horizontal scale would need a durable queue; the mission model is
  already designed for it, since state lives entirely in the database.
- **No authentication.** Every operator is "Ops Lead". Deliberately out of scope.
- **Sentiment is a blunt instrument.** A calm customer with a serious problem
  won't trigger the sentiment rule. That rule is a safety net, not a substitute
  for the others.

---

## 16. Roadmap

**Near term** — a third teammate (Verify, for merchant risk and KYC exceptions);
policy simulation ("what would have escalated last week at a ₹2,500 threshold?");
approval batching for high-volume, low-variance decisions.

**Medium term** — learned escalation thresholds fed by escalation-precision data,
still expressed as deterministic rules a human can read; voice intake through
Sarvam; agent handoff, where Resolve passes a churn-risk merchant to Grow.

**The thesis we'd extend:** more teammates, same governance layer. The policy
engine, approval queue and outcome ledger are agent-agnostic by design.

---

## 17. Try it

```bash
# Backend
cd backend && python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python -m uvicorn app.main:app --port 8000

# Frontend
cd frontend && npm install && npm run dev
```

No API keys required. Open <http://localhost:3000>, press **Reset demo**, run
Scenario B, approve it in the queue, then run the Grow mission.

To verify the claims in this document rather than take them on trust:

```bash
cd backend && .venv/Scripts/python scripts/smoke_test.py
```

62 checks drive the public API through the full sequence — including that the
ledger is **untouched** before approval, that a refund without the service key
is refused, that a double approval is rejected, and that a rejected action never
executes.

---

## 18. In one line

Most AI products give a customer-service or sales team another thing to talk to.

Pulse gives them **two teammates with a job, a permission boundary, tools, and
an outcome they can be held to.**

> **We don't give AI another chat box. We give it a job.**

```
Sarvam   → Understand India
Cognee   → Remember context
LLM      → Decide
Policy   → Govern autonomy
n8n      → Act
Human    → Approve / Take over
Pulse    → Own the outcome
```
