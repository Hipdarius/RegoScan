"use client";

import { Fragment, useEffect, useRef, useState, type ReactNode } from "react";
import {
  motion,
  useReducedMotion,
  useScroll,
  useTransform,
} from "framer-motion";

import { useDocTheme } from "./docs/primitives";

// Capture the JS built-in before our `Math` React component (declared
// later in this file) shadows it. All numeric helpers below use M.*.
const M = globalThis.Math;

/* =============================================================
   Page rhythm tokens — single source of truth for vertical
   pacing on doc pages. Header padding equals the body section
   gap so the page reads with one ramp instead of two.
   ============================================================= */
const PAGE_GUTTER = "clamp(96px, 12vh, 160px)";
const READING_WIDTH = "64ch";

/* =============================================================
   DocPage — quiet shell for /about, /architecture, /methods.
   - aside slot: renders next to the title in the page header
     (e.g., the probe schematic on /about). Hidden below lg.
   - vitals slot: a single mono row directly under the header
     for at-a-glance stats (mass / power / TRL / BOM).
   - tagline override: replaces the templated eyebrow when the
     identity is the eyebrow (builder + institution).
   - marginNav slot: sticky right-rail TOC at lg+.
   ============================================================= */
export function DocPage({
  eyebrow,
  title,
  intro,
  aside,
  vitals,
  marginNav,
  children,
}: {
  eyebrow: string;
  title: string;
  intro?: string;
  aside?: ReactNode;
  vitals?: ReactNode;
  marginNav?: ReactNode;
  children: ReactNode;
}) {
  const t = useDocTheme();
  const reduce = useReducedMotion();
  const ease = [0.16, 1, 0.3, 1] as const;
  const headerRef = useRef<HTMLElement>(null);

  // Header dims and drifts up as the reader scrolls past it. Range
  // [start, end] = [0, full height of the header]. Mapped to opacity
  // 1 → 0.45 and translateY 0 → −24px. Subtle: it tells the eye
  // "the chrome is yielding to the content", not "look at me".
  const { scrollY } = useScroll();
  const headerHeightRef = useRef(0);
  useEffect(() => {
    if (!headerRef.current) return;
    headerHeightRef.current = headerRef.current.offsetHeight;
    const ro = new ResizeObserver(() => {
      if (headerRef.current)
        headerHeightRef.current = headerRef.current.offsetHeight;
    });
    ro.observe(headerRef.current);
    return () => ro.disconnect();
  }, []);
  const headerOpacity = useTransform(
    scrollY,
    (y) => {
      if (reduce) return 1;
      const h = M.max(headerHeightRef.current, 1);
      return M.max(0.45, 1 - (y / h) * 0.55);
    }
  );
  const headerY = useTransform(scrollY, (y) => {
    if (reduce) return 0;
    const h = M.max(headerHeightRef.current, 1);
    return -M.min(24, (y / h) * 24);
  });

  const headerAnim = (delay: number) =>
    reduce
      ? { initial: false }
      : {
          initial: { opacity: 0, y: 8 },
          animate: { opacity: 1, y: 0 },
          transition: { duration: 0.7, delay, ease },
        };

  const headerText = (
    <div className="flex flex-col gap-7">
      <motion.p
        {...headerAnim(0)}
        className="font-mono text-[10px] uppercase tracking-[0.42em]"
        style={{ color: t.cyan }}
      >
        {eyebrow}
      </motion.p>
      <motion.h1
        {...headerAnim(0.05)}
        className="font-display font-semibold tracking-[-0.02em]"
        style={{
          color: t.fg,
          fontSize: "clamp(2.25rem, 4.6vw, 3.75rem)",
          lineHeight: 1.04,
          maxWidth: "22ch",
        }}
      >
        {title}
      </motion.h1>
      {intro && (
        <motion.p
          {...headerAnim(0.1)}
          className="font-mono"
          style={{
            color: t.muted,
            maxWidth: "62ch",
            fontSize: "0.875rem",
            lineHeight: 1.75,
          }}
        >
          {intro}
        </motion.p>
      )}
    </div>
  );

  return (
    <main style={{ color: t.fg }}>
      <header
        ref={headerRef}
        className="border-b px-6"
        style={{
          borderColor: t.border,
          background: t.panelDeep,
          paddingTop: PAGE_GUTTER,
          paddingBottom: PAGE_GUTTER,
        }}
      >
        <motion.div
          className="mx-auto max-w-[1100px]"
          style={{ opacity: headerOpacity, y: headerY, willChange: "transform, opacity" }}
        >
          {aside ? (
            <div className="grid grid-cols-1 items-center gap-12 lg:grid-cols-[1fr_minmax(360px,460px)]">
              {headerText}
              <motion.div
                {...headerAnim(0.15)}
                className="hidden lg:block"
              >
                {aside}
              </motion.div>
            </div>
          ) : (
            headerText
          )}
        </motion.div>
      </header>
      {vitals && (
        <div
          className="border-b px-6"
          style={{ borderColor: t.border, background: t.panel }}
        >
          <div className="mx-auto max-w-[1100px] py-5">{vitals}</div>
        </div>
      )}
      <div
        className="mx-auto max-w-[1100px] px-6"
        style={{
          paddingTop: PAGE_GUTTER,
          paddingBottom: PAGE_GUTTER,
        }}
      >
        {marginNav ? (
          <div className="grid grid-cols-1 gap-x-12 lg:grid-cols-[1fr_140px]">
            <div className="min-w-0">{children}</div>
            <div className="hidden lg:block">{marginNav}</div>
          </div>
        ) : (
          children
        )}
      </div>
    </main>
  );
}

