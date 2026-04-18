"use client";

import { motion } from "framer-motion";
import { CLASS_LABELS, type ClassProbability } from "@/lib/types";
import { useTheme } from "./ThemeProvider";

export function ProbabilityBars({
  probabilities,
  predictedClass,
}: {
  probabilities: ClassProbability[] | null;
  predictedClass: string | null;
}) {
  const { theme } = useTheme();
  const isLight = theme === "light";

  const mutedText = isLight ? "#64748b" : "#94a3b8";
  const dimText = isLight ? "#94a3b8" : "#64748b";
  const topColor = "#f59e0b";
  const normalColor = isLight ? "#0284c7" : "#38bdf8";
  const trackColor = isLight ? "#e2e8f0" : "#1e293b";

  if (!probabilities) {
    return (
      <div
        className="flex h-40 items-center justify-center font-mono text-[11px] uppercase tracking-widest"
        style={{ color: dimText }}
      >
        awaiting classifier…
      </div>
    );
  }

  const sorted = [...probabilities].sort((a, b) => b.probability - a.probability);

  return (
    <ul className="space-y-2.5">
      {sorted.map((cls) => {
        const isTop = cls.name === predictedClass;
        const pct = (cls.probability * 100).toFixed(1);
        const labelColor = isTop ? topColor : mutedText;
        const fillColor = isTop ? topColor : normalColor;

        return (
          <li key={cls.name}>
            <div className="mb-1 flex items-center justify-between font-mono text-[11px] uppercase tracking-widest">
              <span style={{ color: labelColor }}>
                {CLASS_LABELS[cls.name] ?? cls.name}
              </span>
              <span className="tabular-nums" style={{ color: labelColor }}>
                {pct}%
              </span>
            </div>
            <div
              className="relative h-1.5 overflow-hidden"
              style={{ backgroundColor: trackColor }}
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Number(pct)}
              aria-label={CLASS_LABELS[cls.name] ?? cls.name}
            >
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${cls.probability * 100}%` }}
                transition={{ duration: 0.6, ease: [0.4, 0, 0.2, 1] }}
                className="h-full"
                style={{ backgroundColor: fillColor }}
              />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
