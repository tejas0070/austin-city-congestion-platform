# Deploying for free (Hugging Face Space + Netlify)

The app runs on **SQLite + committed ML artifacts**, so there is **no database to
provision**. Total cost: $0.

- **Backend (FastAPI + ML):** a Hugging Face **Docker Space** (2 vCPU / 16 GB free
  tier), which comfortably runs the ML forecast endpoints.
- **Frontend (React + kepler.gl):** **Netlify**.

## 1. Push to `main`

Both hosts build from `main`. Commit and push your work:

```bash
git add -A
git commit -m "chore: deploy"
git push origin main
```

## 2. Backend → Hugging Face Space (free)

Deployment is automated by [`.github/workflows/deploy-hf.yml`](.github/workflows/deploy-hf.yml):
every push to `main` that touches `backend/`, `data/models/`, `data/geo/`, or the
Dockerfile mirrors a runtime-only subset of the repo to the Space, which rebuilds
automatically.

One-time setup:

1. On Hugging Face: **New Space** → SDK **Docker** → create an empty Space.
2. In this repo → **Settings → Secrets and variables → Actions**:
   - secret `HF_TOKEN` = a Hugging Face access token with **write** role
   - variable `HF_USERNAME` = your HF username/org
   - variable `HF_SPACE` = the Space name
3. Push to `main` (or run the workflow from the **Actions** tab). The API lands at
   `https://<username>-<space>.hf.space`. Confirm `…/health` returns
   `{"status":"ok"}`.

Optional: add free-tier keys (`TOMTOM_API_KEY`, `TICKETMASTER_API_KEY`,
`SOCRATA_APP_TOKEN`) in the Space's **Settings → Variables and secrets** for live
flow + events. Without them the app uses silent fallbacks.

> **Free-tier note:** the Space sleeps after idle, so the *first* visit after a nap
> takes a moment to wake. Fine for a demo. Use an uptime pinger against `/health`
> to keep it warm.

## 3. Frontend → Netlify (free)

1. Edit [`netlify.toml`](netlify.toml): set `REACT_APP_API_BASE_URL` to your HF
   Space URL from step 2 (or set it in the Netlify UI under Site → Environment).
2. Go to <https://netlify.com> → **Add new site** → **Import from Git** → pick the
   repo. Netlify reads `netlify.toml` (base `frontend/`, publish `build/`).
3. Deploy. Your site lands at `https://<name>.netlify.app` — already allowed by the
   backend's CORS (`*.netlify.app`), so no extra config is needed.

## 4. Verify

Open the Netlify URL. The kepler.gl map should paint green→red corridors within a
few seconds. If it shows the "add data" empty state, the backend URL is wrong or the
Space is still waking up (reload after a moment).

## Custom domain (optional)

For a custom frontend domain, set `ALLOWED_ORIGINS` (comma-separated) on the HF
Space, e.g. `https://traffic.example.com`.

## Self-updating model

[`.github/workflows/retrain.yml`](.github/workflows/retrain.yml) runs every 6 hours:
it collects a budget-bounded sample of real TomTom congestion, retrains, and — only
if the regression gate approves the new model — commits the improved artifacts back
to `main`. That push re-triggers the HF deploy so the API serves the fresh model.
Add the repo secret `TOMTOM_API_KEY` to enable it.
</content>
