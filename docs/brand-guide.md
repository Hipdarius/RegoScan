# VERA — Brand Guide

The VERA visual identity follows the cadence of mission-program identities
(Artemis, Mars Sample Return): **bold central letterform, single arcing
orbital ribbon, small lunar body, horizon arc, clean wordmark**, adapted
to a `V` that does triple duty:

1. The project initial.
2. A converging optical cone — the geometry of the probe's sensor fusion.
3. An arrow pointing down at the regolith sample.

The mark holds at every scale from a 16 px favicon up to a GitHub social
card.

---

## The mark, broken down

| Element | What it does | Color |
|---|---|---|
| **V letterform** | Project initial; reads as a measurement cone converging on the regolith below | `#0a0d14` charcoal |
| **Spectral ribbon** | Single arc sweeping through the V from lower-left to upper-right — the orbital trajectory and the spectral measurement gesture in one shape | `#f5b840` amber (the LIF channel hue) |
| **Crescent moon** | Small lunar body partially eclipsed by the V's right leg — situates the work in lunar context without pulling focus | `#c8d3da` cool grey |
| **Lunar horizon** | The teal arc the V stands on — anchors the composition and gives the V a "ground" | `#38b3c4` teal |
| **Wordmark** | "VERA" in bold sans-serif below the mark, with the tagline beneath it | `#0a0d14` charcoal (light bg) / `#f0f5f8` (dark bg) |

Everything is geometric primitives — no raster effects, no gradients, no
decoration that won't survive INT8 quantisation on a small screen.

---

## Palette

| Token | Value | Usage |
|---|---|---|
| `vera-base` | `#0a0d14` | V fill, wordmark on light bg, line work in mono variant |
| `vera-teal-500` | `#38b3c4` | Lunar horizon arc (sole appearance — reserved) |
| `vera-amber-500` | `#f5b840` | Spectral ribbon (sole appearance — reserved); also LIF channel in console UI |
| `vera-moon` | `#c8d3da` | Crescent moon, never used elsewhere |
| `vera-light` | `#f0f5f8` | Wordmark on dark, V silhouette on dark |
| `vera-dim` | `#9bb5c2` | Tagline on dark background |

The palette is deliberately compact — four chromatic stops plus two text
greys — so the brand never looks like a gradient soup. Same four-stop
discipline as the program identities the mark cites.

---

## Typography

| Role | Family | Weight | Size | Letter-spacing |
|---|---|---|---|---|
| Wordmark "VERA" stacked | Inter, Space Grotesk fallback | 700 | 48 px (at viewBox 240 × 300) | 7 (≈ 0.15 em) |
| Wordmark "VERA" horizontal | Inter, Space Grotesk fallback | 700 | 64 px (at viewBox 480 × 160) | 9 (≈ 0.14 em) |
| Tagline | Inter, Space Grotesk fallback | 400 | 11 px (horizontal) / 9 px (vertical) | 2 |

For final brand polish, convert all SVG text to outlined paths in a
vector editor before locking the brand files for print, embroidery, or
any context where Inter is not guaranteed.

---

## Files delivered

| File | Use |
|---|---|
| `web/public/logo/vera-mark.svg` | Mark only (no wordmark), 240 × 220 — for app icons, GitHub social card centerpiece, instrument plate |
| `web/public/logo/vera-wordmark-light.svg` | Stacked lockup (mark over wordmark), 240 × 300 — light background |
| `web/public/logo/vera-wordmark-dark.svg` | Stacked lockup, dark background |
| `web/public/logo/vera-horizontal-light.svg` | Horizontal lockup (mark left, wordmark right), 480 × 160 — for nav bars and document headers, light background |
| `web/public/logo/vera-horizontal-dark.svg` | Horizontal lockup, dark background |
| `web/public/logo/vera-mono.svg` | Single-ink version for stamps, lasered plates, embroidery |
| `web/public/favicon.svg` | 32 × 32 viewBox tuned for 16 / 24 / 32 px rendering |

### Alternates kept on file

