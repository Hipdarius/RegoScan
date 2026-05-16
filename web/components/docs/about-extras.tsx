"use client";

import type { ReactNode } from "react";
import { useDocTheme } from "./primitives";

/* =============================================================
   ProbeSchematic — top-down schematic of the handheld probe
   showing the four optical channels arranged around the
   sample window. Pure SVG, no images.
   ============================================================= */
export function ProbeSchematic() {
  const t = useDocTheme();
  const w = 460;
  const h = 280;
  const cx = w / 2;
  const cy = h / 2;

  const channels = [
    { name: "C12880MA", spec: "VIS/NIR · 288 ch", angle: -90, color: t.cyan },
    { name: "AS7265x",  spec: "Triad · 18 ch",    angle:   0, color: t.emerald },
    { name: "InGaAs",   spec: "SWIR · 940/1050",  angle:  90, color: t.amber },
    { name: "405 nm",   spec: "LIF laser",        angle: 180, color: t.rose },
  ];
  const r = 92;

  return (
    <div
      className="flex flex-col gap-3 border px-5 py-5"
      style={{ borderColor: t.border, background: t.panel }}
    >
      <div
        className="flex items-center justify-between font-mono text-[10px] uppercase tracking-[0.28em]"
        style={{ color: t.muted }}
      >
        <span>Probe head · top view</span>
        <span style={{ color: t.dim }}>4 modalities · 1 sample window</span>
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} role="img" aria-label="Probe schematic">
        {/* Outer probe body */}
        <rect
          x={cx - 130}
          y={cy - 110}
          width={260}
          height={220}
          fill={t.panelDeep}
          stroke={t.borderStrong}
          strokeWidth={1}
        />
        {/* Sample window */}
        <circle
          cx={cx}
          cy={cy}
          r={32}
          fill="none"
          stroke={t.fg}
          strokeWidth={1}
          strokeDasharray="3 3"
        />
        <text
          x={cx}
          y={cy + 4}
          fontFamily="var(--font-mono), monospace"
          fontSize="9"
          fill={t.muted}
          textAnchor="middle"
        >
          REGOLITH
        </text>
        <text
          x={cx}
          y={cy + 16}
          fontFamily="var(--font-mono), monospace"
          fontSize="9"
          fill={t.dim}
          textAnchor="middle"
        >
          SAMPLE
        </text>

        {/* 12-LED illumination ring */}
        {Array.from({ length: 12 }).map((_, i) => {
          const ang = (i / 12) * Math.PI * 2 - Math.PI / 2;
          const lx = cx + Math.cos(ang) * 50;
          const ly = cy + Math.sin(ang) * 50;
          return (
            <circle
              key={i}
              cx={lx}
              cy={ly}
              r={2.2}
              fill={t.amber}
              opacity={0.85}
            />
          );
        })}

        {/* Channel modules + leader lines */}
        {channels.map((ch) => {
          const rad = (ch.angle * Math.PI) / 180;
          const mx = cx + Math.cos(rad) * r;
          const my = cy + Math.sin(rad) * r;
          // Module box at edge of probe body
          const isHorizontal = Math.abs(Math.cos(rad)) > 0.9;
          const boxW = 96;
          const boxH = 28;
          const ex = cx + Math.cos(rad) * (isHorizontal ? 110 : 60);
          const ey = cy + Math.sin(rad) * (isHorizontal ? 60 : 90);
          const bx = ex - boxW / 2;
          const by = ey - boxH / 2;
          return (
            <g key={ch.name}>
              <line
                x1={mx}
                y1={my}
                x2={ex}
                y2={ey}
                stroke={ch.color}
                strokeWidth={1}
              />
              <circle cx={mx} cy={my} r={3} fill={ch.color} />
              <rect
                x={bx}
                y={by}
                width={boxW}
                height={boxH}
                fill={t.panelDeep}
                stroke={ch.color}
                strokeWidth={1}
              />
              <text
                x={ex}
                y={ey - 2}
                fontFamily="var(--font-mono), monospace"
                fontSize="10"
                fill={ch.color}
                textAnchor="middle"
              >
                {ch.name}
              </text>
              <text
                x={ex}
                y={ey + 9}
                fontFamily="var(--font-mono), monospace"
                fontSize="8"
                fill={t.muted}
                textAnchor="middle"
              >
                {ch.spec}
              </text>
            </g>
          );
        })}

        {/* Bottom legend */}
        <text
          x={cx}
          y={h - 12}
          fontFamily="var(--font-mono), monospace"
          fontSize="9"
          fill={t.dim}
          textAnchor="middle"
        >
          12 narrowband LEDs · 365 – 1050 nm
        </text>
      </svg>
    </div>
  );
}

/* =============================================================
   Roadmap — vertical mission timeline with completed and
   pending milestones. Each item carries date, title, and a
   status code (DONE / NEXT / LATER).
   ============================================================= */
