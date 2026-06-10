# Project

Austin Traffic Intelligence Platform — Collects live Austin traffic, weather, event, and construction data; stores it in PostgreSQL; runs ML congestion predictions; and serves an interactive Streamlit app with a Folium map. Deployable to Streamlit Community Cloud in minutes.

## Intended Audience / Output

* **Streamlit app** — single-page layout, map takes 70% of screen, sidebar holds all controls and stats
* **Three tabs:** Live Map (default) · Event Impact · Weather Analysis
* **Public URL** on Streamlit Community Cloud for portfolio / resume
* **FastAPI backend** — retained for API-only consumers (Power BI, external tools)

## App Layout

```
+--sidebar (30%)--+--map (70%)--+
| Time slider     |             |
| Day selector    |  Folium map |
| Event toggles   |  + layers   |
| Weather drop    |             |
+-----------------|             |
| City avg speed  |             |
| Congestion idx  |             |
| Top 3 corridors |             |
| Delay severity  |             |
| Weather impact  |             |
+-----------------+-------------+
```

### Sidebar Controls

* Time slider — 12 AM to 11 PM in 30-minute increments
* Day of week selector
* Event toggles — Austin FC, UT Football, SXSW, ACL, Downtown events
* Weather dropdown — Clear, Rain, Heavy Rain, Storm

### Map Layers (all toggleable)

* Congestion Heatmap — green→red gradient, updates with time slider
* Predicted Congestion — ML output per road segment
* Event Markers — venue pins with attendance + congestion impact on hover
* Construction Zones — orange markers from Austin 311
* Hotspot Circles — five highest-risk zones with delay estimates

## Stack

* Python 3.11
* Streamlit — app framework
* Folium + streamlit-folium — interactive map
* Pandas, NumPy — data handling
* Scikit-learn (RandomForest) + Joblib — ML predictions
* GeoJSON — road network and zone geometry
* PostgreSQL 15 + PostGIS (Docker, local) / Supabase (deployed)
* SQLAlchemy + GeoAlchemy2 + Alembic
* httpx + tenacity — async ETL fetchers
* FastAPI + Uvicorn — retained backend API
* CartoDB Dark Matter — base map tiles
* Docker + Docker Compose

## Structure

```
streamlit_app.py          # Entry point — sidebar, tabs, layout
pages/
  live_map.py             # Tab 1: Folium map with all layers
  event_impact.py         # Tab 2: bar charts, before/during congestion
  weather_analysis.py     # Tab 3: speed vs rainfall line charts
components/
  map_builder.py          # Folium map + layer construction
  sidebar.py              # Controls and stat widgets
  tooltips.py             # Hotspot and event hover HTML
data/
  raw/                    # ETL-fetched CSVs
  processed/
    merged_features.csv   # Primary analytics table (1 row per timestamp×corridor)
  geo/
    austin_roads.geojson  # Road network geometry
    corridors.geojson     # 5 monitored corridor LineStrings
    venues.geojson        # Event venue points
    hotspots.geojson      # 5 high-risk zones
    simulated_congestion.json  # Time-block congestion for prototype mode
etl/                      # Async ETL pipeline
  fetchers/
    traffic.py            # TomTom Traffic Flow
    weather.py            # OpenWeatherMap
    events.py             # Ticketmaster Discovery (30-day window)
    construction.py       # Austin 311 Roadway Work Zones (qyfh-gwei)
    pipeline.py           # asyncio.gather over all four fetchers
  transform.py            # Merges CSVs → merged_features.csv
ml/
  train.py                # Offline training
  predict.py              # predict() + predict_with_confidence()
  models/
    congestion_rf.joblib  # Trained RandomForestRegressor
    impact_encoder.joblib # LabelEncoder for weather_traffic_impact_level
backend/
  app/
    main.py               # FastAPI app, lifespan, ETL scheduler
    models.py             # MergedFeature, CachedPrediction SQLAlchemy models
    geo_models.py         # RoadSegment, TrafficObservation, WeatherSnapshot, Event, RoadClosure
    database.py           # SessionLocal, get_db, engine
  routes/
    analytics.py          # /api/analytics/* — flat JSON for Power BI / external consumers
    map_data.py           # /api/map/corridors — 60s cached map feed
    corridors.py          # /api/corridors/*
    predictions.py        # /api/predictions/*
    geo.py                # /api/geo/* (PostGIS spatial)
  services/
    analytics_service.py  # All aggregated query functions
    ml_service.py         # predict_congestion() wrapper
    data_service.py       # get_latest_for_corridor(), get_corridor_history()
scripts/
  setup.sh                # Bootstrap: Docker → Alembic → seed → ETL → retrain
tests/                    # pytest
alembic/                  # DB migrations
```

## Data Sources

| Source | What it provides | Fetcher |
|---|---|---|
| TomTom Traffic Flow | Speed, free-flow speed, congestion index per corridor | `etl/fetchers/traffic.py` |
| OpenWeatherMap | Temp, rain, wind, humidity, condition | `etl/fetchers/weather.py` |
| Ticketmaster Discovery | Austin events, 30-day window, venue coords | `etl/fetchers/events.py` |
| Austin 311 (Socrata `qyfh-gwei`) | Roadway Work Zones — active lane closures | `etl/fetchers/construction.py` |
| `holidays` Python pkg | US federal + Texas holidays | `etl/transform.py` |

