"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, BarChart3, Check, UserCheck } from "lucide-react";
import { usePulseStream } from "@/components/PulseProvider";
import {
  AgentBadge,
  Card,
  EmptyState,
  ErrorNotice,
  MetricCard,
  SectionHeader,
  Skeleton,
  StatusBadge,
} from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { shortDateTime } from "@/lib/format";
import type { Outcomes } from "@/lib/types";

const GOOD_RESULTS = new Set([
  "resolved_autonomously",
  "resolved_with_approval",
  "meeting_booked",
]);

export default function OutcomesPage() {
  const [outcomes, setOutcomes] = useState<Outcomes | null>(null);
  const [error, setError] = useState<string | null>(null);

  const apply = useCallback((data: Outcomes) => {
    setOutcomes(data);
    setError(null);
  }, []);

  const fail = useCallback((err: unknown) => {
    setError(err instanceof ApiError ? err.message : "Failed to load outcomes");
  }, []);

  const load = useCallback(
    () => api.outcomes().then(apply, fail),
    [apply, fail],
  );

  useEffect(() => {
    let cancelled = false;
    api.outcomes().then(
      (data) => {
        if (!cancelled) apply(data);
      },
      (err) => {
        if (!cancelled) fail(err);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [apply, fail]);

  usePulseStream({
    onOutcomesChanged: () => void load(),
    onDemoReset: () => void load(),
  });

  if (error) return <ErrorNotice title="Outcomes unavailable" body={error} />;
  if (!outcomes) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-[120px]" />
        <Skeleton className="h-[220px]" />
      </div>
    );
  }

  const { resolve, grow, missions, trace } = outcomes;
  const hasActivity = trace.missions_recorded > 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-[24px] font-bold leading-tight text-ink">Outcomes</h1>
        <p className="mt-1 max-w-3xl text-[13px] leading-relaxed text-muted">
          {outcomes.note}
        </p>
      </div>

      {/* Resolve */}
      <section className="space-y-3">
        <SectionHeader
          title="Resolve — customer resolution"
          right={
            resolve.in_flight ? (
              <span className="text-[11.5px] font-semibold text-muted">
                {resolve.in_flight} in flight
              </span>
            ) : null
          }
        />
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-6">
          {resolve.metrics.map((metric) => (
            <MetricCard
              key={metric.label}
              value={metric.value}
              label={metric.label}
              basis={metric.basis}
              // A zero is never good news or bad news — only non-zero counts
              // earn a status colour.
              tone={
                metric.value === 0
                  ? "ink"
                  : metric.label === "Resolved autonomously"
                    ? "success"
                    : metric.label === "Escalated"
                      ? "warning"
                      : metric.label === "Failed"
                        ? "danger"
                        : "ink"
              }
            />
          ))}
          <MetricCard
            value={
              resolve.autonomy_rate === null ? "—" : `${resolve.autonomy_rate}%`
            }
            label="Autonomy rate"
            basis={resolve.autonomy_rate_basis}
            tone="brand"
          />
        </div>
      </section>

      {/* Grow */}
      <section className="space-y-3">
        <SectionHeader
          title="Grow — merchant acquisition"
          right={
            grow.in_flight ? (
              <span className="text-[11.5px] font-semibold text-muted">
                {grow.in_flight} in flight
              </span>
            ) : null
          }
        />
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
          {grow.metrics.map((metric) => (
            <MetricCard
              key={metric.label}
              value={metric.value}
              label={metric.label}
              basis={metric.basis}
              tone={
                metric.value > 0 && metric.label === "Meetings booked"
                  ? "success"
                  : "ink"
              }
            />
          ))}
        </div>
      </section>

      {/* Mission table */}
      <section className="space-y-3">
        <SectionHeader title="Mission outcomes" />
        <Card>
          {missions.length === 0 ? (
            <EmptyState
              icon={BarChart3}
              title="No missions yet"
              body="Run a mission on the Live Mission screen. Every figure on this page is counted from mission, approval, action and lead records — so it stays at zero until something actually runs."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-left">
                <thead>
                  <tr className="border-b border-hairline">
                    {["Mission", "Agent", "Objective", "Result", "Human", "Completed"].map(
                      (heading) => (
                        <th
                          key={heading}
                          className="px-4 py-2.5 text-[11px] font-semibold uppercase tracking-[0.05em] text-muted"
                        >
                          {heading}
                        </th>
                      ),
                    )}
                  </tr>
                </thead>
                <tbody>
                  {missions.map((row) => (
                    <tr
                      key={row.id}
                      className="border-b border-hairline last:border-0 hover:bg-[#f8fafc]"
                    >
                      <td className="tnum px-4 py-3 text-[13px] font-semibold text-ink">
                        {row.id}
                      </td>
                      <td className="px-4 py-3">
                        <AgentBadge agent={row.agent} />
                      </td>
                      <td className="max-w-[320px] truncate px-4 py-3 text-[13px] text-muted">
                        {row.objective}
                      </td>
                      <td className="px-4 py-3">
                        {row.result ? (
                          <span className="flex items-center gap-1.5 text-[13px] font-semibold text-ink">
                            {GOOD_RESULTS.has(row.result) ? (
                              <Check size={13} strokeWidth={2.6} color="var(--success)" />
                            ) : (
                              <AlertTriangle
                                size={13}
                                strokeWidth={2.4}
                                color="var(--warning)"
                              />
                            )}
                            {row.result_label}
                          </span>
                        ) : (
                          <StatusBadge status={row.status} />
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {row.human_involved ? (
                          <span className="inline-flex items-center gap-1.5 text-[12.5px] font-semibold text-[var(--paytm-blue-deep)]">
                            <UserCheck size={13} strokeWidth={2.4} />
                            {row.approvals
                              ? `${row.approvals} approval${row.approvals === 1 ? "" : "s"}`
                              : "Takeover"}
                          </span>
                        ) : (
                          <span className="text-[12.5px] text-muted">No</span>
                        )}
                      </td>
                      <td className="tnum px-4 py-3 text-[12.5px] text-muted">
                        {shortDateTime(row.completed_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </section>

      {hasActivity ? (
        <p className="text-[11.5px] text-muted">
          Traceability: {trace.missions_recorded} mission records ·{" "}
          {trace.events_recorded} mission events · {trace.actions_executed} actions
          executed. Reset the demo to clear all of it.
        </p>
      ) : null}
    </div>
  );
}
