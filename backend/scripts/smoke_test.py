"""End-to-end acceptance test for the Paytm Pulse demo.

Drives the exact sequence a judge will see, through the public API only:

    RESET -> Resolve autonomous -> Resolve escalation -> Approve
          -> Resolve sentiment escalation -> Reject
          -> Grow discovery -> reply -> meeting booked
          -> Take over -> Outcomes -> RESET

Run the backend, then:  python scripts/smoke_test.py
"""

from __future__ import annotations

import sys
import time

import httpx

BASE = "http://127.0.0.1:8000"
TIMEOUT = 60.0
failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    mark = "PASS" if condition else "FAIL"
    print(f"  [{mark}] {label}" + (f" — {detail}" if detail else ""))
    if not condition:
        failures.append(label)


def wait_for(client: httpx.Client, mission_id: str, *statuses: str, limit: float = 45.0):
    deadline = time.time() + limit
    last = None
    while time.time() < deadline:
        last = client.get(f"{BASE}/api/missions/{mission_id}").json()
        if last["status"] in statuses:
            return last
        time.sleep(0.4)
    raise AssertionError(
        f"{mission_id} never reached {statuses}; last status={last and last['status']}"
    )


def timeline(mission: dict) -> list[str]:
    return [e["event_type"] for e in mission.get("events", [])]