/* =============================================================
   Section — numbered anchor block. Top spacing equals the
   page gutter so header → first section and section → section
   read with the same rhythm.
   ============================================================= */
export function Section({
  number,
  title,
  children,
}: {
  number: string;
  title: string;
  children: ReactNode;
}) {
  const t = useDocTheme();
  const reduce = useReducedMotion();
  const ease = [0.16, 1, 0.3, 1] as const;

  // Staggered reveal: the section number fades in first, then a
  // hairline draws across to the title (tuning sweep), then the
  // title rises into place. Triggers once when the section enters
  // viewport. Disabled for reduced-motion.
  const container = reduce
    ? {}
    : {
        initial: "hidden",
        whileInView: "show",
        viewport: { once: true, margin: "-80px" },
        variants: {
          hidden: {},
          show: {
            transition: { staggerChildren: 0.12, delayChildren: 0.05 },
          },
        },
      };
  const numberV = reduce
    ? {}
    : {
        variants: {
          hidden: { opacity: 0, y: 6 },
          show: { opacity: 1, y: 0, transition: { duration: 0.5, ease } },
        },
      };
  const lineV = reduce
    ? {}
    : {
        variants: {
          hidden: { scaleX: 0 },
          show: {
            scaleX: 1,
            transition: { duration: 0.85, ease: [0.83, 0, 0.17, 1] },
          },
        },
      };
  const titleV = reduce
    ? {}
    : {
        variants: {
          hidden: { opacity: 0, y: 10 },
          show: { opacity: 1, y: 0, transition: { duration: 0.6, ease } },
        },
      };

  return (
    <section
      id={`s${number}`}
      className="scroll-mt-24 first:!mt-0"
      style={{ marginTop: PAGE_GUTTER }}
    >
      <motion.div
        {...container}
        className="mb-10 flex flex-col gap-3 sm:mb-12 sm:flex-row sm:items-baseline sm:gap-5"
      >
        <motion.span
          {...numberV}
          className="font-mono text-[11px] tabular-nums tracking-[0.28em]"
          style={{ color: t.cyan }}
        >
          {number}
        </motion.span>
        <motion.span
          aria-hidden="true"
          {...lineV}
          className="hidden sm:block"
          style={{
            height: 1,
            width: 36,
            background: t.cyan,
            opacity: 0.45,
            transformOrigin: "0% 50%",
            alignSelf: "center",
          }}
        />
        <motion.h2
          {...titleV}
          className="font-display font-semibold tracking-[-0.015em]"
          style={{
            color: t.fg,
            fontSize: "clamp(1.5rem, 2.6vw, 2.25rem)",
            lineHeight: 1.1,
          }}
        >
          {title}
        </motion.h2>
      </motion.div>
      <div className="flex flex-col gap-10">{children}</div>
    </section>
  );
}

