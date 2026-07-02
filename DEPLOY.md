# Deploying for free (Render + Netlify)

The app runs on **SQLite + committed ML artifacts**, so there is **no database to
provision**. Total cost: $0.

## 1. Push the current work

The deployable code lives on a feature branch with uncommitted changes. Commit and
push (or merge to `main`) so the hosts can build it:

```bash
git add -A
git commit -m "chore: add Render + Netlify deploy configs"
git push origin feat/prediction-confidence   # or merge to main first
```

## 2. Backend → Render (free)

1. Go to <https://render.com> → sign in with GitHub.
2. **New +** → **Blueprint** → pick `austin-city-congestion-platform`.
3. Render reads [`render.yaml`](render.yaml) and creates the `austin-traffic-api`
   web service automatically. Click **Apply**.
4. Wait for the first build (~3–5 min). Note the URL, e.g.
   `https://austin-traffic-api.onrender.com`. Confirm `…/health` returns
   `{"status":"ok"}`.

Optional: add free-tier keys (`TOMTOM_API_KEY`, `TICKETMASTER_API_KEY`) in the
service's **Environment** tab for live flow + events. Without them the app uses
silent fallbacks.

> **Free-tier note:** the service sleeps after ~15 min idle, so the *first* visit
> after a nap takes ~50s to wake. Fine for a demo/portfolio. To avoid it, upgrade
> the Render plan or use an uptime pinger against `/health`.

## 3. Frontend → Netlify (free)

1. Edit [`netlify.toml`](netlify.toml): set `REACT_APP_API_BASE_URL` to your Render
   URL from step 2 (or set it in the Netlify UI under Site → Environment).
2. Go to <https://netlify.com> → **Add new site** → **Import from Git** → pick the
   repo. Netlify reads `netlify.toml` (base `frontend/`, publish `build/`).
3. Deploy. Your site lands at `https://<name>.netlify.app` — already allowed by the
   backend's CORS.

## 4. Verify

Open the Netlify URL. The kepler.gl map should paint green→red corridors within a
few seconds. If it shows the "add data" empty state, the backend URL is wrong or the
API is still waking up (reload after ~1 min).

## Custom domain (optional)

Point CORS at a custom frontend domain by setting `ALLOWED_ORIGINS` on the Render
service (comma-separated), e.g. `https://traffic.example.com`.
