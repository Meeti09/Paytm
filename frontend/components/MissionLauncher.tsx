"use client";

import { useState } from "react";
import { MessageSquareText, Play, Store } from "lucide-react";
import type { AgentName, MissionSummary, ResolveScenario, Scenarios } from "@/lib/types";
import { Button, Card, SectionHeader, StatusBadge } from "./ui";

/**
 * Starts a mission. Resolve takes a customer message; Grow takes a territory and
 * a target. Both post to the backend, which creates the mission and runs it.
 */
export function MissionLauncher({
  agent,
  scenarios,
  missions,
  selectedId,
  onSelect,
  onRunResolve,
  onRunResolveCustom,
  onRunGrow,
  starting,
}: {
  agent: AgentName;
  scenarios: Scenarios | null;
  missions: MissionSummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onRunResolve: (scenario: ResolveScenario) => void;
  onRunResolveCustom: (customerId: string, message: string) => void;
  onRunGrow: (location: string, count: number) => void;
  starting: boolean;
}) {
  const [customMessage, setCustomMessage] = useState("");
  const [customerId, setCustomerId] = useState("CUST-001");
  const [location, setLocation] = useState(scenarios?.grow.location ?? "Thane");
  const [count, setCount] = useState(scenarios?.grow.target_count ?? 5);
  const [showCustom, setShowCustom] = useState(false);

  return (
    <Card>
      <div className="flex items-center justify-between border-b border-hairline px-5 py-3">
        <SectionHeader
          title={agent === "resolve" ? "Start a customer mission" : "Start an acquisition mission"}
        />
        {missions.length ? (
          <label className="flex items-center gap-2 text-[12px] text-muted">
            History
            <select
              value={selectedId ?? ""}
              onChange={(event) => onSelect(event.target.value)}
              className="max-w-[230px] rounded-[8px] border border-hairline bg-surface px-2.5 py-1.5 text-[12.5px] font-medium text-ink outline-none focus:border-[var(--paytm-blue)]"
            >
              {missions.map((mission) => (
                <option key={mission.id} value={mission.id}>
                  {mission.id} — {mission.result_label || mission.status}
                </option>
              ))}
            </select>
          </label>
        ) : null}
      </div>

      {agent === "resolve" ? (
        <div className="px-5 py-4">
          <div className="grid gap-3 md:grid-cols-3">
            {(scenarios?.resolve ?? []).map((scenario) => (
              <button
                key={scenario.id}
                type="button"
                disabled={starting}
                onClick={() => onRunResolve(scenario)}
                className="group flex flex-col rounded-[8px] border border-hairline bg-surface p-3.5 text-left transition-colors hover:border-[var(--paytm-blue)] disabled:opacity-50"
              >
                <div className="flex items-center justify-between">
                  <span className="text-[12px] font-bold uppercase tracking-[0.06em] text-[var(--paytm-blue-deep)]">
                    Scenario {scenario.id}
                  </span>
                  <span className="text-[11px] font-medium text-muted">
                    {scenario.language}
                  </span>
                </div>
                <p className="mt-1 text-[13px] font-bold text-ink">
                  {scenario.title}
                </p>
                <p className="mt-2 border-l-2 border-hairline pl-2.5 text-[12.5px] leading-snug text-ink">
                  “{scenario.message}”
                </p>
                <p className="mt-2 text-[11.5px] leading-snug text-muted">
                  {scenario.expected}
                </p>
                <span className="mt-2.5 inline-flex items-center gap-1.5 text-[12px] font-semibold text-[var(--paytm-blue-deep)] group-hover:underline">
                  <Play size={12} strokeWidth={2.6} />
                  Run mission
                </span>
              </button>
            ))}
          </div>

          <button
            type="button"
            onClick={() => setShowCustom((value) => !value)}
            className="mt-3 inline-flex items-center gap-1.5 text-[12px] font-semibold text-muted hover:text-ink"
          >
            <MessageSquareText size={12} strokeWidth={2.2} />
            {showCustom ? "Hide custom message" : "Send a custom customer message"}
          </button>

          {showCustom ? (
            <div className="mt-3 flex flex-wrap items-center gap-2">
              <select
                value={customerId}
                onChange={(event) => setCustomerId(event.target.value)}
                className="rounded-[8px] border border-hairline bg-surface px-2.5 py-2 text-[13px] text-ink outline-none focus:border-[var(--paytm-blue)]"
              >
                {(scenarios?.customers ?? []).map((customer) => (
                  <option key={customer.id} value={customer.id}>
                    {customer.name} ({customer.language})
                  </option>
                ))}
              </select>
              <input
                value={customMessage}
                onChange={(event) => setCustomMessage(event.target.value)}
                placeholder="e.g. ₹2,000 कट गया लेकिन merchant को नहीं मिला."
                className="min-w-[280px] flex-1 rounded-[8px] border border-hairline bg-surface px-3 py-2 text-[13px] text-ink outline-none placeholder:text-muted focus:border-[var(--paytm-blue)]"
              />
              <Button
                variant="primary"
                icon={Play}
                disabled={!customMessage.trim() || starting}
                loading={starting}
                onClick={() => onRunResolveCustom(customerId, customMessage.trim())}
              >
                Run
              </Button>
            </div>
          ) : null}
        </div>
      ) : (
        <div className="flex flex-wrap items-end gap-3 px-5 py-4">
          <label className="flex flex-col gap-1.5">
            <span className="label">Territory</span>
            <input
              value={location}
              onChange={(event) => setLocation(event.target.value)}
              className="w-[180px] rounded-[8px] border border-hairline bg-surface px-3 py-2 text-[13px] text-ink outline-none focus:border-[var(--paytm-blue)]"
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="label">Target merchants</span>
            <input
              type="number"
              min={1}
              max={20}
              value={count}
              onChange={(event) => setCount(Number(event.target.value) || 1)}
              className="tnum w-[110px] rounded-[8px] border border-hairline bg-surface px-3 py-2 text-[13px] text-ink outline-none focus:border-[var(--paytm-blue)]"
            />
          </label>
          <Button
            variant="primary"
            icon={Store}
            loading={starting}
            onClick={() => onRunGrow(location.trim(), count)}
          >
            Find {count} high-potential merchants
          </Button>
          <p className="ml-auto max-w-[280px] text-[11.5px] leading-snug text-muted">
            Searches the seeded demo dataset, skips merchants already on Paytm,
            then scores and ranks the rest.
          </p>
        </div>
      )}

      {missions.length ? (
        <div className="flex flex-wrap gap-2 border-t border-hairline px-5 py-3">
          {missions.slice(0, 6).map((mission) => (
            <button
              key={mission.id}
              type="button"
              onClick={() => onSelect(mission.id)}
              className={`flex items-center gap-2 rounded-[8px] border px-2.5 py-1.5 text-[12px] font-semibold transition-colors ${
                mission.id === selectedId
                  ? "border-[var(--paytm-blue)] text-[var(--paytm-blue-deep)]"
                  : "border-hairline text-muted hover:text-ink"
              }`}
            >
              {mission.id}
              <StatusBadge status={mission.status} />
            </button>
          ))}
        </div>
      ) : null}
    </Card>
  );
}
