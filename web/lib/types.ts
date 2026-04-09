// Mirrors the Pydantic response models in apps/api.py and web/api/predict.py.
// Keep these in sync — the response shape is the contract between Python
// inference and the React UI.

export interface ClassProbability {
  name: string;
  probability: number;
}

export interface PredictionResponse {
  predicted_class: string;
  predicted_class_index: number;
  probabilities: ClassProbability[];
  ilmenite_fraction: number;
  confidence: number;
  model_version: string;
  as7265x?: number[];
}

export interface DemoResponse extends PredictionResponse {
  spec: number[];
  led: number[];
  lif_450lp: number;
  as7265x?: number[];
  true_class: string;
  true_ilmenite_fraction: number;
}

export interface MetaResponse {
  schema_version: string;
  class_names: string[];
  wavelengths_nm: number[];
  led_wavelengths_nm: number[];
  n_features_total: number;
  model_loaded: boolean;
  model_sha256: string | null;
  model_run_dir: string | null;
  sensor_mode?: string;
  as7265x_bands_nm?: number[];
}

export interface EndmembersResponse {
  wavelengths_nm: number[];
  endmembers: Record<string, number[]>;
  source?: string;
}

// ── UI state types ──────────────────────────────────────
export type ScanState = "idle" | "scanning" | "done" | "error";

export interface ScanHistoryEntry {
  id: number;
  result: DemoResponse;
  timestamp: number;
  predicted_class: string;
  confidence: number;
  ilmenite_fraction: number;
}

export interface TerminalLine {
  timestamp: string;
  text: string;
  level: "info" | "success" | "warn" | "error";
}

// ── Display helpers ─────────────────────────────────────
export const CLASS_LABELS: Record<string, string> = {
  ilmenite_rich: "Ilmenite-Rich",
  olivine_rich: "Olivine-Rich",
  pyroxene_rich: "Pyroxene-Rich",
  anorthositic: "Anorthositic",
  mixed: "Mixed Regolith",
};
