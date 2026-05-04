"use client";

import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { useTheme } from "./ThemeProvider";

/**
 * Shared layout for secondary pages (/about, /architecture, /methods).
 * Mirrors the Hero/MissionPanel aesthetic so docs feel like a continuation
 * of the console rather than a separate marketing site.
 */
export function DocPage({
  eyebrow,
  title,
  intro,
  children,
}: {
  eyebrow: string;
  title: string;
  intro?: string;
  children: ReactNode;
}) {
  const { theme } = useTheme();
  const isLight = theme === "light";

  const fg = isLight ? "#0f172a" : "#e2e8f0";
  const muted = isLight ? "#475569" : "#94a3b8";
  const cyan = isLight ? "#0284c7" : "#38bdf8";
  const borderCol = isLight ? "#e2e8f0" : "#1e293b";
  const headerBg = isLight ? "#f8fafc" : "#0b1220";

  return (
    <main>
      <header
        className="relative border-b px-6 py-10 sm:py-14"
        style={{ borderColor: borderCol, background: headerBg }}
      >
        <div className="mx-auto flex max-w-6xl flex-col gap-3">
          <motion.p
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="font-mono text-[10px] uppercase tracking-[0.32em]"
            style={{ color: cyan }}
          >
            {eyebrow}
          </motion.p>
          <motion.h1
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, delay: 0.05 }}
            className="font-display text-4xl font-semibold leading-[1.05] tracking-[-0.01em] sm:text-5xl"
            style={{ color: fg }}
          >
            {title}
          </motion.h1>
          {intro && (
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.45, delay: 0.1 }}
              className="max-w-3xl text-[13px] leading-relaxed sm:text-sm"
              style={{ color: muted }}
            >
              {intro}
            </motion.p>
          )}
        </div>
      </header>
      <div
        className="mx-auto max-w-6xl px-6 py-10 sm:py-14"
        style={{ color: fg }}
      >
        {children}
      </div>
    </main>
  );
}

/**
 * Section header consistent with the numeric "// 01" / "// 02" markers on
 * the console page, but for docs (no numbering — sequential headings).
 */
export function Section({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  const { theme } = useTheme();
  const isLight = theme === "light";
  const fg = isLight ? "#0f172a" : "#e2e8f0";
  const muted = isLight ? "#475569" : "#94a3b8";
  const cyan = isLight ? "#0284c7" : "#38bdf8";
  const borderCol = isLight ? "#e2e8f0" : "#1e293b";

  return (
    <section className="mt-12 first:mt-0">
      <div
        className="mb-4 flex items-center gap-3 border-b pb-2 font-mono text-[10px] uppercase tracking-[0.28em]"
        style={{ borderColor: borderCol }}
      >
        <span
          className="inline-block h-1 w-1 rounded-full"
          style={{ backgroundColor: cyan }}
          aria-hidden="true"
        />
        <span style={{ color: muted }}>{title}</span>
      </div>
      <div
        className="space-y-4 text-[13px] leading-relaxed sm:text-sm"
        style={{ color: fg }}
      >
        {children}
      </div>
    </section>
  );
}

/**
 * Small key/value table styled like the Hero's facts grid.
 */
export function FactGrid({
  items,
}: {
  items: { label: string; value: string; note?: string }[];
}) {
  const { theme } = useTheme();
  const isLight = theme === "light";
  const fg = isLight ? "#0f172a" : "#e2e8f0";
  const muted = isLight ? "#475569" : "#94a3b8";
  const dim = isLight ? "#94a3b8" : "#64748b";
  const borderCol = isLight ? "#e2e8f0" : "#1e293b";
  const bg = isLight ? "#f8fafc" : "#0b1220";

  return (
    <dl
      className="grid w-full grid-cols-1 gap-px border sm:grid-cols-2 md:grid-cols-3"
      style={{ borderColor: borderCol, background: borderCol }}
    >
      {items.map((it) => (
        <div
          key={it.label}
          className="flex flex-col gap-1 px-4 py-3"
          style={{ background: bg }}
        >
          <dt
            className="font-mono text-[9px] uppercase tracking-[0.25em]"
            style={{ color: dim }}
          >
            {it.label}
          </dt>
          <dd className="flex items-baseline gap-2">
            <span className="font-mono text-sm" style={{ color: fg }}>
              {it.value}
            </span>
            {it.note && (
              <span
                className="font-mono text-[9px] uppercase tracking-widest"
                style={{ color: muted }}
              >
                {it.note}
              </span>
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}
