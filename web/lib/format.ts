/**
 * Number / string formatting helpers shared by the console and the doc pages.
 *
 * Kept in `web/lib/` so they can be imported from any component without
 * circular dependency risk; tests for these live alongside in `format.test.ts`
 * once we add a vitest harness.
 */

/** Format a probability in [0, 1] as `99.3 %` (one-decimal). */
export function formatPercent(p: number, digits: number = 1): string {
  if (!Number.isFinite(p)) return "—";
  const clamped = Math.max(0, Math.min(1, p));
  return `${(clamped * 100).toFixed(digits)} %`;
}

/** Format a small probability in [0, 1] as `0.97`, no percent sign. */
export function formatProbability(p: number, digits: number = 2): string {
  if (!Number.isFinite(p)) return "—";
  const clamped = Math.max(0, Math.min(1, p));
  return clamped.toFixed(digits);
}

/** Format a wavelength integer / float as `940 nm`. */
export function formatWavelength(nm: number): string {
  if (!Number.isFinite(nm)) return "—";
  return `${Math.round(nm)} nm`;
}

/** Format a duration in milliseconds as `4.7 ms` or `1.2 s` for >1000 ms. */
export function formatDuration(ms: number): string {
  if (!Number.isFinite(ms)) return "—";
  if (ms < 1000) return `${ms.toFixed(1)} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

/** Pretty-print a model SHA-256 prefix as `sha256:abcd1234…`. */
export function formatSha(short: string | null | undefined): string {
  if (!short) return "sha256:—";
  return `sha256:${short.slice(0, 8)}…`;
}

/** Convert a sensor-mode string to its display label. */
export function sensorModeLabel(mode: string): string {
  switch (mode) {
    case "full":
      return "VIS/NIR + SWIR";
    case "multispectral":
      return "AS7265x + SWIR";
    case "combined":
      return "Combined (321 ch.)";
    default:
      return mode;
  }
}
