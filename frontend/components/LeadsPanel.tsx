"use client";

import { Fragment, useState } from "react";
import { ChevronDown, ChevronRight, MessageSquare, Send } from "lucide-react";
import { compactInr } from "@/lib/format";
import type { LeadView, Mission } from "@/lib/types";
import { Button, Card, SectionHeader } from "./ui";

const STAGE_STYLE: Record<string, { label: string; color: string; bg: string }> = {
  scored: { label: "Scored", color: "#5c6b7a", bg: "#eef1f5" },
  qualified: { label: "Qualified", color: "#01579b", bg: "#e4f6fd" },
  contacted: { label: "Contacted", color: "#01579b", bg: "#e4f6fd" },
  responded: { label: "Replied", color: "#b3541e", bg: "#fdf1e0" },
  sales_ready: { label: "Sales-ready", color: "#07713f", bg: "#e6f6ee" },
  meeting_booked: { label: "Meeting booked", color: "#07713f", bg: "#e6f6ee" },
  disqualified: { label: "Parked", color: "#5c6b7a", bg: "#eef1f5" },
};

function StagePill({ stage }: { stage: string }) {
  const style = STAGE_STYLE[stage] ?? STAGE_STYLE.scored;
  return (
    <span
      className="inline-flex whitespace-nowrap rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.05em]"
      style={{ color: style.color, background: style.bg }}
    >
      {style.label}
    </span>
  );
}

function ScoreBreakdown({ lead }: { lead: LeadView }) {
  return (
    <div className="space-y-1.5">
      {lead.breakdown.map((factor) => (
        <div key={factor.factor} className="flex items-center gap-3">
          <span className="w-[130px] shrink-0 text-[12px] text-muted">
            {factor.factor}
          </span>
          <div className="h-[5px] w-[90px] shrink-0 overflow-hidden rounded-[3px] bg-hairline">
            <div
              className="h-full rounded-[3px] bg-[var(--paytm-blue)]"
              style={{ width: `${(factor.points / factor.max) * 100}%` }}
            />
          </div>
          <span className="tnum w-[42px] shrink-0 text-[12px] font-bold text-ink">
            {factor.points}/{factor.max}
          </span>
          <span className="min-w-0 flex-1 truncate text-[12px] text-muted">
            {factor.detail}
          </span>
        </div>
      ))}
    </div>
  );
}

