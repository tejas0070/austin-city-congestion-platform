# Austin Traffic Intelligence

An interactive traffic analytics platform for Austin, TX. Visualizes real-time and predicted congestion across the city's major corridors with event overlays, weather impact modeling, and ML-powered forecasts. Deployed as a public Streamlit app.

**Live demo:** `https://yourname-austintraffic.streamlit.app`

---

## What It Does

- **Interactive map** takes 70% of the screen. Overlays update live as you adjust controls.
- **Left sidebar** holds all controls (time, day, events, weather) and key stats (speed, congestion index, top corridors, delay severity).
- **Three tabs:** Live Map - Event Impact - Weather Analysis

### Map Layers

| Layer | What it shows |
| --- | --- |
| Congestion Heatmap | Color gradient (green to red) across the full road network, updates with time slider |
| Predicted Congestion | ML model output per road segment for the selected time window |
| Event Markers | Venue pins with expected attendance and predicted congestion impact on hover |
| Construction Zones | Orange markers for active lane closures from Austin 311 |
| Hotspot Circles | Shaded overlays on the five highest-risk zones with delay estimates |

### Sidebar Controls

- **Time slider** - 12 AM to 11 PM in 30-minute increments
- **Day of week** - Monday through Sunday
- **Event toggles** - Austin FC, UT Football, SXSW, ACL, Downtown events
- **Weather dropdown** - Clear, Rain, Heavy Rain, Storm

### Sidebar Stats

- Current average city speed (mph)
- Congestion index (0-100)
- Top 3 most congested corridors at selected time
- Predicted delay severity (Low / Moderate / Severe)
- Weather impact score

---

## Focus Corridors

| Corridor | Why it matters |
| --- | --- |
| I-35 (full north-south run) | Highest daily volume in Austin |
| MoPac (Loop 1) | Primary alternative to I-35 |
| Highway 183 | Tech corridor, Domain area |
| Downtown Austin grid | Congress Ave, 6th St, Red River |
| UT campus area | Game days cause city-wide ripple effects |
| Q2 Stadium zone | Austin FC matches spike North Austin |

---

## Tech Stack

| Layer | Technology |
| --- | --- |
| App framework | Streamlit |
| Interactive map | Folium + streamlit-folium |
| Data | Pandas, GeoJSON (Austin Open Data) |
| ML predictions | Scikit-learn RandomForestRegressor |
| Database (local) | PostgreSQL 15 + PostGIS (Docker) |
| Database (deployed) | Supabase free tier |
| ETL | httpx async fetchers (TomTom, OpenWeatherMap, Ticketmaster, Austin 311) |
| Base map tiles | CartoDB Dark Matter |

---

## Project Structure

```
austin-city-congestion-platform/
|
+-- streamlit_app.py          # App entry point - layout, sidebar, tab routing
+-- pages/
|   +-- live_map.py           # Tab 1: interactive map with all layers
|   +-- event_impact.py       # Tab 2: congestion before/during events (bar charts)
|   +-- weather_analysis.py   # Tab 3: speed vs rainfall over time (line charts)
|
+-- components/
|   +-- map_builder.py        # Folium map construction and layer toggling
|   +-- sidebar.py            # Controls and stats rendering
|   +-- tooltips.py           # Hotspot and event hover content
|
+-- data/
|   +-- raw/                  # Fetched CSVs from ETL
|   +-- processed/            # merged_features.csv after transform
|   +-- geo/                  # GeoJSON road network and zone boundaries
|
+-- etl/                      # Async ETL pipeline
|   +-- fetchers/
|   |   +-- traffic.py        # TomTom Traffic Flow API
|   |   +-- weather.py        # OpenWeatherMap
|   |   +-- events.py         # Ticketmaster Discovery
|   |   +-- construction.py   # Austin 311 road closures
|   |   +-- pipeline.py       # Runs all four concurrently
|   +-- transform.py          # Merges raw CSVs into merged_features.csv
|
+-- ml/
|   +-- train.py              # Offline training - run after ETL populates data
|   +-- predict.py            # Inference + confidence bands
|   +-- models/               # Saved joblib artifacts
|
+-- backend/                  # FastAPI (retained for API-only consumers)
|   +-- app/                  # SQLAlchemy models, DB setup
|   +-- routes/               # Analytics endpoints (/api/analytics/*)
|   +-- services/             # DB query helpers, ML service wrapper
|
+-- scripts/
|   +-- setup.sh              # One-command bootstrap for new contributors
|
+-- tests/                    # pytest unit and integration tests
+-- requirements.txt
+-- .env.example
+-- docker-compose.yml
```

