"use client";

import Image from "next/image";

import { useTheme } from "./ThemeProvider";

/**
 * VERA logo, themed.
 *
 * Single component for both lockups; flips between the light- and
 * dark-background variants based on the active theme so colour stays
 * load-bearing without each caller having to do the if/else.
 *
 * Always render via this component so the asset path stays in one
 * place — if the brand evolves, only this file needs to change.
 *
 * Variants:
 *   - "mark"        the V mark only (240 × 220)
 *   - "horizontal"  V mark + wordmark side-by-side (480 × 160)
 *   - "wordmark"    V mark + wordmark stacked (240 × 300)
 */
export function VeraLogo({
  variant = "horizontal",
  className,
  ariaLabel = "VERA",
  priority = false,
}: {
  variant?: "mark" | "horizontal" | "wordmark";
  className?: string;
  ariaLabel?: string;
  priority?: boolean;
}) {
  const { theme } = useTheme();
  const isLight = theme === "light";

  // The mark itself doesn't have light/dark variants — it stays charcoal
  // against any background because the V is silhouetted, not stroked.
  const src =
    variant === "mark"
      ? "/logo/vera-mark.svg"
      : variant === "wordmark"
      ? `/logo/vera-wordmark-${isLight ? "light" : "dark"}.svg`
      : `/logo/vera-horizontal-${isLight ? "light" : "dark"}.svg`;

  const dim =
    variant === "mark"
      ? ([240, 220] as const)
      : variant === "wordmark"
      ? ([240, 300] as const)
      : ([480, 160] as const);

  return (
    <Image
      src={src}
      alt={ariaLabel}
      width={dim[0]}
      height={dim[1]}
      className={className}
      priority={priority}
    />
  );
}
