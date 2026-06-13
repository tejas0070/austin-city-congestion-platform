# Austin Traffic Intelligence Platform

React 18 + kepler.gl frontend with a FastAPI backend. Visualizes real-time Austin traffic, events, and weather on an interactive Mapbox map.

## Stack

- **Frontend:** React 18, Redux, @kepler.gl/components v3, Mapbox GL JS, Tailwind CSS, Axios
- **Backend:** FastAPI, SQLAlchemy 2.0, PostgreSQL, Alembic, httpx
- **Data:** TxDOT (traffic + incidents), Open-Meteo (weather, free, no key), Ticketmaster (events), Austin 311 (construction)
- **Build:** CRACO (CRA 5 + webpack polyfills for kepler.gl)

## Project Structure

```text
frontend/              React 18 + kepler.gl app
  src/
    App.js             Root component
    index.js           React 18 entry point
    store.js           Redux store
    components/        MapContainer, Sidebar, EventCard, LayerToggle, TrafficLegend, LoadingOverlay
    hooks/             useTrafficData, useEvents, useWeather
    services/          api.js, trafficService, eventsService, weatherService
    constants/         austinBounds.js
    utils/             colorScales.js, geoHelpers.js
  public/index.html
  package.json         React 18, kepler.gl v3, CRACO build
  craco.config.js      Webpack polyfills for kepler.gl
  tailwind.config.js
backend/               FastAPI backend
  main.py              FastAPI entry point with CORS
  api/routes/          traffic.py, events.py, weather.py
  db/                  database.py, models.py, queries.py
  services/            txdot_service, weather_service, events_service, construction_service
  utils/               cache.py, geojson_builder.py
tests/                 pytest tests (backend)
alembic/               DB migrations
```

## Environment Variables

**Backend (.env at project root):**

```text
DATABASE_URL=postgresql://user:password@localhost:5432/austin_traffic
TICKETMASTER_API_KEY=
SOCRATA_APP_TOKEN=
```

**Frontend (frontend/.env):**

```text
REACT_APP_MAPBOX_TOKEN=your_mapbox_token_here
REACT_APP_API_BASE_URL=http://localhost:8000
```

## Running locally

The map is fed entirely by the backend API. **kepler.gl shows its "add data"
empty state only when no data reached it — that means the backend isn't running
or isn't reachable on :8000.** Start the backend first, then the frontend.

**Easiest (Windows PowerShell)** — two convenience scripts that always run from
the right directory:

```powershell
# terminal 1
.\run-backend.ps1
# terminal 2
.\run-frontend.ps1
```

**Manual** — note two Windows gotchas:

- Run uvicorn **from the project root** (`austin-city-congestion-platform`, the
  folder that contains `backend/`). Running it from the parent folder causes
  `ModuleNotFoundError: No module named 'backend'`.
- **Windows PowerShell 5.1 does not support `&&`.** Use `;` or separate lines.

```powershell
# terminal 1 — backend (cd into the project root first)
cd C:\Users\jaded\OneDrive\Desktop\austin-traffic-intelligence\austin-city-congestion-platform
python -m uvicorn backend.main:app --reload

# terminal 2 — frontend (use ';' not '&&' in PowerShell)
cd C:\Users\jaded\OneDrive\Desktop\austin-traffic-intelligence\austin-city-congestion-platform\frontend ; npm start
```

The ML model + road network artifacts are committed, so the app runs out of the
box. Only re-run the pipeline below if you change features or want fresh data.

## Commands

| Task | Command |
| ---- | ------- |
| Start backend | `uvicorn backend.main:app --reload` |
| Start frontend | `cd frontend && npm start` |
| Fetch Austin road network (once) | `python scripts/fetch_austin_network.py` |
| Generate ML training data | `python scripts/generate_training_data.py` |
| Train congestion model | `python scripts/train_model.py` |
| Run DB migrations | `alembic upgrade head` |
| Run Python tests | `pytest --ignore=tests/test_time_steps.py` |
| Run JS tests | `cd frontend && npm test` |
| Build frontend | `cd frontend && npm run build` |

## Map layers (kepler.gl)

Loaded in `frontend/src/components/MapContainer.jsx`, toggled from the sidebar:

| Layer | Source endpoint | Geometry | Colour / size |
| ----- | --------------- | -------- | ------------- |
| Live Traffic | `/api/traffic/corridors` | city-wide segment lines | green/yellow/red by `congestion_index` |
| Predicted +2h (ML) | `/api/traffic/corridors/predicted` | city-wide segment lines | green/yellow/red by predicted congestion |
| Events | `/api/events/geojson` | venue circles | sized by `expected_attendance`, coloured by category |
| Incidents | `/api/traffic/incidents` | icons | coloured by severity (1–4) |

## Congestion ML model (city-wide)

- **Coverage:** every motorway/trunk/primary/secondary segment in
  `data/geo/austin_network.geojson` (~3,800 segments, fetched from OSM/Overpass).
- **Model:** `HistGradientBoostingRegressor` → `data/models/congestion_model.pkl`.
- **Features (segment-agnostic, so it generalizes to any road):** road class,
  distance to downtown, hour, day-of-week, weekend, month, weather
  (code/temp/precip), and distance/time-weighted **nearby event attendance**.
- **Shared feature code:** `backend/services/congestion_features.py` is the single
  source of truth used by both the data generator and the live predictor.
- **Current training data is synthetic** (`scripts/generate_training_data.py`),
  shaped like Austin's rush-hour curves. See "Swapping in real data" below.

### Swapping in real data

The GeoJSON contract never changes, so real data drops in without touching the
frontend:

1. **Real congestion history** → produce a CSV at
   `data/training/congestion_history.csv` with the same feature + `congestion_pct`
   columns, then re-run `python scripts/train_model.py`. No code changes.
2. **Real live feed** → replace `build_live_segments()` in
   `backend/services/segments_service.py` with the real per-segment source keyed
   on `segment_id`. The `/api/traffic/corridors` response shape stays identical.
3. **More/updated roads** → re-run `python scripts/fetch_austin_network.py`.

## Data Sources

| Source | Endpoint | Key Required |
| ------ | -------- | ------------ |
| TxDOT Traffic | api.travelmapping.txdot.gov | No (basic) |
| Open-Meteo | api.open-meteo.com | No |
| Ticketmaster | app.ticketmaster.com | Yes (free tier) |
| Austin 311 | data.austintexas.gov/resource/qyfh-gwei | No |

## Deployment

- **Frontend:** Netlify — `cd frontend && npm run build`, deploy `build/`
- **Backend:** Render or Railway — `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- **Database:** Supabase free tier (set `DATABASE_URL` in environment)

## Conventions

- All external API calls go through services/ — never inside route handlers
- All API calls use httpx with `timeout=10.0` and silent fallback on error
- In-memory cache (utils/cache.py) prevents hammering free-tier APIs
- kepler.gl layers are loaded via `dispatch(addDataToMap(...))` — never manipulate kepler state directly
