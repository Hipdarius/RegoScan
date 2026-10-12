# Release checklist

VERA's first tagged release will be the version submitted to Jonk
Fuerscher 2027. Until then, every "polish pass" should walk this list.

## Pre-release

- [ ] `make lint` clean (Python ruff + web `next lint`)
- [ ] `make test` clean (214+ tests, 0 skipped)
- [ ] `make typecheck` clean (`tsc --noEmit`)
- [ ] `cd firmware && pio run` succeeds
- [ ] Engineering journal current — every commit since the last
      polish pass has either an entry or a deliberate "small enough
      to skip" note.
- [ ] CHANGELOG `[Unreleased]` section reflects what landed.
- [ ] `web/api/model.onnx` is committed and 2.6 MB ± 100 KB
      (Vercel deploy needs it). Run `git ls-files web/api/`.
- [ ] `runs/cnn_v2/{model.onnx,meta.json}` regenerable via
      `make train` from `data/synth_v1.csv`.

## Tag + release

- [ ] Bump `package.json` and `pyproject.toml` versions in lockstep.
- [ ] Add a real CHANGELOG section (`## [v0.1.0] - YYYY-MM-DD`).
- [ ] `git tag -a vX.Y.Z -m "VERA vX.Y.Z"` — annotated, never
      lightweight.
- [ ] `git push origin vX.Y.Z` to publish the tag.
- [ ] On GitHub: Releases → Draft → pick the tag → use the CHANGELOG
      section as the release notes.
- [ ] If submitting to Zenodo: enable the GitHub-Zenodo integration
      so the tag mints a DOI; update the README BibTeX entry to
      include the DOI once it's live.

## Post-release

- [ ] Open a fresh `[Unreleased]` section at the top of CHANGELOG.
- [ ] Bump the version number on `main` to `vX.Y.(Z+1)-dev` so the
      next commit is unambiguously post-release.
- [ ] Engineering journal entry for the release itself ("Entry N —
      vX.Y.Z tagged + submitted to ...").