/* =============================================================
   Math — inline math typography. Switches to a serif math-font
   chain so Greek letters and italic variables typeset like an
   equation, not like body code. Pair with native <sub>/<sup>
   for subscripts/superscripts (e.g. <Math>τ<sub>p</sub></Math>).
   No KaTeX dependency — chosen to keep the bundle minimal for
   the limited number of formulas this site carries.
   ============================================================= */
const MATH_STACK =
  '"STIX Two Math", "Latin Modern Math", "Cambria Math", "Times New Roman", "Liberation Serif", serif';

export function Math({ children }: { children: ReactNode }) {
  return (
    <span
      style={{
        fontFamily: MATH_STACK,
        fontStyle: "italic",
        fontSize: "1.06em",
        letterSpacing: "0.005em",
        whiteSpace: "nowrap",
      }}
    >
      {children}
    </span>
  );
}

/* =============================================================
   Eq — block-level equation. Centered in its column with
   breathing room. For set-piece formulas (Hapke roundtrip,
   ilmenite reduction).
   ============================================================= */
export function Eq({ children }: { children: ReactNode }) {
  const t = useDocTheme();
  return (
    <div
      className="my-1 flex items-center px-4 py-3"
      style={{
        fontFamily: MATH_STACK,
        fontStyle: "italic",
        fontSize: "1.125rem",
        lineHeight: 1.5,
        letterSpacing: "0.01em",
        color: t.fg,
        background: t.panelDeep,
        border: `1px solid ${t.border}`,
      }}
    >
      {children}
    </div>
  );
}

/* =============================================================
   SubSection — used inside a Section to anchor a sub-numbered
   block (e.g., 06.1 Active learning, 06.2 Mixing ablation).
   Smaller than Section, larger than a paragraph.
   ============================================================= */
export function SubSection({
  number,
  title,
  children,
}: {
  number: string;
  title: string;
  children: ReactNode;
}) {
  const t = useDocTheme();
  return (
    <div
      className="scroll-mt-24 flex flex-col gap-6 pt-12 first:pt-0"
      style={{ borderTop: `1px solid ${t.border}` }}
      id={`s${number}`}
    >
      <div className="flex items-baseline gap-4">
        <span
          className="font-mono text-[11px] tabular-nums tracking-[0.28em]"
          style={{ color: t.cyan }}
        >
          {number}
        </span>
        <h3
          className="font-display font-semibold tracking-[-0.01em]"
          style={{
            color: t.fg,
            fontSize: "clamp(1.125rem, 1.8vw, 1.5rem)",
            lineHeight: 1.2,
          }}
        >
          {title}
        </h3>
      </div>
      <div className="flex flex-col gap-8">{children}</div>
    </div>
  );
}

/* =============================================================
   Prose — reading column at 64ch. Calmer body color than t.fg
   to keep long-form text from glaring. Inherits the project's
   monospace voice with a relaxed measure.
   ============================================================= */
export function Prose({ children }: { children: ReactNode }) {
  const t = useDocTheme();
  const body = t.isLight ? "#334155" : "#cbd5e1";
  return (
    <div
      className="flex flex-col gap-5 font-mono"
      style={{
        color: body,
        maxWidth: READING_WIDTH,
        fontSize: "0.875rem",
        lineHeight: 1.78,
      }}
    >
      {children}
    </div>
  );
}

/* =============================================================
   CountUpValue — splits a value string into [prefix, number,
   suffix] and tweens the numeric portion from 0 → target on
   first viewport entry. Reads as an instrument calibrating onto
   a measurement (the headline numbers feel measured, not typed).
   Reserves the final character width with a fixed minWidth so
   layout doesn't jitter while ticking.
   ============================================================= */
