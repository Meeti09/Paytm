"use client";

import { Database, Brain } from "lucide-react";
import type { MissionContext } from "@/lib/types";
import { Card, SectionHeader } from "./ui";

const TONE_COLOR = {
  ok: "var(--ink)",
  warn: "#b3541e",
  danger: "var(--danger)",
} as const;

/** Context the teammate loaded before deciding. Rendered from backend panels. */
export function ContextPanels({ context }: { context: MissionContext }) {
  const panels = context.panels ?? [];
  const memory = context.memory;

  if (!panels.length) return null;

  return (
    <Card>
      <div className="flex items-center justify-between border-b border-hairline px-5 py-3">
        <SectionHeader title="Context" />
        {memory ? (
          <span
            className="inline-flex items-center gap-1.5 text-[11px] font-medium text-muted"
            title={memory.detail}
          >
            {memory.source === "cognee" ? (
              <Brain size={12} strokeWidth={2.2} color="var(--success)" />
            ) : (
              <Database size={12} strokeWidth={2.2} />
            )}
            {memory.source === "cognee" ? "Cognee memory" : "Local context"}
          </span>
        ) : null}
      </div>

      <div className="divide-y divide-[var(--border)]">
        {panels.map((panel) => (
          <div key={panel.title} className="px-5 py-3">
            <p className="label mb-2">{panel.title}</p>
            <dl className="space-y-1.5">
              {panel.rows.map((row) => (
                <div
                  key={`${panel.title}-${row.label}`}
                  className="flex items-baseline justify-between gap-3"
                >
                  <dt className="shrink-0 text-[12.5px] text-muted">{row.label}</dt>
                  <dd
                    className="tnum min-w-0 truncate text-right text-[13px] font-semibold"
                    style={{ color: TONE_COLOR[row.tone ?? "ok"] }}
                    title={row.value}
                  >
                    {row.value}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        ))}

        {memory?.items?.length ? (
          <div className="px-5 py-3">
            <p className="label mb-2">Memory</p>
            <dl className="space-y-1.5">
              {memory.items.map((item, index) => (
                <div
                  key={`${item.label}-${index}`}
                  className="flex items-baseline justify-between gap-3"
                >
                  <dt className="shrink-0 text-[12.5px] text-muted">{item.label}</dt>
                  <dd className="tnum min-w-0 truncate text-right text-[13px] font-semibold text-ink">
                    {item.value}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        ) : null}
      </div>
    </Card>
  );
}