def main() -> int:
    with httpx.Client(timeout=TIMEOUT) as client:
        print("\n== Reset ==")
        reset = client.post(f"{BASE}/api/demo/reset").json()
        check("demo reset", reset.get("reset") is True)
        check(
            "dataset reseeded",
            reset["seeded"]["merchants"] == 17 and reset["seeded"]["transactions"] == 8,
            str(reset["seeded"]),
        )

        # ---------------------------------------------------------------
        print("\n== Resolve A — autonomous ==")
        a = client.post(f"{BASE}/api/demo/resolve", json={"scenario": "A"}).json()
        a = wait_for(client, a["id"], "completed", "failed", "needs_attention")
        check("A completed", a["status"] == "completed", a["status"])
        check("A resolved autonomously", a["result"] == "resolved_autonomously", str(a["result"]))
        check("A no approval was created", a["pending_approval_id"] is None)
        events = timeline(a)
        for required in ("ACTION_EXECUTED", "ACTION_VERIFIED", "MESSAGE_SENT"):
            check(f"A emitted {required}", required in events)
        tx = client.get(f"{BASE}/paytm/transaction/TX-1001").json()
        check("A refund hit the ledger", tx["status"] == "refunded", tx["status"])

        # ---------------------------------------------------------------
        print("\n== Resolve B — money threshold -> approval ==")
        b = client.post(f"{BASE}/api/demo/resolve", json={"scenario": "B"}).json()
        b = wait_for(client, b["id"], "waiting_approval", "completed", "failed")
        check("B stopped for approval", b["status"] == "waiting_approval", b["status"])
        check("B decision is high risk", (b["decision"] or {}).get("risk_level") == "high")
        check(
            "B cites the money rule",
            (b["decision"] or {}).get("policy_rule") == "MONEY_MOVEMENT_THRESHOLD",
            str((b["decision"] or {}).get("policy_rule")),
        )
        check("B amount came from the ledger", (b["decision"] or {}).get("amount") == 2000.0)

        queue = client.get(f"{BASE}/api/approvals").json()
        check("approval queue has 1 pending", queue["pending_count"] == 1, str(queue["pending_count"]))
        approval = next(x for x in queue["approvals"] if x["mission_id"] == b["id"])
        check("approval carries evidence", len(approval["evidence"]) >= 3, str(len(approval["evidence"])))
        check("approval carries policy detail", bool(approval["policy_detail"]))
        check("approval names a reviewer action", approval["ai_recommendation"] in ("APPROVE", "REVIEW"))

        tx_before = client.get(f"{BASE}/paytm/transaction/TX-1004").json()
        check("B ledger untouched before approval", tx_before["status"] != "refunded", tx_before["status"])

        # A browser must not be able to move money directly.
        direct = client.post(
            f"{BASE}/paytm/refund",
            json={"transaction_id": "TX-1004", "amount": 2000.0, "reference": "browser"},
        )
        check("direct refund without the service key is refused", direct.status_code == 401, str(direct.status_code))

        approved = client.post(
            f"{BASE}/api/approvals/{approval['id']}/approve", json={"reviewer": "Ops Lead"}
        )
        check("approve accepted", approved.status_code == 200, str(approved.status_code))
        again = client.post(
            f"{BASE}/api/approvals/{approval['id']}/approve", json={"reviewer": "Ops Lead"}
        )
        check("double approval refused", again.status_code == 409, str(again.status_code))

        b = wait_for(client, b["id"], "completed", "failed", "needs_attention")
        check("B completed after approval", b["status"] == "completed", b["status"])
        check("B result is resolved_with_approval", b["result"] == "resolved_with_approval", str(b["result"]))
        check("B marked human involved", b["human_involved"] is True)
        tx_after = client.get(f"{BASE}/paytm/transaction/TX-1004").json()
        check("B refund executed after approval", tx_after["status"] == "refunded", tx_after["status"])
        check("B emitted APPROVAL_GRANTED", "APPROVAL_GRANTED" in timeline(b))

        # ---------------------------------------------------------------
        print("\n== Resolve C — sentiment -> approval, then reject ==")
        c = client.post(f"{BASE}/api/demo/resolve", json={"scenario": "C"}).json()
        c = wait_for(client, c["id"], "waiting_approval", "completed", "failed")
        check("C stopped for approval", c["status"] == "waiting_approval", c["status"])
        decision = c["decision"] or {}
        check(
            "C escalated on sentiment, not amount",
            decision.get("policy_rule") == "NEGATIVE_SENTIMENT_REVIEW",
            str(decision.get("policy_rule")),
        )
        check("C amount is below the threshold", decision.get("amount") == 800.0, str(decision.get("amount")))
        check(
            "C read the prior cases from the database",
            (c["context"].get("history") or {}).get("prior_unresolved_cases") == 2,
            str((c["context"].get("history") or {}).get("prior_unresolved_cases")),
        )

        c_approval = client.get(f"{BASE}/api/approvals").json()["approvals"][0]
        client.post(f"{BASE}/api/approvals/{c_approval['id']}/reject", json={"reviewer": "Ops Lead"})
        c = wait_for(client, c["id"], "completed", "failed")
        check("C completed after rejection", c["status"] == "completed", c["status"])
        check("C result is rejected_by_human", c["result"] == "rejected_by_human", str(c["result"]))
        tx_c = client.get(f"{BASE}/paytm/transaction/TX-1007").json()
        check("C refund NOT executed after rejection", tx_c["status"] != "refunded", tx_c["status"])

        # ---------------------------------------------------------------
        print("\n== Grow — discover, score, contact, qualify, book ==")
        g = client.post(
            f"{BASE}/api/demo/grow", json={"location": "Thane", "target_count": 5}
        ).json()
        g = wait_for(client, g["id"], "waiting_response", "completed", "failed", limit=60)
        check("Grow is waiting on a merchant reply", g["status"] == "waiting_response", g["status"])
        stats = (g["context"] or {}).get("stats", {})
        check("12 merchants evaluated", stats.get("evaluated") == 12, str(stats.get("evaluated")))
        check("4 qualified", stats.get("qualified") == 4, str(stats.get("qualified")))
        check("3 contacted", stats.get("contacted") == 3, str(stats.get("contacted")))
        leads = (g["context"] or {}).get("leads", [])
        top = leads[0] if leads else {}
        check("top lead is Mumbai Brew House at 91", top.get("name") == "Mumbai Brew House" and top.get("score") == 91, f"{top.get('name')} {top.get('score')}")
        check("score is explained", len(top.get("breakdown", [])) == 5, str(len(top.get("breakdown", []))))
        check("outreach was drafted", bool(top.get("outreach_message")))

        focus = (g["context"] or {}).get("focus_lead_id")
        client.post(
            f"{BASE}/api/missions/{g['id']}/reply",
            json={"lead_id": focus, "text": "Interested. What do I need to do?"},
        )
        g = wait_for(client, g["id"], "completed", "failed", "waiting_approval", limit=60)
        check("Grow completed", g["status"] == "completed", g["status"])
        check("Grow booked a meeting", g["result"] == "meeting_booked", str(g["result"]))
        check("MEETING_BOOKED emitted", "MEETING_BOOKED" in timeline(g))
        final_stats = (g["context"] or {}).get("stats", {})
        check("1 sales-ready", final_stats.get("sales_ready") == 1, str(final_stats.get("sales_ready")))
        check("1 meeting booked", final_stats.get("meetings_booked") == 1, str(final_stats.get("meetings_booked")))

        # ---------------------------------------------------------------
        print("\n== Take over ==")
        t = client.post(f"{BASE}/api/demo/resolve", json={"scenario": "B"}).json()
        time.sleep(1.2)
        client.post(f"{BASE}/api/missions/{t['id']}/takeover", json={"operator": "Ops Lead"})
        t = wait_for(client, t["id"], "human_takeover", limit=20)
        check("takeover recorded", t["status"] == "human_takeover", t["status"])
        check("HUMAN_TAKEOVER emitted", "HUMAN_TAKEOVER" in timeline(t))

        # ---------------------------------------------------------------
        print("\n== Outcomes ==")
        out = client.get(f"{BASE}/api/outcomes").json()
        r = {m["label"]: m["value"] for m in out["resolve"]["metrics"]}
        gm = {m["label"]: m["value"] for m in out["grow"]["metrics"]}
        print("   resolve:", r, "autonomy:", out["resolve"]["autonomy_rate"])
        print("   grow   :", gm)
        check("processed counts 4 terminal missions", r["Processed"] == 4, str(r["Processed"]))
        check("1 resolved autonomously", r["Resolved autonomously"] == 1, str(r["Resolved autonomously"]))
        # B and C each raised an approval. The taken-over mission was stopped
        # before it reached the approval boundary, so it is not an escalation.
        check("2 escalated", r["Escalated"] == 2, str(r["Escalated"]))
        check("1 human approval", r["Human approvals"] == 1, str(r["Human approvals"]))
        check("0 failed", r["Failed"] == 0, str(r["Failed"]))
        taken_over = next(m for m in out["missions"] if m["result"] == "handled_by_human")
        check("takeover counted as human involved", taken_over["human_involved"] is True)
        check("autonomy rate computed", out["resolve"]["autonomy_rate"] == 25, str(out["resolve"]["autonomy_rate"]))
        check("grow evaluated 12", gm["Merchants evaluated"] == 12, str(gm["Merchants evaluated"]))
        check("grow meetings 1", gm["Meetings booked"] == 1, str(gm["Meetings booked"]))
        check("mission table populated", len(out["missions"]) == 5, str(len(out["missions"])))

        # ---------------------------------------------------------------
        print("\n== Reset is repeatable ==")
        client.post(f"{BASE}/api/demo/reset")
        out2 = client.get(f"{BASE}/api/outcomes").json()
        r2 = {m["label"]: m["value"] for m in out2["resolve"]["metrics"]}
        check("metrics cleared", r2["Processed"] == 0, str(r2["Processed"]))
        check("autonomy rate is None, not 0%", out2["resolve"]["autonomy_rate"] is None)
        check("missions cleared", len(out2["missions"]) == 0, str(len(out2["missions"])))
        tx_reset = client.get(f"{BASE}/paytm/transaction/TX-1004").json()
        check("ledger restored", tx_reset["status"] == "debited_not_settled", tx_reset["status"])
        check(
            "approvals cleared",
            client.get(f"{BASE}/api/approvals", params={"status": "all"}).json()["approvals"] == [],
        )

    print("\n" + "=" * 60)
    if failures:
        print(f"{len(failures)} CHECK(S) FAILED:")
        for name in failures:
            print(f"  - {name}")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
