# web/lib

Shared client-side helpers for the VERA mission console.

| File | Purpose |
|---|---|
| `api.ts` | Typed wrapper around the FastAPI service. Reads `NEXT_PUBLIC_API_BASE` for the dev → prod port swap. |
| `types.ts` | TypeScript types mirroring the API's pydantic response models. Updated whenever a backend schema lands. |

The component layer in `web/components/` should never call `fetch`
directly — it goes through `api.ts` so error handling, base-URL
resolution, and envelope unwrapping live in one place.
