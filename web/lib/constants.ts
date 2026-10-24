/**
 * Shared frontend constants. Mirrors values defined in `src/vera/schema.py`
 * but expressed in TypeScript so the console can reference them without an
 * extra fetch. Keep the two files in sync; ideally a future polish pass
 * generates this from schema.py at build time.
 */

/** Wire-format version. Must match `vera.schema.SCHEMA_VERSION`. */
export const SCHEMA_VERSION = "1.2.0";

/** Six mineral classes the model predicts, in argmax order. */
export const MINERAL_CLASSES = [
  "ilmenite_rich",
  "olivine_rich",
  "pyroxene_rich",
  "anorthositic",
  "glass_agglutinate",
  "mixed",
] as const;
export type MineralClass = (typeof MINERAL_CLASSES)[number];

/** Spectrometer-channel count (Hamamatsu C12880MA). */
export const N_SPEC = 288;

/** AS7265x triad channels. */
export const N_AS7265X = 18;

/** SWIR photodiode channels (940 nm + 1050 nm). */
export const N_SWIR = 2;

/** Narrowband LED channels in the illumination ring. */
export const N_LED = 12;

/** Feature-vector width per sensor mode. */
export const FEATURE_COUNT: Record<"full" | "multispectral" | "combined", number> = {
  full: N_SPEC + N_SWIR + N_LED + 1, // 303
  multispectral: N_AS7265X + N_SWIR + N_LED + 1, // 33
  combined: N_SPEC + N_AS7265X + N_SWIR + N_LED + 1, // 321
};

/** Wavelength of the LIF excitation laser, in nanometres. */
export const LIF_EXCITATION_NM = 405;

/** SWIR photodiode sampling wavelengths, in nanometres. */
export const SWIR_WAVELENGTHS_NM = [940, 1050] as const;
