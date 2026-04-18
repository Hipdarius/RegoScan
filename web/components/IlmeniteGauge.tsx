"use client";

import { motion } from "framer-motion";
import { useTheme } from "./ThemeProvider";

// Pre-computed gauge geometry. Hoisting these out of the render avoids a
// React hydration mismatch — JavaScript engines can produce slightly
// different stringifications of `2*PI*52` on the server (Node) vs in the
// browser, which trips React's exact-string compare on SVG attributes.
// Using rounded fixed-precision strings makes both renderers agree.
const RING_RADIUS = 52;
const RING_CIRC_STR = (2 * Math.PI * RING_RADIUS).toFixed(4);  // "326.7256"
const RING_CIRC_NUM = Number(RING_CIRC_STR);

interface TickGeo {
  x1: string; y1: string; x2: string; y2: string; major: boolean;
}
const TICKS: TickGeo[] = Array.from({ length: 20 }).map((_, i) => {
  const major = i % 5 === 0;
  const angle = (i / 20) * 2 * Math.PI - Math.PI / 2;
  const r1 = 58;
  const r2 = major ? 62 : 60;
  return {
    x1: (60 + Math.cos(angle) * r1).toFixed(4),
    y1: (60 + Math.sin(angle) * r1).toFixed(4),
    x2: (60 + Math.cos(angle) * r2).toFixed(4),
    y2: (60 + Math.sin(angle) * r2).toFixed(4),
    major,
  };
});

export function IlmeniteGauge({
  fraction,
  trueFraction,
}: {
  fraction: number | null;
  trueFraction?: number | null;
}) {
  const { theme } = useTheme();
  const isLight = theme === "light";

  const f = fraction ?? 0;
  const clamped = Math.max(0, Math.min(1, f));
  const pct = clamped * 100;

  const ringBg = isLight ? "#e2e8f0" : "#1e293b";
  const valueColor = isLight ? "#0284c7" : "#38bdf8";
  const mutedColor = isLight ? "#64748b" : "#94a3b8";
  const dimColor = isLight ? "#94a3b8" : "#64748b";

  const residual =
    fraction !== null && trueFraction !== null && trueFraction !== undefined
      ? Math.abs(fraction - trueFraction) * 100
      : null;

  return (
    <div className="flex flex-col items-center gap-4">
      <div className="relative h-40 w-40">
        <svg viewBox="0 0 120 120" className="absolute inset-0" aria-hidden="true">
          {/* Outer tick marks — five per quadrant, marking 20% intervals */}
          {TICKS.map((tick, i) => (
            <line
              key={i}
              x1={tick.x1}
              y1={tick.y1}
              x2={tick.x2}
              y2={tick.y2}
              stroke={dimColor}
              strokeWidth={tick.major ? 1 : 0.5}
            />
          ))}
          <circle cx="60" cy="60" r={RING_RADIUS} fill="none" stroke={ringBg} strokeWidth="6" />
          <motion.circle
            cx="60"
            cy="60"
            r={RING_RADIUS}
            fill="none"
            stroke={valueColor}
            strokeWidth="6"
            strokeLinecap="butt"
            strokeDasharray={RING_CIRC_NUM}
            initial={{ strokeDashoffset: RING_CIRC_NUM }}
            animate={{ strokeDashoffset: RING_CIRC_NUM * (1 - clamped) }}
            transition={{ duration: 0.7, ease: [0.4, 0, 0.2, 1] }}
            transform="rotate(-90 60 60)"
          />
        </svg>

        <div className="absolute inset-0 flex flex-col items-center justify-center gap-0.5">
          <span className="font-mono text-3xl font-semibold tabular-nums" style={{ color: valueColor }}>
            {fraction !== null ? pct.toFixed(1) : "—"}
          </span>
          <span className="font-mono text-[10px] uppercase tracking-widest" style={{ color: mutedColor }}>
            % mass · FeTiO₃
          </span>
        </div>
      </div>

      <dl className="grid w-full grid-cols-2 gap-x-4 gap-y-1 font-mono text-[10px] uppercase tracking-widest" style={{ color: mutedColor }}>
        <dt>Ground truth</dt>
        <dd className="text-right tabular-nums" style={{ color: trueFraction != null ? valueColor : dimColor }}>
          {trueFraction != null ? `${(trueFraction * 100).toFixed(1)} %` : "—"}
        </dd>
        <dt>Residual</dt>
        <dd className="text-right tabular-nums" style={{ color: residual != null ? valueColor : dimColor }}>
          {residual != null ? `${residual.toFixed(2)} pp` : "—"}
        </dd>
      </dl>
    </div>
  );
}
