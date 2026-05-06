import type { DemoResponse, EndmembersResponse, MetaResponse, PredictionResponse } from "./types";

// In production (Vercel), the Python serverless function lives at /api/*
// on the same origin as the Next.js app — leave NEXT_PUBLIC_API_BASE unset.
// In local dev, point it at a uvicorn instance, e.g.:
//   NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000
const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") ?? "";

async function jsonFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${path} failed: ${res.status} ${text}`);
  }
  return (await res.json()) as T;
}

export function fetchMeta(): Promise<MetaResponse> {
  return jsonFetch<MetaResponse>("/api/meta");
}

export function fetchDemoPrediction(seed?: number): Promise<DemoResponse> {
  const qs = seed !== undefined ? `?seed=${seed}` : "";
  return jsonFetch<DemoResponse>(`/api/predict/demo${qs}`, { method: "POST" });
}

export function fetchEndmembers(): Promise<EndmembersResponse> {
  return jsonFetch<EndmembersResponse>("/api/endmembers");
}

export function postPrediction(payload: {
  spec: number[];
  led: number[];
  lif_450lp: number;
  swir?: number[];
  as7265x?: number[];
}): Promise<PredictionResponse> {
  return jsonFetch<PredictionResponse>("/api/predict", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
