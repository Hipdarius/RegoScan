# VERA Frontend Design System

## Aesthetic: Aerospace / ESA Mission Control

This is a ground-station terminal for a lunar instrument, not a consumer
web app. Every pixel must reinforce that context.

## Banned Tailwind Classes

- `rounded-lg`, `rounded-xl`, `rounded-full` (except status indicator dots)
- `shadow-md`, `shadow-lg`, `shadow-xl`
- `bg-gradient-to-r`, `bg-gradient-to-b`, `bg-gradient-to-*`

Use `rounded-none` or `rounded-sm` maximum. Separate panels with 1px
borders (`border border-slate-700`), not drop shadows.

## Typography

- **Labels & Headers:** `text-xs uppercase tracking-widest text-slate-400 font-semibold`
- **Telemetry & Data:** `font-mono text-emerald-400` (prevents width-jumping)
- **No Lorem Ipsum.** Use domain-specific placeholders:
  `AWAITING C12880MA SYNC...`, `BUFFER EMPTY`, `NO LOCK`

## ESA Lore Color Palette (Tailwind only)

| Role               | Class                          |
|--------------------|--------------------------------|
| App background     | `bg-slate-950`                 |
| Panel background   | `bg-slate-900`                 |
| Interactive / hdr  | `bg-slate-800`                 |
| Borders            | `border-slate-800` or `-700`   |
| Primary accent     | `text-sky-400` / `bg-sky-500`  |
| Nominal / online   | `emerald-400` / `emerald-500`  |
| Active / scanning  | `amber-400` / `amber-500`      |
| Error / offline    | `rose-500`                     |

## Component Rules

- No monolith files. Max ~120 lines per component.
- Icons: inline SVG only — no icon library. The console intentionally
  avoids icons in numeric panels; if a glyph is needed (cyan dots,
  status pips), draw it inline so the bundle stays lean.
- All numeric telemetry in `font-mono` to prevent layout shift.
