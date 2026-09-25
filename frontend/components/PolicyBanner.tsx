"use client";

import { Info } from "lucide-react";
import type { Policy } from "@/lib/types";
import { Card } from "./ui";

/**
 * The autonomy policy, always visible on the queue. A judge should be able to
 * see *why* an action was escalated without asking anyone.
 */
export function PolicyBanner({ policy }: { policy: Policy }) {
  return (
    <Card>
      <div className="grid gap-5 px-5 py-4 md:grid-cols-2">
        <div>
          <div className="flex items-center gap-2">
            <Info size={14} strokeWidth={2.3} color="var(--paytm-blue-deep)" />
            <h2 className="label">Autonomy policy — human approval required for</h2>
          </div>
          <ul className="mt-2.5 space-y-1">
            {policy.rules
              .filter((rule) => rule.enabled)
              .map((rule) => (
                <li
                  key={rule.rule}
                  className="flex items-baseline gap-2 text-[13px] text-ink"
                >
                  <span className="text-muted">•</span>
                  <span>{rule.label}</span>
                </li>
              ))}
          </ul>
        </div>

        <div>
          <h2 className="label">Autonomous without asking</h2>
          <ul className="mt-2.5 grid gap-x-5 gap-y-1 sm:grid-cols-2">
            {policy.autonomous.map((item) => (
              <li
                key={item}
                className="flex items-baseline gap-2 text-[12.5px] text-muted"
              >
                <span>•</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <p className="border-t border-hairline px-5 py-2.5 text-[11.5px] text-muted">
        {policy.disclaimer}
      </p>
    </Card>
  );
}