---

## Quick Start (Local)

Prerequisites: Python 3.11+, Docker Desktop, git

```bash
# 1. Clone and enter the project
git clone https://github.com/yourusername/austin-traffic-intelligence
cd austin-city-congestion-platform

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy and fill in API keys
cp .env.example .env
# Edit .env: add TOMTOM_API_KEY, OPENWEATHER_API_KEY, TICKETMASTER_API_KEY

# 4. Bootstrap: start DB, run migrations, seed data, first ETL run
bash scripts/setup.sh

# 5. Launch the Streamlit app
streamlit run streamlit_app.py
```

Opens at `http://localhost:8501` with live data on first load.

### What `setup.sh` Does

| Step | Action |
| --- | --- |
| 1 | Starts PostGIS via Docker Compose |
| 2 | Waits for DB health check |
| 3 | Runs Alembic migrations (all tables + indexes) |
| 4 | Seeds road segments from GeoJSON |
| 5 | Runs first ETL cycle (fetch, transform, load) |
| 6 | Pre-computes ML predictions into `cached_predictions` |

Without steps 5-6 the map shows no congestion data on first load.

### API Keys Required

| Service | Environment variable | Free tier |
| --- | --- | --- |
| TomTom Traffic Flow | `TOMTOM_API_KEY` | Yes |
| OpenWeatherMap | `OPENWEATHER_API_KEY` | Yes |
| Ticketmaster Discovery | `TICKETMASTER_API_KEY` | Yes |
| Austin 311 / Socrata | `SOCRATA_APP_TOKEN` | Optional (raises rate limits) |

---

## Running the ETL Manually

```bash
# Fetch all sources and write to DB
python -m etl.fetchers.pipeline

# Fetch only, no DB writes (test API keys)
python -m etl.fetchers.pipeline --dry-run

# Rebuild merged_features.csv from raw CSVs
python etl/transform.py
```

## Training the ML Model

```bash
# Requires at least one full ETL run first
python ml/train.py
```

Artifacts saved to `ml/models/`. The app reads predictions from `cached_predictions` in the DB. Retrain after accumulating more history.

---

## Deploying to Streamlit Community Cloud

1. Push the repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) and click **New app**
3. Select your repo, branch `main`, entry point `streamlit_app.py`
4. Add secrets in the **Secrets** panel (TOML format):

```toml
TOMTOM_API_KEY = "your_key"
OPENWEATHER_API_KEY = "your_key"
TICKETMASTER_API_KEY = "your_key"
DATABASE_URL = "postgresql://..."
```

5. Click **Deploy** - app gets a public URL in about 2 minutes

For the database: create a free [Supabase](https://supabase.com) project, copy the connection string as `DATABASE_URL`, and run `alembic upgrade head` against it once.

---

## Data Architecture

### Prototype Mode (no API keys)

Set `USE_SIMULATED_DATA=true` in `.env` to run entirely offline using bundled data in `data/geo/` and `data/processed/`:

- Austin road network GeoJSON from Austin Open Data Portal
- Congestion values per road segment per 30-minute time block
- Event schedule with venue coordinates and attendance estimates
- Weather multipliers applied to base congestion values

### Live Mode

The congestion layer reads from `cached_predictions` (pre-computed each ETL cycle). Event and construction layers read from the DB. The ML output slot-swaps with the simulated table - the visual structure is identical.

---

## ML Model

- **Algorithm:** RandomForestRegressor (200 trees, max_depth=10)
- **Target:** `congestion_index` from 0.0 (free flow) to 1.0 (standstill), displayed as 0-100
- **Features:** speed, free-flow speed, 6 weather fields, nearby event count, hour, day of week, is_weekend, is_holiday, weather impact level
- **Confidence bands:** std deviation across individual tree predictions, shown as a shaded band on the forecast overlay
- **Retraining:** run `python ml/train.py` offline after ETL has populated a few days of history

---

## Contributing

```bash
pytest          # run tests
flake8 .        # lint
```

---

## Roadmap

- [ ] Replace simulated data with full live pipeline
- [ ] Scheduled ETL via GitHub Actions (30-minute cron)
- [ ] Supabase deployment with persistent history
- [ ] Animated time-lapse mode (play button on time slider)
- [ ] Mobile-responsive sidebar collapse