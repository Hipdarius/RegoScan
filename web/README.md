# VERA Web — Mission Console

Next.js 14 + Tailwind + Recharts + Framer Motion frontend backed by an
ONNX/FastAPI Python serverless function. Deploys to Vercel as a single
project.

## Layout

```
web/
├── app/                  # Next.js 14 app router
│   ├── layout.tsx
│   ├── page.tsx          # The mission console page
│   └── globals.css
├── components/           # React components (all 'use client')
│   ├── Hero.tsx
│   ├── ScanButton.tsx
│   ├── SpectrumChart.tsx
│   ├── ProbabilityBars.tsx
│   ├── IlmeniteGauge.tsx
│   └── MissionPanel.tsx
├── lib/
│   ├── api.ts            # Fetch helpers
│   └── types.ts          # Shared TS types matching the Python schema
├── api/                  # Vercel Python serverless (NOT typed by tsconfig)
│   ├── predict.py        # FastAPI app, ONNX inference
│   ├── requirements.txt  # Pinned: fastapi, onnxruntime, numpy, pydantic
│   └── model.onnx        # Trained 1D ResNet (committed)
├── vercel.json           # Function config + same-origin rewrites
├── tailwind.config.ts    # "Modern Space Mission" palette
├── next.config.js
├── tsconfig.json
└── package.json
```

## Local development

You need **two** processes during local dev — `next dev` and the FastAPI
backend — because `next dev` does not run the Python serverless function
itself.

```bash
# Terminal A — FastAPI backend (from repo root)
uv sync --extra serve
uv run uvicorn apps.api:app --reload --port 8000

# Terminal B — Next.js dev server (from repo root)
cd web
npm install
NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000 npm run dev
```

Then open http://localhost:3000.

In production on Vercel, **do not** set `NEXT_PUBLIC_API_BASE` — the
client uses same-origin requests and Vercel's rewrites point them at
`web/api/predict.py`.

## Deploying to Vercel — step by step

### 1. Re-export the ONNX model (only if you re-trained)

```bash
# from repo root
uv run python -m vera.train --model cnn \
    --data data/synth_v2.csv \
    --out runs/cnn_v2 \
    --epochs 60 \
    --batch-size 128 \
    --lr 2e-3 \
    --early-stopping-patience 10 \
    --seed 0

uv run python -m vera.quantize \
    --run runs/cnn_v2 \
    --out runs/cnn_v2/model.tflite

cp runs/cnn_v2/model.onnx web/api/model.onnx
```

### 2. Push to GitHub

> :warning: This step pushes commits to a remote. Confirm the branch and
> remote are what you intend before running.

```bash
# from repo root
git checkout -b feature/web-mission-console
git add web apps/api.py src/vera/inference.py pyproject.toml \
        runs/cnn_v2/model.onnx scripts/download_relab.py
git commit -m "feat(web): mission console UI + FastAPI/ONNX backend"
git push -u origin feature/web-mission-console
```

If you want to push directly to `main` (and you have permission):

```bash
git checkout main
git merge feature/web-mission-console
git push origin main
```

### 3. Link the project to Vercel

You only need to do this once per repo.

```bash
# Install the Vercel CLI globally
npm install -g vercel

# From the repo root, link the web/ subdirectory
cd web
vercel link
# When prompted:
#   "Set up and deploy?" → y
#   "Which scope?"       → your personal account or team
#   "Link to existing project?" → N (first time)
#   "Project name?"      → vera
#   "In which directory is your code located?" → ./  (you're already in web/)
```

This creates `web/.vercel/project.json` (already in `.gitignore`).

### 4. Deploy a preview

```bash
# from web/
vercel
```

Vercel will:

1. Run `npm install` and `next build`
2. Build the `api/predict.py` Python function with the deps in
   `api/requirements.txt`
3. Bundle `api/model.onnx` into the function (configured via
   `vercel.json` `includeFiles`)
4. Print a preview URL (e.g. `https://vera-xxxx.vercel.app`)

Open that URL and click **Initiate Scan** to verify the production
inference path works.

### 5. Promote to production

Once the preview looks good:

```bash
# from web/
vercel --prod
```

This redeploys the same artefacts at the production domain
(`https://vera.vercel.app` or your custom domain).

### 6. (Optional) Connect to GitHub for auto-deploys

In the Vercel dashboard:

1. Project Settings → Git → **Connect to Git Repository**
2. Pick the GitHub repo and the `main` branch
3. Set the **Root Directory** to `web/`
4. Save

Every push to `main` then ships a production build automatically and
every PR gets its own preview URL.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `model.onnx missing at /var/task/api/model.onnx` | Re-run `cp runs/cnn_v2/model.onnx web/api/model.onnx`, commit, redeploy. |
| CORS errors in dev | Set `NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000` (the FastAPI app already serves `Access-Control-Allow-Origin: *`). |
| `next build` fails on a Tailwind class | Check `tailwind.config.ts` — only color utilities support `/<opacity>` modifiers, not custom shadows. |
| Python function exceeds 50 MB | The default 1D ResNet ONNX is 2.7 MB — well under the limit. If you swap in a much larger model, prune unused deps in `api/requirements.txt` (e.g. drop `pydantic` for `dataclasses`). |

## See also

- [docs/brand-guide.md](../docs/brand-guide.md) — palette, typography, sizing.
- [web/UI_STANDARDS.md](./UI_STANDARDS.md) — Tailwind class conventions.
