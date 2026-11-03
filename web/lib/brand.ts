/**
 * Brand colour tokens, mirrored from `docs/brand-guide.md`.
 *
 * Available in the same shape as the Tailwind theme extension and the
 * CSS variables in `globals.css`. Use this when reading the colour
 * inside a TypeScript expression (e.g. for a Recharts axis stroke);
 * use the Tailwind class or CSS variable otherwise.
 */
export const BRAND = {
  base: "#0a0d14",
  teal: "#38b3c4",
  amber: "#f5b840",
  moon: "#c8d3da",
  light: "#f0f5f8",
  dim: "#9bb5c2",
} as const;

export type BrandToken = keyof typeof BRAND;