function CountUpValue({ value }: { value: string }) {
  // Earlier revisions tweened the numeric portion from 0 → target on
  // first viewport entry. That coupled the headline metrics to React
  // 18 StrictMode's double-invoke and to Next.js client-side navigation,
  // which produced two visible failure modes: numbers that restarted
  // from 0 on every parent rerender (MarginNav scroll updates), and
  // numbers that never reached their target on a second visit to the
  // page. The reliability budget for a science-fair headline number is
  // zero. Render the static value as written. Keep the parse so we can
  // reserve the numeric width and avoid layout jitter if a future rev
  // restores the tween behind a stable feature flag.
  const m = value.match(/^([^\d-]*)(-?\d+(?:\.\d+)?)([\s\S]*)$/);
  if (!m) return <span>{value}</span>;
  const prefix = m[1];
  const number = m[2];
  const suffix = m[3];
  const numCharCount = number.length;
  return (
    <span>
      {prefix}
      <span
        style={{
          display: "inline-block",
          minWidth: `${numCharCount}ch`,
          textAlign: "right",
        }}
      >
        {number}
      </span>
      {suffix}
    </span>
  );
}

/* =============================================================
   MetricRow — editorial replacement for MetricHero. Each metric
   takes its own row: large mono number on the left, one-sentence
   caption on the right. Reads as Apple-ML "we measured X" rather
   than "stats hero block".
   ============================================================= */
export function MetricRow({
  items,
}: {
  items: { value: string; unit?: string; label: string; caption: string }[];
}) {
  const t = useDocTheme();
  const body = t.isLight ? "#334155" : "#cbd5e1";
  return (
    <div className="flex flex-col">
      {items.map((item, i) => (
        <div
          key={item.label}
          className="grid grid-cols-1 gap-y-3 py-8 sm:grid-cols-[200px_1fr] sm:gap-x-12 sm:py-10"
          style={{
            borderTop: i === 0 ? "none" : `1px solid ${t.border}`,
          }}
        >
          <div className="flex flex-col gap-1.5">
            <div className="flex items-baseline gap-2">
              <span
                className="font-mono font-semibold tabular-nums"
                style={{
                  color: t.fg,
                  fontSize: "clamp(2rem, 3.6vw, 3rem)",
                  lineHeight: 0.95,
                  letterSpacing: "-0.02em",
                }}
              >
                <CountUpValue value={item.value} />
              </span>
              {item.unit && (
                <span
                  className="font-mono text-sm uppercase tracking-widest"
                  style={{ color: t.muted }}
                >
                  {item.unit}
                </span>
              )}
            </div>
            <span
              className="font-mono text-[10px] uppercase tracking-[0.28em]"
              style={{ color: t.dim }}
            >
              {item.label}
            </span>
          </div>
          <p
            className="font-mono"
            style={{
              color: body,
              fontSize: "0.875rem",
              lineHeight: 1.78,
              maxWidth: "60ch",
            }}
          >
            {item.caption}
          </p>
        </div>
      ))}
    </div>
  );
}

/* =============================================================
   VitalStats — single inline mono row directly under the page
   header. Used on /about for the "vital stats" block (mass,
   power, TRL, BOM) so a mission planner sees the engineering
   delta in the first viewport.
   ============================================================= */
export function VitalStats({
  items,
}: {
  items: { label: string; value: string }[];
}) {
  const t = useDocTheme();
  return (
    <dl className="grid grid-cols-2 gap-x-8 gap-y-3 sm:flex sm:flex-wrap sm:items-baseline sm:gap-x-10">
      {items.map((it) => (
        <div key={it.label} className="flex items-baseline gap-2.5">
          <dt
            className="font-mono text-[10px] uppercase tracking-[0.28em]"
            style={{ color: t.dim }}
          >
            {it.label}
          </dt>
          <dd
            className="font-mono text-[12px] tabular-nums"
            style={{ color: t.fg }}
          >
            {it.value}
          </dd>
        </div>
      ))}
    </dl>
  );
}

/* =============================================================
   SpecList — quiet two-column key/value list. Default size is
   "headline" (text-[13px]); pass size="footnote" for the
   smaller reproducibility variant so the two registers are
   distinguishable on a glance.
   ============================================================= */
