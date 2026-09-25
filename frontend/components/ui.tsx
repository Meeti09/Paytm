"use client";

/**
 * Shared primitives. Every screen composes these so the product reads as one
 * system: hairline borders, 8–10px radius, no shadows, status colour used only
 * for status. Design.md §37–38.
 */

import type { ReactNode } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Ban,
  Check,
  CircleDot,
  Clock,
  Loader2,
  Pause,
  ShieldAlert,
  UserCheck,
  X,
} from "lucide-react";
import type { EventLevel, MissionStatus, RiskLevel } from "@/lib/types";

/* -------------------------------------------------------------- Card ---- */

export function Card({
  children,
  className = "",
  accent,
}: {
  children: ReactNode;
  className?: string;
  accent?: RiskLevel | "brand";
}) {
  const accentColor =
    accent === "high"
      ? "var(--danger)"
      : accent === "medium"
        ? "var(--warning)"
        : accent === "low"
          ? "var(--success)"
          : accent === "brand"
            ? "var(--paytm-blue)"
            : undefined;

  return (
    <section
      className={`rounded-[10px] border border-hairline bg-surface ${className}`}
      style={accentColor ? { borderLeft: `3px solid ${accentColor}` } : undefined}
    >
      {children}
    </section>
  );
}

export function SectionHeader({
  title,
  right,
  className = "",
}: {
  title: string;
  right?: ReactNode;
  className?: string;
}) {
  return (
    <div className={`flex items-center justify-between gap-3 ${className}`}>
      <h2 className="label">{title}</h2>
      {right}
    </div>
  );
}

/* ------------------------------------------------------------ Button ---- */

type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";

export function Button({
  children,
  onClick,
  variant = "secondary",
  disabled,
  loading,
  icon: Icon,
  size = "md",
  className = "",
  title,
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: ButtonVariant;
  disabled?: boolean;
  loading?: boolean;
  icon?: React.ComponentType<{ size?: number; strokeWidth?: number }>;
  size?: "sm" | "md";
  className?: string;
  title?: string;
}) {
  const base =
    "inline-flex items-center justify-center gap-1.5 rounded-[8px] font-semibold transition-colors disabled:opacity-45 disabled:cursor-not-allowed";
  const sizing = size === "sm" ? "px-2.5 py-1.5 text-[12px]" : "px-3.5 py-2 text-[13px]";
  const variants: Record<ButtonVariant, string> = {
    primary: "bg-[var(--paytm-blue)] text-white hover:bg-[var(--paytm-blue-deep)]",
    secondary:
      "bg-surface text-ink border border-hairline hover:border-[var(--paytm-blue)] hover:text-[var(--paytm-blue-deep)]",
    danger:
      "bg-surface text-[var(--danger)] border border-[#f0c4c4] hover:bg-[#fdf3f3]",
    ghost: "text-muted hover:text-ink",
  };

  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      disabled={disabled || loading}
      className={`${base} ${sizing} ${variants[variant]} ${className}`}
    >
      {loading ? (
        <Loader2 size={14} strokeWidth={2.2} className="animate-spin" />
      ) : Icon ? (
        <Icon size={14} strokeWidth={2.2} />
      ) : null}
      {children}
    </button>
  );
}

/* ------------------------------------------------------------- Pills ---- */

function Pill({
  children,
  color,
  bg,
  border,
  icon: Icon,
}: {
  children: ReactNode;
  color: string;
  bg: string;
  border?: string;
  icon?: React.ComponentType<{ size?: number; strokeWidth?: number; className?: string }>;
}) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-bold uppercase tracking-[0.05em] whitespace-nowrap"
      style={{ color, background: bg, border: border ? `1px solid ${border}` : undefined }}
    >
      {Icon ? <Icon size={12} strokeWidth={2.5} /> : null}
      {children}
    </span>
  );
}

const STATUS_STYLE: Record<
  MissionStatus,
  { label: string; color: string; bg: string; icon: React.ComponentType<never> }
> = {
  created: { label: "Queued", color: "#5c6b7a", bg: "#eef1f5", icon: Clock as never },
  running: { label: "Running", color: "#01579b", bg: "#e4f6fd", icon: CircleDot as never },
  waiting_approval: {
    label: "Approval required",
    color: "#b3541e",
    bg: "#fdf1e0",
    icon: ShieldAlert as never,
  },
  waiting_response: {
    label: "Awaiting reply",
    color: "#b3541e",
    bg: "#fdf1e0",
    icon: Clock as never,
  },
  paused: { label: "Paused", color: "#b3541e", bg: "#fdf1e0", icon: Pause as never },
  needs_attention: {
    label: "Needs attention",
    color: "#c02c2c",
    bg: "#fdecec",
    icon: AlertTriangle as never,
  },
  human_takeover: {
    label: "Human takeover",
    color: "#01579b",
    bg: "#e4f6fd",
    icon: UserCheck as never,
  },
  completed: { label: "Completed", color: "#07713f", bg: "#e6f6ee", icon: Check as never },
  failed: { label: "Failed", color: "#c02c2c", bg: "#fdecec", icon: X as never },
};

