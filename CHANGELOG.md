# Changelog

All notable changes to VERA are tracked here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project adheres to [Semantic Versioning](https://semver.org/) once it
ships a tagged release.

The pre-1.0 entries below are dated by week and group commits
thematically rather than by release. The first tagged release will be
the version submitted to Jonk Fuerscher 2027.

## [Unreleased]

### Added (Oct)
- Release checklist at `docs/release-checklist.md`.
- Data-format reference at `docs/data-format.md`.
- `web/lib/format.ts` shared display helpers.
- `web/lib/constants.ts` mirroring `vera.schema` constants in TypeScript.
- `web/components/SkipLink.tsx` keyboard-a11y skip link.
- `scripts/check-schema-version.sh` pre-commit hook scaffold.
- `web/lib/brand.ts` type-safe brand-colour access.

### Added (Sep)
- Project brand identity: V-letterform mark, stacked + horizontal
  lockups (light + dark), monochrome variant, mission-patch insignia,
  three alternate concepts, and a brand guide at `docs/brand-guide.md`.
- `Logo` component for theme-aware lockup rendering.
- OpenGraph + Twitter card metadata wired to the wordmark.

## 2026-W26 (June 22 – June 28)

### Fixed
- README badge link strip — Tests and Coverage badges had empty
  `()` link targets and the Coverage badge claimed coverage with no
  measurement tooling. Coverage badge removed, Tests repointed to
  `tests/`, technology badges repointed to in-repo paths.

### Added
- `SECURITY.md` (private vulnerability disclosure policy).
- `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1, shortened).

## 2026-W22 (May 25 – May 31)

### Added
- Ruff lint policy in `pyproject.toml` and parallel CI jobs (Lint ·
  Python and Lint · Web).
- INT8 ONNX model committed at `web/api/model.onnx` so Vercel
  serverless cold-starts can load it.

### Fixed
- Five real bugs flushed by the new lint policy: missing exception
  chaining (`B904`), unused loop variable (`B007`), dead assignments
  (`F841` × 2), one-line `if` (`E701`).
- CONTRIBUTING.md repository URL placeholder.

### Removed
- `lucide-react` dependency (zero imports anywhere).

## 2026-W19 (May 4 – May 10)

### Added
- Documentation surface: `/about`, `/architecture`, `/methods` route
  pages composed on a shared docs primitives layer.

## 2026-W17 (April 20 – April 26)

### Added
- Hapke intimate-mixture synth model with closed-form IMSA roundtrip.
- SAM baseline classifier for paper ablation.
- Test-time augmentation, sample fusion, temperature fitting.
- Real INT8 ONNX quantization via `onnxruntime.quantization`.
- SWIR field in the wire protocol (`schema v1.2.0`).
- ESP32 SWIR acquisition state machine.

## 2026-W16 (April 13 – April 19)

### Added
- Calibration pipeline (dark / white / integration / temperature /
  photometric).
- Uncertainty quantification module (entropy, margin, four-state OOD).

## 2026-W15 (April 6 – April 12)

### Added
- Initial six-class mineral classifier with crystal-field synthetic
  endmembers; cross-seed accuracy 99.3 %.
- ESP32-S3 firmware with non-blocking acquisition state machine.
- FastAPI backend + Next.js mission console.
- Schema v1.0.0 → v1.1.0 → v1.2.0 across the sensor-mode evolution.