export function LeadsPanel({
  mission,
  onReply,
  replying,
}: {
  mission: Mission;
  onReply: (leadId: string, text: string) => void;
  replying: boolean;
}) {
  const leads = mission.context.leads ?? [];
  const focusId = mission.context.focus_lead_id ?? null;
  const [expanded, setExpanded] = useState<string | null>(focusId);
  const [draft, setDraft] = useState("");

  if (!leads.length) return null;

  const awaitingReply = mission.status === "waiting_response";
  const suggestions = mission.context.suggested_replies ?? [];

  return (
    <Card>
      <div className="flex items-center justify-between border-b border-hairline px-5 py-3">
        <SectionHeader title="Merchant pipeline" />
        <span className="tnum text-[11px] font-semibold text-muted">
          {leads.length} evaluated · ranked by lead score
        </span>
      </div>

      <div className="max-h-[430px] overflow-y-auto">
        <table className="w-full border-collapse text-left">
          <thead className="sticky top-0 z-10 bg-surface">
            <tr className="border-b border-hairline">
              <th className="w-8" />
              <th className="px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.05em] text-muted">
                Merchant
              </th>
              <th className="px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.05em] text-muted">
                Category
              </th>
              <th className="px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.05em] text-muted">
                Est. volume
              </th>
              <th className="px-3 py-2 text-right text-[11px] font-semibold uppercase tracking-[0.05em] text-muted">
                Score
              </th>
              <th className="px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.05em] text-muted">
                Stage
              </th>
            </tr>
          </thead>
          <tbody>
            {leads.map((lead) => {
              const open = expanded === lead.id;
              const isFocus = lead.id === focusId;
              return (
                <Fragment key={lead.id}>
                  <tr
                    onClick={() => setExpanded(open ? null : lead.id)}
                    className={`cursor-pointer border-b border-hairline transition-colors hover:bg-[#f8fafc] ${
                      isFocus ? "bg-[#f3fbfe]" : ""
                    }`}
                  >
                    <td className="pl-4 align-middle">
                      {open ? (
                        <ChevronDown size={14} strokeWidth={2.4} color="var(--ink-muted)" />
                      ) : (
                        <ChevronRight size={14} strokeWidth={2.4} color="var(--ink-muted)" />
                      )}
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="text-[13px] font-semibold text-ink">
                        {lead.name}
                      </div>
                      <div className="text-[11.5px] text-muted">{lead.location}</div>
                    </td>
                    <td className="px-3 py-2.5 text-[12.5px] text-muted">
                      {lead.category}
                    </td>
                    <td className="tnum px-3 py-2.5 text-[12.5px] text-muted">
                      {compactInr(lead.estimated_volume)}/mo
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      <span className="tnum text-[17px] font-bold text-ink">
                        {lead.score}
                      </span>
                      <span className="ml-1 text-[11px] text-muted">
                        {lead.opportunity}
                      </span>
                    </td>
                    <td className="px-3 py-2.5">
                      <StagePill stage={lead.stage} />
                    </td>
                  </tr>

                  {open ? (
                    <tr className="border-b border-hairline">
                      <td colSpan={6} className="bg-[#fbfcfe] px-5 py-4">
                        <div className="grid gap-5 lg:grid-cols-2">
                          <div className="space-y-3">
                            <div>
                              <p className="label mb-1.5">Why selected</p>
                              <ul className="space-y-1">
                                {lead.reasons.map((reason, index) => (
                                  <li
                                    key={index}
                                    className="flex gap-2 text-[12.5px] leading-snug text-ink"
                                  >
                                    <span className="text-muted">•</span>
                                    {reason}
                                  </li>
                                ))}
                              </ul>
                            </div>
                            <div>
                              <p className="label mb-1.5">Score breakdown</p>
                              <ScoreBreakdown lead={lead} />
                            </div>
                          </div>

                          <div className="space-y-3">
                            {lead.outreach_message ? (
                              <div>
                                <p className="label mb-1.5">
                                  Outreach sent · simulated channel
                                </p>
                                <p className="rounded-[8px] border border-hairline bg-surface px-3 py-2.5 text-[12.5px] leading-relaxed text-ink">
                                  {lead.outreach_message}
                                </p>
                              </div>
                            ) : null}

                            {lead.response_message ? (
                              <div>
                                <p className="label mb-1.5">Merchant reply</p>
                                <p className="rounded-[8px] border border-hairline bg-surface px-3 py-2.5 text-[12.5px] leading-relaxed text-ink">
                                  {lead.response_message}
                                </p>
                              </div>
                            ) : null}

                            {lead.qualification_note ? (
                              <div>
                                <p className="label mb-1.5">Qualification</p>
                                <p className="text-[12.5px] leading-relaxed text-ink">
                                  {lead.qualification_note}
                                </p>
                              </div>
                            ) : null}

                            <div className="flex flex-wrap gap-x-6 gap-y-2 border-t border-hairline pt-3">
                              <div>
                                <p className="label">Next action</p>
                                <p className="mt-0.5 text-[12.5px] font-semibold text-ink">
                                  {lead.next_action || "—"}
                                </p>
                              </div>
                              {lead.meeting_slot ? (
                                <div>
                                  <p className="label">Meeting</p>
                                  <p className="mt-0.5 text-[12.5px] font-semibold text-[var(--success)]">
                                    {lead.meeting_slot}
                                  </p>
                                </div>
                              ) : null}
                              <div>
                                <p className="label">Contact</p>
                                <p className="mt-0.5 text-[12.5px] text-ink">
                                  {lead.contact || "None on record"}
                                </p>
                              </div>
                            </div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {awaitingReply && focusId ? (
        <div className="border-t border-hairline bg-[#fbfcfe] px-5 py-4">
          <div className="flex items-center gap-2">
            <MessageSquare size={14} strokeWidth={2.2} color="var(--paytm-blue-deep)" />
            <p className="text-[13px] font-semibold text-ink">
              Simulate a merchant reply
            </p>
          </div>
          <p className="mt-1 text-[12px] text-muted">
            Grow is waiting on{" "}
            {leads.find((l) => l.id === focusId)?.name ?? "the top merchant"}. The
            reply is fed to the backend, qualified, and drives the next step.
          </p>

          <div className="mt-3 flex flex-wrap gap-2">
            {suggestions.map((text) => (
              <Button
                key={text}
                size="sm"
                variant={text.toLowerCase().includes("interested") && !text.toLowerCase().includes("not") ? "primary" : "secondary"}
                disabled={replying}
                onClick={() => onReply(focusId, text)}
              >
                {text}
              </Button>
            ))}
          </div>

          <div className="mt-3 flex gap-2">
            <input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && draft.trim()) {
                  onReply(focusId, draft.trim());
                  setDraft("");
                }
              }}
              placeholder="Or type the merchant's reply…"
              className="flex-1 rounded-[8px] border border-hairline bg-surface px-3 py-2 text-[13px] text-ink outline-none placeholder:text-muted focus:border-[var(--paytm-blue)]"
            />
            <Button
              icon={Send}
              variant="secondary"
              disabled={!draft.trim() || replying}
              loading={replying}
              onClick={() => {
                onReply(focusId, draft.trim());
                setDraft("");
              }}
            >
              Send
            </Button>
          </div>
        </div>
      ) : null}
    </Card>
  );
}
