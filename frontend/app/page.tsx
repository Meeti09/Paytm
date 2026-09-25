"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  CheckCircle2,
  CircuitBoard,
  Headset,
  Pause,
  Play,
  RefreshCw,
  ShieldAlert,
  Store,
  UserCheck,
} from "lucide-react";
import { ContextPanels } from "@/components/ContextPanels";
import { DecisionCard } from "@/components/DecisionCard";
import { LeadsPanel } from "@/components/LeadsPanel";
import { MissionLauncher } from "@/components/MissionLauncher";
import { MissionTimeline } from "@/components/MissionTimeline";
import { usePulse, usePulseStream } from "@/components/PulseProvider";
import {
  AgentBadge,
  Button,
  Card,
  EmptyState,
  ErrorNotice,
  ProgressBar,
  SectionHeader,
  Skeleton,
  StatusBadge,
} from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { titleCase } from "@/lib/format";
import type {
  AgentName,
  Mission,
  MissionEvent,
  MissionSummary,
  ResolveScenario,
  Scenarios,
} from "@/lib/types";

const AGENTS: {
  id: AgentName;
  name: string;
  role: string;
  mission: string;
  icon: typeof Headset;
}[] = [
  {
    id: "resolve",
    name: "Resolve",
    role: "Customer Resolution Teammate",
    mission: "Own every customer issue until it is verified as resolved.",
    icon: Headset,
  },
  {
    id: "grow",
    name: "Grow",
    role: "Merchant Acquisition Teammate",
    mission: "Find and convert the next generation of Paytm merchants.",
    icon: Store,
  },
];

const LIVE_STATUSES = new Set(["running", "created"]);

