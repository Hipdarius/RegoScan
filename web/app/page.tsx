"use client";

import { useCallback, useEffect, useRef, useState } from "react";
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

  // Scan history (max 10)
  const [scanHistory, setScanHistory] = useState<DemoResponse[]>([]);
  const [selectedHistoryIdx, setSelectedHistoryIdx] = useState(0);

  // Fetch meta + endmembers on mount
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
    setScanHistory((prev) => {
      const next = [result, ...prev].slice(0, 10);
      return next;
    });
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

  // Handle upload result (PredictionResponse → DemoResponse shape)
  const handleUploadResult = useCallback(
    (result: DemoResponse) => {
      pushScan(result);
    },
    [pushScan]
  );

  // Select a historical scan
  const handleHistorySelect = useCallback(
    (idx: number) => {
      setSelectedHistoryIdx(idx);
      setScan(scanHistory[idx]);
    },
    [scanHistory]
  );

  const cyanText = isLight ? "#0284c7" : "#38bdf8";
  const amberText = isLight ? "#f59e0b" : "#f59e0b";
  const mutedText = isLight ? "#94a3b8" : "#64748b";
  const borderColor = isLight ? "rgba(15, 23, 42, 0.12)" : "rgba(56, 189, 248, 0.15)";
  const panelBg = isLight ? "rgba(255,255,255,0.85)" : "rgba(15, 23, 42, 0.7)";
  const telemetryBorder = isLight ? "#e2e8f0" : "#1e293b";

  return (
    <main className="relative min-h-screen pb-24">
      <Hero
        schemaVersion={meta?.schema_version ?? null}
        modelLoaded={meta?.model_loaded ?? false}
        metaLoading={metaLoading}
      />

      <div className="mx-auto mt-10 flex max-w-6xl flex-col gap-6 px-6">
        {/* Model offline warning */}
        {!metaLoading && meta && !meta.model_loaded && (
          <div
            className="rounded-lg border px-4 py-3 font-mono text-xs"
            style={{
              borderColor: isLight ? "rgba(217,119,6,0.3)" : "rgba(251,191,36,0.3)",
              background: isLight ? "rgba(217,119,6,0.08)" : "rgba(251,191,36,0.1)",
              color: amberText,
            }}
          >
            MODEL OFFLINE — ONNX model not loaded. Check the backend server.
          </div>
        )}

        {/* Action bar */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="flex flex-wrap items-center justify-between gap-4 rounded-xl px-5 py-4 backdrop-blur-sm"
          style={{
            border: `1px solid ${borderColor}`,
            background: panelBg,
            boxShadow: isLight
              ? "0 1px 3px rgba(0,0,0,0.06)"
              : "0 0 24px rgba(34, 211, 238, 0.08)",
          }}
        >
          <div className="flex flex-col gap-1">
            <span
              className="font-mono text-[10px] uppercase tracking-widest"
              style={{ color: mutedText }}
            >
              Probe operation
            </span>
            <span
              className="font-mono text-sm"
              style={{ color: isLight ? "#0f172a" : "#e2e8f0" }}
            >
              Synthetic acquisition · 288 ch · 340–850 nm
            </span>
          </div>
          <div className="flex items-center gap-3">
            <UploadPanel onResult={handleUploadResult} />
            <ScanButton
              onClick={runScan}
              isScanning={isScanning}
              disabled={!meta?.model_loaded}
            />
          </div>
        </motion.div>

        {error && (
          <div
            className="rounded-lg border px-4 py-3 font-mono text-xs"
            style={{
              borderColor: isLight ? "rgba(217,119,6,0.3)" : "rgba(251,191,36,0.3)",
              background: isLight ? "rgba(217,119,6,0.08)" : "rgba(251,191,36,0.1)",
              color: amberText,
            }}
          >
            {error}
          </div>
        )}

        {/* Top row: spectrum + ilmenite */}
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
                className="mt-3 flex flex-wrap gap-4 font-mono text-[10px] uppercase tracking-widest"
                style={{ color: mutedText }}
              >
                <span>340 nm – 850 nm</span>
                <span>·</span>
                <span>Hamamatsu C12880MA emulation</span>
                {scan && (
                  <>
                    <span>·</span>
                    <span style={{ color: cyanText }}>
                      LIF 450lp = {scan.lif_450lp.toFixed(3)}
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

        {/* Bottom row */}
        <div className="grid gap-6 lg:grid-cols-3">
          <MissionPanel title="Mineral Class Posterior" delay={0.1}>
            <ProbabilityBars
              probabilities={scan?.probabilities ?? null}
              predictedClass={scan?.predicted_class ?? null}
            />
          </MissionPanel>

          <MissionPanel title="Mission Telemetry" delay={0.15}>
            <dl className="space-y-4">
              <Telemetry label="Predicted class" value={scan ? CLASS_LABELS[scan.predicted_class] ?? scan.predicted_class : "\u2014"} color={cyanText} borderColor={telemetryBorder} labelColor={mutedText} />
              <Telemetry label="Confidence" value={scan ? `${(scan.confidence * 100).toFixed(1)}%` : "\u2014"} color={cyanText} borderColor={telemetryBorder} labelColor={mutedText} />
              <Telemetry label="Ground truth" value={scan ? CLASS_LABELS[scan.true_class] ?? scan.true_class : "\u2014"} color={amberText} borderColor={telemetryBorder} labelColor={mutedText} />
              <Telemetry
                label="Match"
                value={scan ? (scan.predicted_class === scan.true_class ? "NOMINAL" : "DEVIATION") : "\u2014"}
                color={scan ? (scan.predicted_class === scan.true_class ? cyanText : amberText) : cyanText}
                borderColor={telemetryBorder}
                labelColor={mutedText}
              />
            </dl>
          </MissionPanel>

          <MissionPanel title="Model Provenance" delay={0.2}>
            <dl className="space-y-4">
              <Telemetry label="Model" value={scan?.model_version ?? "vera-resnet"} color={cyanText} borderColor={telemetryBorder} labelColor={mutedText} />
              <Telemetry label="Schema" value={meta?.schema_version ?? "\u2014"} color={cyanText} borderColor={telemetryBorder} labelColor={mutedText} />
              <Telemetry label="ONNX SHA-256" value={meta?.model_sha256 ?? "\u2014"} color={cyanText} borderColor={telemetryBorder} labelColor={mutedText} mono />
              <Telemetry label="Features" value={meta ? `${meta.n_features_total}` : "\u2014"} color={cyanText} borderColor={telemetryBorder} labelColor={mutedText} />
            </dl>
          </MissionPanel>
        </div>

        {/* Scan history */}
        {scanHistory.length > 0 && (
          <MissionPanel title="Scan History" delay={0.25}>
            <ScanHistory
              history={scanHistory}
              selectedIndex={selectedHistoryIdx}
              onSelect={handleHistorySelect}
            />
          </MissionPanel>
        )}

        <footer
          className="mt-6 flex flex-col items-center gap-1 text-center font-mono text-[10px] uppercase tracking-widest"
          style={{ color: mutedText }}
        >
          <span>VERA · 1D ResNet · ONNXRuntime · FastAPI</span>
          <span>Inference at the edge — same model that fits the embedded probe.</span>
        </footer>
      </div>
    </main>
  );
}

function Telemetry({
  label,
  value,
  color,
  borderColor,
  labelColor,
  mono = false,
}: {
  label: string;
  value: string;
  color: string;
  borderColor: string;
  labelColor: string;
  mono?: boolean;
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
      <dd className={`font-mono ${mono ? "text-[11px]" : "text-sm"}`} style={{ color }}>
        {value}
      </dd>
    </div>
  );
}