| File | What it offers |
|---|---|
| `web/public/logo/vera-mission-patch.svg` | Full circular mission insignia in the crew-patch tradition — for hero / project-cover / shirt-back contexts where the V mark would feel too compact |
| `web/public/logo/alternates/vera-alt-aperture.svg` | Aperture-iris hexagon — pure geometry alternate, kept for completeness |
| `web/public/logo/alternates/vera-alt-convergent.svg` | Three-beam convergent V — earlier exploration, kept for documentation |
| `web/public/logo/alternates/vera-alt-spectral-hex.svg` | Spectral-line hex — earlier exploration, kept for documentation |

---

## Sizing

| Context | Min size | Variant |
|---|---|---|
| Favicon, browser tab | 16 × 16 | `favicon.svg` |
| README header / status bar | 80 – 128 px | `vera-mark.svg` or `favicon.svg` |
| Console nav bar | ≈ 40 px tall | `vera-horizontal-dark.svg` |
| Hero / cover slide | ≥ 240 px wide | `vera-wordmark-light.svg` / `vera-wordmark-dark.svg` |
| GitHub social card / project poster | ≥ 480 px | `vera-wordmark-*.svg` or `vera-mission-patch.svg` |
| Single-color print, etched plate | any | `vera-mono.svg` |

---

## Clear space

Reserve a margin equal to the cap height of the wordmark (≈ 48 px at the
canonical 240-wide artboard, or 10 % of the artboard width at any other
size) on every side of the lockup. The horizontal lockup needs the same
envelope on left/right and half that on top/bottom.

---

## Don'ts

- Don't recolor the amber ribbon to teal or the teal horizon to amber.
  The two-color story (teal = ground, amber = sky beam) is load-bearing
  for the composition's reading order.
- Don't fill the V with anything other than `#0a0d14` (light backgrounds)
  or `#e6edf2` (dark backgrounds). Mid-greys flatten the mark against
  either ground.
- Don't add a glow, gradient, or drop-shadow. The chosen identity is
  decisively flat — the moment VERA's mark adopts depth effects it stops
  looking like a peer to mission-program identities and starts looking
  like a tech-startup logo.
- Don't replace the crescent moon with a full disc. The crescent is the
  link to lunar mission imagery; a full disc reads as a generic dot.
- Don't shrink the horizontal lockup below 160 px wide — the tagline
  becomes unreadable.

---

## Implementation notes for the Next.js console

```tsx
// web/components/Logo.tsx
//
// Single component for both lockups; flips between light/dark by theme.
// Always render via this component so the asset path stays in one place.
import Image from "next/image";

export function VeraLogo({
  variant = "horizontal",
  theme = "dark",
  className,
  ariaLabel = "VERA",
}: {
  variant?: "mark" | "horizontal" | "wordmark";
  theme?: "light" | "dark";
  className?: string;
  ariaLabel?: string;
}) {
  const src =
    variant === "mark"
      ? "/logo/vera-mark.svg"
      : variant === "wordmark"
      ? `/logo/vera-wordmark-${theme}.svg`
      : `/logo/vera-horizontal-${theme}.svg`;
  const dim = variant === "mark" ? [240, 220] : variant === "wordmark" ? [240, 300] : [480, 160];
  return (
    <Image
      src={src}
      alt={ariaLabel}
      width={dim[0]}
      height={dim[1]}
      className={className}
      priority={variant !== "mark"}
    />
  );
}
```

Drop `vera-favicon.svg` into `web/public/favicon.svg` (overwrite). The
existing `<img src="web/public/favicon.svg" width="80" alt="VERA logo" />`
reference at the top of the README keeps working — same path, new art.
For a GitHub repo social card, export `vera-wordmark-light.svg` to PNG
at 1280 × 640 with the lockup centered against `#0a0d14`.

---

## Accessibility

- Every SVG carries `role="img"`, `<title>`, and `<desc>` so screen
  readers announce "VERA — bold V letterform with spectral ribbon,
  crescent moon, and lunar horizon."
- Contrast: `#0a0d14` V on white = 18.6 : 1 (WCAG AAA).
  `#f5b840` ribbon on white = 1.7 : 1 (decorative only — not used to
  convey text). `#38b3c4` horizon on white = 2.4 : 1 (decorative).
- The mark works without colour — `vera-mono.svg` is a true single-ink
  fallback for users with custom contrast settings or for media where
  colour reproduction can't be relied on.
