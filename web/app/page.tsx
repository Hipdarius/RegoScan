"use client";

import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";

import { Hero } from "@/components/Hero";
import { ScanButton } from "@/components/ScanButton";
import { MissionPanel } from "@/components/MissionPanel";
import { SpectrumChart } from "@/components/SpectrumChart";
import { ProbabilityBars } from "@/components/ProbabilityBars";
import { IlmeniteGauge } from "@/components/IlmeniteGauge";
import { UploadPanel } from "@/components/UploadPanel";
import { ScanHistory } from "@/components/ScanHistory";
import { useTheme } from "@/components/ThemeProvider";

import { fetchDemoPrediction, fetchEndmembers, fetchMeta } from "@/lib/api";
import {
  CLASS_LABELS,
  type DemoResponse,
  type EndmembersResponse,
  type MetaResponse,
} from "@/lib/types";

const SCAN_TIMEOUT_MS = 10_000;

export default function Home() {
  const { theme } = useTheme();
  const isLight = theme === "light";

  const [meta, setMeta] = useState<MetaResponse | null>(null);
  const [metaLoading, setMetaLoading] = useState(true);
  const [endmembers, setEndmembers] = useState<EndmembersResponse | null>(null);
  const [scan, setScan] = useState<DemoResponse | null>(null);
  const [isScanning, setIsScanning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [scanHistory, setScanHistory] = useState<DemoResponse[]>([]);
  const [selectedHistoryIdx, setSelectedHistoryIdx] = useState(0);

  useEffect(() => {
    setMetaLoading(true);
    Promise.all([
      fetchMeta().catch(() => null),
      fetchEndmembers().catch(() => null),
    ]).then(([m, e]) => {
      if (m) setMeta(m);
      else setError("Could not reach API — is the backend running on port 8000?");
      if (e) setEndmembers(e);
      setMetaLoading(false);
    });
  }, []);

  const pushScan = useCallback((result: DemoResponse) => {
    setScan(result);
    setScanHistory((prev) => [result, ...prev].slice(0, 10));
    setSelectedHistoryIdx(0);
  }, []);

  const runScan = useCallback(async () => {
    setIsScanning(true);
    setError(null);
    const startedAt = performance.now();
    const timeout = new Promise<never>((_, reject) =>
      setTimeout(() => reject(new Error("Scan timed out after 10 seconds")), SCAN_TIMEOUT_MS)
    );
    try {
      const result = await Promise.race([fetchDemoPrediction(), timeout]);
      const elapsed = performance.now() - startedAt;
      const remaining = Math.max(0, 700 - elapsed);
      if (remaining > 0) await new Promise((r) => setTimeout(r, remaining));
      pushScan(result);
    } catch (e) {
      setError(String(e));
    } finally {
      setIsScanning(false);
    }
  }, [pushScan]);

  const handleUploadResult = useCallback(
    (result: DemoResponse) => {
      pushScan(result);
    },
    [pushScan]
  );

  const handleHistorySelect = useCallback(
    (idx: number) => {
      setSelectedHistoryIdx(idx);
      setScan(scanHistory[idx]);
    },
    [scanHistory]
  );

  const cyanText = isLight ? "#0284c7" : "#38bdf8";
  const amberText = "#f59e0b";
  const mutedText = isLight ? "#64748b" : "#94a3b8";
  const dimText = isLight ? "#94a3b8" : "#64748b";
  const borderColor = isLight ? "#e2e8f0" : "#1e293b";
  const telemetryBorder = borderColor;
  const warnBg = isLight ? "rgba(245, 158, 11, 0.06)" : "rgba(245, 158, 11, 0.08)";
  const warnBorder = "rgba(245, 158, 11, 0.35)";
  const sensorLabel = meta
    ? `Synthetic acquisition · ${meta.n_features_total} ch · ${meta.sensor_mode ?? "full"} mode`
    : "Synthetic acquisition · awaiting meta…";

  return (
    <main className="relative min-h-screen pb-24">
      <Hero
        schemaVersion={meta?.schema_version ?? null}
        modelLoaded={meta?.model_loaded ?? false}
        metaLoading={metaLoading}
      />

      <div className="mx-auto mt-10 flex max-w-6xl flex-col gap-10 px-6">
        {/* Alerts sit above the section rhythm so they never compete with it */}
        {!metaLoading && meta && !meta.model_loaded && (
          <div
            className="border px-4 py-3 font-mono text-[11px] uppercase tracking-widest"
            style={{ borderColor: warnBorder, background: warnBg, color: amberText }}
            role="status"
          >
            Model offline · ONNX not loaded · check backend server
          </div>
        )}
        {error && (
          <div
            className="border px-4 py-3 font-mono text-[11px]"
            style={{ borderColor: warnBorder, background: warnBg, color: amberText }}
            role="alert"
          >
            {error}
          </div>
        )}

        {/* ── 01 Acquisition ─────────────────────────────────────────── */}
        <motion.section
          className="flex flex-col gap-5"
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <SectionHeader
            index="01"
            title="Acquisition"
            cyanText={cyanText}
            mutedText={mutedText}
            dimText={dimText}
            borderColor={borderColor}
            actions={
              <>
                <UploadPanel onResult={handleUploadResult} />
                <ScanButton
                  onClick={runScan}
                  isScanning={isScanning}
                  disabled={!meta?.model_loaded}
                />
              </>
            }
          />
          <div
            className="font-mono text-[11px] uppercase tracking-widest"
            style={{ color: mutedText }}
          >
            {sensorLabel}
          </div>

          <div className="grid gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <MissionPanel title="VIS/NIR Spectrum">
                <SpectrumChart
                  wavelengths={meta?.wavelengths_nm ?? null}
                  spectrum={scan?.spec ?? null}
                  endmembers={endmembers}
                  as7265x={scan?.as7265x}
                  as7265xBands={meta?.as7265x_bands_nm}
                />
                <div
                  className="mt-3 flex flex-wrap gap-x-4 gap-y-1 font-mono text-[10px] uppercase tracking-widest"
                  style={{ color: dimText }}
                >
                  <span>340–850 nm · 288 ch</span>
                  <span>·</span>
                  <span>Hamamatsu C12880MA (emulated)</span>
                  {scan && (
                    <>
                      <span>·</span>
                      <span style={{ color: cyanText }}>
                        LIF 450 LP = {scan.lif_450lp.toFixed(3)}
                      </span>
                    </>
                  )}
                </div>
              </MissionPanel>
            </div>

            <MissionPanel title="Ilmenite Regression" delay={0.05}>
              <IlmeniteGauge
                fraction={scan?.ilmenite_fraction ?? null}
                trueFraction={scan?.true_ilmenite_fraction ?? null}
              />
            </MissionPanel>
          </div>
        </motion.section>

        {/* ── 02 Inference ───────────────────────────────────────────── */}
        <motion.section
          className="flex flex-col gap-5"
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.05 }}
        >
          <SectionHeader
            index="02"
            title="Inference"
            cyanText={cyanText}
            mutedText={mutedText}
            dimText={dimText}
            borderColor={borderColor}
          />

          {/* Asymmetric 2/1: primary output (posterior) gets the space it
              deserves; provenance + telemetry stack in the narrow right column. */}
          <div className="grid gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <MissionPanel title="Mineral Class Posterior">
                <ProbabilityBars
                  probabilities={scan?.probabilities ?? null}
                  predictedClass={scan?.predicted_class ?? null}
                />
              </MissionPanel>
            </div>

            <div className="flex flex-col gap-6">
              <MissionPanel title="Mission Telemetry" delay={0.05}>
                <dl className="space-y-3">
                  <Telemetry label="Predicted class" value={scan ? CLASS_LABELS[scan.predicted_class] ?? scan.predicted_class : "—"} color={cyanText} borderColor={telemetryBorder} labelColor={dimText} />
                  <Telemetry label="Confidence" value={scan ? `${(scan.confidence * 100).toFixed(1)}%` : "—"} color={cyanText} borderColor={telemetryBorder} labelColor={dimText} />
                  <Telemetry label="Ground truth" value={scan ? CLASS_LABELS[scan.true_class] ?? scan.true_class : "—"} color={amberText} borderColor={telemetryBorder} labelColor={dimText} />
                  <Telemetry
                    label="Match"
                    value={scan ? (scan.predicted_class === scan.true_class ? "NOMINAL" : "DEVIATION") : "—"}
                    color={scan ? (scan.predicted_class === scan.true_class ? cyanText : amberText) : cyanText}
                    borderColor={telemetryBorder}
                    labelColor={dimText}
                  />
                </dl>
              </MissionPanel>

              <MissionPanel title="Model Provenance" delay={0.1}>
                <dl className="space-y-3">
                  <Telemetry label="Model" value={scan?.model_version ?? "vera-resnet"} color={cyanText} borderColor={telemetryBorder} labelColor={dimText} />
                  <Telemetry label="Schema" value={meta?.schema_version ?? "—"} color={cyanText} borderColor={telemetryBorder} labelColor={dimText} />
                  <Telemetry label="ONNX SHA-256" value={meta?.model_sha256 ?? "—"} color={cyanText} borderColor={telemetryBorder} labelColor={dimText} mono truncate />
                  <Telemetry label="Features" value={meta ? `${meta.n_features_total}` : "—"} color={cyanText} borderColor={telemetryBorder} labelColor={dimText} />
                </dl>
              </MissionPanel>
            </div>
          </div>
        </motion.section>

        {/* ── 03 Log ─────────────────────────────────────────────────── */}
        <motion.section
          className="flex flex-col gap-5"
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
        >
          <SectionHeader
            index="03"
            title="Log"
            cyanText={cyanText}
            mutedText={mutedText}
            dimText={dimText}
            borderColor={borderColor}
          />
          <div className="panel">
            <div className="panel-body">
              {scanHistory.length === 0 ? (
                <div
                  className="flex h-16 items-center justify-center font-mono text-[11px] uppercase tracking-widest"
                  style={{ color: dimText }}
                >
                  buffer empty · awaiting first scan
                </div>
              ) : (
                <ScanHistory
                  history={scanHistory}
                  selectedIndex={selectedHistoryIdx}
                  onSelect={handleHistorySelect}
                />
              )}
            </div>
          </div>
        </motion.section>

        <footer
          className="mt-4 flex flex-col gap-1 border-t pt-4 font-mono text-[10px] uppercase tracking-widest sm:flex-row sm:items-center sm:justify-between"
          style={{ color: dimText, borderColor: telemetryBorder }}
        >
          <span>VERA · 1D ResNet · onnxruntime · FastAPI</span>
          <span>Same ONNX artifact targets the ESP32-S3 probe via TFLite INT8</span>
        </footer>
      </div>
    </main>
  );
}

