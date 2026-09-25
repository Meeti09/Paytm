# n8n — the execution layer

In Paytm Pulse, **n8n is the hands of the AI**.

```
Agent decides  →  Policy engine authorises  →  n8n executes  →  Pulse verifies
```

FastAPI owns the domain logic: mission state, policy, persistence, orchestration.
n8n owns external workflow execution: lookups, refunds, notifications, CRM
updates, outreach and meeting booking against the simulated Paytm boundary.

n8n never decides whether an action is allowed. A workflow only receives an
action that the deterministic policy engine has already cleared — and, where the
policy demanded it, that a human has already approved.

## The six workflows

| File | Code | Agent | Purpose |
|---|---|---|---|
| `WF1-customer-issue-intake.json` | WF1 | Resolve | Webhook → Sarvam → normalise intent |
| `WF2-transaction-investigation.json` | WF2 | Resolve | Customer, transaction, merchant, history, eligibility, policy |
| `WF3-resolution-execution.json` | WF3 | Resolve | Execute → verify against the ledger → notify |
| `WF4-lead-discovery.json` | WF4 | Grow | Search → filter onboarded → enrich → score → rank |
| `WF5-outreach-qualification.json` | WF5 | Grow | Personalised outreach on the simulated channel |
| `WF6-followup-meeting.json` | WF6 | Grow | Book the meeting, hand off to onboarding |

## Running without n8n

If `N8N_BASE_URL` is unset, `LocalWorkflowRunner` (in
`backend/app/integrations/n8n.py`) executes the **same workflow steps** in
process, against the same boundary, returning the same response contract. The
workflow boundary is preserved either way — the app never bypasses it.

The mission timeline names which path ran, for example:

```
Refund ₹2,000 executed via WF3 (local workflow runner)
Refund ₹2,000 executed via WF3 (n8n)
```

## Running with n8n

1. Start n8n (for example `npx n8n`), then import each JSON from this folder.
2. Set these n8n environment variables:

   | Variable | Value |
   |---|---|
   | `PULSE_API_URL` | `http://localhost:8000` |
   | `INTERNAL_API_KEY` | the same value as `INTERNAL_API_KEY` in the project `.env` |
   | `SARVAM_API_KEY` | your Sarvam key (WF1 only; optional) |
   | `SARVAM_BASE_URL` | `https://api.sarvam.ai` (optional) |

3. Set `INTERNAL_API_KEY` in the project `.env` to a value you choose. It is
   generated per process when left blank, which is fine for the local runner but
   will not match n8n — so set it explicitly when using n8n.
4. Activate the workflows, then set in the project `.env`:

   ```env
   N8N_BASE_URL=http://localhost:5678
   N8N_WEBHOOK_PREFIX=/webhook/paytm-pulse
   ```

5. Restart the backend. Missions now execute through n8n, and every timeline
   entry will say `(n8n)`.

If an n8n call fails, the mission moves to **needs attention** with the error
visible and a Retry available. Failures are never reported as success.

## The security boundary

The mutating endpoints — `/paytm/refund`, `/paytm/refund/verify`,
`/paytm/notification`, `/paytm/meeting`, `/paytm/onboarding`,
`/paytm/leads/{id}/outreach` — require the `X-Pulse-Internal-Key` header. Only
the execution layer holds it. A browser cannot move money, and the frontend
never receives the key.

Read endpoints are open: they return fictional demo records.