export function Roadmap() {
  const t = useDocTheme();
  type Item = {
    code: string;
    date: string;
    title: string;
    state: "done" | "next" | "later";
  };
  const items: Item[] = [
    { code: "M0", date: "Apr 2026", title: "Synthetic data pipeline (linear + Hapke)",        state: "done"  },
    { code: "M1", date: "Apr 2026", title: "1D ResNet trained · 99.3 % cross-seed acc.",      state: "done"  },
    { code: "M2", date: "Apr 2026", title: "ONNX export · INT8 lossless · 707 KB",            state: "done"  },
    { code: "M3", date: "Apr 2026", title: "Calibration · uncertainty · OOD · active learning",state: "done"  },
    { code: "M4", date: "Apr 2026", title: "FastAPI service · Next.js console · 214 tests",   state: "done"  },
    { code: "M5", date: "May 2026", title: "Probe assembly (C12880MA + AS7265x + SWIR + LIF)", state: "next"  },
    { code: "M6", date: "Jun 2026", title: "BaSO₄ white reference + endmember capture",       state: "next"  },
    { code: "M7", date: "Jul 2026", title: "Real-sample temperature scaling refit",            state: "later" },
    { code: "M8", date: "Aug 2026", title: "TFLite Micro flash to ESP32-S3 · live demo",      state: "later" },
    { code: "M9", date: "2027",     title: "Jonk Fuerscher submission · paper writeup",       state: "later" },
  ];
  const tint = (s: Item["state"]) =>
    s === "done" ? t.cyan : s === "next" ? t.amber : t.dim;
  const code = (s: Item["state"]) =>
    s === "done" ? "DONE" : s === "next" ? "NEXT" : "LATER";

  return (
    <div
      className="border"
      style={{ borderColor: t.border, background: t.panel }}
    >
      <div
        className="flex items-center justify-between border-b px-5 py-2 font-mono text-[10px] uppercase tracking-[0.28em]"
        style={{ borderColor: t.border, color: t.cyan }}
      >
        <span>Mission roadmap</span>
        <span style={{ color: t.dim }}>{items.filter(i => i.state === "done").length} of {items.length} milestones</span>
      </div>
      <ol>
        {items.map((it) => (
          <li
            key={it.code}
            className="grid grid-cols-[60px_88px_1fr_72px] items-center gap-3 border-b px-5 py-3 last:border-b-0"
            style={{ borderColor: t.border }}
          >
            <span
              className="font-mono text-[11px] uppercase tracking-widest"
              style={{ color: tint(it.state) }}
            >
              {it.code}
            </span>
            <span
              className="font-mono text-[11px]"
              style={{ color: t.muted }}
            >
              {it.date}
            </span>
            <span
              className="font-mono text-[12px]"
              style={{ color: t.fg }}
            >
              {it.title}
            </span>
            <span
              className="text-right font-mono text-[10px] uppercase tracking-[0.25em]"
              style={{ color: tint(it.state) }}
            >
              {code(it.state)}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

/* =============================================================
   BibCard — single citation rendered as a labeled card. Used
   in the Standing-on-the-shoulders-of section in place of
   inline parentheticals.
   ============================================================= */
export function BibCard({
  authors,
  year,
  title,
  venue,
  contribution,
}: {
  authors: string;
  year: string;
  title: string;
  venue: string;
  contribution: string;
}) {
  const t = useDocTheme();
  return (
    <div
      className="flex flex-col gap-2 border px-4 py-3"
      style={{ borderColor: t.border, background: t.panel }}
    >
      <div className="flex items-baseline justify-between gap-2">
        <span
          className="font-mono text-[11px] font-semibold"
          style={{ color: t.cyan }}
        >
          {authors}
        </span>
        <span
          className="font-mono text-[10px] tabular-nums"
          style={{ color: t.dim }}
        >
          {year}
        </span>
      </div>
      <span
        className="font-display text-[13px] leading-snug"
        style={{ color: t.fg }}
      >
        {title}
      </span>
      <span
        className="font-mono text-[10px] uppercase tracking-widest"
        style={{ color: t.muted }}
      >
        {venue}
      </span>
      <span
        className="border-t pt-2 font-mono text-[11px]"
        style={{ borderColor: t.border, color: t.amber }}
      >
        → {contribution}
      </span>
    </div>
  );
}

/* =============================================================
   SplitColumn — labeled two-column container used for "what's
   real / what's pending" status board. Keeps headers aligned
   and rules uniform across the two halves.
   ============================================================= */
export function SplitColumn({
  left,
  right,
  leftTitle,
  rightTitle,
  leftLabel,
  rightLabel,
}: {
  left: ReactNode;
  right: ReactNode;
  leftTitle: string;
  rightTitle: string;
  leftLabel: string;
  rightLabel: string;
}) {
  const t = useDocTheme();
  return (
    <div className="grid grid-cols-1 gap-px border md:grid-cols-2"
         style={{ borderColor: t.border, background: t.border }}>
      <div className="flex flex-col gap-3 px-5 py-4" style={{ background: t.panel }}>
        <div className="flex items-center justify-between">
          <span className="font-mono text-[10px] uppercase tracking-[0.28em]" style={{ color: t.cyan }}>
            {leftLabel}
          </span>
          <span className="font-mono text-[10px] uppercase tracking-widest" style={{ color: t.dim }}>
            {leftTitle}
          </span>
        </div>
        <div>{left}</div>
      </div>
      <div className="flex flex-col gap-3 px-5 py-4" style={{ background: t.panel }}>
        <div className="flex items-center justify-between">
          <span className="font-mono text-[10px] uppercase tracking-[0.28em]" style={{ color: t.amber }}>
            {rightLabel}
          </span>
          <span className="font-mono text-[10px] uppercase tracking-widest" style={{ color: t.dim }}>
            {rightTitle}
          </span>
        </div>
        <div>{right}</div>
      </div>
    </div>
  );
}