export function SpecList({
  items,
  size = "headline",
}: {
  items: { label: string; value: string }[];
  size?: "headline" | "footnote";
}) {
  const t = useDocTheme();
  const valueSize = size === "footnote" ? "text-[11px]" : "text-[13px]";
  const labelSize = size === "footnote" ? "text-[9px]" : "text-[10px]";
  return (
    <dl
      className="grid grid-cols-1 gap-y-4 sm:grid-cols-[160px_1fr] sm:gap-x-8"
      style={{ borderTop: `1px solid ${t.border}` }}
    >
      {items.map((it) => (
        <Fragment key={it.label}>
          <dt
            className={`font-mono ${labelSize} uppercase tracking-[0.28em] sm:pt-3`}
            style={{ color: t.dim }}
          >
            {it.label}
          </dt>
          <dd
            className={`font-mono ${valueSize} sm:border-t sm:py-3`}
            style={{ color: t.fg, borderColor: t.border }}
          >
            {it.value}
          </dd>
        </Fragment>
      ))}
    </dl>
  );
}

/* =============================================================
   SymbolLegend — footer block defining the technical symbols
   that appear inline in /methods (τ_p, τ_m, τ_h, H̃, IMSA, ECE,
   SAM, OOD). For the technical-reviewer persona who needs a path
   to the definitions without leaving the page.
   ============================================================= */
export function SymbolLegend({
  items,
}: {
  items: { symbol: ReactNode; expansion: ReactNode }[];
}) {
  const t = useDocTheme();
  const body = t.isLight ? "#334155" : "#cbd5e1";
  return (
    <div className="flex flex-col gap-5">
      <span
        className="font-mono text-[10px] uppercase tracking-[0.28em]"
        style={{ color: t.dim }}
      >
        Symbols & abbreviations
      </span>
      <dl
        className="grid grid-cols-1 gap-y-2 sm:grid-cols-[100px_1fr] sm:gap-x-8"
      >
        {items.map((it, i) => (
          <Fragment key={i}>
            <dt
              className="text-[13px]"
              style={{ color: t.cyan }}
            >
              {it.symbol}
            </dt>
            <dd
              className="font-mono text-[12px]"
              style={{ color: body, lineHeight: 1.7 }}
            >
              {it.expansion}
            </dd>
          </Fragment>
        ))}
      </dl>
    </div>
  );
}

/* =============================================================
   Bibliography — typeset academic citations. Hanging-indent
   first line with author + year as the anchor; title in display
   font (the only place display escapes the page header); venue
   and contribution as smaller continuations. No rules between
   citations — spacing carries the separation.
   ============================================================= */
