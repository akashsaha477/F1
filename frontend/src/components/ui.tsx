import type { ReactNode } from "react";
import { ApiError } from "../api/client";

export function Card({ title, subtitle, actions, children, className = "" }: {
  title?: ReactNode; subtitle?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string;
}) {
  return (
    <section className={`rounded-lg border border-line bg-surface-1 p-4 ${className}`}>
      {(title || actions) && (
        <header className="mb-3 flex items-start justify-between gap-3">
          <div>
            {title && <h2 className="text-sm font-semibold text-ink">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-xs text-ink-muted">{subtitle}</p>}
          </div>
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}

export function PageHeader({ title, description, children }: { title: string; description?: ReactNode; children?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">{title}</h1>
        {description && <p className="mt-1 max-w-3xl text-sm text-ink-2">{description}</p>}
      </div>
      {children}
    </div>
  );
}

export function StatTile({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="rounded-lg border border-line bg-surface-1 px-4 py-3">
      <div className="text-xs text-ink-muted">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
      {hint && <div className="mt-0.5 text-xs text-ink-2">{hint}</div>}
    </div>
  );
}

type Status = "good" | "warning" | "serious" | "critical" | "info";
const STATUS_ICON: Record<Status, string> = { good: "✓", warning: "!", serious: "!", critical: "✕", info: "i" };
const STATUS_CLASS: Record<Status, string> = {
  good: "border-good/40 text-good",
  warning: "border-warn/40 text-warn",
  serious: "border-serious/40 text-serious",
  critical: "border-critical/50 text-critical",
  info: "border-line text-ink-2",
};

/** Status always carries an icon and a text label, never colour alone. */
export function StatusPill({ status, children }: { status: Status; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs ${STATUS_CLASS[status]}`}>
      <span aria-hidden className="font-bold">{STATUS_ICON[status]}</span>
      <span className="text-ink-2">{children}</span>
    </span>
  );
}

export function Badge({ children }: { children: ReactNode }) {
  return <span className="rounded border border-line bg-surface-2 px-1.5 py-0.5 text-[11px] text-ink-2">{children}</span>;
}

export function LoadingState({ label = "Loading…" }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-2 py-8 text-sm text-ink-muted">
      <span className="h-3 w-3 animate-pulse rounded-full bg-accent" aria-hidden />
      {label}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const msg = error instanceof ApiError ? error.message : error instanceof Error ? error.message : "Unknown error";
  const code = error instanceof ApiError ? error.code : null;
  return (
    <div role="alert" className="rounded-md border border-critical/40 bg-critical/10 p-3 text-sm">
      <div className="font-medium text-ink">
        <span aria-hidden className="mr-1 text-critical">✕</span>
        {code === "unsupported_scenario" ? "This question cannot be answered from the stored data" : "Something went wrong"}
      </div>
      <p className="mt-1 text-ink-2">{msg}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-2 rounded border border-line px-2 py-1 text-xs hover:bg-surface-2">Retry</button>
      )}
    </div>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <div className="rounded-md border border-dashed border-line p-6 text-center text-sm text-ink-muted">{children}</div>;
}

export function InsufficientEvidence({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-md border border-warn/40 bg-warn/5 p-3 text-sm">
      <span aria-hidden className="mr-1 font-bold text-warn">!</span>
      <span className="font-medium">Insufficient evidence.</span> <span className="text-ink-2">{children}</span>
    </div>
  );
}

export function Warnings({ items }: { items: string[] }) {
  if (!items?.length) return null;
  return (
    <ul className="space-y-1">
      {items.map((w) => (
        <li key={w} className="flex gap-2 text-sm text-ink-2">
          <span aria-hidden className="font-bold text-warn">!</span>
          {w}
        </li>
      ))}
    </ul>
  );
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="flex flex-col gap-1 text-xs text-ink-muted">
      <span>{label}</span>
      {children}
      {hint && <span className="text-[11px] text-ink-muted">{hint}</span>}
    </label>
  );
}

export const inputClass =
  "rounded-md border border-line bg-surface-2 px-2 py-1.5 text-sm text-ink focus:border-accent focus:outline-none";

export function Select<T extends string | number>({ value, onChange, options, ariaLabel, className = "" }: {
  value: T | ""; onChange: (v: T) => void; options: { value: T; label: string }[]; ariaLabel: string; className?: string;
}) {
  return (
    <select aria-label={ariaLabel} className={`${inputClass} ${className}`} value={value}
      onChange={(e) => {
        const raw = e.target.value;
        const match = options.find((o) => String(o.value) === raw);
        if (match) onChange(match.value);
      }}>
      {options.map((o) => (
        <option key={String(o.value)} value={String(o.value)}>{o.label}</option>
      ))}
    </select>
  );
}

export function Button({ children, onClick, disabled, type = "button", variant = "primary" }: {
  children: ReactNode; onClick?: () => void; disabled?: boolean; type?: "button" | "submit"; variant?: "primary" | "ghost";
}) {
  const cls = variant === "primary"
    ? "bg-accent text-white hover:brightness-110 disabled:opacity-40"
    : "border border-line text-ink-2 hover:bg-surface-2 disabled:opacity-40";
  return (
    <button type={type} onClick={onClick} disabled={disabled} className={`rounded-md px-3 py-1.5 text-sm font-medium ${cls}`}>
      {children}
    </button>
  );
}

export function KV({ rows }: { rows: [ReactNode, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
      {rows.map(([k, v], i) => (
        <div key={i} className="contents">
          <dt className="text-ink-muted">{k}</dt>
          <dd className="tabular text-ink">{v}</dd>
        </div>
      ))}
    </dl>
  );
}