function SectionHeader({
  index,
  title,
  actions,
  cyanText,
  mutedText,
  dimText,
  borderColor,
}: {
  index: string;
  title: string;
  actions?: React.ReactNode;
  cyanText: string;
  mutedText: string;
  dimText: string;
  borderColor: string;
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-3">
      <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.32em]">
        <span style={{ color: cyanText }}>{"//"}</span>
        <span style={{ color: dimText }}>{index}</span>
        <span style={{ color: mutedText }}>{title}</span>
      </div>
      <span
        className="h-px min-w-[2rem] flex-1"
        style={{ backgroundColor: borderColor }}
        aria-hidden="true"
      />
      {actions && <div className="flex items-center gap-3">{actions}</div>}
    </div>
  );
}

function Telemetry({
  label,
  value,
  color,
  borderColor,
  labelColor,
  mono = false,
  truncate = false,
}: {
  label: string;
  value: string;
  color: string;
  borderColor: string;
  labelColor: string;
  mono?: boolean;
  truncate?: boolean;
}) {
  return (
    <div
      className="flex items-center justify-between gap-4 pb-2 last:border-b-0 last:pb-0"
      style={{ borderBottom: `1px solid ${borderColor}` }}
    >
      <dt
        className="font-mono text-[10px] uppercase tracking-widest"
        style={{ color: labelColor }}
      >
        {label}
      </dt>
      <dd
        className={`font-mono ${mono ? "text-[11px]" : "text-sm"} ${truncate ? "max-w-[8rem] truncate" : ""}`}
        style={{ color }}
        title={truncate ? value : undefined}
      >
        {value}
      </dd>
    </div>
  );
}