export function Bibliography({
  items,
  note,
}: {
  items: {
    authors: string;
    year: string;
    title: string;
    venue: string;
    used: string;
  }[];
  note?: string;
}) {
  const t = useDocTheme();
  const body = t.isLight ? "#334155" : "#cbd5e1";
  return (
    <div className="flex flex-col gap-4">
      {note && (
        <span
          className="font-mono text-[10px] uppercase tracking-[0.28em]"
          style={{ color: t.dim }}
        >
          {note}
        </span>
      )}
      <ol className="flex flex-col gap-7">
        {items.map((r) => (
          <li
            key={r.title}
            className="grid grid-cols-1 gap-1 sm:grid-cols-[200px_1fr] sm:gap-x-10"
          >
            <div className="flex items-baseline gap-3">
              <span
                className="font-mono text-[12px] font-semibold"
                style={{ color: t.fg }}
              >
                {r.authors}
              </span>
              <span
                className="font-mono text-[11px] tabular-nums"
                style={{ color: t.dim }}
              >
                {r.year}
              </span>
            </div>
            <div className="flex flex-col gap-1.5">
              <span
                className="font-display font-medium leading-snug"
                style={{
                  color: t.fg,
                  fontSize: "clamp(0.95rem, 1.2vw, 1.05rem)",
                  letterSpacing: "-0.005em",
                }}
              >
                {r.title}
              </span>
              <span
                className="font-mono text-[11px]"
                style={{ color: t.muted }}
              >
                {r.venue}
              </span>
              <span
                className="font-mono text-[11px]"
                style={{ color: body, lineHeight: 1.7, marginTop: 4 }}
              >
                <span style={{ color: t.cyan, marginRight: 6 }}>→</span>
                {r.used}
              </span>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

/* =============================================================
   MarginNav — sticky right-rail TOC. Active section's label is
   permanently visible; inactive sections show only the number
   and a short tick mark, label appearing on hover. Tracks
   active section via IntersectionObserver.
   ============================================================= */
export function MarginNav({
  items,
}: {
  items: { number: string; label: string }[];
}) {
  const t = useDocTheme();
  const [active, setActive] = useState(items[0]?.number ?? "");

  useEffect(() => {
    if (typeof window === "undefined") return;
    let raf = 0;

    // Reference line at 30% of the viewport: the active section is the
    // last one whose top has crossed it. Pin to the final section once
    // the viewport is within 8 px of the document end so short trailing
    // sections (which can never reach the reference line) still light up.
    const update = () => {
      raf = 0;
      const refY = window.innerHeight * 0.3;
      const scrollBottom = window.scrollY + window.innerHeight;
      const docHeight = document.documentElement.scrollHeight;

      if (docHeight - scrollBottom < 8) {
        const last = items[items.length - 1]?.number;
        if (last) setActive(last);
        return;
      }

      let current = items[0]?.number ?? "";
      for (const item of items) {
        const el = document.getElementById(`s${item.number}`);
        if (!el) continue;
        if (el.getBoundingClientRect().top <= refY) current = item.number;
        else break;
      }
      setActive(current);
    };

    const onScroll = () => {
      if (raf) return;
      raf = requestAnimationFrame(update);
    };

    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (raf) cancelAnimationFrame(raf);
    };
  }, [items]);

  return (
    <nav
      aria-label="On this page"
      className="sticky flex flex-col gap-3"
      style={{ top: "clamp(80px, 14vh, 140px)", alignSelf: "start" }}
    >
      <span
        className="font-mono text-[10px] uppercase tracking-[0.28em]"
        style={{ color: t.dim }}
      >
        On this page
      </span>
      <ul className="flex flex-col gap-2.5">
        {items.map((item) => {
          const isActive = active === item.number;
          return (
            <li key={item.number}>
              <a
                href={`#s${item.number}`}
                className="group flex items-center gap-3 font-mono text-[11px] tabular-nums tracking-[0.2em] transition-colors"
                style={{ color: isActive ? t.cyan : t.dim }}
              >
                <span
                  aria-hidden="true"
                  className="inline-block h-px transition-all"
                  style={{
                    background: isActive ? t.cyan : t.borderStrong,
                    width: isActive ? 24 : 12,
                  }}
                />
                <span>{item.number}</span>
                <span
                  className={
                    isActive
                      ? "opacity-100"
                      : "opacity-0 group-hover:opacity-100"
                  }
                  style={{
                    color: isActive ? t.fg : t.muted,
                    transition: "opacity 0.18s ease",
                  }}
                >
                  {item.label}
                </span>
              </a>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

/* =============================================================
   FactGrid — kept for backwards-compat with any consumer that
   still imports it. Not used by the recalibrated pages.
   ============================================================= */
export function FactGrid({
  items,
}: {
  items: { label: string; value: string; note?: string }[];
}) {
  const t = useDocTheme();
  return (
    <dl
      className="grid w-full grid-cols-1 gap-px border sm:grid-cols-2 md:grid-cols-3"
      style={{ borderColor: t.border, background: t.border }}
    >
      {items.map((it) => (
        <div
          key={it.label}
          className="flex flex-col gap-1 px-4 py-3"
          style={{ background: t.panel }}
        >
          <dt
            className="font-mono text-[9px] uppercase tracking-[0.25em]"
            style={{ color: t.dim }}
          >
            {it.label}
          </dt>
          <dd className="flex items-baseline gap-2">
            <span className="font-mono text-sm" style={{ color: t.fg }}>
              {it.value}
            </span>
            {it.note && (
              <span
                className="font-mono text-[9px] uppercase tracking-widest"
                style={{ color: t.muted }}
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
