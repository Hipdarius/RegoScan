"use client";

import { motion } from "framer-motion";
import { useTheme } from "./ThemeProvider";

export function Hero({
  schemaVersion,
  modelLoaded,
  metaLoading = false,
}: {
  schemaVersion: string | null;
  modelLoaded: boolean;
  metaLoading?: boolean;
}) {
  const { theme, toggle } = useTheme();
  const isLight = theme === "light";

  const cyan = isLight ? "#0284c7" : "#38bdf8";
  const fg = isLight ? "#0f172a" : "#e2e8f0";
  const muted = isLight ? "#475569" : "#94a3b8";
  const dim = isLight ? "#94a3b8" : "#64748b";
  const borderCol = isLight ? "#e2e8f0" : "#1e293b";
  const headerBg = isLight ? "#f8fafc" : "#0b1220";

  return (
    <header
      className="relative border-b px-6 py-10 sm:py-14"
      style={{ borderColor: borderCol, background: headerBg }}
    >
      <div className="mx-auto flex max-w-6xl flex-col gap-8">
        <div className="flex items-center justify-between">
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="flex items-center gap-3 font-mono text-[10px] uppercase tracking-[0.3em]"
            style={{ color: muted }}
          >
            <span
              className="inline-block h-1.5 w-1.5 rounded-full"
              style={{ backgroundColor: cyan }}
            />
            Bench mode · Synthetic acquisition pipeline
          </motion.div>

          <button
            onClick={toggle}
            className="flex items-center gap-2 border px-3 py-1.5 font-mono text-[10px] uppercase tracking-widest transition-colors hover:border-sky-500/60"
            style={{ borderColor: borderCol, background: "transparent", color: muted }}
            aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
          >
            {theme === "dark" ? (
              <>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <circle cx="12" cy="12" r="5" />
                  <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
                </svg>
                Light
              </>
            ) : (
              <>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                  <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
                </svg>
                Dark
              </>
            )}
          </button>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.05 }}
          className="flex flex-col gap-3"
        >
          <h1
            className="font-display text-6xl font-semibold leading-[0.9] tracking-[-0.01em] sm:text-8xl"
            style={{ color: fg }}
          >
            VERA
          </h1>
          <p
            className="font-mono text-xs uppercase tracking-[0.32em]"
            style={{ color: cyan }}
          >
            Visible &amp; Emission Regolith Assessment
          </p>
        </motion.div>

        <motion.p
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="max-w-2xl text-[13px] leading-relaxed sm:text-sm"
          style={{ color: muted }}
        >
          Compact VIS/NIR spectrometer with 405&nbsp;nm LIF and dual SWIR
          photodiodes at 940 / 1050&nbsp;nm, targeting in-situ mineral
          classification of lunar regolith. This console runs against{" "}
          <span style={{ color: fg }}>synthetic data</span> through the trained
          1D&nbsp;ResNet; real-sample validation pending.
        </motion.p>

        <dl
          className="grid w-full grid-cols-2 gap-px border sm:grid-cols-4"
          style={{ borderColor: borderCol, background: borderCol }}
        >
          {metaLoading ? (
            <Fact label="Status" value="Connecting…" ok={false} fg={fg} muted={dim} bg={headerBg} />
          ) : (
            <>
              <Fact label="Schema" value={schemaVersion ?? "—"} ok={!!schemaVersion} fg={fg} muted={dim} bg={headerBg} />
              <Fact label="Model" value={modelLoaded ? "Online" : "Offline"} ok={modelLoaded} fg={fg} muted={dim} bg={headerBg} />
              <Fact label="Runtime" value="onnxruntime" ok fg={fg} muted={dim} bg={headerBg} />
              <Fact label="Cross-seed accuracy" value="99.3 %" ok fg={fg} muted={dim} bg={headerBg} note="synthetic" />
            </>
          )}
        </dl>
      </div>
    </header>
  );
}

function Fact({
  label,
  value,
  ok,
  fg,
  muted,
  bg,
  note,
}: {
  label: string;
  value: string;
  ok: boolean;
  fg: string;
  muted: string;
  bg: string;
  note?: string;
}) {
  return (
    <div className="flex flex-col gap-1 px-4 py-3" style={{ background: bg }}>
      <dt className="font-mono text-[9px] uppercase tracking-[0.25em]" style={{ color: muted }}>
        {label}
      </dt>
      <dd className="flex items-baseline gap-2">
        <span className="font-mono text-sm" style={{ color: ok ? fg : "#f59e0b" }}>
          {value}
        </span>
        {note && (
          <span className="font-mono text-[9px] uppercase tracking-widest" style={{ color: muted }}>
            {note}
          </span>
        )}
      </dd>
    </div>
  );
}
