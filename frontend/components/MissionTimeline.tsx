"use client";

import { useEffect, useRef } from "react";
import { clockTime } from "@/lib/format";
import type { MissionEvent } from "@/lib/types";
import { Card, EmptyState, EventIcon, SectionHeader } from "./ui";
import { ListTree } from "lucide-react";

const ACTOR_LABEL: Record<string, string> = {
  resolve: "Resolve",
  grow: "Grow",
  human: "Human",
  system: "System",
};

/**
 * The live activity timeline. Every row here corresponds to a MissionEvent row
 * in the database — nothing is synthesised in the browser.
 */
export function MissionTimeline({
  events,
  live,
}: {
  events: MissionEvent[];
  live: boolean;
}) {
  const endRef = useRef<HTMLDivElement>(null);
  const count = events.length;

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [count]);

  return (
    <Card className="flex min-h-0 flex-col">
      <div className="flex items-center justify-between border-b border-hairline px-5 py-3">
        <SectionHeader title="Live activity" />
        <span className="tnum text-[11px] font-semibold text-muted">
          {count} event{count === 1 ? "" : "s"}
          {live ? (
            <span className="ml-2 inline-flex items-center gap-1 text-[var(--paytm-blue-deep)]">
              <span className="live-dot h-1.5 w-1.5 rounded-full bg-[var(--paytm-blue)]" />
              running
            </span>
          ) : null}
        </span>
      </div>

      {count === 0 ? (
        <EmptyState
          icon={ListTree}
          title="No activity yet"
          body="Start a mission and the teammate's actions will appear here as they happen."
        />
      ) : (
        <ol className="max-h-[420px] min-h-0 overflow-y-auto px-2 py-2">
          {events.map((event) => (
            <li
              key={event.id}
              className="row-in flex items-start gap-3 rounded-[6px] px-3 py-1.5 hover:bg-[#f8fafc]"
            >
              <span className="tnum mt-[3px] shrink-0 text-[11px] font-medium text-muted">
                {clockTime(event.timestamp)}
              </span>
              <span className="mt-[3px] shrink-0">
                <EventIcon level={event.level} />
              </span>
              <span className="min-w-0 flex-1 text-[13px] leading-[1.5] text-ink">
                {event.message}
              </span>
              <span className="mt-[3px] hidden shrink-0 text-[10px] font-semibold uppercase tracking-[0.05em] text-muted sm:block">
                {ACTOR_LABEL[event.actor] ?? event.actor}
              </span>
            </li>
          ))}
          <div ref={endRef} />
        </ol>
      )}
    </Card>
  );
}
