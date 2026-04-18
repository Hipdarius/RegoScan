"use client";

import { useTheme } from "./ThemeProvider";
import { CLASS_LABELS, type DemoResponse } from "@/lib/types";

export function ScanHistory({
  history,
  selectedIndex,
  onSelect,
}: {
  history: DemoResponse[];
  selectedIndex: number;
  onSelect: (idx: number) => void;
}) {
  const { theme } = useTheme();
  const isLight = theme === "light";

  if (history.length === 0) return null;

  const cyanText = isLight ? "#0284c7" : "#38bdf8";
  const amberText = "#f59e0b";
  const mutedText = isLight ? "#64748b" : "#94a3b8";
  const dimText = isLight ? "#94a3b8" : "#64748b";
  const selectedBg = isLight ? "rgba(2, 132, 199, 0.06)" : "rgba(56, 189, 248, 0.06)";
  const hoverBg = isLight ? "rgba(15, 23, 42, 0.03)" : "rgba(148, 163, 184, 0.05)";

  const okColor = isLight ? "#16a34a" : "#4ade80";

  return (
    <div>
      <div
        className="mb-3 flex items-center justify-between font-mono text-[10px] uppercase tracking-widest"
        style={{ color: mutedText }}
      >
        <span>Scan log · n={history.length}</span>
        <span>index / class / confidence / FeTiO₃</span>
      </div>
      <ul>
        {history.map((scan, idx) => {
          const isSelected = idx === selectedIndex;
          const isMatch = scan.predicted_class === scan.true_class;
          const conf = (scan.confidence * 100).toFixed(1);
          const ilm = (scan.ilmenite_fraction * 100).toFixed(1);
          const marker = isSelected ? "▸" : " ";

          return (
            <li
              key={idx}
              className="border-b last:border-b-0"
              style={{ borderColor: isLight ? "#e2e8f0" : "#1e293b" }}
            >
              <button
                onClick={() => onSelect(idx)}
                className="flex w-full items-center justify-between gap-4 px-2 py-2 text-left font-mono transition-colors"
                style={{ background: isSelected ? selectedBg : "transparent" }}
                onMouseEnter={(e) => {
                  if (!isSelected)
                    (e.currentTarget as HTMLElement).style.background = hoverBg;
                }}
                onMouseLeave={(e) => {
                  if (!isSelected)
                    (e.currentTarget as HTMLElement).style.background = "transparent";
                }}
                aria-current={isSelected ? "true" : undefined}
              >
                <div className="flex items-center gap-3">
                  <span
                    className="inline-block w-3 text-center text-xs"
                    style={{ color: isSelected ? cyanText : dimText }}
                    aria-hidden="true"
                  >
                    {marker}
                  </span>
                  <span className="w-8 text-[10px]" style={{ color: dimText }}>
                    {String(idx + 1).padStart(3, "0")}
                  </span>
                  <span
                    className="text-xs uppercase tracking-wider"
                    style={{ color: isSelected ? cyanText : (isLight ? "#0f172a" : "#e2e8f0") }}
                  >
                    {CLASS_LABELS[scan.predicted_class] ?? scan.predicted_class}
                  </span>
                </div>
                <div className="flex items-center gap-4">
                  <span
                    className="text-[11px] tabular-nums"
                    style={{ color: isMatch ? cyanText : amberText }}
                  >
                    {conf}%
                  </span>
                  <span
                    className="text-[11px] tabular-nums"
                    style={{ color: mutedText }}
                  >
                    {ilm}%
                  </span>
                  <span
                    className="inline-block h-1.5 w-1.5 rounded-full"
                    style={{ backgroundColor: isMatch ? okColor : amberText }}
                    aria-label={isMatch ? "match" : "mismatch"}
                  />
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
