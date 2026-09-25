"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, RotateCcw } from "lucide-react";
import { usePulse } from "./PulseProvider";
import { Button } from "./ui";

const NAV = [
  { href: "/", label: "Live Mission" },
  { href: "/approvals", label: "Approvals" },
  { href: "/outcomes", label: "Outcomes" },
];

const INTEGRATION_ORDER = ["sarvam", "cognee", "llm", "n8n", "paytm"] as const;
const INTEGRATION_ROLE: Record<string, string> = {
  sarvam: "Understand",
  cognee: "Remember",
  llm: "Decide",
  n8n: "Act",
  paytm: "Paytm",
};

export function AppHeader() {
  const pathname = usePathname();
  const { streamStatus, pendingApprovals, status, resetDemo, resetting } = usePulse();

  return (
    <header className="sticky top-0 z-20 border-b border-hairline bg-surface">
      <div className="mx-auto flex h-14 max-w-[1400px] items-center gap-6 px-6">
        <Link href="/" className="flex shrink-0 items-baseline gap-2">
          <span className="text-[15px] font-extrabold tracking-[0.14em] text-ink">
            PAYTM
          </span>
          <span className="text-[15px] font-extrabold tracking-[0.14em] text-[var(--paytm-blue)]">
            PULSE
          </span>
          <span className="hidden border-l border-hairline pl-2 text-[11px] font-semibold text-muted sm:inline">
            AI workforce
          </span>
        </Link>

        <nav className="flex h-full items-stretch gap-1" aria-label="Main">
          {NAV.map((item) => {
            const active =
              item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`relative flex items-center gap-2 px-3 text-[13px] font-semibold transition-colors ${
                  active
                    ? "text-[var(--paytm-blue-deep)]"
                    : "text-muted hover:text-ink"
                }`}
              >
                {item.label}
                {item.href === "/approvals" && pendingApprovals > 0 ? (
                  <span className="tnum inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-[var(--danger)] px-1 text-[10px] font-bold text-white">
                    {pendingApprovals}
                  </span>
                ) : null}
                {active ? (
                  <span className="absolute inset-x-2 bottom-0 h-[2px] bg-[var(--paytm-blue)]" />
                ) : null}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto flex items-center gap-3">
          <div className="hidden items-center gap-1.5 xl:flex">
            {INTEGRATION_ORDER.map((key) => {
              const state = status?.integrations?.[key];
              if (!state) return null;
              const live = state.mode === "live";
              return (
                <span
                  key={key}
                  title={`${key}: ${state.detail}`}
                  className="inline-flex items-center gap-1.5 rounded-[6px] border border-hairline px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.05em] text-muted"
                >
                  <span
                    className="h-1.5 w-1.5 rounded-full"
                    style={{
                      background: live ? "var(--success)" : "var(--ink-muted)",
                    }}
                  />
                  {INTEGRATION_ROLE[key] ?? key}
                </span>
              );
            })}
          </div>

          <span
            className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-muted"
            title={
              streamStatus === "live"
                ? "Receiving live mission events"
                : "Event stream disconnected"
            }
          >
            <Activity
              size={13}
              strokeWidth={2.4}
              color={streamStatus === "live" ? "var(--success)" : "var(--danger)"}
              className={streamStatus === "live" ? "live-dot" : undefined}
            />
            {streamStatus === "live" ? "Live" : "Offline"}
          </span>

          <Button
            size="sm"
            icon={RotateCcw}
            onClick={resetDemo}
            loading={resetting}
            title="Clear all missions, approvals and events, and restore the seeded dataset"
          >
            Reset demo
          </Button>
        </div>
      </div>
    </header>
  );
}
