"use client";

import { useCallback, useEffect, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { ApprovalCard } from "@/components/ApprovalCard";
import { PolicyBanner } from "@/components/PolicyBanner";
import { usePulseStream } from "@/components/PulseProvider";
import { Card, EmptyState, ErrorNotice, Skeleton } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import type { Approval, Policy } from "@/lib/types";

type Filter = "pending" | "all";

export default function ApprovalsPage() {
  const [filter, setFilter] = useState<Filter>("pending");
  const [approvals, setApprovals] = useState<Approval[] | null>(null);
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const apply = useCallback((data: Awaited<ReturnType<typeof api.approvals>>) => {
    setApprovals(data.approvals);
    setPolicy(data.policy);
    setError(null);
  }, []);

  const fail = useCallback((err: unknown) => {
    setError(err instanceof ApiError ? err.message : "Failed to load approvals");
    setApprovals([]);
  }, []);

  const load = useCallback(
    (which: Filter) => api.approvals(which).then(apply, fail),
    [apply, fail],
  );

  useEffect(() => {
    // Guard against a slow response for the previous filter landing last.
    let cancelled = false;
    api.approvals(filter).then(
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
  }, [filter, apply, fail]);

  usePulseStream({
    onApprovalsChanged: () => void load(filter),
    onDemoReset: () => void load(filter),
  });

  const act = async (id: string, fn: () => Promise<unknown>) => {
    setBusyId(id);
    setError(null);
    try {
      await fn();
      await load(filter);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Action failed");
    } finally {
      setBusyId(null);
    }
  };

  const pendingCount = (approvals ?? []).filter((a) => a.status === "pending").length;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[24px] font-bold leading-tight text-ink">
            Approval queue
          </h1>
          <p className="mt-1 text-[13px] text-muted">
            {approvals === null
              ? "Loading…"
              : pendingCount === 0
                ? "No actions need your attention."
                : pendingCount === 1
                  ? "1 action needs your attention."
                  : `${pendingCount} actions need your attention.`}
          </p>
        </div>

        <div className="flex rounded-[8px] border border-hairline bg-surface p-0.5">
          {(["pending", "all"] as Filter[]).map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setFilter(option)}
              className={`rounded-[6px] px-3 py-1.5 text-[12.5px] font-semibold capitalize transition-colors ${
                filter === option
                  ? "bg-[#e4f6fd] text-[var(--paytm-blue-deep)]"
                  : "text-muted hover:text-ink"
              }`}
            >
              {option === "pending" ? "Pending" : "All decisions"}
            </button>
          ))}
        </div>
      </div>

      {policy ? <PolicyBanner policy={policy} /> : <Skeleton className="h-[180px]" />}

      {error ? (
        <ErrorNotice title="Approval action failed" body={error} />
      ) : null}

      {approvals === null ? (
        <Skeleton className="h-[260px]" />
      ) : approvals.length === 0 ? (
        <Card>
          <EmptyState
            icon={ShieldCheck}
            title="No approvals pending"
            body="All teammate actions are currently inside their permitted autonomy. Run a mission above the ₹1,000 threshold — or one with strongly negative sentiment — and it will stop here."
          />
        </Card>
      ) : (
        <div className="space-y-4">
          {approvals.map((approval) => (
            <ApprovalCard
              key={approval.id}
              approval={approval}
              busy={busyId === approval.id}
              onApprove={() => act(approval.id, () => api.approve(approval.id))}
              onReject={() => act(approval.id, () => api.reject(approval.id))}
              onTakeover={() =>
                act(approval.id, () => api.takeoverApproval(approval.id))
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}
