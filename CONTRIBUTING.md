# Contributing to VERA

Thank you for your interest in contributing to the VERA lunar mineral classification probe project.

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | ML pipeline, API server, scripts |
| [uv](https://docs.astral.sh/uv/) | latest | Python package and project management |
| Node.js | 20+ | Web dashboard (TypeScript) |
| [PlatformIO](https://platformio.org/) | latest | ESP32-S3 firmware builds |

## Getting Started

```bash
# Clone the repo
git clone https://github.com/Hipdarius/VERA.git
cd VERA

# Install Python dependencies (includes dev extras)
uv sync --all-extras

# Install web dashboard dependencies
cd web && npm install && cd ..

# Run the test suite to verify everything works
make test
```

## Code Style

### Python

We use **ruff** for both linting and formatting. Check before committing:

```bash
make lint
```

Ruff configuration lives in `pyproject.toml`. Do not disable rules without discussion in the PR.

### TypeScript (web/)

TypeScript strict mode is enabled. The CI runs `tsc --noEmit` to catch type errors:

```bash
cd web && npx tsc --noEmit
```

### Firmware (C++)

- Target: ESP32-S3 via PlatformIO.
- All code lives in the `vera` namespace.
- No heap allocations in the main loop -- use stack or `constexpr` sizing.
- Use `constexpr` for all compile-time constants (never `#define`).
- Pin assignments and magic numbers belong in `Config.h`.

## Testing

All tests must pass before a PR can be merged:

```bash
make test
```

Add tests for any new functionality. Tests live in the `tests/` directory and mirror the `src/` layout — currently 214 across 15 modules.

## Branch Naming

Use a descriptive prefix:

- `feature/` -- new functionality (e.g. `feature/as7265x-driver`)
- `fix/` -- bug fixes (e.g. `fix/spectral-clipping`)
- `docs/` -- documentation only (e.g. `docs/calibration-guide`)

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add AS7265x triad sensor I2C driver
fix: correct wavelength calibration offset for C12880MA
docs: update wiring diagram for rev2 PCB
refactor: extract LED sequencing into Illumination module
```

The type must be one of: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `ci`.

## Schema contract

The spectral schema (`src/vera/schema.py`) defines the canonical column layout used across the entire pipeline -- from firmware JSON frames through training to inference.

- **Do not modify schema.py without bumping its version.**
- Any column rename or reorder is a breaking change and requires a migration note in the PR description.
- Column names use the `spec_000..spec_287` convention (see the module docstring in `src/vera/schema.py` for rationale).

## Pull Request Checklist

- [ ] `make test` passes locally
- [ ] `make lint` reports no issues
- [ ] New code has tests
- [ ] Commit messages follow conventional commits
- [ ] Schema version bumped if `schema.py` changed
- [ ] Firmware builds with `make firmware-build` if firmware changed