## Monitored Corridors

I-35_Downtown · Mopac_Expressway_Downtown · US-183_North · Loop-360_West · Congress_Ave_Downtown

Approximate centroids:

| Corridor | Lat | Lon |
|---|---|---|
| I-35_Downtown | 30.269 | -97.7341 |
| Mopac_Expressway_Downtown | 30.2764 | -97.7735 |
| US-183_North | 30.3877 | -97.7232 |
| Loop-360_West | 30.3278 | -97.7998 |
| Congress_Ave_Downtown | 30.2672 | -97.7431 |

## Key DB Tables

| Table | Purpose |
|---|---|
| `merged_features` | One row per (timestamp, corridor) — primary analytics source |
| `cached_predictions` | Pre-computed ML results written each ETL cycle |
| `road_segments` | PostGIS LINESTRING geometries per corridor |
| `traffic_observations` | Raw speed readings linked to road segments |
| `weather_snapshots` | Weather readings with PostGIS POINT geometry |
| `events` | Ticketmaster events with venue geometry and subtype tag |
| `road_closures` | Austin 311 Roadway Work Zone records |

## ML Model

* Algorithm: RandomForestRegressor (200 trees, max_depth=10)
* Target: `congestion_index` (0.0 free-flow → 1.0 standstill)
* 13 features: current_speed_mph, free_flow_speed_mph, weather_temp_f, weather_humidity_pct, weather_wind_speed_mph, weather_cloud_cover_pct, weather_rain_1h_mm, nearby_event_count, hour_of_day, day_of_week, is_weekend, is_holiday, weather_traffic_impact_level
* Confidence bands via tree std deviation → confidence_low / confidence_high
* Artifacts: `ml/models/congestion_rf.joblib`, `ml/models/impact_encoder.joblib`

## Event Subtypes

* `austin_fc` — Q2 Stadium (30.3872, -97.7188)
* `ut_football` — DKR-Texas Memorial Stadium (30.2836, -97.7320)
* `concert` — Music segment events
* `festival` — ACL (Zilker Park: 30.2669, -97.7730), SXSW (Downtown)
* `sports_other` — other Sports segment events
* `other` — everything else

## Prototype / Simulated Data

When `USE_SIMULATED_DATA=true` in `.env` (or no DB available), the app reads from:
* `data/geo/simulated_congestion.json` — congestion values per corridor per 30-min time block
* `data/geo/venues.geojson` — static event venue points
* Weather multipliers applied in `components/map_builder.py`

This lets the app run completely offline for demos. The visual structure is identical to live mode.

## API Routers (FastAPI backend)

| Prefix | File | Purpose |
|---|---|---|
| `/api/analytics` | `routes/analytics.py` | Flat aggregated data for Power BI |
| `/api/map` | `routes/map_data.py` | All corridors + cached predictions (60s TTL) |
| `/api/corridors` | `routes/corridors.py` | Latest + history per corridor |
| `/api/predictions` | `routes/predictions.py` | Live ML prediction per corridor |
| `/api/geo` | `routes/geo.py` | PostGIS spatial queries |

Analytics endpoints return flat list[dict] — no geometry, no nested objects (Power BI requirement).

## Deployment

* **Local:** `streamlit run streamlit_app.py` on port 8501
* **Streamlit Cloud:** push to GitHub → share.streamlit.io → set secrets → Deploy
* **Database (deployed):** Supabase free tier — set `DATABASE_URL` in Streamlit secrets
* **FastAPI (optional):** `uvicorn backend.app.main:app --reload` on port 8000

## Commands

* Streamlit app: `streamlit run streamlit_app.py`
* FastAPI server: `uvicorn backend.app.main:app --reload`
* Bootstrap: `bash scripts/setup.sh`
* Run ETL: `python -m etl.fetchers.pipeline`
* ETL dry-run: `python -m etl.fetchers.pipeline --dry-run`
* Transform: `python etl/transform.py`
* Train ML: `python ml/train.py`
* Test: `pytest`
* Lint: `flake8 .`

## Verification

After any change:
1. `python -m py_compile streamlit_app.py pages/*.py components/*.py` — syntax
2. `pytest` — tests
3. `flake8 .` — lint
4. `streamlit run streamlit_app.py` — visual check

## Conventions

* Streamlit app is the primary user-facing product; FastAPI is secondary
* Prototype mode (`USE_SIMULATED_DATA=true`) must always work without DB or API keys
* Map layers are constructed in `components/map_builder.py` — not inline in pages
* Sidebar controls are defined in `components/sidebar.py` — return a plain dict of selections
* Analytics endpoints return flat list[dict] — no geometry, no nested objects
* ETL fetchers are async (httpx.AsyncClient); one file per data source
* ML predictions are pre-computed during ETL — never run inference in the Streamlit hot path
* Use snake_case for Python files and DB columns

## Don't

* Don't run ML inference inside Streamlit callbacks — read from cached_predictions or merged_features
* Don't return geometry from analytics endpoints
* Don't hardcode API keys — use .env (local) or Streamlit secrets (deployed)
* Don't put map construction logic inline in pages — use map_builder.py
* Don't aggregate raw rows in the frontend — use analytics_service.py or pre-aggregated CSVs