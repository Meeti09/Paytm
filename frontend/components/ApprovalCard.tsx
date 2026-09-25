"use client";

import Link from "next/link";
import { ArrowUpRight, Check, Scale, UserCheck, X } from "lucide-react";
import { ruleLabel, shortDateTime } from "@/lib/format";
import type { Approval } from "@/lib/types";
import { AgentBadge, Button, Card, RiskBadge, SectionHeader } from "./ui";

/**
 * One pending decision. Answers: what does the AI want to do, why, which policy
 * rule stopped it, what evidence supports it, and what happens if approved.
 */
export function ApprovalCard({
  approval,
  onApprove,
  onReject,
  onTakeover,
  busy,
}: {
  approval: Approval;
  onApprove: () => void;
  onReject: () => void;
  onTakeover: () => void;
  busy: boolean;
}) {
  const pending = approval.status === "pending";

  return (
    <Card accent={approval.risk_level}>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-hairline px-5 py-3">
        <div className="flex flex-wrap items-center gap-2.5">
          <RiskBadge risk={approval.risk_level} />
          <AgentBadge agent={approval.agent} />
          <Link
            href="/"
            className="tnum inline-flex items-center gap-1 text-[12px] font-semibold text-muted hover:text-[var(--paytm-blue-deep)]"
          >
            {approval.mission_id}
            <ArrowUpRight size={12} strokeWidth={2.4} />
          </Link>
        </div>
        <span className="tnum text-[11px] text-muted">
          {approval.id} · raised {shortDateTime(approval.created_at)}
        </span>
      </div>

      <div className="px-5 py-4">
        <p className="text-[12px] font-semibold text-muted">
          {approval.agent === "resolve" ? "Resolve" : "Grow"} wants to execute
        </p>
        <h3 className="mt-0.5 text-[22px] font-bold leading-tight text-ink">
          {approval.title}
        </h3>
        {approval.subject ? (
          <p className="mt-1 text-[13px] text-muted">{approval.subject}</p>
        ) : null}

        <div className="mt-4 grid gap-5 lg:grid-cols-2">
          <div className="space-y-4">
            <div>
              <p className="label mb-1.5">Why it stopped</p>
              <div className="rounded-[8px] border border-hairline bg-[#fbfcfe] px-3.5 py-3">
                <div className="flex items-start gap-2">
                  <Scale
                    size={14}
                    strokeWidth={2.2}
                    color="var(--paytm-blue-deep)"
                    className="mt-[2px] shrink-0"
                  />
                  <div className="min-w-0">
                    <p className="text-[12px] font-bold uppercase tracking-[0.05em] text-ink">
                      {ruleLabel(approval.policy_rule)}
                    </p>
                    <p className="mt-1 text-[12.5px] leading-relaxed text-muted">
                      {approval.reason}
                    </p>
                  </div>
                </div>
                {approval.triggered_rules.length > 1 ? (
                  <ul className="mt-2.5 space-y-1 border-t border-hairline pt-2.5">
                    {approval.triggered_rules.slice(1).map((rule) => (
                      <li key={rule.rule} className="text-[12px] text-muted">
                        <span className="font-semibold text-ink">
                          {ruleLabel(rule.rule)}
                        </span>{" "}
                        · {rule.detail}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            </div>

            {approval.impact ? (
              <div>
                <p className="label mb-1.5">If you approve</p>
                <p className="text-[13px] leading-relaxed text-ink">
                  {approval.impact}
                </p>
              </div>
            ) : null}
          </div>

          <div>
            <p className="label mb-1.5">Evidence</p>
            <ul className="space-y-1.5">
              {approval.evidence.map((item, index) => (
                <li
                  key={index}
                  className="flex items-start gap-2 text-[13px] leading-snug text-ink"
                >
                  <Check
                    size={13}
                    strokeWidth={2.6}
                    color="var(--success)"
                    className="mt-[3px] shrink-0"
                  />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
            <div className="mt-3 border-t border-hairline pt-3">
              <p className="label">Teammate recommendation</p>
              <p
                className="mt-0.5 text-[13px] font-bold"
                style={{
                  color:
                    approval.ai_recommendation === "APPROVE"
                      ? "var(--success)"
                      : "#b3541e",
                }}
              >
                {approval.ai_recommendation}
              </p>
            </div>
          </div>
        </div>
      </div>

      {pending ? (
        <div className="flex flex-wrap items-center gap-2 border-t border-hairline px-5 py-3">
          <Button variant="primary" icon={Check} loading={busy} onClick={onApprove}>
            Approve
          </Button>
          <Button variant="danger" icon={X} disabled={busy} onClick={onReject}>
            Reject
          </Button>
          <Button icon={UserCheck} disabled={busy} onClick={onTakeover}>
            Take over
          </Button>
          <p className="ml-auto text-[11.5px] text-muted">
            The action executes only after you approve. Nothing has moved yet.
          </p>
        </div>
      ) : (
        <div className="border-t border-hairline px-5 py-3">
          <SectionHeader
            title={`${approval.status} by ${approval.reviewed_by ?? "operator"} · ${shortDateTime(approval.reviewed_at)}`}
          />
        </div>
      )}
    </Card>
  );
}
