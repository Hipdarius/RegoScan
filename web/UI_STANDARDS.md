# VERA Frontend Design System

## Aesthetic: Aerospace / ESA Mission Control

This is a ground-station terminal for a lunar instrument, not a consumer
web app. Every pixel must reinforce that context.

## Two surfaces, one aesthetic

The frontend has two layout modes that share a colour palette and
type system but compose them differently:

| Surface | Routes | Driver | Reading mode |
|--|--|--|--|
| **Console** | `/` | `Hero` + `MissionPanel` + side panels | Glance — at-a-glance numbers, live telemetry |
| **Docs** | `/about`, `/architecture`, `/methods` | `DocPage` + `Section` + `Prose` | Linear read — long-form prose with diagrams |

Console components live directly in `web/components/`. Doc-page
primitives live under `web/components/docs/` (see "Doc primitives"
below). The two surfaces share the `ThemeProvider` so theme switches
propagate everywhere; otherwise they are independent and should not
import each other's components.

## Banned Tailwind Classes

- `rounded-lg`, `rounded-xl`, `rounded-full` (except status indicator dots — `h-1.5 w-1.5 rounded-full` is allowed and used as a consistent pattern across `Hero`, `NavBar`, `ScanButton`, `MissionPanel`, `ScanHistory`, and the docs primitives)
- `shadow-md`, `shadow-lg`, `shadow-xl`
- `bg-gradient-to-r`, `bg-gradient-to-b`, `bg-gradient-to-*`

Use `rounded-none` or `rounded-sm` maximum. Separate panels with 1px
borders (`border border-slate-700`), not drop shadows.

## Typography

- **Labels & Headers:** `text-xs uppercase tracking-widest text-slate-400 font-semibold`
- **Telemetry & Data:** `font-mono text-emerald-400` (prevents width-jumping)
- **No Lorem Ipsum.** Use domain-specific placeholders:
  `AWAITING C12880MA SYNC...`, `BUFFER EMPTY`, `NO LOCK`

## Color Palette

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

### Status escalation palette (used by `StatusFieldStates` on /methods)

The four-state classifier collapses to **three colours** by escalation
urgency, not four-by-category — both `nominal` and `borderline`
operate normally so they share cyan; colour signals when the operator
needs to escalate.

| Status              | Colour token   |
|---------------------|----------------|
| nominal / borderline | `cyan` (sky-400 / sky-500) |
| low_confidence      | `amber-400`    |
| likely_ood          | `rose-500`     |

## Doc primitives

All doc-page components must be composed out of the primitives in
`web/components/docs/` and `web/components/DocPage.tsx` rather than
written directly with Tailwind. The primitives encode the rhythm,
colour tokens, and animation that make the doc surface feel
consistent.

Available primitives:

| Component | From | Used for |
|--|--|--|
| `DocPage` | `@/components/DocPage` | The page shell — eyebrow + title + intro + optional aside / vitals / margin nav |
| `Section`, `SubSection` | `@/components/DocPage` | Numbered chapters within a `DocPage` |
| `Prose` | `@/components/DocPage` | Long-form text blocks |
| `MetricRow` | `@/components/DocPage` | Headline numbers — large mono on the left, one-sentence caption on the right |
| `VitalStats`, `SpecList` | `@/components/DocPage` | Mono key/value strips |
| `FactGrid` | `@/components/DocPage` | At-a-glance grid of cells (legacy /about) |
| `Bibliography` | `@/components/DocPage` | Typeset academic citations with audit-trail "→ used" line |
| `MarginNav`, `SymbolLegend` | `@/components/DocPage` | Right-rail TOC; bottom-of-page symbol glossary |
| `Math`, `Eq` | `@/components/DocPage` | Inline + block equations |
| `FadeIn`, `useDocTheme`, `StatusRow` | `@/components/docs/primitives` | Enter animation, theme tokens, OK/pending row |
| `LayerStack`, `WavelengthCoverage`, `StateMachine`, `PacketFrame`, `ResNetDiagram`, `PipelineFlow`, `StatusFieldStates`, `AcquisitionScore`, `TransferMatrix`, `DeploymentTiers` | `@/components/docs/diagrams` | Declarative SVG diagrams |
| `ProbeSchematic`, `Roadmap`, `SplitColumn` | `@/components/docs/about-extras` | /about-only components |

A new doc page should:
1. Live under `web/app/<route>/page.tsx` with `"use client"`
2. Use `<DocPage>` as its outer wrapper
3. Compose `<Section number="01" title="...">` for each chapter
4. Use `<Prose>` for paragraphs, the diagram primitives for visuals
5. Inherit theme tokens via `useDocTheme()` instead of hard-coding hex

If a primitive is missing, add it to `web/components/docs/` rather
than inlining it in the page file. Primitives are how the surface
stays consistent.

## Component Rules

- No monolith files. Max ~120 lines per component (DocPage.tsx is the
  one allowed exception — it's the design-system root).
- Icons: inline SVG only — no icon library. The console intentionally
  avoids icons in numeric panels; if a glyph is needed (cyan dots,
  status pips), draw it inline so the bundle stays lean.
- All numeric telemetry in `font-mono` to prevent layout shift.
- Status indicator dots use the consistent
  `inline-block h-1.5 w-1.5 rounded-full` pattern across all
  components — Hero, NavBar, ScanButton, MissionPanel, ScanHistory,
  and the docs primitives. Don't invent variants.
