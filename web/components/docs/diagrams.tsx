"use client";

import type { ReactNode } from "react";

import { Math as Mx } from "@/components/DocPage";
import { useDocTheme } from "./primitives";

/* =============================================================
   WavelengthCoverage — horizontal axis from 340 → 1100 nm with
   each sensor's coverage shown as a labeled band. Replaces a
   sentence ("288 channels from 340–850 nm…") with a glance.
   ============================================================= */
export function WavelengthCoverage() {
  const t = useDocTheme();

  // Wavelength domain: 340 → 1100 nm
  const xMin = 340;
  const xMax = 1100;
  const span = xMax - xMin;
  const x = (nm: number) => ((nm - xMin) / span) * 100;

  type Band = {
    label: string;
    from: number;
    to: number;
    note: string;
    color: string;
    row: 0 | 1 | 2;
  };
  const bands: Band[] = [
    { label: "C12880MA · 288 ch", from: 340, to: 850, note: "VIS / NIR", color: t.cyan, row: 0 },
    { label: "AS7265x · 18 ch",   from: 410, to: 940, note: "triad",     color: t.muted, row: 1 },
    { label: "InGaAs SWIR · 2 ch",from: 935, to: 1055,note: "Fe²⁺ band", color: t.amber, row: 2 },
  ];
  // 405 nm LIF rendered as a hairline tick rather than a 5-nm
  // band — at that width the band was decoration, not data.
  const lifTickNm = 405;
  const ticks = [400, 500, 600, 700, 800, 900, 1000];

  return (
    <div
      className="flex flex-col gap-4 border px-5 py-5"
      style={{ borderColor: t.border, background: t.panel }}
    >
      <div
        className="flex items-center justify-between font-mono text-[10px] uppercase tracking-[0.28em]"
        style={{ color: t.muted }}
      >
        <span>Spectral coverage</span>
        <span style={{ color: t.dim }}>{xMin} – {xMax} nm</span>
      </div>

      <div className="relative" style={{ height: `${bands.length * 28 + 28}px` }}>
        {/* Bands */}
        {bands.map((b) => {
          const left = x(b.from);
          const width = x(b.to) - left;
          const top = b.row * 28;
          return (
            <div
              key={b.label}
              className="absolute h-5 border"
              style={{
                left: `${left}%`,
                width: `${Math.max(width, 0.5)}%`,
                top,
                borderColor: b.color,
                background: `${b.color}22`,
              }}
              title={`${b.label}: ${b.from}–${b.to} nm`}
            >
              <span
                className="absolute -top-[10px] left-1 whitespace-nowrap font-mono text-[9px] uppercase tracking-widest"
                style={{ color: b.color }}
              >
                {b.label}
              </span>
              <span
                className="absolute right-1 top-1/2 -translate-y-1/2 font-mono text-[9px] uppercase tracking-widest"
                style={{ color: t.dim }}
              >
                {b.note}
              </span>
            </div>
          );
        })}

        {/* 405 nm LIF — vertical tick spanning all band rows */}
        <div
          className="absolute"
          style={{
            left: `${x(lifTickNm)}%`,
            top: 0,
            bottom: 8,
            width: 1,
            background: t.amber,
            opacity: 0.9,
          }}
          aria-label="405 nm LIF laser"
          title="405 nm LIF laser"
        />
        <span
          className="absolute font-mono text-[9px] uppercase tracking-widest"
          style={{
            left: `calc(${x(lifTickNm)}% + 6px)`,
            top: 0,
            color: t.amber,
          }}
        >
          405 LIF
        </span>

        {/* Axis */}
        <div
          className="absolute bottom-0 left-0 right-0 h-px"
          style={{ background: t.border }}
        />
        {ticks.map((tk) => (
          <div
            key={tk}
            className="absolute bottom-0 flex -translate-x-1/2 flex-col items-center"
            style={{ left: `${x(tk)}%` }}
          >
            <span
              className="h-1.5 w-px"
              style={{ background: t.borderStrong }}
              aria-hidden="true"
            />
            <span
              className="mt-1 font-mono text-[9px] tabular-nums"
              style={{ color: t.dim }}
            >
              {tk}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* =============================================================
   LayerStack — vertical stack of labeled blocks for the
   Architecture page hero. 5 layers: Optical → MCU → Bridge →
   Inference → Console. Each block carries hardware/software
   identifiers + a short capability line.
   ============================================================= */
export function LayerStack() {
  const t = useDocTheme();
  const layers: {
    n: string;
    name: string;
    impl: string;
    desc: string;
    out: string;
  }[] = [
    {
      n: "L5",
      name: "Console",
      impl: "Next.js 14 · React 18 · App Router",
      desc: "Spectrum, posterior, ilmenite gauge, mission log",
      out: "browser → human",
    },
    {
      n: "L4",
      name: "Inference service",
      impl: "FastAPI · ONNX Runtime · Python 3.12",
      desc: "1D ResNet · temperature scaling · OOD detector",
      out: "JSON posterior + uncertainty",
    },
    {
      n: "L3",
      name: "Bridge",
      impl: "USB-CDC · JSON line protocol",
      desc: "schema validate · CSV stream · feature ordering",
      out: "validated frames",
    },
    {
      n: "L2",
      name: "MCU firmware",
      impl: "ESP32-S3 · 240 MHz · 512 KB SRAM",
      desc: "FSM · adaptive integration · SWIR sub-states",
      out: "JSON @ ≥ 1 kHz loop",
    },
    {
      n: "L1",
      name: "Optical front end",
      impl: "C12880MA + AS7265x + InGaAs + 405 nm LIF",
      desc: "VIS/NIR + triad + SWIR Fe²⁺ + fluorescence",
      out: "analog → 16-bit ADC",
    },
  ];

  return (
    <div className="flex flex-col">
      <div
        className="flex items-center justify-between border-x border-t px-5 py-2 font-mono text-[10px] uppercase tracking-[0.28em]"
        style={{ borderColor: t.border, background: t.panel, color: t.cyan }}
      >
        <span>↑ Decision · class label · uncertainty</span>
        <span style={{ color: t.dim }}>output</span>
      </div>
      {layers.map((l, i) => (
        <div
          key={l.n}
          className="grid grid-cols-[60px_1fr_1.4fr_1fr] items-center gap-4 border px-5 py-4"
          style={{
            borderColor: t.border,
            background: i % 2 === 0 ? t.panel : t.panelDeep,
            borderTopWidth: i === 0 ? 1 : 0,
          }}
        >
          <span
            className="font-mono text-xs uppercase tracking-widest"
            style={{ color: t.cyan }}
          >
            {l.n}
          </span>
          <span
            className="font-display text-base font-semibold"
            style={{ color: t.fg }}
          >
            {l.name}
          </span>
          <span
            className="font-mono text-[11px]"
            style={{ color: t.muted }}
          >
            {l.impl}
          </span>
          <span
            className="font-mono text-[10px] uppercase tracking-widest"
            style={{ color: t.dim }}
          >
            {l.desc}
          </span>
        </div>
      ))}
      <div
        className="flex items-center justify-between border-x border-b px-5 py-2 font-mono text-[10px] uppercase tracking-[0.28em]"
        style={{ borderColor: t.border, background: t.panel, color: t.amber }}
      >
        <span>↓ Photons from regolith surface</span>
        <span style={{ color: t.dim }}>input</span>
      </div>
    </div>
  );
}

/* =============================================================
   StateMachine — SVG diagram of a finite-state machine. Used
   for the MCU main loop and the SWIR sub-loop. Each state is a
   bordered rectangle, transitions are arrows along a straight
   path (loop closes back to the first state).
   ============================================================= */
export function StateMachine({
  states,
  loopLabel,
  title,
}: {
  states: string[];
  loopLabel?: string;
  title: string;
}) {
  const t = useDocTheme();
  // Layout: states arranged horizontally, wrapping at 4 per row
  const perRow = 4;
  const rows = Math.ceil(states.length / perRow);
  const w = 760;
  const cellW = w / perRow;
  const cellH = 56;
  const padY = 28;
  const h = rows * cellH + (rows - 1) * padY + 50;

  return (
    <div
      className="flex flex-col gap-3 border px-5 py-5"
      style={{ borderColor: t.border, background: t.panel }}
    >
      <div
        className="flex items-center justify-between font-mono text-[10px] uppercase tracking-[0.28em]"
        style={{ color: t.muted }}
      >
        <span>{title}</span>
        {loopLabel && <span style={{ color: t.amber }}>{loopLabel}</span>}
      </div>
      <div className="overflow-x-auto">
        <svg
          width="100%"
          viewBox={`0 0 ${w} ${h}`}
          preserveAspectRatio="xMinYMin meet"
          role="img"
          aria-label={title}
        >
          <defs>
            <marker
              id={`arrow-${title.replace(/\s/g, "-")}`}
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M0,0 L10,5 L0,10 z" fill={t.cyan} />
            </marker>
          </defs>
          {states.map((s, i) => {
            const row = Math.floor(i / perRow);
            const col = i % perRow;
            const x = col * cellW + 8;
            const y = row * (cellH + padY) + 24;
            const cx = x + cellW / 2 - 8;
            const cy = y + cellH / 2;
            return (
              <g key={s}>
                <rect
                  x={x}
                  y={y}
                  width={cellW - 16}
                  height={cellH}
                  fill={t.panelDeep}
                  stroke={t.cyan}
                  strokeWidth={1}
                />
                <text
                  x={cx}
                  y={cy + 4}
                  fontFamily="var(--font-mono), monospace"
                  fontSize="11"
                  fill={t.fg}
                  textAnchor="middle"
                >
                  {s}
                </text>
                {/* index label */}
                <text
                  x={x + 6}
                  y={y - 6}
                  fontFamily="var(--font-mono), monospace"
                  fontSize="9"
                  fill={t.dim}
                >
                  {String(i).padStart(2, "0")}
                </text>
              </g>
            );
          })}
          {/* Arrows between consecutive states */}
          {states.map((_, i) => {
            if (i === states.length - 1) return null;
            const aRow = Math.floor(i / perRow);
            const aCol = i % perRow;
            const bRow = Math.floor((i + 1) / perRow);
            const bCol = (i + 1) % perRow;
            const aX = aCol * cellW + cellW - 16;
            const aY = aRow * (cellH + padY) + 24 + cellH / 2;
            const bX = bCol * cellW + 12;
            const bY = bRow * (cellH + padY) + 24 + cellH / 2;
            // simple straight line for same-row, L-shape across rows
            if (aRow === bRow) {
              return (
                <line
                  key={`l${i}`}
                  x1={aX}
                  y1={aY}
                  x2={bX}
                  y2={bY}
                  stroke={t.cyan}
                  strokeWidth={1}
                  markerEnd={`url(#arrow-${title.replace(/\s/g, "-")})`}
                />
              );
            }
            // wrap arrow: from end of last row down and back to start
            const midY = (aY + bY) / 2;
            return (
              <path
                key={`l${i}`}
                d={`M ${aX} ${aY} L ${aX + 8} ${aY} L ${aX + 8} ${midY} L ${bX - 8} ${midY} L ${bX - 8} ${bY} L ${bX} ${bY}`}
                fill="none"
                stroke={t.cyan}
                strokeWidth={1}
                markerEnd={`url(#arrow-${title.replace(/\s/g, "-")})`}
              />
            );
          })}
          {/* Loop back arrow from last to first */}
          {(() => {
            const last = states.length - 1;
            const lastRow = Math.floor(last / perRow);
            const lastCol = last % perRow;
            const aX = lastCol * cellW + cellW - 16;
            const aY = lastRow * (cellH + padY) + 24 + cellH / 2;
            const bX = 12;
            const bY = 24 + cellH / 2;
            const yLow = (lastRow + 1) * (cellH + padY) + 14;
            return (
              <path
                d={`M ${aX} ${aY} L ${aX + 6} ${aY} L ${aX + 6} ${yLow} L ${bX - 6} ${yLow} L ${bX - 6} ${bY} L ${bX} ${bY}`}
                fill="none"
                stroke={t.amber}
                strokeWidth={1}
                strokeDasharray="3 3"
                markerEnd={`url(#arrow-${title.replace(/\s/g, "-")})`}
              />
            );
          })()}
        </svg>
      </div>
    </div>
  );
}

/* =============================================================
   PacketFrame — renders a JSON wire-protocol frame as a labeled
   stack of fields with type, range, and a comment. Replaces a
   raw <pre> code block with something that looks like a
   datasheet page.
   ============================================================= */
type PacketField = {
  key: string;
  type: string;
  size: string;
  desc: string;
  optional?: boolean;
};

export function PacketFrame({
  schema,
  fields,
}: {
  schema: string;
  fields: PacketField[];
}) {
  const t = useDocTheme();
  return (
    <div
      className="flex flex-col border"
      style={{ borderColor: t.border, background: t.panel }}
    >
      <div
        className="flex items-center justify-between border-b px-5 py-2 font-mono text-[10px] uppercase tracking-[0.28em]"
        style={{ borderColor: t.border, color: t.cyan }}
      >
        <span>USB-CDC frame · newline-delimited JSON</span>
        <span style={{ color: t.dim }}>schema {schema}</span>
      </div>
      <div className="grid grid-cols-[1fr_0.8fr_0.7fr_2fr] border-b font-mono text-[9px] uppercase tracking-[0.25em]"
           style={{ borderColor: t.border, color: t.dim }}>
        <div className="px-5 py-2">field</div>
        <div className="px-3 py-2">type</div>
        <div className="px-3 py-2">size</div>
        <div className="px-5 py-2">description</div>
      </div>
      {fields.map((f, i) => (
        <div
          key={f.key}
          className="grid grid-cols-[1fr_0.8fr_0.7fr_2fr] items-center font-mono text-[12px]"
          style={{
            background: i % 2 === 0 ? t.panel : t.panelDeep,
            color: t.fg,
          }}
        >
          <div className="px-5 py-2 flex items-center gap-2">
            <span style={{ color: t.cyan }}>{f.key}</span>
            {f.optional && (
              <span
                className="text-[9px] uppercase tracking-widest"
                style={{ color: t.amber }}
              >
                opt
              </span>
            )}
          </div>
          <div className="px-3 py-2" style={{ color: t.muted }}>{f.type}</div>
          <div className="px-3 py-2 tabular-nums" style={{ color: t.muted }}>{f.size}</div>
          <div className="px-5 py-2 text-[11px]" style={{ color: t.muted }}>{f.desc}</div>
        </div>
      ))}
    </div>
  );
}

/* =============================================================
   PipelineFlow — horizontal sequence of labeled stages with
   arrows between them. Used for the calibration pipeline and
   any other "5-step procedure" visualization.
   ============================================================= */
export function PipelineFlow({
  stages,
  inputLabel,
  outputLabel,
}: {
  stages: {
    code: string;
    title: string;
    formula?: import("react").ReactNode;
    note?: string;
  }[];
  inputLabel?: string;
  outputLabel?: string;
}) {
  const t = useDocTheme();
  return (
    <div
      className="flex flex-col gap-3 border px-5 py-5"
      style={{ borderColor: t.border, background: t.panel }}
    >
      {(inputLabel || outputLabel) && (
        <div className="flex items-center justify-between font-mono text-[10px] uppercase tracking-[0.28em]"
             style={{ color: t.muted }}>
          <span>{inputLabel}</span>
          <span style={{ color: t.cyan }}>{outputLabel}</span>
        </div>
      )}
      <div className="flex flex-col gap-px">
        {stages.map((s, i) => (
          <div
            key={s.code}
            className="grid grid-cols-[44px_44px_1fr_1.2fr] items-stretch gap-px"
          >
            <div
              className="flex items-center justify-center font-mono text-xs"
              style={{ color: t.cyan, background: t.panelDeep }}
            >
              {s.code}
            </div>
            <div
              className="flex items-center justify-center font-mono text-[10px]"
              style={{ color: t.dim, background: t.panelDeep }}
            >
              {String(i + 1).padStart(2, "0")}
            </div>
            <div
              className="flex flex-col justify-center gap-0.5 px-3 py-2.5"
              style={{ background: t.panelDeep }}
            >
              <span
                className="font-display text-sm font-semibold"
                style={{ color: t.fg }}
              >
                {s.title}
              </span>
              {s.note && (
                <span className="font-mono text-[10px]" style={{ color: t.muted }}>
                  {s.note}
                </span>
              )}
            </div>
            <div
              className="flex items-center px-3 py-2.5 font-mono text-[11px]"
              style={{ background: t.panelDeep, color: t.amber }}
            >
              {s.formula ?? "—"}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* =============================================================
   ResNetDiagram — schematic of the 1D ResNet classifier. Three
   residual stages with channel counts, GAP, then dual heads
   (classifier softmax + ilmenite regression sigmoid).
   ============================================================= */
export function ResNetDiagram() {
  const t = useDocTheme();
  const stages = [
    { name: "Input", chan: "321 ch", note: "spec | as7 | swir | led | lif" },
    { name: "ResBlock × 2", chan: "32", note: "conv1d k=7 stride 2" },
    { name: "ResBlock × 2", chan: "64", note: "conv1d k=5 stride 2" },
    { name: "ResBlock × 2", chan: "128", note: "conv1d k=3 stride 2" },
    { name: "GAP", chan: "128", note: "global average pool" },
  ];
  const heads = [
    { name: "Class head", type: "softmax", out: "6 classes", color: t.cyan },
    { name: "Regression head", type: "sigmoid", out: "ilmenite ∈ [0,1]", color: t.amber },
  ];

  return (
    <div
      className="flex flex-col gap-4 border px-5 py-5"
      style={{ borderColor: t.border, background: t.panel }}
    >
      <div
        className="flex items-center justify-between font-mono text-[10px] uppercase tracking-[0.28em]"
        style={{ color: t.muted }}
      >
        <span>1D ResNet · ≈ 280 K params · AdamW + cosine</span>
        <span style={{ color: t.dim }}>FP32 / INT8 ONNX</span>
      </div>
      <div className="flex flex-col gap-px md:flex-row md:items-stretch">
        {stages.map((s, i) => (
          <div
            key={s.name}
            className="flex flex-1 items-center gap-2 px-3 py-3 md:flex-col md:items-start md:justify-center"
            style={{ background: t.panelDeep }}
          >
            <span
              className="font-mono text-[10px] uppercase tracking-widest"
              style={{ color: t.dim }}
            >
              {String(i).padStart(2, "0")}
            </span>
            <span
              className="font-display text-sm font-semibold"
              style={{ color: t.fg }}
            >
              {s.name}
            </span>
            <span className="font-mono text-[12px]" style={{ color: t.cyan }}>
              {s.chan}
            </span>
            <span
              className="font-mono text-[10px] uppercase tracking-widest"
              style={{ color: t.muted }}
            >
              {s.note}
            </span>
          </div>
        ))}
      </div>
      <div
        className="grid grid-cols-1 gap-px border md:grid-cols-2"
        style={{ borderColor: t.border, background: t.border }}
      >
        {heads.map((h) => (
          <div
            key={h.name}
            className="flex flex-col gap-1 px-4 py-3"
            style={{ background: t.panelDeep }}
          >
            <span
              className="font-mono text-[10px] uppercase tracking-widest"
              style={{ color: h.color }}
            >
              {h.name}
            </span>
            <span className="font-display text-sm" style={{ color: t.fg }}>
              {h.type}
            </span>
            <span className="font-mono text-[11px]" style={{ color: t.muted }}>
              → {h.out}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* =============================================================
   StatusFieldStates — the 4-state classifier visualized as a
   horizontal scale with the threshold positions marked. Helps
   the jury see at a glance how nominal / borderline /
   low-confidence / likely-OOD relate.
   ============================================================= */
export function StatusFieldStates() {
  const t = useDocTheme();
  // Two-color palette: cyan for the nominal-family, amber for
  // soft caution (low_confidence), rose reserved for the only
  // state the operator must actually escalate (likely_ood).
  // borderline shares cyan; the state name carries the
  // differentiation, not a third color.
  const tau = (sub: string) => (
    <Mx>
      τ<sub>{sub}</sub>
    </Mx>
  );
  const states: { name: string; rule: ReactNode; color: string }[] = [
    {
      name: "nominal",
      rule: (
        <>
          top-1 ≥ {tau("p")} · margin ≥ {tau("m")} · entropy &lt; {tau("h")}
        </>
      ),
      color: t.cyan,
    },
    {
      name: "borderline",
      rule: (
        <>
          margin &lt; {tau("m")}  (top-2 within reach)
        </>
      ),
      color: t.cyan,
    },
    {
      name: "low_confidence",
      rule: (
        <>
          top-1 &lt; {tau("p")}   (calibrated)
        </>
      ),
      color: t.amber,
    },
    {
      name: "likely_ood",
      rule: (
        <>
          entropy ≥ {tau("h")}  · or SAM/CNN disagree
        </>
      ),
      color: t.rose,
    },
  ];
  return (
    <div
      className="grid grid-cols-1 gap-px border md:grid-cols-2"
      style={{ borderColor: t.border, background: t.border }}
    >
      {states.map((s) => (
        <div
          key={s.name}
          className="flex flex-col gap-2 px-4 py-3"
          style={{ background: t.panel }}
        >
          <div className="flex items-center gap-2">
            <span
              className="inline-block h-1.5 w-1.5 rounded-full"
              style={{ background: s.color }}
              aria-hidden="true"
            />
            <span
              className="font-mono text-[12px] uppercase tracking-widest"
              style={{ color: s.color }}
            >
              {s.name}
            </span>
          </div>
          <span
            className="font-mono text-[11px]"
            style={{ color: t.muted }}
          >
            {s.rule}
          </span>
        </div>
      ))}
    </div>
  );
}

/* =============================================================
   TransferMatrix — 2 × 2 matrix for the Linear-vs-Hapke
   ablation. Rows = trained on, Cols = evaluated on. Cells
   carry placeholder %s with a "synthetic" caveat label.
   ============================================================= */
export function TransferMatrix() {
  const t = useDocTheme();
  const rowsHeader = ["Trained ↓ / Eval →", "Linear", "Hapke"];
  const data: { trained: string; linear: string; hapke: string }[] = [
    { trained: "Linear", linear: "99.4 %", hapke: "97.1 %" },
    { trained: "Hapke",  linear: "97.6 %", hapke: "99.2 %" },
  ];
  return (
    <div
      className="flex flex-col border"
      style={{ borderColor: t.border, background: t.panel }}
    >
      <div
        className="flex items-center justify-between border-b px-5 py-2 font-mono text-[10px] uppercase tracking-[0.28em]"
        style={{ borderColor: t.border, color: t.cyan }}
      >
        <span>2 × 2 transfer matrix · synthetic only</span>
        <span style={{ color: t.dim }}>real-sample test pending</span>
      </div>
      <div className="grid grid-cols-3">
        {rowsHeader.map((h) => (
          <div
            key={h}
            className="border-b px-4 py-2 font-mono text-[10px] uppercase tracking-widest"
            style={{ borderColor: t.border, color: t.muted, background: t.panelDeep }}
          >
            {h}
          </div>
        ))}
        {data.map((r) => (
          <div key={r.trained} className="contents">
            <div
              className="border-b px-4 py-3 font-mono text-[11px] uppercase tracking-widest"
              style={{ borderColor: t.border, color: t.amber, background: t.panelDeep }}
            >
              {r.trained}
            </div>
            <div
              className="border-b px-4 py-3 font-mono text-base tabular-nums"
              style={{ borderColor: t.border, color: t.cyan }}
            >
              {r.linear}
            </div>
            <div
              className="border-b px-4 py-3 font-mono text-base tabular-nums"
              style={{ borderColor: t.border, color: t.cyan }}
            >
              {r.hapke}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* =============================================================
   DeploymentTiers — three quality tiers (FP32 / INT8 / TFLite
   Micro) shown as a comparison grid with size, accuracy drop,
   and target host.
   ============================================================= */
export function DeploymentTiers() {
  const t = useDocTheme();
  const tiers = [
    {
      tier: "FP32",
      size: "~ 2.6 MB",
      drop: "—",
      target: "Server · ONNX Runtime · canonical",
      color: t.cyan,
    },
    {
      tier: "INT8",
      size: "707 KB",
      drop: "0.0 pp",
      target: "Server / laptop · 3.7× smaller",
      color: t.emerald,
    },
    {
      tier: "TFLite Micro",
      size: "~ 700 KB",
      drop: "≤ 0.5 pp*",
      target: "ESP32-S3 · embedded · build pending",
      color: t.amber,
    },
  ];
  return (
    <div
      className="grid grid-cols-1 gap-px border md:grid-cols-3"
      style={{ borderColor: t.border, background: t.border }}
    >
      {tiers.map((tier, i) => (
        <div
          key={tier.tier}
          className="flex flex-col gap-3 px-4 py-4"
          style={{ background: t.panel }}
        >
          <div className="flex items-center justify-between">
            <span
              className="font-mono text-[10px] uppercase tracking-widest"
              style={{ color: tier.color }}
            >
              T{i + 1} · {tier.tier}
            </span>
            <span
              className="font-mono text-[10px] uppercase tracking-widest"
              style={{ color: t.dim }}
            >
              {tier.size}
            </span>
          </div>
          <div className="flex items-baseline gap-2">
            <span
              className="font-mono text-2xl font-semibold tabular-nums"
              style={{ color: tier.color }}
            >
              {tier.drop}
            </span>
            <span className="font-mono text-[10px] uppercase tracking-widest" style={{ color: t.muted }}>
              acc. drop
            </span>
          </div>
          <span className="font-mono text-[11px]" style={{ color: t.muted }}>
            {tier.target}
          </span>
        </div>
      ))}
    </div>
  );
}

/* =============================================================
   AcquisitionScore — the active-learning score breakdown shown
   as a 3-component formula with each weight.
   ============================================================= */
export function AcquisitionScore() {
  const t = useDocTheme();
  const components = [
    { sym: "H̃(p)",        name: "Normalised entropy",     weight: "α" },
    { sym: "1 − margin",  name: "Top-1 vs top-2 closeness", weight: "β" },
    { sym: "𝟙[SAM≠CNN]",  name: "SAM/CNN disagreement",   weight: "γ" },
  ];
  return (
    <div
      className="flex flex-col gap-4 border px-5 py-5"
      style={{ borderColor: t.border, background: t.panel }}
    >
      <div
        className="flex items-center justify-between font-mono text-[10px] uppercase tracking-[0.28em]"
        style={{ color: t.muted }}
      >
        <span>Acquisition score · per unlabelled candidate</span>
        <span style={{ color: t.amber }}>≈ 2× efficiency vs random</span>
      </div>
      <div
        className="border px-5 py-3 text-center font-mono text-base"
        style={{ borderColor: t.border, background: t.panelDeep, color: t.cyan }}
      >
        score = α · H̃(p) + β · (1 − margin) + γ · 𝟙[SAM ≠ CNN]
      </div>
      <div
        className="grid grid-cols-1 gap-px border md:grid-cols-3"
        style={{ borderColor: t.border, background: t.border }}
      >
        {components.map((c, i) => (
          <div
            key={c.sym}
            className="flex flex-col gap-1 px-3 py-3"
            style={{ background: t.panelDeep }}
          >
            <span
              className="font-mono text-[10px] uppercase tracking-widest"
              style={{ color: t.dim }}
            >
              term {String(i + 1).padStart(2, "0")} · {c.weight}
            </span>
            <span className="font-mono text-base" style={{ color: t.cyan }}>
              {c.sym}
            </span>
            <span className="font-mono text-[11px]" style={{ color: t.muted }}>
              {c.name}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
