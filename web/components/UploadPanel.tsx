"use client";

import { useCallback, useRef, useState } from "react";
import { motion } from "framer-motion";
import { useTheme } from "./ThemeProvider";
import { postPrediction } from "@/lib/api";
import type { DemoResponse } from "@/lib/types";

/**
 * Parse a CSV file and extract the first data row's canonical sensor columns.
 */
type ParsedMeasurement = {
  spec: number[];
  led: number[];
  lif_450lp: number;
  swir?: number[];
  as7265x?: number[];
};

function numericColumns(
  headers: string[],
  values: number[],
  columns: string[]
): number[] | null {
  const out: number[] = [];
  for (const col of columns) {
    const idx = headers.indexOf(col);
    if (idx === -1) return null;
    out.push(values[idx]);
  }
  return out.every(Number.isFinite) ? out : null;
}

function parseCSV(text: string): ParsedMeasurement | null {
  const lines = text.trim().split(/\r?\n/);
  if (lines.length < 2) return null;

  const headers = lines[0].split(",").map((h) => h.trim());
  const values = lines[1].split(",").map((v) => parseFloat(v.trim()));

  const spec = numericColumns(
    headers,
    values,
    Array.from({ length: 288 }, (_, i) => `spec_${String(i).padStart(3, "0")}`)
  );
  if (!spec) return null;

  const led = numericColumns(
    headers,
    values,
    [
      "led_385",
      "led_405",
      "led_450",
      "led_500",
      "led_525",
      "led_590",
      "led_625",
      "led_660",
      "led_730",
      "led_780",
      "led_850",
      "led_940",
    ]
  );
  if (!led) return null;

  const lifIdx = headers.indexOf("lif_450lp");
  if (lifIdx === -1) return null;
  const lif_450lp = values[lifIdx];
  if (!Number.isFinite(lif_450lp)) return null;

  const swir = numericColumns(headers, values, ["swir_940", "swir_1050"]);
  if (!swir) return null;

  const as7265x = numericColumns(
    headers,
    values,
    [
      "as7_410",
      "as7_435",
      "as7_460",
      "as7_485",
      "as7_510",
      "as7_535",
      "as7_560",
      "as7_585",
      "as7_610",
      "as7_645",
      "as7_680",
      "as7_705",
      "as7_730",
      "as7_760",
      "as7_810",
      "as7_860",
      "as7_900",
      "as7_940",
    ]
  );

  return {
    spec,
    led,
    lif_450lp,
    swir,
    ...(as7265x ? { as7265x } : {}),
  };
}

export function UploadPanel({
  disabled,
  onResult,
}: {
  disabled?: boolean;
  onResult: (result: DemoResponse) => void;
}) {
  const { theme } = useTheme();
  const isLight = theme === "light";

  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const cyanText = isLight ? "#0284c7" : "#38bdf8";
  const mutedText = isLight ? "#64748b" : "#94a3b8";
  const amberText = "#f59e0b";

  const handleFile = useCallback(
    async (file: File) => {
      setUploadError(null);
      setFileName(file.name);
      setUploading(true);
      try {
        const text = await file.text();
        const parsed = parseCSV(text);
        if (!parsed) {
          throw new Error(
            "CSV must contain spec_000..spec_287, swir_940/swir_1050, led_* and lif_450lp columns. Add as7_* columns for combined or multispectral models."
          );
        }
        const result = await postPrediction(parsed);
        // Wrap PredictionResponse into DemoResponse shape for display
        const demo: DemoResponse = {
          ...result,
          spec: parsed.spec,
          led: parsed.led,
          lif_450lp: parsed.lif_450lp,
          swir: parsed.swir,
          as7265x: parsed.as7265x,
          true_class: result.predicted_class,
          true_ilmenite_fraction: result.ilmenite_fraction,
        };
        onResult(demo);
      } catch (e) {
        setUploadError(String(e));
      } finally {
        setUploading(false);
      }
    },
    [onResult]
  );

  const onFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
      // Reset so the same file can be re-uploaded
      e.target.value = "";
    },
    [handleFile]
  );

  return (
    <div className="flex flex-col gap-2">
      <input
        ref={fileRef}
        type="file"
        accept=".csv"
        onChange={onFileChange}
        className="hidden"
      />
      <div className="flex items-center gap-3">
        <motion.button
          whileTap={{ scale: disabled ? 1 : 0.99 }}
          onClick={() => fileRef.current?.click()}
          disabled={disabled || uploading}
          className="group relative overflow-hidden border px-5 py-3 font-mono text-[11px] uppercase tracking-[0.28em] transition-colors disabled:cursor-not-allowed disabled:opacity-40"
          style={{
            borderColor: isLight ? "#cbd5e1" : "#334155",
            background: "transparent",
            color: mutedText,
          }}
        >
          <span className="flex items-center gap-2">
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
            {uploading ? "Processing…" : "Upload CSV"}
          </span>
        </motion.button>
        {fileName && (
          <span
            className="font-mono text-[10px] uppercase tracking-widest"
            style={{ color: mutedText }}
          >
            {fileName}
          </span>
        )}
      </div>
      {uploadError && (
        <span
          className="font-mono text-[10px]"
          style={{ color: amberText }}
        >
          {uploadError}
        </span>
      )}
    </div>
  );
}
