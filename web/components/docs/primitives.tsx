"use client";

import type { ReactNode } from "react";
import { motion, useReducedMotion } from "framer-motion";

import { useTheme } from "@/components/ThemeProvider";

/* ──────────────────────────────────────────────────────────────
   Shared theme palette for documentation pages. Single source of
   truth so every diagram resolves the same cyan / amber / muted /
   border colors. Mirrors the Hero & DocPage palette.
   ────────────────────────────────────────────────────────────── */
export function useDocTheme() {
  const { theme } = useTheme();
  const isLight = theme === "light";
  return {
    isLight,
    fg: isLight ? "#0f172a" : "#e2e8f0",
    muted: isLight ? "#475569" : "#94a3b8",
    dim: isLight ? "#94a3b8" : "#64748b",
    cyan: isLight ? "#0284c7" : "#38bdf8",
    amber: "#f59e0b",
    emerald: isLight ? "#059669" : "#34d399",
    rose: "#f43f5e",
    border: isLight ? "#e2e8f0" : "#1e293b",
    borderStrong: isLight ? "#cbd5e1" : "#334155",
    panel: isLight ? "#f8fafc" : "#0b1220",
    panelDeep: isLight ? "#f1f5f9" : "#060c1a",
  };
}

/* ──────────────────────────────────────────────────────────────
   MetricCell — oscilloscope-style readout with big mono number,
   units, label, and an optional small note. Used in headline
   metric boards. NEVER uses border-left stripes.
   ────────────────────────────────────────────────────────────── */
export function MetricCell({
  value,
  unit,
  label,
  note,
  state = "nominal",
  index,
}: {
  value: string;
  unit?: string;
  label: string;
  note?: string;
  state?: "nominal" | "watch" | "muted";
  index?: string;
}) {
  const t = useDocTheme();
  const valueColor =
    state === "nominal" ? t.cyan : state === "watch" ? t.amber : t.fg;

  return (
    <div
      className="relative flex flex-col justify-between gap-3 px-4 py-4 sm:px-5 sm:py-5"
      style={{ background: t.panel }}
    >
      <div className="flex items-center justify-between gap-2">
        <span
          className="font-mono text-[9px] uppercase tracking-[0.28em]"
          style={{ color: t.dim }}
        >
          {label}
        </span>
        {index && (
          <span
            className="font-mono text-[9px] tracking-widest"
            style={{ color: t.dim }}
          >
            {index}
          </span>
        )}
      </div>
      <div className="flex items-baseline gap-1.5">
        <span
          className="font-mono text-2xl font-semibold tabular-nums sm:text-3xl"
          style={{ color: valueColor }}
        >
          {value}
        </span>
        {unit && (
          <span
            className="font-mono text-[11px] uppercase tracking-widest"
            style={{ color: t.muted }}
          >
            {unit}
          </span>
        )}
      </div>
      {note && (
        <span
          className="font-mono text-[10px] uppercase tracking-widest"
          style={{ color: t.muted }}
        >
          {note}
        </span>
      )}
    </div>
  );
}

/* ──────────────────────────────────────────────────────────────
   MetricBoard — grid wrapper for MetricCell. Uses 1px gap fill
   so cells share borders, like a periodic table layout.
   ────────────────────────────────────────────────────────────── */
export function MetricBoard({
  children,
  cols = 3,
}: {
  children: ReactNode;
  cols?: 2 | 3 | 4;
}) {
  const t = useDocTheme();
  const colClass =
    cols === 2
      ? "sm:grid-cols-2"
      : cols === 4
      ? "sm:grid-cols-2 lg:grid-cols-4"
      : "sm:grid-cols-2 lg:grid-cols-3";
  return (
    <div
      className={`grid grid-cols-1 gap-px border ${colClass}`}
      style={{ borderColor: t.border, background: t.border }}
    >
      {children}
    </div>
  );
}

