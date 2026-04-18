"use client";

import { motion } from "framer-motion";
import { useTheme } from "./ThemeProvider";

export function ScanButton({
  onClick,
  isScanning,
  disabled,
}: {
  onClick: () => void;
  isScanning: boolean;
  disabled?: boolean;
}) {
  const { theme } = useTheme();
  const isLight = theme === "light";

  const cyan = isLight ? "#0284c7" : "#38bdf8";
  const borderCol = isLight ? "rgba(2, 132, 199, 0.4)" : "rgba(56, 189, 248, 0.4)";
  const bgCol = isLight ? "rgba(2, 132, 199, 0.06)" : "rgba(56, 189, 248, 0.08)";

  return (
    <motion.button
      whileTap={{ scale: disabled ? 1 : 0.99 }}
      onClick={onClick}
      disabled={disabled || isScanning}
      className="group relative overflow-hidden border px-6 py-3 font-mono text-xs uppercase tracking-[0.28em] transition-colors disabled:cursor-not-allowed disabled:opacity-40"
      style={{ borderColor: borderCol, background: bgCol, color: cyan }}
      aria-busy={isScanning}
    >
      <span className="relative z-10 flex items-center gap-3">
        <span
          className={`inline-block h-1.5 w-1.5 rounded-full ${isScanning ? "animate-blink" : ""}`}
          style={{ backgroundColor: cyan }}
        />
        {isScanning ? "Scanning…" : "Initiate scan"}
      </span>

      {isScanning && (
        <span className="pointer-events-none absolute inset-x-0 top-0 h-full" aria-hidden="true">
          <span
            className="absolute inset-x-0 h-px animate-scan-line"
            style={{ backgroundColor: cyan }}
          />
        </span>
      )}
    </motion.button>
  );
}
