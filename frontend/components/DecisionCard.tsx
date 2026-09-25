"use client";

import { Check, Cpu, Scale } from "lucide-react";
import { ruleLabel } from "@/lib/format";
import type { Decision } from "@/lib/types";
import { Card, RiskBadge, SectionHeader, VerdictBadge } from "./ui";

const SOURCE_LABEL: Record<string, string> = {
  deterministic_reasoner: "Deterministic reasoner",
};

function sourceLabel(source: string): string {
  if (SOURCE_LABEL[source]) return SOURCE_LABEL[source];
  if (source.startsWith("llm:")) return source.slice(4);
  return source;
}

/**
 * What the teammate decided, on what evidence, and what the policy engine did
 * with it. Actions and evidence only — no chain-of-thought.
 */
export function DecisionCard({ decision }: { decision: Decision }) {
  const requiresApproval = decision.verdict === "REQUIRES_APPROVAL";
  const resolved = decision.resolved === true;

  return (
    <Card accent={resolved ? "low" : requiresApproval ? decision.risk_level : "low"}>
      <div className="flex items-center justify-between border-b border-hairline px-5 py-3">
        <SectionHeader title="AI decision" />
        <div className="flex items-center gap-2">
          <RiskBadge risk={decision.risk_level} />
          {resolved ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-[#e6f6ee] px-2.5 py-1 text-[11px] font-bold uppercase tracking-[0.05em] text-[#07713f]">
              <Check size={12} strokeWidth={2.5} />
              Executed
            </span>
          ) : (
            <VerdictBadge verdict={decision.verdict} />
          )}
        </div>
      </div>

      <div className="space-y-4 px-5 py-4">
        <div>
          <h3 className="text-[20px] font-bold leading-tight text-ink">
            {decision.title}
          </h3>
          <p className="mt-1.5 text-[13px] leading-relaxed text-muted">
            {decision.reason}
          </p>
        </div>

        {decision.evidence?.length ? (
          <div>
            <p className="label mb-1.5">Evidence</p>
            <ul className="space-y-1">
              {decision.evidence.map((item, index) => (
                <li
                  key={index}
                  className="flex gap-2 text-[13px] leading-snug text-ink"
                >
                  <span className="tnum mt-[1px] shrink-0 text-[11px] font-bold text-muted">
                    {index + 1}
                  </span>
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        ) : null}

        <div className="rounded-[8px] border border-hairline bg-[#f8fafc] px-3.5 py-3">
          <div className="flex items-start gap-2">
            <Scale
              size={14}
              strokeWidth={2.2}
              color="var(--paytm-blue-deep)"
              className="mt-[2px] shrink-0"
            />
            <div className="min-w-0">
              <p className="text-[12px] font-bold uppercase tracking-[0.05em] text-ink">
                {ruleLabel(decision.policy_rule)}
              </p>
              <p className="mt-1 text-[12.5px] leading-relaxed text-muted">
                {decision.policy_detail}
              </p>
            </div>
          </div>

          {decision.triggered_rules?.length > 1 ? (
            <ul className="mt-2.5 space-y-1 border-t border-hairline pt-2.5">
              {decision.triggered_rules.map((rule) => (
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

        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-hairline pt-3">
          <p
            className="text-[13px] font-bold"
            style={{
              color:
                requiresApproval && !resolved
                  ? "var(--danger)"
                  : "var(--success)",
            }}
          >
            {decision.next}
          </p>
          <span
            className="inline-flex items-center gap-1.5 text-[11px] font-medium text-muted"
            title="Which reasoner produced this decision"
          >
            <Cpu size={12} strokeWidth={2.2} />
            {sourceLabel(decision.source)}
          </span>
        </div>
      </div>
    </Card>
  );
}
