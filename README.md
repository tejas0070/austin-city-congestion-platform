# Austin Traffic Intelligence Platform

Real-time Austin, TX traffic rendered on an interactive kepler.gl map, plus a
city-wide **machine-learning congestion forecast** with a calibrated confidence
signal. The model **retrains itself every 6 hours** from real Austin sensor data
and hot-reloads with no downtime.

**Live demo:** <https://subtle-sprite-d869b3.netlify.app> &nbsp;·&nbsp; **API:** <https://vtejas00-austin-traffic-api.hf.space/health>

> Runs on a $0 stack — SQLite + committed model artifacts, free-tier hosting, and
> a GitHub Actions retrain loop that stays inside every free API budget.

## What it does

- **Live map** — every major Austin corridor colored green → yellow → red by a
  real-time congestion index.
- **ML forecast** — predicted congestion +2h, a whole-day curve, and a Mon–Sun
  outlook for the entire road network, each with a per-segment confidence score.
- **Calibrated confidence** — a conformal-calibrated prediction interval mapped to
  a 0–100 score, capped by how much real history backs each road, so a fallback
  road can never out-confidence a genuinely measured one.
- **Context overlays** — weather, federal holidays, and nearby-event crowds are
  layered on top of the learned baseline as transparent, interpretable multipliers.
- **Self-updating** — a scheduled job collects fresh real-world data, retrains, and
  redeploys automatically; a regression gate blocks any model that got worse.

## Stack

| Layer    | Technology                                                     |
| -------- | -------------------------------------------------------------- |
| Frontend | React 18, Redux, kepler.gl v3, framer-motion, Tailwind         |
| Backend  | FastAPI, SQLAlchemy 2.0, httpx (SQLite by default)             |
| ML       | scikit-learn `HistGradientBoostingRegressor` + quantiles       |
| Map      | MapLibre GL JS + Carto Dark Matter (no token needed)           |
| Build    | CRACO (CRA 5 + webpack polyfills)                              |
| Hosting  | Netlify (frontend) + Hugging Face Space (API) + GitHub Actions |

## Quick Start

### Prerequisites

- Python 3.11+ and Node 18+. **No database to install** — the backend uses SQLite
  out of the box (set `DATABASE_URL` only if you want Postgres).

### Backend

```bash
cd austin-city-congestion-platform
python -m venv .venv && .venv\Scripts\activate     # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                                # optional: add free-tier API keys
uvicorn backend.main:app --reload
```

Tables are created automatically on startup and the trained model + road-network
artifacts are committed, so the API serves out of the box — no migrations, no
seeding. On Windows you can use `./run-backend.ps1` and `./run-frontend.ps1`.

### Frontend

```bash
cd frontend
npm install
npm start
```

App opens at <http://localhost:3000>, API at <http://localhost:8000>. Start the
backend first — kepler.gl shows its "add data" empty state if `:8000` isn't up.

## Forecast model & confidence

The platform predicts city-wide congestion for every road segment and reports how
sure it is.

- **Model:** `HistGradientBoostingRegressor` over segment-agnostic features (road
  class, distance to downtown, hour, day, weekend, month, and a data-driven
  **`seasonal_level`** — each segment's real typical congestion for that
  hour-of-week). Trained on **real** Austin data (see below). Weather, holidays,
  and events are applied as transparent overlays on top of the learned baseline
  rather than as model features, because the real speed data carries no reliable
  weather/event signal.
- **Confidence:** an expected-value prediction interval, split-conformal calibrated
  on held-out bucket means, mapped to a 0–100 score
  (`backend/etl/confidence.py`). A **density cap** stops a road from reading more
  confident than the history behind it, and per-corridor modulation makes
  confidence genuinely fall at rush hour and on volatile roads.
- **Honest metrics:** evaluation is leak-free (`seasonal_level` is rebuilt per fold,
  never over the whole set before the split). `python scripts/evaluate_model.py`
  writes the full scorecard to `model_meta.json` and `docs/model_evaluation.md`.
- **UI:** the sidebar **Forecast Model** panel shows the accuracy badge plus
  day-scale and week-scale confidence and congestion readouts. Per-segment
  confidence appears in the Predicted +2h map tooltip.
- **Endpoints:** `/api/traffic/corridors/predicted`, `/corridors/day?date=…`,
  `/corridors/week?start=…`, `/model/info`.

Full ML details are in [CLAUDE.md](CLAUDE.md) and [docs/model_card.md](docs/model_card.md).

## Results

Forecasts the **typical congestion for each corridor by hour-of-week**, evaluated
on a **leak-free** hold-out set of 907 corridor-hours (real Austin sensor data,
~382K readings). Full write-up: **[docs/RESULTS.md](docs/RESULTS.md)**.

| Metric | Result |
| ------ | ------ |
| Typical-congestion **R²** | **0.74** |
| **MAE** (0–100 scale) | **2.7** |
| Traffic-tier (green/yellow/red) accuracy | **85%** |
| Within ±10 points | **95%** |
| 80% prediction intervals → empirical coverage | **~80%** (calibrated) |