export default function LiveMissionPage() {
  const { apiOnline } = usePulse();
  const [agent, setAgent] = useState<AgentName>("resolve");
  const [scenarios, setScenarios] = useState<Scenarios | null>(null);
  const [missions, setMissions] = useState<MissionSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [mission, setMission] = useState<Mission | null>(null);
  const [events, setEvents] = useState<MissionEvent[]>([]);
  const [starting, setStarting] = useState(false);
  const [replying, setReplying] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Stream handlers need the currently selected mission without being
  // re-registered on every selection change.
  const selectedRef = useRef<string | null>(null);
  useEffect(() => {
    selectedRef.current = selectedId;
  }, [selectedId]);

  /* ---------------------------------------------------------- loading -- */

  const fail = useCallback(
    (fallback: string) => (err: unknown) =>
      setError(err instanceof ApiError ? err.message : fallback),
    [],
  );

  const applyMissions = useCallback((list: MissionSummary[], pick?: string) => {
    setMissions(list);
    const next = pick ?? selectedRef.current;
    const valid = next && list.some((m) => m.id === next) ? next : list[0]?.id;
    setSelectedId(valid ?? null);
    if (!valid) {
      setMission(null);
      setEvents([]);
    }
  }, []);

  const applyMission = useCallback((data: Mission) => {
    setMission(data);
    setEvents(data.events ?? []);
    setError(null);
  }, []);

  const loadMissions = useCallback(
    (forAgent: AgentName, pick?: string) =>
      api
        .missions(forAgent)
        .then((list) => applyMissions(list, pick), fail("Failed to load missions")),
    [applyMissions, fail],
  );

  const loadMission = useCallback(
    (id: string) => api.mission(id).then(applyMission, fail("Failed to load mission")),
    [applyMission, fail],
  );

  useEffect(() => {
    api.scenarios().then(setScenarios, () => undefined);
  }, []);

  // Each fetch is cancelled if its input changes first, so a slow response for
  // the previous agent or mission can never overwrite newer state.
  useEffect(() => {
    let cancelled = false;
    api.missions(agent).then(
      (list) => {
        if (!cancelled) applyMissions(list);
      },
      (err) => {
        if (!cancelled) fail("Failed to load missions")(err);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [agent, applyMissions, fail]);

  useEffect(() => {
    if (!selectedId) return;
    let cancelled = false;
    api.mission(selectedId).then(
      (data) => {
        if (!cancelled) applyMission(data);
      },
      (err) => {
        if (!cancelled) fail("Failed to load mission")(err);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [selectedId, applyMission, fail]);

  /* ------------------------------------------------------ live stream -- */

  usePulseStream({
    onMissionEvent: (event) => {
      if (event.mission_id !== selectedRef.current) return;
      setEvents((current) =>
        current.some((e) => e.id === event.id) ? current : [...current, event],
      );
    },
    onMissionUpdate: (updated) => {
      setMissions((current) =>
        current.map((m) =>
          m.id === updated.id
            ? {
                ...m,
                status: updated.status,
                stage: updated.stage,
                progress: updated.progress,
                result: updated.result,
                result_label: updated.result_label,
                human_involved: updated.human_involved,
              }
            : m,
        ),
      );
      if (updated.id === selectedRef.current) {
        setMission((current) =>
          current ? { ...updated, events: undefined } : updated,
        );
      }
    },
    onDemoReset: () => {
      setMission(null);
      setEvents([]);
      setSelectedId(null);
      void loadMissions(agent);
    },
  });

  /* ---------------------------------------------------------- actions -- */

  const guard = async (fn: () => Promise<unknown>, setter = setBusy) => {
    setter(true);
    setError(null);
    try {
      await fn();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Action failed");
    } finally {
      setter(false);
    }
  };

  const startResolve = (scenario: ResolveScenario) =>
    guard(async () => {
      const created = await api.runResolve(scenario.id);
      await loadMissions("resolve", created.id);
    }, setStarting);

  const startResolveCustom = (customerId: string, message: string) =>
    guard(async () => {
      const created = await api.runResolveCustom(customerId, message);
      await loadMissions("resolve", created.id);
    }, setStarting);

  const startGrow = (location: string, count: number) =>
    guard(async () => {
      const created = await api.runGrow(location, count);
      await loadMissions("grow", created.id);
    }, setStarting);

  const sendReply = (leadId: string, text: string) =>
    guard(async () => {
      if (mission) await api.replyToMission(mission.id, leadId, text);
    }, setReplying);

  /* ------------------------------------------------------------ view -- */

  const activeAgent = AGENTS.find((a) => a.id === agent)!;
  const live = mission ? LIVE_STATUSES.has(mission.status) : false;
  const stats = mission?.context?.stats;

  const controls = useMemo(() => {
    if (!mission) return null;
    const finished = ["completed", "failed", "human_takeover"].includes(
      mission.status,
    );
    return (
      <div className="flex flex-wrap items-center gap-2">
        {mission.status === "waiting_approval" && mission.pending_approval_id ? (
          <Link href="/approvals">
            <Button variant="primary" icon={ShieldAlert}>
              Open approval
            </Button>
          </Link>
        ) : null}
        {mission.status === "running" ? (
          <Button icon={Pause} loading={busy} onClick={() => guard(() => api.pauseMission(mission.id))}>
            Pause
          </Button>
        ) : null}
        {mission.status === "paused" ? (
          <Button icon={Play} loading={busy} onClick={() => guard(() => api.startMission(mission.id))}>
            Resume
          </Button>
        ) : null}
        {["paused", "needs_attention", "failed"].includes(mission.status) ? (
          <Button
            variant="primary"
            icon={RefreshCw}
            loading={busy}
            onClick={() => guard(() => api.retryMission(mission.id))}
          >
            Retry
          </Button>
        ) : null}
        {!finished ? (
          <Button
            icon={UserCheck}
            loading={busy}
            onClick={() => guard(() => api.takeoverMission(mission.id))}
            title="Stop the agent and take ownership of this mission"
          >
            Take over
          </Button>
        ) : null}
      </div>
    );
  }, [mission, busy]);

  return (
    <div className="space-y-5">
      {!apiOnline ? (
        <ErrorNotice
          title="Backend unreachable"
          body="The Paytm Pulse API is not responding. Start the backend, then reload this page."
        />
      ) : null}

      {/* Agent identity — what a judge sees first. */}
      <div className="grid gap-4 md:grid-cols-2">
        {AGENTS.map((entry) => {
          const Icon = entry.icon;
          const active = entry.id === agent;
          return (
            <button
              key={entry.id}
              type="button"
              onClick={() => setAgent(entry.id)}
              aria-pressed={active}
              className={`flex items-start gap-3.5 rounded-[10px] border bg-surface p-4 text-left transition-colors ${
                active
                  ? "border-[var(--paytm-blue)]"
                  : "border-hairline hover:border-[#c9d4e0]"
              }`}
            >
              <span
                className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-[8px]"
                style={{
                  background: active ? "#e4f6fd" : "#f2f5f9",
                  color: active ? "var(--paytm-blue-deep)" : "var(--ink-muted)",
                }}
              >
                <Icon size={17} strokeWidth={2.2} />
              </span>
              <span className="min-w-0">
                <span className="flex items-center gap-2">
                  <span className="text-[15px] font-extrabold uppercase tracking-[0.08em] text-ink">
                    {entry.name}
                  </span>
                  {active ? (
                    <span className="rounded-full bg-[#e4f6fd] px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.05em] text-[var(--paytm-blue-deep)]">
                      Selected
                    </span>
                  ) : null}
                </span>
                <span className="mt-0.5 block text-[12px] font-semibold text-muted">
                  {entry.role}
                </span>
                <span className="mt-1.5 block text-[12.5px] leading-snug text-ink">
                  {entry.mission}
                </span>
              </span>
            </button>
          );
        })}
      </div>

      <MissionLauncher
        agent={agent}
        scenarios={scenarios}
        missions={missions}
        selectedId={selectedId}
        onSelect={setSelectedId}
        onRunResolve={startResolve}
        onRunResolveCustom={startResolveCustom}
        onRunGrow={startGrow}
        starting={starting}
      />

      {error ? (
        <ErrorNotice
          title="Action could not be completed"
          body={error}
          actions={
            mission ? (
              <Button size="sm" onClick={() => void loadMission(mission.id)}>
                Reload mission
              </Button>
            ) : undefined
          }
        />
      ) : null}

      {!mission ? (
        selectedId ? (
          <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
            <Skeleton className="h-[280px]" />
            <Skeleton className="h-[280px]" />
          </div>
        ) : (
          <Card>
            <EmptyState
              icon={CircuitBoard}
              title={`No ${activeAgent.name} mission yet`}
              body={`Give ${activeAgent.name} a job above. The mission, its decisions, the policy check and the outcome all appear here as they happen.`}
            />
          </Card>
        )
      ) : (
        <>
          {/* Mission header */}
          <Card accent="brand">
            <div className="flex flex-wrap items-start justify-between gap-4 px-5 py-4">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2.5">
                  <AgentBadge agent={mission.agent} />
                  <span className="tnum text-[12px] font-bold tracking-[0.05em] text-muted">
                    MISSION {mission.id}
                  </span>
                  {mission.context?.transaction ? (
                    <span className="tnum rounded-[6px] border border-hairline px-2 py-0.5 text-[11px] font-semibold text-muted">
                      {(mission.context.transaction as { id: string }).id}
                    </span>
                  ) : null}
                  <StatusBadge status={mission.status} />
                  {mission.human_involved ? (
                    <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-[var(--paytm-blue-deep)]">
                      <UserCheck size={12} strokeWidth={2.4} />
                      Human involved
                    </span>
                  ) : null}
                </div>
                <h1 className="mt-2 text-[22px] font-bold leading-tight text-ink">
                  {mission.objective}
                </h1>
                {typeof mission.inputs?.message === "string" ? (
                  <p className="mt-1.5 border-l-2 border-hairline pl-2.5 text-[13px] leading-snug text-muted">
                    “{mission.inputs.message as string}”
                  </p>
                ) : null}
              </div>
              {controls}
            </div>

            <div className="border-t border-hairline px-5 py-3">
              <div className="mb-2 flex items-center justify-between text-[12px]">
                <span className="font-semibold text-muted">
                  {titleCase(mission.stage)}
                </span>
                <span className="tnum font-bold text-ink">{mission.progress}%</span>
              </div>
              <ProgressBar value={mission.progress} />
            </div>

            {mission.status === "needs_attention" || mission.status === "paused" ? (
              <div className="border-t border-hairline px-5 py-4">
                <ErrorNotice
                  title={
                    mission.status === "paused"
                      ? "Mission paused"
                      : "Mission needs attention"
                  }
                  body={mission.error || "The mission stopped before completion."}
                  actions={
                    <>
                      <Button
                        size="sm"
                        variant="primary"
                        icon={RefreshCw}
                        loading={busy}
                        onClick={() => guard(() => api.retryMission(mission.id))}
                      >
                        Retry
                      </Button>
                      <Button
                        size="sm"
                        icon={UserCheck}
                        loading={busy}
                        onClick={() => guard(() => api.takeoverMission(mission.id))}
                      >
                        Take over
                      </Button>
                    </>
                  }
                />
              </div>
            ) : null}

            {mission.status === "completed" && mission.summary?.headline ? (
              <div className="border-t border-hairline px-5 py-4">
                <div className="flex items-start gap-2.5">
                  <CheckCircle2
                    size={16}
                    strokeWidth={2.3}
                    color="var(--success)"
                    className="mt-0.5 shrink-0"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="text-[14px] font-bold text-ink">
                      {mission.summary.headline}
                    </p>
                    {mission.summary.lines?.length ? (
                      <ul className="mt-1.5 space-y-0.5">
                        {mission.summary.lines.map((line, index) => (
                          <li key={index} className="text-[12.5px] text-muted">
                            {line}
                          </li>
                        ))}
                      </ul>
                    ) : null}
                    {mission.summary.customer_message ? (
                      <div className="mt-2.5">
                        <p className="label mb-1">Message sent to the customer</p>
                        <p className="rounded-[8px] border border-hairline bg-[#fbfcfe] px-3 py-2 text-[12.5px] leading-relaxed text-ink">
                          {mission.summary.customer_message}
                        </p>
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>
            ) : null}
          </Card>

          {/* Grow pipeline counters */}
          {stats ? (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
              {[
                ["Evaluated", stats.evaluated],
                ["Qualified", stats.qualified],
                ["Contacted", stats.contacted],
                ["Sales-ready", stats.sales_ready],
                ["Meetings", stats.meetings_booked],
              ].map(([label, value]) => (
                <div
                  key={label as string}
                  className="rounded-[10px] border border-hairline bg-surface px-4 py-3"
                >
                  <div className="tnum text-[24px] font-bold leading-none text-ink">
                    {value as number}
                  </div>
                  <div className="mt-1 text-[12px] font-semibold text-muted">
                    {label as string}
                  </div>
                </div>
              ))}
            </div>
          ) : null}

          {/* Context + decision */}
          <div className="grid items-start gap-4 lg:grid-cols-[340px_1fr]">
            <ContextPanels context={mission.context} />
            {mission.decision ? (
              <DecisionCard decision={mission.decision} />
            ) : (
              <Card>
                <div className="border-b border-hairline px-5 py-3">
                  <SectionHeader title="AI decision" />
                </div>
                <EmptyState
                  title="No decision yet"
                  body="The teammate is still loading context and evidence."
                />
              </Card>
            )}
          </div>

          {mission.agent === "grow" && (mission.context.leads?.length ?? 0) > 0 ? (
            <LeadsPanel mission={mission} onReply={sendReply} replying={replying} />
          ) : null}

          <MissionTimeline events={events} live={live} />
        </>
      )}
    </div>
  );
}
