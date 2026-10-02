# web/

Confirm UI. Plain HTML/JS, no build step. Phase 5 of `roadmap.md`.

## Running locally (against the test DB)

```bash
# terminal 1 — API, pointed at TEST_DATABASE_URL
DATABASE_URL="$TEST_DATABASE_URL" ALLOWED_ORIGINS=http://localhost:5500 \
  .venv/bin/uvicorn traininglogs.api.app:app --reload

# terminal 2 — serve this directory
cd web && python3 -m http.server 5500
```

Open `http://localhost:5500`, set the API key (matches `.env`'s `API_KEY`) and API base URL
(`http://localhost:8000` by default) — both are saved to `localStorage` so they persist across
reloads. Paste session notes, hit Extract.

`sample_inputs.md` has six ready-to-paste samples spanning different levels of detail and
structure (terse one-liner, casual paragraph, numbered list, headered markdown, bare minimum)
for exercising the UI without composing test input by hand. Each Extract click is a real paid
call — see the file for details.