**What makes it trustworthy:** evaluation is leak-free (`seasonal_level` rebuilt
per fold, so held-out targets never leak), a **regression gate** blocks any retrain
that gets worse, and confidence is a **conformal-calibrated** interval capped by how
much real history backs each road. Individual 15-min readings are ~70% irreducible
noise (R² 0.26) — so the system forecasts, and reports on, the level where the
signal is genuinely strong. Reproduce with `python scripts/evaluate_model.py`.

## Real training data

The model trains on real City of Austin + TomTom data (no synthetic shaping).
Coverage grows as more data is collected.

| Source | Script | Notes |
| ------ | ------ | ----- |
| Bluetooth travel sensors (`v7zg-5jg9`) | `scripts/build_real_training_data.py` | corridor speed history |
| Radar traffic counts (`i626-g7ub`) | `scripts/build_radar_training_data.py` (+ `geocode_radar_detectors.py`) | dense intersection readings; geocoded via OSM Overpass |
| TomTom Traffic Flow (free tier) | `scripts/collect_tomtom_observations.py` → `build_tomtom_training_data.py` | real per-segment current congestion |

Rebuild + retrain manually:

```bash
python scripts/build_real_training_data.py   # pulls Bluetooth, caches, merges all sources
python scripts/train_model.py                # retrains model + quantiles (regression-gated)
python scripts/evaluate_model.py             # writes the honest, leak-free scorecard
```

## Self-updating (autonomous)

The deployed model improves on its own — collect real data, retrain, redeploy,
refresh UI — all hands-off and **always within the free API budget**.

**In production (GitHub Actions):** [`.github/workflows/retrain.yml`](.github/workflows/retrain.yml)
runs every 6 hours and:

- **Collects** real TomTom congestion for a rotating sample of segments. A hard
  daily-budget guard (`backend/services/tomtom_budget.py`, default 2,400/day) makes
  exceeding the free tier impossible; once spent, the run skips retraining.
- **Retrains** fast (static Bluetooth history is cached, so no re-pull) and runs the
  **regression gate** — a model with materially worse R²/MAE is rejected, so the
  last good model keeps serving.
- **Commits** the improved artifacts back to `main`, which triggers an automatic
  redeploy of the API with the fresh model.

Add the repo secret `TOMTOM_API_KEY` (Settings → Secrets and variables → Actions)
to enable it; `SOCRATA_APP_TOKEN` and `TICKETMASTER_API_KEY` are optional.

Run one cycle locally: `python scripts/auto_update.py`. A Windows Task Scheduler
equivalent is available via `scripts/register_self_update.ps1`.

## Environment Variables

**Backend (`.env` at project root):**

| Variable               | Required | Description                                     |
| ---------------------- | -------- | ----------------------------------------------- |
| `DATABASE_URL`         | No       | Postgres connection string (defaults to SQLite) |
| `TOMTOM_API_KEY`       | No       | Real-time flow collection (free tier)           |
| `TICKETMASTER_API_KEY` | No       | Events (free tier)                              |
| `SOCRATA_APP_TOKEN`    | No       | Raises Austin open-data rate limit              |
| `TOMTOM_DAILY_LIMIT`   | No       | Hard request cap/day (default 2,400)            |
| `ALLOWED_ORIGINS`      | No       | Extra CORS origins (custom domains)             |

**Frontend (`frontend/.env`):** `REACT_APP_API_BASE_URL` (defaults to
<http://localhost:8000>). No Mapbox token required — the map uses MapLibre + Carto.

## Features

- Live traffic corridors colored green → yellow → red by congestion
- ML Predicted +2h, whole-day, and Mon–Sun forecasts with confidence
- Collapsible animated sidebar (Map Layers / Forecast Model / Events)
- Incident markers, venue/event pins, events calendar, weather
- Map bounds locked to the Austin metro area

## Data Sources

| Source | Use | Key |
| ------ | --- | --- |
| City of Austin (Socrata) | Bluetooth + radar congestion history | No |
| TomTom Traffic Flow | real-time per-segment congestion | Free tier |
| Open-Meteo | weather (current + historical archive) | No |
| Ticketmaster | events | Free tier |
| OSM Overpass / Nominatim | road network + detector geocoding | No |

## Deployment

Free-tier, $0 total — see [DEPLOY.md](DEPLOY.md) for the step-by-step guide.

- **Frontend → Netlify:** base `frontend/`, build `npm run build`, publish `build/`
  (config in [`netlify.toml`](netlify.toml)); set `REACT_APP_API_BASE_URL` to the
  API Space URL. `*.netlify.app` is already allowed by the backend's CORS.
- **Backend → Hugging Face Space:** a Docker Space (2 vCPU) auto-deployed from
  `main` by [`.github/workflows/deploy-hf.yml`](.github/workflows/deploy-hf.yml).
  HF's free tier comfortably runs the ML forecast endpoints.
- **Database:** none required — SQLite + committed artifacts. Set `DATABASE_URL`
  only to point at Postgres.

## Tests

```bash
pytest --ignore=tests/test_time_steps.py     # backend
cd frontend && npm test                       # frontend
```

## Project Layout

See [CLAUDE.md](CLAUDE.md) for the full module map, ML details, and conventions.
</content>
</invoke>
