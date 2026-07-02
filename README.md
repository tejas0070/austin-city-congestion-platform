# Austin Traffic Intelligence Platform

Real-time Austin, TX traffic on an interactive kepler.gl map, plus a city-wide
**machine-learning congestion forecast** with a calibrated confidence signal that
**improves itself over time** from real sensor data.

## Stack

| Layer    | Technology                                                |
| -------- | --------------------------------------------------------- |
| Frontend | React 18, Redux, kepler.gl v3, framer-motion, Tailwind    |
| Backend  | FastAPI, SQLAlchemy 2.0, PostgreSQL, httpx                |
| ML       | scikit-learn `HistGradientBoostingRegressor` + quantiles  |
| Map      | MapLibre GL JS + Carto Dark Matter (no token needed)      |
| Build    | CRACO (CRA 5 + webpack polyfills)                         |

## Quick Start

### Prerequisites

- Python 3.11+, Node 18+, PostgreSQL (local or Supabase)

### Backend

```bash
cd austin-city-congestion-platform
python -m venv .venv && .venv\Scripts\activate     # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in DATABASE_URL and any API keys
alembic upgrade head
uvicorn backend.main:app --reload
```

The trained model + road-network artifacts are committed, so the API runs out of
the box. On Windows you can use the convenience scripts `./run-backend.ps1` and
`./run-frontend.ps1`.

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
  class, distance to downtown, hour, day, weekend, month, weather, nearby-event
  attendance, and a data-driven **`seasonal_level`** — each segment's real typical
  congestion for that hour-of-week). Trained on **real** Austin data (see below).
- **Confidence:** a tight **central 50% prediction interval** (q25/q75 quantile
  models) mapped to a 0–100 score via fixed, interpretable width anchors
  (`backend/etl/confidence.py`). The separate **accuracy badge** is the wide 80%
  interval's empirical coverage (~0.90).
- **UI:** the sidebar **Forecast Model** panel shows the accuracy badge plus
  day-scale and week-scale Confidence (blue) and Congestion (green/yellow/red)
  readouts. Per-segment confidence appears in the Predicted +2h map tooltip.
- **Endpoints:** `/api/traffic/corridors/predicted`, `/corridors/day?date=…`,
  `/corridors/week?start=…`, `/model/info`.

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
python scripts/train_model.py                # retrains model + quantiles
python scripts/confidence_report.py          # with/without-seasonal before/after
```

## Self-updating (autonomous)

The model improves on its own — collect real data, retrain, hot-reload, refresh UI
— all hands-off and **always within the free API budget**.

1. Get a free **TomTom** key at <https://developer.tomtom.com> and add
   `TOMTOM_API_KEY=…` to `.env`.
2. Register the scheduled task (Windows):

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\register_self_update.ps1
   ```

What happens every 3 hours, automatically:

- **Collect** real TomTom congestion for a rotating sample of segments. A hard
  daily-budget guard (`backend/services/tomtom_budget.py`, default 2,400/day)
  makes exceeding the free tier impossible; once spent, the run skips retraining.
- **Retrain** fast (the static Bluetooth history is cached, so no re-pull).
- **Hot-reload:** the running API detects the new model files and serves them with
  no restart (`backend/services/ml_model.py`).
- **Live UI:** the map (2-min poll) and the Forecast panel (3-min silent poll)
  refresh themselves — no page reload.

Run one cycle manually: `python scripts/auto_update.py`.
Stop the schedule: `Unregister-ScheduledTask -TaskName "AustinTraffic-SelfUpdate" -Confirm:$false`.

## Environment Variables

**Backend (`.env` at project root):**

| Variable               | Required | Description                            |
| ---------------------- | -------- | -------------------------------------- |
| `DATABASE_URL`         | Yes      | PostgreSQL connection string           |
| `TOMTOM_API_KEY`       | No       | Real-time flow collection (free tier)  |
| `TICKETMASTER_API_KEY` | No       | Events (free tier)                     |
| `SOCRATA_APP_TOKEN`    | No       | Raises Austin open-data rate limit     |
| `TOMTOM_DAILY_LIMIT`   | No       | Hard request cap/day (default 2,400)   |

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

- **Frontend:** `npm run build` in `frontend/`, deploy `build/` to Netlify
- **Backend:** Render/Railway — `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- **Database:** Supabase free tier — set `DATABASE_URL`

## Tests

```bash
pytest --ignore=tests/test_time_steps.py     # backend
cd frontend && npm test                       # frontend
```

## Project Layout

See [CLAUDE.md](CLAUDE.md) for the full module map, ML details, and conventions.
Model details are in [docs/model_card.md](docs/model_card.md).