export function StatusBadge({ status }: { status: MissionStatus }) {
  const style = STATUS_STYLE[status] ?? STATUS_STYLE.created;
  const Icon = style.icon as React.ComponentType<{ size?: number; strokeWidth?: number }>;
  return (
    <Pill color={style.color} bg={style.bg} icon={Icon}>
      {style.label}
    </Pill>
  );
}

export function RiskBadge({ risk }: { risk: RiskLevel }) {
  const map = {
    high: { color: "#c02c2c", bg: "#fdecec", label: "High risk" },
    medium: { color: "#b3541e", bg: "#fdf1e0", label: "Medium risk" },
    low: { color: "#07713f", bg: "#e6f6ee", label: "Low risk" },
  } as const;
  const style = map[risk] ?? map.low;
  return (
    <Pill color={style.color} bg={style.bg} icon={ShieldAlert}>
      {style.label}
    </Pill>
  );
}

export function VerdictBadge({
  verdict,
}: {
  verdict: "AUTONOMOUS" | "REQUIRES_APPROVAL";
}) {
  return verdict === "AUTONOMOUS" ? (
    <Pill color="#07713f" bg="#e6f6ee" icon={Check}>
      Autonomous
    </Pill>
  ) : (
    <Pill color="#c02c2c" bg="#fdecec" icon={ShieldAlert}>
      Approval required
    </Pill>
  );
}

export function AgentBadge({ agent }: { agent: "resolve" | "grow" }) {
  return (
    <span
      className="inline-flex items-center rounded-[6px] px-2 py-1 text-[11px] font-bold uppercase tracking-[0.08em]"
      style={{
        color: agent === "resolve" ? "#01579b" : "#07713f",
        background: agent === "resolve" ? "#e4f6fd" : "#e6f6ee",
      }}
    >
      {agent}
    </span>
  );
}

/* -------------------------------------------------------- ProgressBar --- */

export function ProgressBar({ value }: { value: number }) {
  return (
    <div
      className="h-[5px] w-full overflow-hidden rounded-[4px] bg-hairline"
      role="progressbar"
      aria-valuenow={value}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className="h-full rounded-[4px] bg-[var(--paytm-blue)] transition-[width] duration-500 ease-out"
        style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
      />
    </div>
  );
}

/* --------------------------------------------------------- MetricCard --- */

export function MetricCard({
  value,
  label,
  basis,
  tone = "ink",
}: {
  value: ReactNode;
  label: string;
  basis?: string;
  tone?: "ink" | "success" | "warning" | "danger" | "brand";
}) {
  const colors = {
    ink: "var(--ink)",
    success: "var(--success)",
    warning: "#b3541e",
    danger: "var(--danger)",
    brand: "var(--paytm-blue-deep)",
  } as const;

  return (
    <div className="rounded-[10px] border border-hairline bg-surface p-5">
      <div
        className="tnum text-[32px] font-bold leading-none"
        style={{ color: colors[tone] }}
      >
        {value}
      </div>
      <div className="mt-2 text-[13px] font-semibold text-ink">{label}</div>
      {basis ? (
        <div className="mt-1 text-[11px] leading-snug text-muted">{basis}</div>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------- Event icons ---- */

export function EventIcon({ level }: { level: EventLevel }) {
  const size = 13;
  const stroke = 2.6;
  if (level === "error")
    return <X size={size} strokeWidth={stroke} color="var(--danger)" aria-label="failed" />;
  if (level === "warn")
    return (
      <AlertTriangle
        size={size}
        strokeWidth={stroke}
        color="var(--warning)"
        aria-label="needs review"
      />
    );
  if (level === "pending")
    return <Clock size={size} strokeWidth={stroke} color="var(--ink-muted)" aria-label="pending" />;
  if (level === "info")
    return (
      <ArrowRight size={size} strokeWidth={stroke} color="var(--paytm-blue-deep)" aria-label="info" />
    );
  return <Check size={size} strokeWidth={stroke} color="var(--success)" aria-label="done" />;
}

/* ------------------------------------------------------- Empty/Error ---- */

export function EmptyState({
  icon: Icon = CircleDot,
  title,
  body,
  action,
}: {
  icon?: React.ComponentType<{ size?: number; strokeWidth?: number; color?: string }>;
  title: string;
  body?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-14 text-center">
      <Icon size={20} strokeWidth={1.8} color="var(--ink-muted)" />
      <p className="text-[14px] font-semibold text-ink">{title}</p>
      {body ? <p className="max-w-sm text-[13px] text-muted">{body}</p> : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}

export function ErrorNotice({
  title,
  body,
  actions,
}: {
  title: string;
  body: string;
  actions?: ReactNode;
}) {
  return (
    <div
      className="rounded-[10px] border border-hairline bg-surface p-4"
      style={{ borderLeft: "3px solid var(--danger)" }}
      role="alert"
    >
      <div className="flex items-start gap-2.5">
        <Ban size={15} strokeWidth={2.2} color="var(--danger)" className="mt-0.5 shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="text-[13px] font-bold text-ink">{title}</p>
          <p className="mt-1 text-[13px] leading-relaxed text-muted">{body}</p>
          {actions ? <div className="mt-3 flex flex-wrap gap-2">{actions}</div> : null}
        </div>
      </div>
    </div>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-[6px] bg-[#eef1f5] ${className}`} />;
}