/* ──────────────────────────────────────────────────────────────
   Callout — a flush bordered panel that holds a labeled fact or
   short prose. Used for "Why ilmenite?" type emphasis cards.
   No border-stripes; uses a small status-dot + label header.
   ────────────────────────────────────────────────────────────── */
export function Callout({
  label,
  title,
  children,
  tone = "cyan",
}: {
  label: string;
  title?: string;
  children: ReactNode;
  tone?: "cyan" | "amber" | "emerald";
}) {
  const t = useDocTheme();
  const tint =
    tone === "amber" ? t.amber : tone === "emerald" ? t.emerald : t.cyan;
  return (
    <aside
      className="flex flex-col gap-3 border px-5 py-5"
      style={{ borderColor: t.border, background: t.panel }}
    >
      <div
        className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.28em]"
        style={{ color: tint }}
      >
        <span
          className="inline-block h-1.5 w-1.5 rounded-full"
          style={{ backgroundColor: tint }}
          aria-hidden="true"
        />
        {label}
      </div>
      {title && (
        <h3
          className="font-display text-xl font-semibold leading-snug"
          style={{ color: t.fg }}
        >
          {title}
        </h3>
      )}
      <div
        className="space-y-2 text-[13px] leading-relaxed"
        style={{ color: t.muted }}
      >
        {children}
      </div>
    </aside>
  );
}

/* ──────────────────────────────────────────────────────────────
   StatusRow — single line in a status board (REAL / PENDING).
   Uses a glyph + monospace label + status text. Color is paired
   with a textual code so color is never the sole signal.
   ────────────────────────────────────────────────────────────── */
export function StatusRow({
  label,
  status,
  state,
}: {
  label: string;
  status: string;
  state: "ok" | "pending" | "blocked";
}) {
  const t = useDocTheme();
  const tint =
    state === "ok" ? t.cyan : state === "pending" ? t.amber : t.rose;
  const glyph = state === "ok" ? "■" : state === "pending" ? "◇" : "△";
  return (
    <li
      className="flex items-center justify-between gap-4 border-t py-2.5 first:border-t-0"
      style={{ borderColor: t.border }}
    >
      <span
        className="flex items-center gap-3 font-mono text-[12px]"
        style={{ color: t.fg }}
      >
        <span
          className="font-mono text-[12px] leading-none"
          style={{ color: tint }}
          aria-hidden="true"
        >
          {glyph}
        </span>
        {label}
      </span>
      <span
        className="font-mono text-[10px] uppercase tracking-[0.25em]"
        style={{ color: tint }}
      >
        {status}
      </span>
    </li>
  );
}

/* ──────────────────────────────────────────────────────────────
   PageGrid — opinionated 12-col grid wrapper for two-column
   prose+visual layouts. Keeps the page rhythm consistent.
   ────────────────────────────────────────────────────────────── */
export function PageGrid({
  children,
  cols = "1-1",
}: {
  children: ReactNode;
  cols?: "1-1" | "2-1" | "1-2";
}) {
  const ratio =
    cols === "2-1"
      ? "lg:grid-cols-[2fr_1fr]"
      : cols === "1-2"
      ? "lg:grid-cols-[1fr_2fr]"
      : "lg:grid-cols-2";
  return (
    <div className={`grid grid-cols-1 gap-6 ${ratio}`}>{children}</div>
  );
}

/* ──────────────────────────────────────────────────────────────
   FadeIn — calm scroll-reveal. Slow ease-out-quart for a
   reading-page rhythm; respects prefers-reduced-motion so
   reduced-motion users get content immediately.
   ────────────────────────────────────────────────────────────── */
export function FadeIn({
  children,
  delay = 0,
}: {
  children: ReactNode;
  delay?: number;
}) {
  const reduce = useReducedMotion();
  if (reduce) return <>{children}</>;
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-80px" }}
      transition={{ duration: 0.6, delay, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </motion.div>
  );
}
