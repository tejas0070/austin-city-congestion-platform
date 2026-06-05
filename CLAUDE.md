# Project

Austin Traffic Intelligence Platform — Collects live Austin traffic, weather, event, and construction data; stores it in PostgreSQL; runs ML congestion predictions; and exposes a Power BI–ready analytics API and interactive Leaflet map.

## Intended Audience / Output

* **Power BI dashboards** — five tabs: Executive Overview, Traffic Hotspots, Weather Impact, Event Impact, Predictive Forecast
* **Interactive web map** — served at `localhost:8000`, Leaflet.js, real-time congestion markers
* **REST API** — consumed by Power BI (Web connector or DirectQuery) and the frontend map

## Stack

* Python 3.11
* FastAPI + Uvicorn
* PostgreSQL 15 + PostGIS (via Docker)
* SQLAlchemy + GeoAlchemy2 + Alembic
* Pandas, NumPy, Scikit-learn (RandomForest), Joblib
* httpx + tenacity (async ETL fetchers)
* Leaflet.js (frontend map)
* Power BI Desktop (dashboard authoring)
* Docker + Docker Compose
* Deployed locally with Docker (GCP deployment planned)

## Structure

* `etl/` — async ETL fetchers (TomTom, OpenWeatherMap, Ticketmaster, Austin 311/construction), transform, and DB loader
* `etl/fetchers/` — one file per data source; `pipeline.py` runs all concurrently
* `backend/app/` — FastAPI app, SQLAlchemy models, database setup
* `backend/routes/` — API routers: corridors, predictions, map_data, geo, analytics
* `backend/services/` — data_service (DB queries), ml_service (inference wrapper)
* `backend/static/` — Leaflet.js map (`index.html`)
* `ml/` — `train.py` (offline), `predict.py` (inference), `models/` (joblib artifacts)
* `dashboard/` — Power BI `.pbix` files and exported visuals
* `data/raw/` — CSV snapshots from ETL fetchers
* `data/processed/` — `merged_features.csv` after transform
* `scripts/` — `setup.sh` (one-shot bootstrap for new contributors)
* `tests/` — pytest unit and integration tests
* `docs/` — architecture notes, `ml_pipeline.md`, Power BI connection guide

## Data Sources

| Source | What it provides | Fetcher file |
| --- | --- | --- |
| TomTom Traffic Flow API | Speed, free-flow speed, congestion index per corridor | `etl/fetchers/traffic.py` |
| OpenWeatherMap Current | Temp, rain, wind, humidity, weather condition | `etl/fetchers/weather.py` |
| Ticketmaster Discovery | Austin events in 48-hr window with venue coords | `etl/fetchers/events.py` |
| Austin 311 / TxDOT | Road construction and lane closures | `etl/fetchers/construction.py` *(to build)* |
| `holidays` Python pkg | US federal + Texas holidays | added in `etl/transform.py` |

## Monitored Corridors

I-35_Downtown, Mopac_Expressway_Downtown, US-183_North, Loop-360_West, Congress_Ave_Downtown

## Key DB Tables

| Table | Purpose |
| --- | --- |
| `merged_features` | One row per (timestamp, corridor) — primary analytics table |
| `cached_predictions` | Pre-computed ML results written each ETL cycle |
| `road_segments` | PostGIS LINESTRING geometries per corridor |
| `traffic_observations` | Raw speed readings linked to road segments |
| `weather_snapshots` | Weather readings with PostGIS POINT geometry |
| `events` | Ticketmaster events with venue geometry and subtype tag |
| `road_closures` | Construction / lane closure records *(to build)* |

## API Routers

| Prefix | File | Purpose |
| --- | --- | --- |
| `/api/corridors` | `routes/corridors.py` | Latest + history per corridor |
| `/api/predictions` | `routes/predictions.py` | Live ML prediction per corridor |
| `/api/map` | `routes/map_data.py` | All corridors + cached predictions (60s cache) |
| `/api/geo` | `routes/geo.py` | PostGIS spatial queries |
| `/api/analytics` | `routes/analytics.py` | Aggregated flat data for Power BI *(to build)* |

## Power BI Dashboard Tabs

1. **Executive Overview** — avg speed, congestion index, top corridors, daily trend
2. **Traffic Hotspot Analysis** — corridor map, bottleneck ranking, construction overlays
3. **Weather Impact** — rain/temp/wind vs avg congestion, storm impact
4. **Event Impact** — before/during/after congestion per event type (Austin FC, UT football, ACL, SXSW, concerts)
5. **Predictive Forecast** — next 6-hr congestion forecast per corridor, confidence bands

Power BI connects via **Web connector** to `/api/analytics/*` endpoints. Each analytics endpoint returns flat tabular JSON (list of objects with scalar values only — no nested geometry).

## Event Subtypes

Events fetched from Ticketmaster are classified into subtypes for the Event Impact dashboard:

* `austin_fc` — Q2 Stadium events tagged Austin FC
* `ut_football` — DKR-Texas Memorial Stadium football games
* `concert` — Music segment events
* `festival` — ACL, SXSW, and multi-day festivals
* `sports_other` — Other Sports segment events
* `other` — everything else

## ML Model

* Algorithm: `RandomForestRegressor` (200 trees, max_depth=10)
* Target: `congestion_index` (0.0 free-flow → 1.0 standstill)
* Features: speed, free-flow speed, 6 weather fields, nearby event count, hour, day, is_weekend, is_holiday, weather impact level
* Confidence: std deviation across individual tree predictions (expose as `confidence_low` / `confidence_high`)
* Trained offline via `python ml/train.py` after ETL has populated enough history
* Artifacts: `ml/models/congestion_rf.joblib`, `ml/models/impact_encoder.joblib`
* Future forecasts: `GET /api/analytics/forecast?corridor=...&hours_ahead=6` synthesizes future feature vectors

## Commands

* Dev server: `uvicorn backend.app.main:app --reload`
* Docker: `docker-compose up --build`
* Bootstrap (first time): `bash scripts/setup.sh`
* Train ML model: `python ml/train.py`
* Run ETL manually: `python etl/run_all_etl.py`
* Test: `pytest`
* Lint: `flake8 .`

## Verification

After every change, run in this order:

1. `python -m py_compile backend/**/*.py` — fix syntax/type errors
2. `pytest` — fix failing tests
3. `flake8 .` — fix lint errors

## Conventions

* Use FastAPI routers for all API endpoints
* Analytics endpoints must return **flat list-of-dicts** (no nested objects, no geometry) — Power BI requirement
* Store configuration in `.env` files — never hardcode keys
* Use snake_case for Python files and database columns
* Keep ETL, ML, backend, and dashboard logic in separate directories
* ETL fetchers are async (`httpx.AsyncClient`); one file per data source
* Spatial queries use `ST_DWithin` on `::geography` cast (meters, not degrees)
* In-process cache on `/api/map/corridors` has a 60s TTL (`_MAP_CACHE` dict in `map_data.py`)
* ML predictions are pre-computed during ETL and stored in `cached_predictions` — never run inference in the map hot path

## Don’t

* Don’t hardcode API keys — use environment variables
* Don’t mix dashboard logic into backend services
* Don’t train models inside API routes — use `ml/train.py` offline
* Don’t return geometry objects from analytics endpoints — Power BI can’t deserialize WKB/GeoJSON directly
* Don’t add raw event rows or raw weather rows to analytics endpoints — aggregate first
