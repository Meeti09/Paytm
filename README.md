# Paytm Pulse

### The AI workforce for Paytm

Two AI teammates that own business outcomes instead of answering questions.

| Teammate | Mission |
|---|---|
| **Resolve** | Own every customer issue until it is verified as resolved. |
| **Grow** | Find and convert the next generation of Paytm merchants. |

> **Give AI a job, not a prompt.**

### ▶ Live demo — **https://paytm-pulse-eight.vercel.app**

Press **Reset demo**, then run Scenario B and approve it in the queue.

> The API is on Render's free tier and sleeps after ~15 minutes idle. The first
> request then takes ~50s to wake it. **Before demoing, open
> [the API health check](https://paytm-pulse-api.onrender.com/api/health) once
> and wait for it to return** — after that everything is instant.

📄 **[Proposed Solution](Docs/Proposed-Solution.md)** — the submission write-up:
problem, approach, differentiators, measurable outcomes, limitations.
Also: [Architecture](Docs/Architecture.md) · [Design system](Docs/Design.md) ·
[n8n workflows](n8n/README.md) · [Deployment](#deployment).

---

## What this actually does

Every mission runs the same loop, and every step of it is real:

```
objective → understand context → decide → check policy
         → act autonomously  OR  ask a human
         → verify → measurable outcome
```

The thing that makes it a *teammate* rather than a chatbot is the middle:

- The model **proposes** an action and writes the customer-facing wording.
- A **deterministic policy engine** decides whether that action may execute.
- **n8n** executes it against the payments boundary.
- The system **verifies** the result by reading the ledger back.

The model never authorises itself, never invents an amount, and cannot skip an
approval. Those are Python rules in `backend/app/policy/risk.py`, not a prompt.

---

## Three screens

| Screen | Question it answers |
|---|---|
| **Live Mission** | What is the teammate doing right now, on what evidence, and what did it decide? |
| **Approval Queue** | Why did the AI stop, and what happens if I approve? |
| **Outcomes** | What did the AI actually accomplish? |

There is no chat box anywhere in the product.

---

## Quick start

Two terminals. No API keys required — the full demo runs on deterministic local
fallbacks, and the header shows which mode each integration is in.

**Backend**

```bash
cd backend && python -m venv .venv && .venv/Scripts/python -m pip install -r requirements.txt && .venv/Scripts/python -m uvicorn app.main:app --port 8000
```

**Frontend**

```bash
cd frontend && npm install && npm run dev
```

Open <http://localhost:3000>. The database seeds itself on first boot.

On macOS/Linux use `.venv/bin/python` instead of `.venv/Scripts/python`.

### Adding real integrations

```bash
cp .env.example .env
```

Paste your own keys. Every one is optional and independent:

| Variable | Effect when set |
|---|---|
| `LLM_PROVIDER` + `LLM_API_KEY` + `LLM_MODEL` | The model writes the decision rationale and message copy |
| `SARVAM_API_KEY` | Real language ID, translation and intent classification |
| `COGNEE_API_URL` | Graph memory recall instead of database-derived context |
| `N8N_BASE_URL` | Actions execute through n8n instead of the local runner — see [`n8n/README.md`](n8n/README.md) |

When one is unavailable the mission degrades to a labelled fallback rather than
breaking — except a configured-but-unreachable LLM, which pauses the mission
with a retry, because silently substituting a different reasoner would be a lie.

---

## The 4-minute demo

Click **Reset demo** first — it clears every mission, approval, event and lead,
and restores the seeded records, including any transaction that was refunded on
a previous run.

**0:00 — Framing.** Two teammates, two jobs. Resolve owns customer problems.
Grow owns merchant acquisition.

**0:30 — Resolve, Scenario B.** A Hindi message: *"₹2,000 कट गया लेकिन merchant
को नहीं मिला."* Watch the timeline: language detected, intent classified,
customer identified, transaction found, merchant settlement failed, policy
retrieved, decision generated — then it stops:

```
Policy check: MONEY_MOVEMENT_THRESHOLD — approval required
```

**1:15 — Approve.** The Approval Queue shows what it wants to do, why it
stopped, the policy rule, the evidence, and what happens if you approve. Approve
it. The refund executes through WF3, is verified against the ledger, and the
customer is notified in Hindi.

**1:45 — Grow.** *"Find 5 high-potential merchants in Thane."* 12 evaluated,
4 qualified, 3 contacted. Open Mumbai Brew House — lead score 91, broken down by
factor. Simulate the reply *"Interested. What do I need to do?"* → qualified →
meeting booked.

**3:15 — Outcomes.** Every metric with the records it was counted from.

**3:45 —**

> We don't give AI another chat box. We give it a job.

Scenario **A** (₹500, autonomous) and Scenario **C** (angry Hindi message, ₹800 —
*under* the money threshold, escalated purely on sentiment) are worth showing if
you have time. C is the sharper governance story: the same amount that would run
autonomously gets routed to a human because of how the customer is writing.

---

## Architecture

```
                 ┌──────────────────────────────┐
                 │  Next.js — 3 screens         │
                 │  Live Mission · Approvals ·  │
                 │  Outcomes                    │
                 └──────────────┬───────────────┘
                       REST + Server-Sent Events
                 ┌──────────────▼───────────────┐
                 │  FastAPI                     │
                 │  missions · events · policy  │
                 └──────────────┬───────────────┘
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
    ┌───────────┐         ┌──────────┐        ┌──────────────┐
    │  Resolve  │         │   Grow   │        │ Policy engine│
    │   agent   │         │  agent   │        │ deterministic│
    └─────┬─────┘         └────┬─────┘        └──────┬───────┘
          └──────────┬─────────┘                     │
                     ▼                               │
        ┌────────────────────────┐                   │
        │ Sarvam · Cognee · LLM  │                   │
        └────────────────────────┘                   │
                                                     ▼
                                            ┌─────────────────┐
                                            │ n8n  (WF1–WF6)  │
                                            └────────┬────────┘
                                                     ▼
                                      Simulated Paytm boundary
                                                     │
                                          verified outcome → event
```

Third-party services are isolated behind adapters — `SarvamAdapter`,
`CogneeAdapter`, `N8nAdapter`, `LLMAdapter`, `PaytmAdapter` — so swapping
`MockPaytmAdapter` for a production implementation would change no agent code.

### Layout

```
backend/app/
├── agents/        resolve.py, grow.py, scoring.py, permissions.py, orchestrator.py
├── policy/risk.py the autonomy boundary
├── integrations/  sarvam, cognee, llm, n8n, paytm_mock
├── services/      mission, event (SSE bus), outcome aggregation
├── api/           missions, approvals, outcomes, demo, stream, paytm
└── demo/          seed.py, scenarios.py
frontend/
├── app/           page.tsx (Live Mission), approvals/, outcomes/
├── components/    PulseProvider (one SSE connection), DecisionCard, ApprovalCard, …
└── lib/           api.ts, types.ts, format.ts
n8n/workflows/     WF1–WF6, importable
```

---

## Why the numbers on the Outcomes screen are real

Nothing is hardcoded. Every figure is counted from mission, approval, action and
lead records, and each one carries the query it came from:

```
Processed            missions in a terminal state
Resolved autonomously   missions with result resolved_autonomously
Escalated            missions that created an approval request
Human approvals      approval records marked approved
Autonomy rate        autonomous ÷ processed — "—" when nothing has run
```

The Grow figures are equally derived. The seeded dataset holds 12 unonboarded
Thane merchants; the scorer qualifies 4 of them and puts 3 above the outreach
bar. Those numbers come out of the formula in `agents/scoring.py`, not a
constant — change a merchant's estimated volume and they change.

Run the acceptance test to see the whole chain verified end to end:

```bash
cd backend && .venv/Scripts/python scripts/smoke_test.py
```

It drives the public API only: reset → autonomous resolution → escalation →
approve → sentiment escalation → reject → Grow → takeover → outcomes → reset,
asserting at each step that the ledger changed only when it should have.

---

## Deployment

| Piece | Host | URL |
|---|---|---|
| Frontend (Next.js) | Vercel | https://paytm-pulse-eight.vercel.app |
| Backend (FastAPI) | Render | https://paytm-pulse-api.onrender.com |

Both auto-deploy from `main`.

**Why the backend isn't on Vercel.** It needs a persistent process, and
serverless breaks it in four places: missions run as background `asyncio` tasks
that outlive the HTTP response; the event bus holds in-memory SSE subscribers,
so a client on one instance would never see events published from another;
SQLite needs a writable filesystem; and the task registry is per-process. Even
with Postgres and Redis swapped in, Vercel has no long-running worker runtime
for the agent loop. Render runs it as an ordinary web service, which suits all
four. The blueprint is in [`render.yaml`](render.yaml).

The frontend reaches the backend through `NEXT_PUBLIC_API_URL` (a URL, not a
secret). The backend allows the Vercel origin via `CORS_ORIGIN_REGEX`, which
covers preview deployments too.

Verify the deployment the same way you'd verify a local one:

```bash
cd backend && PULSE_API_URL=https://paytm-pulse-api.onrender.com .venv/Scripts/python scripts/smoke_test.py
```

Render's free tier has an ephemeral filesystem, so the SQLite demo dataset is
recreated on each restart — the same state **Reset demo** produces. Attach a
Postgres instance and set `DATABASE_URL` to persist mission history; the psycopg
driver is already in `requirements.txt`.

---

## Safety boundaries

- The policy engine is deterministic Python. The LLM cannot override it, and an
  action type the system does not recognise is treated as unauthorised and routed
  to a human.
- Refund amounts come from the transaction ledger, never from model output. The
  payments boundary rejects a refund whose amount does not match the record.
- Approval state is validated server-side: a decided approval cannot be decided
  again, and an approval cannot be applied to a mission that has moved on.
- Mutating `/paytm/*` endpoints require an internal service key that only the
  execution layer holds. A browser cannot move money.
- No secret reaches the frontend. The only `NEXT_PUBLIC_*` value is the API URL.

---

## Prototype disclosure

This prototype uses a **simulated Paytm integration boundary**. It has no access
to Paytm production systems.

All customers, merchants, transactions, policies and support cases are
**fictional demo data**, and the dataset makes no claim about which real
businesses accept Paytm. Lead scores are computed from seeded demo attributes,
not from real acquisition signals.

The ₹1,000 approval threshold is a **configurable hackathon demo policy**
(`REFUND_APPROVAL_THRESHOLD`), not a statement about Paytm's production policy.

Sentiment classification routes workflows. It is not a psychological assessment.
