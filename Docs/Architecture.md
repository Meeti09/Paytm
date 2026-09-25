# Paytm Pulse — Architecture

> **As-built architecture for the hackathon MVP**
>
> **Product:** Paytm Pulse — the AI workforce for Paytm
> **Teammates:** Resolve (customer resolution) + Grow (merchant acquisition)
> **Primary principle:** **Give AI a job, not a prompt.**
>
> This document describes the system **as implemented**, not as originally
> proposed. Where the build deviated from the initial design, the deviation and
> its reason are recorded in [§39](#39-deviations-from-the-original-design).

---

## 1. Executive Summary

Paytm Pulse is a mission-based AI workforce prototype. Instead of a chatbot, it
gives two specialised teammates ownership of concrete business outcomes.

### Resolve — Customer Resolution Teammate

Owns a customer issue from intake to verified resolution.

Example input:

> "₹2,000 कट गया लेकिन merchant को नहीं मिला."

Resolve runs: understand the message → identify the customer → discover the
disputed transaction → check merchant settlement → retrieve support history and
memory → retrieve the applicable policy → generate a decision → submit it to the
policy engine → execute autonomously **or** request human approval → execute
through the workflow layer → verify against the ledger → notify the customer →
close the mission and record the outcome.

### Grow — Merchant Acquisition Teammate

Owns a merchant-acquisition mission.

Example input:

> "Find 5 high-potential merchants in Thane."

Grow runs: search the demo dataset → filter out merchants already on Paytm →
enrich → score with an explainable formula → rank → submit outreach to the
policy engine → send on a simulated channel → wait for a reply → qualify it →
book an onboarding meeting → record the outcome.

### Human Governance

- Agents act autonomously inside a declared policy envelope.
- Actions that cross a policy boundary stop and enter the Approval Queue.
- A human can **approve**, **reject**, or **take over**.
- Rejection is not a dead end: the mission takes the alternative path (assign a
  specialist, notify the customer) and still closes with a recorded outcome.
- Every meaningful transition is an auditable event.

---

## 2. Technology Stack

Verified versions from the working build.

### 2.1 Frontend

| Component | Version | Role |
|---|---|---|
| **Next.js** | 16.3.6 (App Router, Turbopack) | Three-screen application shell |
| **React** | 19.2.8 | UI runtime |
| **TypeScript** | 5.x | Types across API client, domain models, components |
| **Tailwind CSS** | 4.x (`@tailwindcss/postcss`) | Design tokens via `@theme inline` |
| **lucide-react** | 1.48.0 | The single icon set — no emoji as functional icons |
| **ESLint** | 9.x + `eslint-config-next` | Lint gate (clean, including React Compiler rules) |
| **Node.js** | 24.20.0 | Build/runtime |

The frontend holds **no secrets** and makes **no third-party calls**. The only
`NEXT_PUBLIC_*` value in the project is `NEXT_PUBLIC_API_URL`.

### 2.2 Backend

| Component | Version | Role |
|---|---|---|
| **Python** | 3.14.5 | Runtime |
| **FastAPI** | 0.141.1 | HTTP API, dependency injection, OpenAPI |
| **Starlette** | 1.7.0 | ASGI core, `StreamingResponse` for SSE |
| **Uvicorn** | 0.54.0 | ASGI server |
| **SQLAlchemy** | 2.1.0 (`DeclarativeBase`, typed `Mapped[...]`) | ORM |
| **Pydantic** | 2.13.5 | Request/response validation |
| **pydantic-settings** | 2.15.0 | Environment configuration |
| **httpx** | 0.28.1 | Async client for every outbound integration |
| **python-dotenv** | 1.2.3 | `.env` loading |

No agent framework is used. The agents are explicit state machines in plain
Python — see [§12](#12-agent-architecture).

### 2.3 Database

**SQLite by default**, PostgreSQL-ready.

`DATABASE_URL` blank → `backend/pulse.db`, created and seeded on first boot,
with `journal_mode=WAL` and `busy_timeout=5000` so agent tasks and API requests
do not block each other. Set `DATABASE_URL` to a PostgreSQL URL and the same
SQLAlchemy models and code paths are used unchanged; `postgres://` is
normalised to `postgresql://` automatically.

SQLite was chosen for the MVP because it makes the demo runnable with zero
setup, which matters more for a hackathon than the durability Postgres adds.

### 2.4 Integrations

Each is isolated behind an adapter and each has a deterministic local fallback,
so the complete demo runs with **no API keys at all**.

| Integration | Adapter | Configured | Fallback |
|---|---|---|---|
| **LLM** | `LLMAdapter` | `anthropic` / `openai` / `openai_compatible` / `sarvam` | Deterministic rule-based reasoner |
| **Sarvam** | `SarvamAdapter` | `/text-lid`, `/translate`, `/v1/chat/completions` | Local language + intent + sentiment classifier |
| **Cognee** | `CogneeAdapter` | `/search`, `/add` | Context derived from the application database |
| **n8n** | `N8nAdapter` | Webhooks for WF1–WF6 | `LocalWorkflowRunner` — same steps, same contract, in-process |
| **Paytm** | `PaytmAdapter` | *(not available)* | `MockPaytmAdapter` — simulated boundary |

`GET /api/demo/status` reports the live/fallback mode of each without ever
exposing a key; the UI header renders it as `Understand · Remember · Decide ·
Act · Paytm` chips.

---

## 3. Architecture Principles

### 3.1 Mission over conversation

The primary object is a **Mission**, not a chat session. There is no chat box
anywhere in the product. A mission carries:

```
id · agent · objective · status · stage · progress
inputs · context · decision · summary
actions · approvals · events · result
```

### 3.2 The model reasons; the policy engine authorises; n8n executes

```
Agent
  │  proposes an ActionProposal
  ▼
Policy / Risk Engine      ← deterministic Python, no model call
  │
  ├── REQUIRES_APPROVAL ──► Approval Queue ──► human decision
  │                                              │
  └── AUTONOMOUS ─────────────────────────────┬──┘
                                              ▼
                                       n8n / LocalWorkflowRunner
                                              ▼
                                   Simulated Paytm boundary
                                              ▼
                                   Verification (ledger read-back)
```

Three separations are enforced in code:

1. **Reasoning vs authorisation** — the model proposes; `evaluate_action()`
   decides. `BaseAgent.propose()` recomputes the `authorized` flag from the
   agent's declared permissions, so an agent cannot mark its own action as
   authorised.
2. **Narrative vs numbers** — the model writes the rationale and the customer
   message. The refund amount is always read from the transaction ledger, and
   `MockPaytmAdapter.execute_refund()` rejects any amount that does not match
   the record (`AMOUNT_MISMATCH`).
3. **Decision vs execution** — no agent calls an external system directly.

### 3.3 Real demo state, not fake KPIs

Every figure on the Outcomes screen is counted from mission, approval, action
and lead records, and each metric carries a `basis` string naming the records it
came from. Autonomy rate is `None` (rendered `—`) when nothing has been
processed — never a misleading `0%`.

### 3.4 Explicit autonomy boundaries

The policy is visible on the Approval Queue at all times, so a judge can see
*why* an action was escalated without asking. The ₹1,000 threshold is a
**hackathon demo policy**, configurable via `REFUND_APPROVAL_THRESHOLD`, and is
not a claim about Paytm's production policy.

### 3.5 Degrade loudly, never fake success

An unavailable integration falls back to a **labelled** local path. A failed
execution moves the mission to `needs_attention` with the error visible and a
Retry available. The one deliberate exception: an LLM that is *configured but
unreachable* pauses the mission rather than silently substituting a different
reasoner, because that substitution would be invisible to the operator.

---

## 4. Scope

### 4.1 Built

Resolve teammate · Grow teammate · mission-based execution · three screens ·
human approval workflow with approve/reject/take-over · deterministic risk
policy · agent tool permission model · live SSE activity timeline · outcome
aggregation from records · Sarvam adapter · Cognee adapter · LLM adapter ·
n8n adapter with six workflows and a local runner · simulated Paytm boundary
with an authenticated mutation surface · seeded demo dataset · repeatable demo
reset · 62-check end-to-end acceptance test.

### 4.2 Explicitly out of scope

Real Paytm production APIs · real payment processing · real autonomous
financial transfers · detecting Paytm adoption from public internet data ·
WhatsApp bot · mobile app · multi-tenant SaaS · authentication/user accounts ·
ten or more agents · trained ML models · production payment infrastructure.

---

## 5. Three-Screen Product Architecture

```
┌──────────────────────────────────────────┐
│               PAYTM PULSE                │
├──────────────────────────────────────────┤
│  1. LIVE MISSION      /                  │
│  2. APPROVAL QUEUE    /approvals         │
│  3. OUTCOMES          /outcomes          │
└──────────────────────────────────────────┘
```

Implemented as three Next.js App Router routes sharing one layout. The header
carries the wordmark, the three nav links (Approvals shows a live pending-count
badge), the integration chips, a stream-status indicator and **Reset demo**.

There is no Command Center, Memory page, Customers page, Merchants page,
Analytics page, Settings page or per-agent dashboard.

---

## 6. Screen 1 — Live Mission

### 6.1 Agent selector

Two identity cards select the active teammate:

```
RESOLVE                          GROW
Customer Resolution Teammate     Merchant Acquisition Teammate
Own every customer issue until   Find and convert the next
it is verified as resolved.      generation of Paytm merchants.
```

### 6.2 Mission launcher

**Resolve** — three deterministic scenario cards, each showing the verbatim
customer message, its language and the expected policy outcome. A "Send a custom
customer message" control accepts any seeded customer plus free text.

**Grow** — a territory field, a target count and a single action button.

A history dropdown and recent-mission chips switch between past missions.

### 6.3 Mission header

```
RESOLVE   MISSION R-0001   TX-1004   ⚠ APPROVAL REQUIRED   [Open approval] [Take over]

Resolve customer payment issue
"₹2,000 कट गया लेकिन merchant को नहीं मिला."

WAITING APPROVAL                                                        80%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━░░░░░░░░░░░░░
```

Mission identifiers are `R-000N` / `G-000N`. When a Resolve mission has found
its transaction, the transaction reference is shown beside the mission id
(see [§39.1](#391-mission-identifiers)).

Controls are only rendered when valid for the current status: **Open approval**
(waiting_approval), **Pause** (running), **Resume** (paused), **Retry**
(paused / needs_attention / failed), **Take over** (any non-terminal state).

### 6.4 Context panel

Rendered from `mission.context.panels`, which the backend builds — the frontend
does not know the difference between a Resolve and a Grow panel.

Resolve panels: **Customer**, **Transaction**, **Merchant**, **Case**,
**Memory**. Grow panels: **Objective**, **Pipeline**, **Top merchant**.

A `tone` field per row drives amber for non-settled states. The panel header
shows whether memory came from Cognee or local context.

### 6.5 Decision card

```
AI DECISION                                   ! HIGH RISK   ⚠ APPROVAL REQUIRED

Refund ₹2,000

₹2,000 was debited from Aarav Shah but settlement to Demo Cafe did not
complete. POL-REFUND-01 makes the debited amount refundable to source.

EVIDENCE
1  Customer debit confirmed on TX-1004 (₹2,000, UPI)
2  Merchant settlement to Demo Cafe is failed
3  Transaction is inside the 7-day refund window under POL-REFUND-01

  MONEY MOVEMENT THRESHOLD
  ₹2,000 exceeds the ₹1,000 autonomous money-movement limit.

Human approval required.                            ⚙ Deterministic reasoner
```

A danger/warning left border marks a high/medium-risk decision; the card is
never filled with the status colour. When more than one policy rule fired, the
remaining rules are listed beneath the primary one.

Once the action has executed and verified, the card becomes the record of what
happened: the badge changes to **EXECUTED** and the footer line becomes
"Approved by Ops Lead · executed and verified." The reasoner that produced the
decision is always named.

### 6.6 Live activity timeline

```
09:39:00  ✓ Mission accepted by Resolve                              RESOLVE
09:39:00  ✓ Language detected: Hindi (Devanagari) via local classifier
09:39:00  ✓ Intent: Amount debited but not received by merchant · sentiment neutral
09:39:01  ✓ Customer identified: Aarav Shah (CUST-001)
09:39:01  ✓ Transaction TX-1004 found — ₹2,000 UPI, status debited not settled
09:39:01  ⚠ Merchant Demo Cafe — settlement failed
09:39:01  ✓ Context memory: 3 items (Derived from the application database)
09:39:02  ✓ Policy POL-REFUND-01 retrieved — Debited but not settled to merchant
09:39:02  ✓ Support case CASE-003 opened
09:39:03  ✓ Decision: Refund ₹2,000
09:39:03  ✓ Action proposed: Refund ₹2,000
09:39:03  ⚠ Policy check: MONEY_MOVEMENT_THRESHOLD — approval required
09:39:04  ⚠ Human approval requested — ₹2,000 exceeds the ₹1,000 limit
```

Every row is one `MissionEvent` row in the database, delivered over SSE. No
timeline entry is synthesised in the browser. Rows carry a timestamp (muted,
tabular), a status icon, the message, and the actor (`resolve`, `grow`, `human`,
`system`). The list auto-scrolls and each new row animates in once.

### 6.7 Grow-specific panels

A five-tile pipeline counter (Evaluated / Qualified / Contacted / Sales-ready /
Meetings), then the merchant pipeline table: rank-ordered by lead score, each
row expandable to show *why selected*, the per-factor score breakdown as small
bars, the outreach message sent, the merchant reply, the qualification note, the
next action and the booked meeting slot.

When the mission is `waiting_response`, an inline reply simulator offers the
suggested replies and a free-text field. The reply posts to the backend and
drives the real qualification step.

### 6.8 Completion summary

On completion the header gains a summary block: headline, the verified steps,
and the exact message sent to the customer in their language.

---

## 7. Screen 2 — Approval Queue

### 7.1 Policy banner

Always visible, rendered from `current_policy()`:

```
AUTONOMY POLICY — HUMAN APPROVAL REQUIRED FOR      AUTONOMOUS WITHOUT ASKING
• Money movement above ₹1,000                      • Read customer, transaction
• Account-level actions                              and merchant records
• Strong negative customer sentiment                • Classify intent and language
• Irreversible external actions                     • Score and rank leads
• Actions outside agent permissions                 • Draft outreach and responses
                                                    • Refunds at or below ₹1,000
Hackathon demo policy. Not Paytm's production        • Send low-risk notifications
policy. Configurable via REFUND_APPROVAL_THRESHOLD.
```

### 7.2 Approval card

Each card answers five questions:

| Question | Field |
|---|---|
| What does the AI want to do? | `title` + `subject` |
| Why did it stop? | `policy_rule` + `reason` (+ additional `triggered_rules`) |
| What evidence supports it? | `evidence[]` |
| What happens if approved? | `impact` |
| What does the teammate recommend? | `ai_recommendation` |

Buttons: **Approve**, **Reject**, **Take over**, with the standing note *"The
action executes only after you approve. Nothing has moved yet."* — which the
acceptance test verifies is literally true by checking the ledger before and
after.

A `pending` / `all decisions` filter shows decided approvals with reviewer and
timestamp.

### 7.3 Approval lifecycle

```
pending ──approve──► approved   ──► continuation task executes the action
        ──reject───► rejected   ──► alternative path: specialist + customer notice
        ──takeover─► taken_over ──► agent stopped, human owns the mission
```

Every transition writes an event (`APPROVAL_GRANTED`, `APPROVAL_REJECTED`,
`HUMAN_TAKEOVER`) and publishes an `approvals_changed` broadcast.

### 7.4 Server-side validation

`_load_pending()` rejects a decision when the approval is not `pending`
(HTTP 409), the mission no longer exists, the mission has moved past a state
where the approval can apply, or the approval does not match its action. A
double-approve returns 409 — verified by the acceptance test.

---

## 8. Screen 3 — Outcomes

### 8.1 Resolve metrics

| Metric | Counted from |
|---|---|
| Processed | Resolve missions in a terminal state |
| Resolved autonomously | Missions with result `resolved_autonomously` |
| Escalated | Missions that created an approval request |
| Human approvals | Approval records marked `approved` |
| Failed | Missions in a `failed` state |
| Autonomy rate | `resolved_autonomously ÷ processed`, `—` when processed is 0 |

The `basis` string is rendered under every tile, so each number is traceable on
screen.

### 8.2 Grow metrics

| Metric | Counted from |
|---|---|
| Merchants evaluated | Lead records scored by Grow |
| Qualified | Leads at stage `qualified` or beyond |
| Contacted | Leads that received outreach |
| Sales-ready | Leads qualified from a reply |
| Meetings booked | Leads with a booked meeting |

Stage comparisons use `Lead.stage_rank`, so "at least contacted" stays correct
as a lead advances.

### 8.3 Mission outcome table

`Mission · Agent · Objective · Result · Human · Completed`, where **Human** shows
the approval count or `Takeover`. A traceability footer reports the total
mission, event and executed-action counts.

### 8.4 Event sourcing

```
Mission / Approval / Action / Lead records
            ▼
   outcome_service.build_outcomes()
            ▼
        GET /api/outcomes
            ▼
        Outcomes screen
```

Metrics are never computed from UI state, and the screen refreshes on the
`outcomes_changed` SSE channel.

---

## 9. High-Level System Architecture

```
                 ┌──────────────────────────────┐
                 │  Next.js 16 — three screens  │
                 │  Live Mission · Approvals ·  │
                 │  Outcomes                    │
                 └──────────────┬───────────────┘
                     REST + Server-Sent Events
                 ┌──────────────▼───────────────┐
                 │  FastAPI                     │
                 │  missions · approvals ·      │
                 │  outcomes · demo · stream    │
                 └──────────────┬───────────────┘
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
    ┌───────────┐         ┌──────────┐        ┌────────────────┐
    │  Resolve  │         │   Grow   │        │  Policy engine │
    │   agent   │         │  agent   │        │  deterministic │
    └─────┬─────┘         └────┬─────┘        └───────┬────────┘
          └──────────┬─────────┘                      │
                     ▼                                │
        ┌────────────────────────────┐                │
        │ Sarvam · Cognee · LLM      │                │
        │ (adapters, each with a     │                │
        │  deterministic fallback)   │                │
        └────────────────────────────┘                │
                     │                                │
                     ▼                                ▼
            ┌─────────────────┐           ┌──────────────────────┐
            │ SQLite/Postgres │◄──────────┤ n8n  (WF1–WF6)       │
            │ canonical state │           │ or LocalWorkflowRunner│
            └─────────────────┘           └──────────┬───────────┘
                                                     ▼
                                       Simulated Paytm boundary
                                         (/paytm/*, key-guarded)
                                                     ▼
                                     verified outcome → MissionEvent
                                                     ▼
                                                 Outcomes
```

---

## 10. Repository Layout

```
backend/
├── app/
│   ├── main.py                  app factory, lifespan, CORS, router wiring
│   ├── config.py                pydantic-settings, integration_status()
│   ├── db.py                    engine, SessionLocal, init_db, session_scope
│   ├── api/
│   │   ├── missions.py          mission lifecycle + reply endpoint
│   │   ├── approvals.py         approve / reject / take over + validation
│   │   ├── outcomes.py          aggregated metrics
│   │   ├── demo.py              scenarios, status, reset, run resolve/grow
│   │   ├── stream.py            SSE endpoint
│   │   └── paytm.py             simulated Paytm boundary (key-guarded writes)
│   ├── agents/
│   │   ├── base.py              BaseAgent: propose → policy → execute → events
│   │   ├── resolve.py           Resolve state machine + WF1/WF2/WF3 handlers
│   │   ├── grow.py              Grow state machine + WF4/WF5/WF6 handlers
│   │   ├── scoring.py           explainable lead scoring
│   │   ├── permissions.py       per-agent tool permissions, action catalogue
│   │   └── orchestrator.py      asyncio task registry, continuations, takeover
│   ├── policy/
│   │   └── risk.py              the autonomy boundary
│   ├── integrations/
│   │   ├── llm.py               multi-provider adapter + JSON validation
│   │   ├── sarvam.py            language ID, translation, intent/sentiment
│   │   ├── cognee.py            memory recall/write with labelled fallback
│   │   ├── n8n.py               workflow catalogue, n8n or local runner
│   │   └── paytm_mock.py        PaytmAdapter + MockPaytmAdapter + policies
│   ├── services/
│   │   ├── mission_service.py   lifecycle, id allocation, serialization
│   │   ├── event_service.py     EventBus (loop-aware) + record_event
│   │   └── outcome_service.py   metric aggregation with basis strings
│   ├── models/models.py         all nine tables
│   └── demo/
│       ├── seed.py              fictional dataset, reset_demo, ensure_seeded
│       └── scenarios.py         the three Resolve scenarios + Grow objective
├── scripts/smoke_test.py        62-check end-to-end acceptance test
└── requirements.txt

frontend/
├── app/
│   ├── layout.tsx               header, PulseProvider, disclosure footer
│   ├── globals.css              design tokens (Design.md §3)
│   ├── page.tsx                 Live Mission
│   ├── approvals/page.tsx       Approval Queue
│   └── outcomes/page.tsx        Outcomes
├── components/
│   ├── PulseProvider.tsx        the single SSE connection + fan-out
│   ├── AppHeader.tsx            nav, badge, integration chips, reset
│   ├── MissionLauncher.tsx      scenario cards / Grow objective form
│   ├── MissionTimeline.tsx      live activity
│   ├── DecisionCard.tsx         decision, evidence, policy, outcome
│   ├── ContextPanels.tsx        backend-driven context panels
│   ├── LeadsPanel.tsx           merchant pipeline + reply simulator
│   ├── ApprovalCard.tsx         the governance card
│   ├── PolicyBanner.tsx         the visible autonomy policy
│   └── ui.tsx                   Button, Card, badges, MetricCard, ProgressBar…
└── lib/
    ├── api.ts                   typed API client
    ├── types.ts                 domain types mirroring the backend
    └── format.ts                currency, time, label helpers

n8n/
├── README.md                    import + environment instructions
└── workflows/                   WF1–WF6, importable JSON
```

---

## 11. Component Responsibilities

### 11.1 Next.js frontend

Renders the three screens, consumes the event stream, sends operator commands,
and displays real outcomes. It **never** decides whether an action is safe, and
it holds no credentials.

One `EventSource` is opened by `PulseProvider` for the whole application, and
screens register handlers through `usePulseStream()`. This keeps a single source
of truth and avoids a connection per screen.

### 11.2 FastAPI backend

Owns mission lifecycle, agent orchestration, policy evaluation, persistence,
event publishing, approval handling, workflow dispatch, the simulated Paytm
boundary and outcome aggregation.

---

## 12. Agent Architecture

Agents are explicit state machines, not unconstrained loops. No agent framework
is used.

### 12.1 `BaseAgent`

Shared machinery that must behave identically for both teammates:

| Method | Responsibility |
|---|---|
| `beat(factor)` | Paces steps so the live timeline is readable on stage |
| `guard(session)` | Aborts immediately if a human paused or took over |
| `emit(...)` | Persists a `MissionEvent` and broadcasts it |
| `advance(...)` | Updates stage / progress / status and publishes the mission |
| `propose(proposal)` | **The only path to an action.** Recomputes authorisation, runs the risk engine, writes the `Action` row, emits `ACTION_PROPOSED` + `RISK_EVALUATED` |
| `request_approval(...)` | Writes the `Approval` row, emits `APPROVAL_REQUESTED`, stops the mission |
| `execute(...)` | Dispatches a cleared action to the workflow layer, records the result, emits `ACTION_EXECUTED` or `ACTION_FAILED` |
| `needs_attention` / `fail_mission` | Surface failures rather than swallowing them |

Because `propose()` is the only route to an `Action` row, an agent physically
cannot execute anything without a policy verdict.

### 12.2 Orchestration

`orchestrator.py` runs each mission as an `asyncio.Task` inside the API process.

FastAPI request handlers are synchronous and execute on a worker thread, so the
orchestrator and the event bus both capture the application event loop at
startup (`bind_loop()`) and marshal task creation, cancellation and SSE delivery
back onto it with `call_soon_threadsafe`. Without this, `asyncio.create_task()`
from a request handler raises `no running event loop`.

**An agent that reaches an approval boundary ends its task** rather than parking
on a lock. When a human decides, a fresh continuation task
(`_continue_approved` / `_continue_rejected`) reloads state and resumes. The
approval boundary is therefore a real stop, not a blocked thread.

### 12.3 Common loop

```
Mission created
      ▼
Understand objective          (WF1 for Resolve)
      ▼
Load context                  (WF2 for Resolve, WF4 for Grow)
      ▼
Determine next action         (LLM or deterministic reasoner)
      ▼
Evaluate risk                 (policy engine — deterministic)
      ├── REQUIRES_APPROVAL ──► Approval Queue ──► human ──┐
      └── AUTONOMOUS ─────────────────────────────────────┤
                                                          ▼
                                                      Execute (WF3 / WF5 / WF6)
                                                          ▼
                                                      Verify
                                                          ▼
                                                 Complete + record outcome
```

---

## 13. Resolve Agent

### 13.1 Inputs

```
customer_id   (required)
message       (required, any language)
scenario      (optional, demo label)
```

The transaction is **discovered**, not supplied — the agent locates the disputed
transaction from the customer and any amount mentioned in the message, exactly
as it would from a real inbound message.

### 13.2 Tools

```
READ        get_customer · get_transaction · get_merchant · get_policy
            get_customer_history · get_memory · verify_refund
WRITE       create_case · send_customer_notification
CONTROLLED  request_refund · account_action
```

### 13.3 State machine

```
UNDERSTANDING (12%)
      ▼
CONTEXT_LOADING (28%)
      ▼
INVESTIGATING (46%)
      ▼
DECISION (64%)
      ▼
RISK_CHECK (74%)
      ├── AUTONOMOUS ──► EXECUTING (88%) ──► VERIFYING (94%) ──► RESOLVED (100%)
      │
      └── REQUIRES_APPROVAL ──► WAITING_APPROVAL (80%)
                                      │
                    ┌─────────────────┼──────────────────┐
                 approved          rejected          taken over
                    ▼                 ▼                  ▼
              EXECUTING         specialist +        human owns
                    ▼            customer notice     the mission
              VERIFYING               ▼
                    ▼            RESOLVED (100%)
              RESOLVED (100%)
```

### 13.4 Decision generation

1. The deterministic reasoner always produces a complete, valid decision from
   the evidence: action type, rationale, evidence bullets, recommendation.
2. If an LLM is configured, it is asked for the same structure and its output is
   **merged over** the deterministic baseline — never used raw.
3. Validation: `action_type` must be in `{refund, escalate_to_specialist,
   notify_customer}` or it is forced to `escalate_to_specialist`; free text is
   length-clamped; **the amount is overwritten with the ledger amount
   regardless of what the model returned**.
4. If an LLM is configured but unreachable, `SYSTEM_WARNING` is emitted and the
   mission is **paused** with a Retry available.

### 13.5 Verification

`verify_refund()` calls `session.expire_all()` and re-reads the transaction row.
The mission only completes when the ledger actually reports `refunded`;
otherwise the mission moves to `needs_attention`. Verification is a real
read-back, not a canned success.

### 13.6 Post-execution refresh

On completion the agent re-reads the transaction and rebuilds
`mission.context`, so the context panel shows `Refunded / Refunded To Source`
rather than the snapshot taken during investigation. The decision card is
simultaneously stamped `resolved: true` with the outcome line, so it stops
saying "approval required" once the approval has been granted and executed.

### 13.7 Rejection path

A rejected action is not a dead end. The agent reassigns the support case to a
human specialist, notifies the customer in their language that a specialist will
follow up, and completes the mission with result `rejected_by_human`. The
refund is verified **not** to have executed.

---

## 14. Grow Agent

### 14.1 Inputs

```
location       default "Thane"
target_count   default 5 (1–20)
category       optional
```

### 14.2 Tools

```
READ        search_demo_merchants · get_merchant_profile · get_paytm_status · get_memory
WRITE       score_lead · generate_outreach · update_lead · process_reply · book_meeting
CONTROLLED  send_outreach
```

### 14.3 State machine

```
DISCOVERING (12%) ─► ENRICHING (26%) ─► SCORING (42%) ─► PRIORITIZING (54%)
      ▼
OUTREACH (68%)          ← policy-checked like any other action
      ▼
WAITING_RESPONSE (78%)  ← mission parks here for a merchant reply
      ▼
QUALIFYING (86%) ─► SALES_READY (92%) ─► MEETING_BOOKED (100%)
```

If the reply is negative the lead is parked (`disqualified`) and the mission
completes with `no_qualified_leads` — an honest outcome, not a forced success.

### 14.4 Lead stages

```
discovered(1) · scored(2) · disqualified(2) · qualified(3)
contacted(4) · responded(5) · sales_ready(6) · meeting_booked(7)
```

`stage_rank` makes "reached at least stage X" a correct comparison for metrics.

### 14.5 Outreach selection

Two thresholds, both configurable:

- `LEAD_QUALIFICATION_THRESHOLD` (75) — a lead is *qualified*.
- `LEAD_OUTREACH_THRESHOLD` (80) — a qualified lead with a reachable contact
  goes in the **first** outreach wave, capped at `target_count`.

With the seeded dataset this yields 12 evaluated → 4 qualified → 3 contacted.
Those numbers are computed, not configured; changing a merchant's estimated
volume changes them.

### 14.6 Governance parity

Grow's actions go through the same `propose()` path as Resolve's.
`send_outreach` and `book_meeting` move no money, change no account and are
reversible, so the engine returns `AUTONOMOUS · WITHIN_AUTONOMY` — which the
decision card displays. The policy engine governs both teammates; it simply has
nothing to stop here.

---

## 15. Lead Scoring

Deterministic and fully explainable. Every point maps to a named factor with a
one-line reason, so "Lead score 91" can always be broken down in the UI.

| Factor | Max | Basis |
|---|---|---|
| Transaction potential | 35 | `min(35, round(volume / 900,000 × 35))` |
| Category fit | 20 | Category → digital-payment affinity table |
| Digital presence | 20 | Website 12 + reachable contact 8 |
| Territory match | 15 | Location contains the mission territory |
| Availability | 10 | Not onboarded in the demo dataset |
| **Total** | **100** | |

Opportunity label: `≥80 High · ≥65 Medium · else Low`.

Worked example — Mumbai Brew House:

```
Transaction potential  26/35   ₹660,000 estimated monthly volume
Category fit           20/20   Cafe — digital-payment affinity
Digital presence       20/20   Website and direct contact available
Territory match        15/15   Thane West matches the mission territory
Availability           10/10   Not onboarded in the demo dataset
                       ─────
Lead score             91/100  High opportunity
```

These are **demo-dataset attributes**, not Paytm acquisition signals, and
nothing here infers whether a real business accepts Paytm.

---

## 16. Escalation and Risk Policy

### 16.1 Policy object

```json
{
  "refund_threshold": 1000,
  "account_actions_require_approval": true,
  "negative_sentiment_requires_review": true,
  "irreversible_actions_require_approval": true,
  "unknown_permissions_require_approval": true
}
```

All five are independently configurable via environment variables.

### 16.2 The five rules

| Rule | Risk | Trigger |
|---|---|---|
| `MONEY_MOVEMENT_THRESHOLD` | high | `money_amount > REFUND_APPROVAL_THRESHOLD` |
| `ACCOUNT_LEVEL_ACTION` | high | Action changes account-level state |
| `NEGATIVE_SENTIMENT_REVIEW` | medium | Sentiment is `strongly_negative` or `angry` |
| `IRREVERSIBLE_ACTION` | high | Action cannot be automatically reversed |
| `PERMISSION_BOUNDARY` | high | Action is outside the agent's declared permissions |
| `WITHIN_AUTONOMY` | low/medium | Nothing fired — proceed autonomously |

**All** matching rules are collected. They are sorted by severity and the most
severe becomes the `primary_rule` shown on the approval card; the rest are
listed beneath it. This is why Scenario C reports
`NEGATIVE_SENTIMENT_REVIEW` cleanly — its ₹800 amount is under the threshold, so
only the sentiment rule fires.

Sentiment classification routes workflows. It is not a psychological assessment.

---

## 17. Risk Engine

`app/policy/risk.py` — deterministic, side-effect free, no model call.

```python
def evaluate_action(proposal: ActionProposal) -> RiskDecision:
    triggered = []
    if proposal.money_amount > settings.refund_approval_threshold:
        triggered.append(MONEY_MOVEMENT_THRESHOLD, risk="high")
    if proposal.affects_account and settings.account_actions_require_approval:
        triggered.append(ACCOUNT_LEVEL_ACTION, risk="high")
    if settings.negative_sentiment_requires_review and proposal.sentiment in NEGATIVE_SENTIMENTS:
        triggered.append(NEGATIVE_SENTIMENT_REVIEW, risk="medium")
    if proposal.irreversible and settings.irreversible_actions_require_approval:
        triggered.append(IRREVERSIBLE_ACTION, risk="high")
    if not proposal.authorized and settings.unknown_permissions_require_approval:
        triggered.append(PERMISSION_BOUNDARY, risk="high")

    if not triggered:
        return RiskDecision("AUTONOMOUS", WITHIN_AUTONOMY, ...)

    triggered.sort(by=severity, reverse=True)
    return RiskDecision("REQUIRES_APPROVAL", primary=triggered[0], all=triggered)
```

The `RiskDecision` carries the verdict, risk level, primary rule, human-readable
reason, a combined policy detail and the full list of triggered rules — enough
for the Approval Queue to explain itself without any additional lookup.

---

## 18. Agent Tool Permission Model

`app/agents/permissions.py` declares, per agent, every tool and its trust level
(`read` / `write` / `controlled`), plus an **action catalogue** mapping each
action type to its owning agent, backing tool and human label.

```python
require_tool(agent, tool)      # hard gate — raises ToolPermissionError
authorize_action(agent, action_type) -> (authorized, note)
```

`authorize_action()` returns `False` when the action type is not in the
catalogue, belongs to the other teammate, or maps to a tool the agent has not
declared. An unauthorised action is **not silently dropped** — it is handed to
the risk engine, which routes it to a human via `PERMISSION_BOUNDARY`. An
unexpected model proposal therefore becomes visible rather than disappearing.

---

## 19. n8n Architecture

n8n is the execution layer — **the hands of the AI**. It never decides whether
an action is allowed; it only receives actions the policy engine has already
cleared and, where required, a human has already approved.

```
Agent decides → Policy authorises → n8n executes → Pulse verifies
```

### 19.1 Two modes, one contract

| `N8N_BASE_URL` | Path |
|---|---|
| set | `POST {base}{prefix}/{workflow}` with `X-N8N-API-KEY` |
| unset | `LocalWorkflowRunner` executes the same steps in-process |

`N8nAdapter.run(workflow, payload, local=handler)` returns a `WorkflowResult`
with `success`, `workflow_code`, `executed_via`, `data` and `error` in both
modes. The workflow boundary is preserved either way — the application never
bypasses it. The timeline names the path that ran:

```
Refund ₹2,000 executed via WF3 (local workflow runner)
Refund ₹2,000 executed via WF3 (n8n)
```

An n8n failure returns `success=False`; the mission moves to `needs_attention`
with the error shown and Retry offered. Failure is never reported as success.

### 19.2 The six workflows

| Code | Webhook path | Agent | Steps |
|---|---|---|---|
| WF1 | `/webhook/paytm-pulse/issue-intake` | Resolve | Webhook → Sarvam `/text-lid` → normalise intent → respond |
| WF2 | `/webhook/paytm-pulse/investigation` | Resolve | Customer → disputed transaction → merchant → history → refund eligibility → policy → assemble evidence |
| WF3 | `/webhook/paytm-pulse/resolution` | Resolve | Branch refund/escalate → execute refund → verify → notify → build result |
| WF4 | `/webhook/paytm-pulse/lead-discovery` | Grow | Search merchants → filter onboarded → enrich → score → rank |
| WF5 | `/webhook/paytm-pulse/outreach` | Grow | Split leads → send outreach (simulated) → collect results |
| WF6 | `/webhook/paytm-pulse/followup` | Grow | Book meeting → reload lead → initiate onboarding → build result |

Importable JSON lives in `n8n/workflows/`. Each uses `n8n-nodes-base.webhook`,
`httpRequest`, `code`, `if` and `respondToWebhook`, and calls back into the
simulated Paytm boundary over HTTP — so in n8n mode the side effects genuinely
happen through n8n.

### 19.3 n8n environment

| Variable | Value |
|---|---|
| `PULSE_API_URL` | `http://localhost:8000` |
| `INTERNAL_API_KEY` | must match the backend's `INTERNAL_API_KEY` |
| `SARVAM_API_KEY` / `SARVAM_BASE_URL` | WF1 only, optional |

`INTERNAL_API_KEY` is generated per process when left blank — fine for the local
runner, but it must be set explicitly when using n8n so both sides agree.

### 19.4 Webhook contract

```http
POST /webhook/paytm-pulse/resolution
```

```json
{
  "mission_id": "R-0001",
  "agent": "resolve",
  "action": "refund",
  "action_id": "ACT-001",
  "approval_id": "APR-001",
  "transaction_id": "TX-1004",
  "customer_id": "CUST-001",
  "case_id": "CASE-003",
  "amount": 2000,
  "message": "…",
  "channel": "sms"
}
```

```json
{
  "success": true,
  "action_id": "ACT-001",
  "status": "executed",
  "refund": { "success": true, "amount": 2000, "refund_reference": "PULSE-R-0001-ACT-001" },
  "verification": { "verified": true, "status": "refunded" },
  "notification": { "success": true, "channel": "sms", "delivery": "simulated" }
}
```

---

## 20. Sarvam Integration

The India-native language layer, used for actual teammate interaction rather
than translating static UI labels.

```
"₹2,000 कट गया लेकिन merchant को नहीं मिला."
              ▼
        Sarvam /text-lid            → language + script
        Sarvam /v1/chat/completions → intent + sentiment (JSON)
              ▼
{ "intent": "payment_failed_after_debit", "language": "hi-IN",
  "sentiment": "neutral", "amount_mentioned": 2000 }
```

Outbound customer messages are composed in English and rendered in the
customer's language through `/translate` when Sarvam is available.

**Fallback.** Without `SARVAM_API_KEY`, a local classifier handles Devanagari
detection, keyword intent matching across Hindi / English / transliterated
forms, sentiment markers and amount extraction. Every result carries a `source`
field (`sarvam` or `fallback`) which the timeline reports verbatim: *"Language
detected: Hindi (Devanagari) via local classifier"*. When Sarvam is unreachable
mid-call, the adapter degrades to the same path and records the error.

Outbound messages fall back to bundled per-language templates labelled
`template` rather than claiming a translation happened.

The amount extracted from a message is used **only** to locate the transaction —
never to set a refund amount.

---

## 21. Cognee Integration

Contextual memory. Not a UI screen — agents call `recall()` while loading
context and the results appear inline in the context panel.

```python
await cognee.recall(scope="customer", subject_id="CUST-001",
                    query="support history for Aarav Shah",
                    local_context=[...])
```

`local_context` is both the fallback and the floor: Cognee results are added on
top of database-derived context, never substituted for canonical transactional
state. The return value carries `source` (`cognee` or `local_context`) and a
human-readable `detail`, which the context panel header renders. When Cognee is
unavailable the panel says *"Local context"* — it never fakes a successful
memory retrieval.

---

## 22. LLM Integration

`LLMAdapter` supports `anthropic`, `openai`, `openai_compatible` and `sarvam`
through one interface, with `complete_json()` enforcing that the response is a
JSON object containing the required keys.

Where the model is used:

| Use | Fallback when unavailable |
|---|---|
| Resolve decision rationale, evidence bullets, customer message | Deterministic reasoner |
| Grow outreach drafting | Template with the merchant's top score reason |
| Grow reply qualification | Keyword intent rules |

Where the model is **never** used: authorising an action, setting an amount,
choosing whether to stop for approval.

Outreach drafting and reply qualification degrade quietly to their fallbacks
(they are cosmetic and recoverable). A failure of the Resolve decision call
pauses the mission, because silently swapping the reasoner that produced a
refund decision would be invisible to the operator.

---

## 23. Paytm Integration Boundary

### 23.1 Adapter

```
              PaytmAdapter  (abstract interface)
                     │
          ┌──────────┴────────────┐
          ▼                       ▼
  MockPaytmAdapter        ProductionPaytmAdapter
      IMPLEMENTED                FUTURE
```

Agents code against `PaytmAdapter`. Swapping in a production implementation
would change no agent code. Mock Paytm logic is confined to
`integrations/paytm_mock.py`; it is not scattered through the codebase.

State changes are real within the prototype: a refund actually mutates the
transaction row, and the adapter refuses to refund an amount that does not match
the ledger or a transaction that is already refunded.

### 23.2 Simulated boundary API

Reads are open (fictional demo records). **Every mutation requires the
`X-Pulse-Internal-Key` header**, which only the execution layer holds — so a
browser cannot move money even though the endpoint exists.

```http
GET  /paytm/customer/{id}
GET  /paytm/customer/{id}/history
GET  /paytm/customer/{id}/disputed-transaction?amount=
GET  /paytm/transaction/{id}
GET  /paytm/transaction/{id}/settlement
GET  /paytm/transaction/{id}/refund-eligibility
GET  /paytm/merchant/{id}
GET  /paytm/merchants?location=&category=
GET  /paytm/policy/{policy_id}
GET  /paytm/leads?mission_id=

POST /paytm/refund                    🔒
POST /paytm/refund/verify             🔒
POST /paytm/notification              🔒
POST /paytm/leads/{id}/outreach       🔒
POST /paytm/meeting                   🔒
POST /paytm/onboarding                🔒
```

### 23.3 Demo policy documents

`POL-REFUND-01` (debited but not settled), `POL-DELAY-01` (delayed settlement),
`POL-ESCALATION-01` (repeat complaint handling). The agent selects
`POL-ESCALATION-01` when the customer has prior unresolved cases.

---

## 24. Data Model

Nine tables, SQLAlchemy 2.x typed declarative mappings.

### Customer
`id · name · phone · language · segment · joined_on`

### Merchant
`id · name · category · location · paytm_status · estimated_volume · contact · website · notes`

`paytm_status` ∈ `active | not_onboarded`

### Transaction
`id · customer_id · merchant_id · amount · payment_method · status · settlement_status · timestamp`

`status` ∈ `success | debited_not_settled | pending | failed | refunded`
`settlement_status` ∈ `settled | failed | pending | refunded_to_source`

### SupportCase
`id · customer_id · transaction_id · issue · sentiment · status · assigned_agent · resolution · mission_id · created_at`

`status` ∈ `open | reopened | resolved | with_specialist`

### Lead
`id · mission_id · merchant_id · score · stage · stage_rank · reason[] · score_breakdown[] · next_action · outreach_message · outreach_channel · response_message · qualification_note · meeting_slot · created_at · updated_at`

### Mission
`id · agent · objective · status · stage · progress · result · result_label · inputs · context · decision · summary · error · human_involved · created_at · updated_at · completed_at`

`status` ∈ `created | running | waiting_approval | waiting_response | paused | needs_attention | human_takeover | completed | failed`
Terminal: `completed | failed | human_takeover`
`result` ∈ `resolved_autonomously | resolved_with_approval | rejected_by_human | handled_by_human | meeting_booked | no_qualified_leads | failed`

### Action
`id · mission_id · action_type · description · risk_level · requires_approval · approval_id · status · payload · result · executed_via · created_at · completed_at`

`status` ∈ `proposed | pending_approval | executing | executed | failed | cancelled`

### Approval
`id · mission_id · action_id · agent · title · subject · reason · policy_rule · policy_detail · risk_level · evidence[] · triggered_rules[] · ai_recommendation · impact · status · reviewed_by · reviewed_at · created_at`

`status` ∈ `pending | approved | rejected | taken_over`

### MissionEvent
`id · mission_id · timestamp · event_type · actor · message · level · metadata`

`level` ∈ `ok | pending | warn | error | info` — drives the timeline icon colour.
The `metadata` column is mapped to the Python attribute `meta`, because
`metadata` is reserved on a SQLAlchemy declarative class.

### Identifier allocation

| Entity | Scheme |
|---|---|
| Mission (Resolve) | `R-0001`, `R-0002`, … |
| Mission (Grow) | `G-0001`, `G-0002`, … |
| Action | `ACT-001` |
| Approval | `APR-001` |
| Lead | `L-001` |
| Support case | `CASE-003` (seeded cases occupy 001–002) |

`next_mission_id()` appends `-2`, `-3` on collision so a repeated run can never
overwrite an existing mission.

---

## 25. Event Model

33 event types, validated on write:

```
MISSION_CREATED · MISSION_STARTED · LANGUAGE_DETECTED · INTENT_CLASSIFIED
CONTEXT_LOADED · MEMORY_RETRIEVED · CUSTOMER_IDENTIFIED · TRANSACTION_FOUND
MERCHANT_CHECKED · POLICY_RETRIEVED · CASE_CREATED · DECISION_GENERATED
ACTION_PROPOSED · RISK_EVALUATED · APPROVAL_REQUESTED · APPROVAL_GRANTED
APPROVAL_REJECTED · ACTION_EXECUTED · ACTION_VERIFIED · ACTION_FAILED
MESSAGE_SENT · LEAD_DISCOVERED · LEAD_SCORED · LEAD_CONTACTED · LEAD_RESPONDED
LEAD_QUALIFIED · MEETING_BOOKED · MISSION_PAUSED · MISSION_RESUMED
MISSION_COMPLETED · MISSION_FAILED · HUMAN_TAKEOVER · SYSTEM_WARNING
```

`record_event()` persists first, then broadcasts — so an event is durable before
any client sees it, and the timeline can always be rebuilt from the database via
`GET /api/missions/{id}/events`.

---

## 26. Real-Time UI Updates

A single SSE endpoint carries every live update.

```http
GET /api/stream          → text/event-stream
```

| Channel | Payload |
|---|---|
| `connected` | Handshake |
| `mission_event` | One serialised `MissionEvent` |
| `mission_update` | The full serialised mission after a state change |
| `approvals_changed` | Invalidation signal |
| `outcomes_changed` | Invalidation signal |
| `demo_reset` | Clear all client state |

`EventBus` holds one bounded `asyncio.Queue` per subscriber, drops a subscriber
whose queue is full (a stalled client must never slow an agent down), sends a
`: keep-alive` comment every 15 s, and is loop-aware so `publish()` is safe from
both agent coroutines and request-handler worker threads.

```
Action executed → MissionEvent persisted → published → SSE
                → timeline row → mission status → outcome counters
```

---

## 27. API Design

### Missions

```http
GET    /api/missions?agent=resolve|grow
POST   /api/missions
GET    /api/missions/{id}                 # includes events + running flag
GET    /api/missions/{id}/events
POST   /api/missions/{id}/start
POST   /api/missions/{id}/pause
POST   /api/missions/{id}/retry           # paused | needs_attention | failed
POST   /api/missions/{id}/takeover
POST   /api/missions/{id}/reply           # Grow: simulated merchant reply
```

### Approvals

```http
GET    /api/approvals?status=pending|all
GET    /api/approvals/{id}
POST   /api/approvals/{id}/approve
POST   /api/approvals/{id}/reject
POST   /api/approvals/{id}/takeover
```

### Outcomes

```http
GET    /api/outcomes
GET    /api/outcomes/resolve
GET    /api/outcomes/grow
```

### Demo & system

```http
GET    /api/demo/scenarios
GET    /api/demo/status
POST   /api/demo/reset
POST   /api/demo/resolve      { scenario } | { customer_id, message }
POST   /api/demo/grow         { location, target_count, category }
GET    /api/stream
GET    /api/health
GET    /docs                  # OpenAPI
```

Mission state transitions are validated server-side and return `409 Conflict`
rather than corrupting state — starting a running mission, retrying a mission
that is not recoverable, replying to a mission that is not waiting, or taking
over a finished mission.

---

## 28. Demo Dataset

All records are **fictional**. This dataset is not Paytm's customer or merchant
data, and it makes no claim about which real businesses accept Paytm.

| Entity | Count | Composition |
|---|---|---|
| Customers | 4 | Hindi and English speakers, retail and premium |
| Merchants | 17 | 3 onboarded transaction counterparties · 12 Thane prospects · 2 out-of-area prospects |
| Transactions | 8 | 3 disputed (the scenarios) · 5 settled history |
| Support cases | 2 | Both prior unresolved cases for CUST-003 |

Merchants in Thane: 14 total — 2 already on Paytm (filtered out by Grow, and
reported as skipped) and 12 prospects (the "12 evaluated" figure).

The prospect volumes are deliberately chosen so the scorer produces **exactly 4
qualified and 3 above the outreach bar**. Those figures come out of the formula,
not a constant.

The two seeded support cases matter: they make the "third complaint" in
Scenario C a **fact in the database** rather than a claim in the message. The
evidence line *"2 prior unresolved case(s) on record for this customer"* is read
from `SupportCase`, not inferred from the text.

---

## 29. Demo Scenarios

### Resolve A — autonomous

```
Customer   CUST-002 Neha Kulkarni (English)
Message    "₹500 was debited from my account but the shop says they did
            not receive it. Please check."
Discovers  TX-1001 · ₹500 · settlement failed
Policy     WITHIN_AUTONOMY — ₹500 is at or below the ₹1,000 limit
Outcome    resolved_autonomously
```

### Resolve B — money threshold (the headline demo)

```
Customer   CUST-001 Aarav Shah (Hindi)
Message    "₹2,000 कट गया लेकिन merchant को नहीं मिला."
Discovers  TX-1004 · ₹2,000 · settlement failed
Policy     MONEY_MOVEMENT_THRESHOLD — high risk, approval required
Outcome    resolved_with_approval (after a human approves)
```

### Resolve C — sentiment escalation

```
Customer   CUST-003 Imran Shaikh (Hindi)
Message    "तीन बार शिकायत कर चुका हूँ, अभी तक पैसे वापस नहीं आए!"
Discovers  TX-1007 · ₹800 · settlement failed · 2 prior unresolved cases
Policy     NEGATIVE_SENTIMENT_REVIEW — medium risk, approval required
Outcome    Escalated. ₹800 is UNDER the money threshold, so sentiment is the
           only reason it stopped.
```

Scenario C is the sharper governance story: the same amount that would run
autonomously is routed to a human because of how the customer is writing.

### Grow

```
Objective  "Find 5 high-potential merchants in Thane"
Result     14 matched · 2 already on Paytm (skipped) · 12 evaluated
           4 qualified (≥75) · 3 contacted (≥80 with a contact)
           top lead Mumbai Brew House at 91
Reply      "Interested. What do I need to do?"
Outcome    sales_ready → meeting_booked
```

---

## 30. Outcome Computation

```python
processed  = missions in a terminal state
autonomous = missions with result == "resolved_autonomously"
escalated  = missions that created at least one approval record
approvals  = approval records with status == "approved"
failed     = missions with status == "failed"

autonomy_rate = round(autonomous / processed * 100) if processed else None
```

Every metric is returned as `{value, label, basis}`, and the UI renders the
`basis` beneath the number.

Running Scenario A, then Scenario B with an approval, then the Grow mission
produces:

```
Processed 2 · Resolved autonomously 1 · Escalated 1 · Human approvals 1
Failed 0 · Autonomy rate 50%

Merchants evaluated 12 · Qualified 4 · Contacted 3
Sales-ready 1 · Meetings booked 1
```

A mission taken over before it reaches the approval boundary counts as
*processed* and *human-involved* but **not** as *escalated* — it never created
an approval. The acceptance test asserts this distinction.

---

## 31. Demo Reset

```http
POST /api/demo/reset
```

1. Cancels every running agent task.
2. Deletes all mission events, approvals, actions, leads and missions.
3. Deletes and re-seeds customers, merchants, transactions and support cases —
   so a transaction refunded during a run returns to `debited_not_settled`.
4. Broadcasts `demo_reset`, `approvals_changed` and `outcomes_changed`.
5. Leaves configuration and environment untouched.

The full four-minute demo is therefore repeatable from the **Reset demo** button
in the header, with no manual database edits.

---

## 32. Error Handling

| Failure | Behaviour |
|---|---|
| LLM configured but unreachable | `SYSTEM_WARNING`, mission `paused`, reason shown, **Retry** offered |
| No LLM configured | Deterministic reasoner — the designed offline path, shown in the header chips |
| n8n / workflow failure | Action `failed`, mission `needs_attention`, error shown, **Retry** + **Take over** |
| Refund rejected at the boundary | Mission `needs_attention` with the rejection reason (`AMOUNT_MISMATCH`, `ALREADY_REFUNDED`) |
| Verification fails | `SYSTEM_WARNING`, mission `needs_attention` — the mission does **not** complete |
| Sarvam unavailable | Local classifier / template, labelled in the timeline |
| Cognee unavailable | Database-derived context, labelled "Local context" |
| Backend unreachable | Persistent banner on every screen, not a transient toast |
| Unhandled agent exception | Caught by the orchestrator, mission marked `failed` with the message |

`retry` on a Resolve mission that already gathered context resumes at the
decision step rather than re-investigating. A re-proposed action is re-judged by
the policy engine, so a retry can never skip an approval that is still due.

---

## 33. Security and Safety Boundaries

- The policy engine is deterministic Python. The LLM cannot override it.
- An unrecognised action type is treated as unauthorised and routed to a human.
- Refund amounts come from the ledger; the boundary rejects a mismatch.
- Approval state is validated server-side: a decided approval cannot be decided
  again (409), and an approval cannot be applied to a mission that has moved on.
- Mutating `/paytm/*` endpoints require `X-Pulse-Internal-Key`. A browser
  cannot move money.
- No secret reaches the frontend. `integration_status()` reports live/fallback
  mode without exposing values. The only `NEXT_PUBLIC_*` value is the API URL.
- `.env` is git-ignored; `.env.example` ships blank placeholders only.
- Sensitive actions are logged and every one has a durable event trail.
- All demo data is fictional.

---

## 34. Configuration

26 settings, all with working defaults. Every integration key is optional.

```env
# Application
NODE_ENV · PORT · CORS_ORIGINS · NEXT_PUBLIC_API_URL

# Database — blank = SQLite at backend/pulse.db
DATABASE_URL

# LLM — blank = deterministic reasoner
LLM_PROVIDER · LLM_API_KEY · LLM_MODEL · LLM_BASE_URL

# Sarvam — blank = local classifier
SARVAM_API_KEY · SARVAM_BASE_URL · SARVAM_MODEL

# Cognee — blank = local context
COGNEE_API_URL · COGNEE_API_KEY

# n8n — blank = local workflow runner
N8N_BASE_URL · N8N_API_KEY · N8N_WEBHOOK_PREFIX

# Internal service auth — generated per process if blank
INTERNAL_API_KEY

# Demo policy (hackathon policy, not Paytm's production policy)
REFUND_APPROVAL_THRESHOLD=1000
ACCOUNT_ACTIONS_REQUIRE_APPROVAL=true
NEGATIVE_SENTIMENT_REQUIRES_REVIEW=true
IRREVERSIBLE_ACTIONS_REQUIRE_APPROVAL=true
UNKNOWN_PERMISSIONS_REQUIRE_APPROVAL=true

# Grow tuning
LEAD_QUALIFICATION_THRESHOLD=75
LEAD_OUTREACH_THRESHOLD=80

# Demo
DEMO_MODE=true
AGENT_STEP_DELAY_MS=550
```

`AGENT_STEP_DELAY_MS` paces agent steps so the live timeline is legible on
stage. Set it to `0` for fast automated runs.

---

## 35. Frontend State

```
PulseProvider   streamStatus · pendingApprovals · integration status · resetDemo
Live Mission    agent · scenarios · missions · selectedId · mission · events
Approval Queue  filter · approvals · policy · busyId
Outcomes        outcomes
```

Everything else is derived from backend state. Fetches are cancellable, so a
slow response for a previous agent, mission or filter can never overwrite newer
state. Stream handlers are registered through a ref synced in an effect, so
handlers stay fresh without resubscribing and without writing to a ref during
render.

---

## 36. Verification

`backend/scripts/smoke_test.py` drives the **public API only** through the exact
sequence a judge will see, asserting 62 checks:

```
RESET
 → Resolve A: completes autonomously, ledger shows refunded
 → Resolve B: stops at approval, cites MONEY_MOVEMENT_THRESHOLD,
              amount came from the ledger,
              ledger UNTOUCHED before approval,
              direct /paytm/refund without the service key → 401,
              approve → 200, double approve → 409,
              completes as resolved_with_approval, ledger now refunded
 → Resolve C: stops on NEGATIVE_SENTIMENT_REVIEW at ₹800,
              prior_unresolved_cases == 2 read from the database,
              reject → completes as rejected_by_human,
              refund NOT executed
 → Grow:      12 evaluated / 4 qualified / 3 contacted,
              top lead Mumbai Brew House at 91 with 5 score factors,
              reply → sales_ready → meeting booked
 → Takeover:  mission stopped mid-run, HUMAN_TAKEOVER recorded
 → Outcomes:  all metrics match the records
 → RESET:     metrics cleared, autonomy rate None (not 0%),
              ledger restored, approvals cleared
```

```bash
cd backend && .venv/Scripts/python scripts/smoke_test.py
```

Frontend gates: `npx tsc --noEmit`, `npx eslint .` and `npm run build` all pass
clean, including React Compiler lint rules.

---

## 37. Four-Minute Demo

**0:00–0:30 — Framing.** Two teammates, two jobs. Resolve owns customer
problems. Grow owns merchant acquisition. Press **Reset demo**.

**0:30–1:45 — Resolve.** Run Scenario B. Watch the timeline: Sarvam → intent →
customer → transaction → merchant settlement → memory → policy → decision. Then
it stops on `MONEY_MOVEMENT_THRESHOLD`. Open the Approval Queue, show the five
questions the card answers, approve. Refund executes through WF3, is verified
against the ledger, customer notified in Hindi, mission complete.

**1:45–3:15 — Grow.** "Find 5 high-potential merchants in Thane." 12 evaluated,
4 qualified, 3 contacted. Open Mumbai Brew House — score 91 broken down by
factor. Simulate *"Interested. What do I need to do?"* → qualified → meeting
booked.

**3:15–3:45 — Outcomes.** Every metric with the records it was counted from.

**3:45–4:00 —**

> "We don't give AI another chat box. We give it a job."

```
Sarvam   → Understand India
Cognee   → Remember context
LLM      → Decide
Policy   → Govern autonomy
n8n      → Act
Human    → Approve / Take over
Pulse    → Own the outcome
```

If time allows, Scenario C is the stronger governance moment: ₹800 is *under*
the money threshold, and it still stops — purely on sentiment.

---

## 38. Definition of Done

| Requirement | Status |
|---|---|
| Resolve end-to-end with verification | ✅ |
| Grow end-to-end to a booked meeting | ✅ |
| Approve / reject / take over, all validated server-side | ✅ |
| Deterministic policy engine the model cannot override | ✅ |
| Agent tool permission model enforced | ✅ |
| Live event timeline backed by database rows | ✅ |
| Outcomes computed from records, with a traceable basis | ✅ |
| Exactly three screens, no chat box | ✅ |
| Repeatable demo reset | ✅ |
| Six n8n workflows, importable, with a local-runner fallback | ✅ |
| Sarvam, Cognee, LLM adapters with labelled fallbacks | ✅ |
| No secrets in the frontend; money-moving endpoints key-guarded | ✅ |
| Error states with retry and take-over | ✅ |
| Runs with zero API keys | ✅ |

---

## 39. Deviations from the Original Design

Recorded for transparency.

### 39.1 Mission identifiers

**Designed:** `MISSION #TX-1004` — the mission named after the transaction.
**Built:** `R-0001` / `G-0001`, with the transaction shown beside it.

The agent *discovers* the transaction from the customer message rather than
being handed it, so naming a mission after a transaction it has not yet found
would be circular. The header shows `MISSION R-0001 · TX-1004` once discovered,
keeping the case reference visible without the false precision.

### 39.2 Scenario C amount

**Designed:** an angry message with no specified amount.
**Built:** ₹800 — deliberately **under** the ₹1,000 threshold.

If the amount also exceeded the threshold, two rules would fire and the
sentiment rule would be indistinguishable from the money rule. At ₹800 the
sentiment rule is the only reason the mission stops, which demonstrates the
policy engine far more clearly.

### 39.3 Database default

**Designed:** PostgreSQL preferred.
**Built:** SQLite by default, PostgreSQL supported by changing `DATABASE_URL`.

Zero-setup matters more than durability for a hackathon demo. No code differs
between the two.

### 39.4 Grow outreach is autonomous

**Designed:** external communication is a CONTROLLED capability.
**Built:** `send_outreach` remains CONTROLLED in the permission model and is
still evaluated by the policy engine, but on a simulated channel with no money
movement and no account change it resolves to `AUTONOMOUS · WITHIN_AUTONOMY`.

This keeps the Grow demo flowing while still showing the policy engine governing
both teammates. The approval story lives in Resolve, where it is strongest.

### 39.5 Rejection takes an alternative path

**Designed:** "Mission blocked / alternative path."
**Built:** the alternative path is implemented — specialist reassignment plus a
customer notification — and the mission completes with `rejected_by_human`
rather than stalling.

### 39.6 Webhook contract

**Designed:** a single `/webhook/paytm-pulse/action` endpoint.
**Built:** six named webhooks, one per logical workflow, so the n8n workflow
boundaries match the architecture rather than multiplexing through one path.

### 39.7 Added: internal service key

Not in the original design. The `/paytm/*` mutation endpoints exist so n8n can
act over HTTP, which would otherwise expose an unauthenticated refund endpoint
to any browser. `X-Pulse-Internal-Key` closes that hole.

### 39.8 Added: retry and reply endpoints

`POST /api/missions/{id}/retry` implements the recovery half of the error
policy. `POST /api/missions/{id}/reply` feeds the simulated merchant response
into a waiting Grow mission, making the qualification step a real backend
transition rather than a frontend animation.

---

## 40. Product Thesis

Paytm Pulse is not:

> "An AI chatbot for Paytm."

It is:

> **"An AI workforce where specialised teammates own measurable jobs."**

The core loop:

```
GIVE AI A JOB
      ▼
UNDERSTAND CONTEXT
      ▼
MAKE A DECISION
      ▼
CHECK POLICY
      ▼
ACT AUTONOMOUSLY  or  ASK A HUMAN
      ▼
VERIFY
      ▼
MEASURE OUTCOME
```

The distinction that matters:

> **AI teammates with ownership, not conversations.**

---

## 41. Prototype Disclosure

This prototype uses a **simulated Paytm integration boundary**. It has no access
to Paytm production systems.

All customers, merchants, transactions, policies, support cases and business
outcomes shown are **fictional demo data**. The dataset makes no claim about
which real businesses accept Paytm, and lead scores are computed from seeded
demo attributes rather than real acquisition signals.

This prototype does **not** claim:

- access to Paytm's private databases,
- production Paytm API access,
- reliable detection of Paytm usage from public internet data,
- real customer-resolution performance,
- real merchant-conversion performance.

The ₹1,000 approval threshold is a **configurable hackathon demo policy**
(`REFUND_APPROVAL_THRESHOLD`), not a statement about Paytm's production policy.
Sentiment classification routes workflows; it is not a psychological assessment.

The architecture demonstrates how this workflow would integrate with production
systems through the defined adapters and APIs.

> **The prototype demonstrates the workforce architecture and controlled
> autonomy — not production Paytm infrastructure.**
