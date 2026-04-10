"use client";

import {
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useTheme } from "./ThemeProvider";
import type { EndmembersResponse } from "@/lib/types";

const ENDMEMBER_COLORS: Record<string, { dark: string; light: string }> = {
  olivine: { dark: "#4ade80", light: "#16a34a" },
  pyroxene: { dark: "#fb923c", light: "#ea580c" },
  anorthite: { dark: "#60a5fa", light: "#2563eb" },
  ilmenite: { dark: "#8b5cf6", light: "#7c3aed" },
  glass_agglutinate: { dark: "#f87171", light: "#dc2626" },
};

function getEndmemberColor(name: string, isLight: boolean): string {
  const key = Object.keys(ENDMEMBER_COLORS).find((k) =>
    name.toLowerCase().includes(k)
  );
  if (!key) return isLight ? "#94a3b8" : "#64748b";
  return isLight ? ENDMEMBER_COLORS[key].light : ENDMEMBER_COLORS[key].dark;
}

export function SpectrumChart({
  wavelengths,
  spectrum,
  endmembers,
  as7265x,
  as7265xBands,
}: {
  wavelengths: number[] | null;
  spectrum: number[] | null;
  endmembers: EndmembersResponse | null;
  as7265x?: number[];
  as7265xBands?: number[];
}) {
  const { theme } = useTheme();
  const isLight = theme === "light";

  const hasSpec = wavelengths && spectrum;
  const hasAs7 = as7265x && as7265xBands && as7265x.length > 0;

  if (!hasSpec && !hasAs7) {
    return (
      <div
        className="flex h-72 items-center justify-center font-mono text-xs uppercase tracking-widest"
        style={{ color: isLight ? "#94a3b8" : "#64748b" }}
      >
        awaiting acquisition\u2026
      </div>
    );
  }

  // Endmember names from the dict-shaped response
  const endmemberNames = endmembers ? Object.keys(endmembers.endmembers) : [];

  // Build data array with spectrum + endmember columns
  const data = hasSpec
    ? wavelengths.map((nm, i) => {
        const row: Record<string, number | undefined> = {
          nm: Math.round(nm),
          reflectance: spectrum[i],
        };
        if (endmembers) {
          for (const name of endmemberNames) {
            const emSpec = endmembers.endmembers[name];
            const emIdx = endmembers.wavelengths_nm.findIndex(
              (w) => Math.abs(w - nm) < 2
            );
            if (emIdx !== -1 && emIdx < emSpec.length) {
              row[name] = emSpec[emIdx];
            }
          }
        }
        return row;
      })
    : [];

  // Build AS7265x scatter data points
  const as7Data: Array<Record<string, number>> = [];
  if (hasAs7) {
    for (let i = 0; i < as7265xBands.length; i++) {
      as7Data.push({
        nm: as7265xBands[i],
        as7265x: as7265x[i],
      });
    }
  }

  // If only AS7265x data exists (no continuous spectrum), merge into main data
  // and render as a connected scatter/line instead
  const as7Only = hasAs7 && !hasSpec;
  const chartData = as7Only
    ? as7Data.map((d) => ({
        nm: d.nm,
        reflectance: d.as7265x,
        as7265x: d.as7265x,
      }))
    : data;

  const gridColor = isLight ? "#e2e8f0" : "#1e293b";
  const axisStroke = isLight ? "#cbd5e1" : "#475569";
  const tickFill = isLight ? "#64748b" : "#94a3b8";
  const labelFill = isLight ? "#94a3b8" : "#64748b";
  const tooltipBg = isLight ? "#ffffff" : "#0f172a";
  const tooltipBorder = isLight ? "1px solid #e2e8f0" : "1px solid #38bdf844";
  const tooltipColor = isLight ? "#0f172a" : "#e2e8f0";

  const as7Color = isLight ? "#d97706" : "#f59e0b";

  return (
    <div>
      <div className="h-72 w-full">
        <ResponsiveContainer>
          <ComposedChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 8 }}>
            <defs>
              <linearGradient id="specGrad" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0%" stopColor={isLight ? "#0284c7" : "#38bdf8"} stopOpacity={0.9} />
                <stop offset="60%" stopColor={isLight ? "#0284c7" : "#38bdf8"} stopOpacity={0.9} />
                <stop offset="100%" stopColor={isLight ? "#d97706" : "#fbbf24"} stopOpacity={0.9} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke={gridColor} strokeDasharray="3 6" />
            <XAxis
              dataKey="nm"
              stroke={axisStroke}
              tick={{ fill: tickFill, fontSize: 10, fontFamily: "ui-monospace" }}
              label={{
                value: "wavelength (nm)",
                position: "insideBottom",
                offset: -2,
                fill: labelFill,
                fontSize: 10,
              }}
              type="number"
              domain={["dataMin", "dataMax"]}
            />
            <YAxis
              stroke={axisStroke}
              tick={{ fill: tickFill, fontSize: 10, fontFamily: "ui-monospace" }}
              domain={[0, "dataMax + 0.1"]}
              tickFormatter={(v) => v.toFixed(2)}
            />
            <Tooltip
              contentStyle={{
                background: tooltipBg,
                border: tooltipBorder,
                borderRadius: 8,
                fontFamily: "ui-monospace",
                fontSize: 11,
                color: tooltipColor,
              }}
              formatter={(v: number, name: string) => [
                v.toFixed(4),
                name === "as7265x" ? "AS7265X" : name,
              ]}
              labelFormatter={(v) => `${v} nm`}
            />
            {/* Endmember lines rendered first (behind main spectrum) */}
            {endmemberNames.map((name) => (
              <Line
                key={name}
                type="monotone"
                dataKey={name}
                stroke={getEndmemberColor(name, isLight)}
                strokeWidth={1.5}
                strokeDasharray="6 4"
                strokeOpacity={0.3}
                dot={false}
                isAnimationActive={false}
                connectNulls
              />
            ))}
            {/* Main spectrum line (or connected AS7265x line in as7-only mode) */}
            <Line
              type="monotone"
              dataKey="reflectance"
              stroke={as7Only ? as7Color : "url(#specGrad)"}
              strokeWidth={2}
              dot={as7Only ? { r: 4, fill: as7Color, stroke: as7Color } : false}
              isAnimationActive
              animationDuration={650}
            />
            {/* AS7265x scatter overlay (when both spec and AS7265x are present) */}
            {hasAs7 && !as7Only && (
              <Scatter
                data={as7Data}
                dataKey="as7265x"
                fill={as7Color}
                stroke={isLight ? "#92400e" : "#fbbf24"}
                strokeWidth={1}
                r={4}
                isAnimationActive
                animationDuration={650}
                name="AS7265X"
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div
        className="mt-2 flex flex-wrap gap-4 font-mono text-[10px] uppercase tracking-widest"
        style={{ color: isLight ? "#94a3b8" : "#64748b" }}
      >
        {/* AS7265x legend entry */}
        {hasAs7 && (
          <span className="flex items-center gap-1.5">
            <span
              style={{
                display: "inline-block",
                width: 8,
                height: 8,
                borderRadius: "50%",
                backgroundColor: as7Color,
              }}
            />
            AS7265X
          </span>
        )}
        {/* Endmember legend entries */}
        {endmemberNames.map((name) => {
          const color = getEndmemberColor(name, isLight);
          return (
            <span key={name} className="flex items-center gap-1.5">
              <span
                style={{
                  display: "inline-block",
                  width: 16,
                  height: 2,
                  backgroundColor: color,
                  opacity: 0.5,
                  borderTop: `1px dashed ${color}`,
                }}
              />
              {name}
            </span>
          );
        })}
      </div>
    </div>
  );
}
