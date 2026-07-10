# Austin Traffic Intelligence Platform

React 18 + kepler.gl frontend with a FastAPI backend. Visualizes real-time Austin traffic, events, and weather on an interactive MapLibre map.

## Stack

- **Frontend:** React 18, Redux, @kepler.gl/components v3, MapLibre GL JS + Carto (no token), Tailwind CSS, Axios
- **Backend:** FastAPI, SQLAlchemy 2.0, SQLite by default (Postgres optional), Alembic, httpx
- **Data:** City of Austin / Socrata (Bluetooth + radar), TomTom (real-time flow), Open-Meteo (weather, free, no key), Ticketmaster (events), OSM Overpass (road network)
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

**Backend (.env at project root) — all optional; the app runs on SQLite + committed artifacts without any of them:**

```text
DATABASE_URL=            # optional; defaults to SQLite (sqlite:///./dev.db)
TOMTOM_API_KEY=          # optional; real-time flow + self-update collection
TICKETMASTER_API_KEY=    # optional; events (free tier)
SOCRATA_APP_TOKEN=       # optional; raises Austin open-data rate limit
```

**Frontend (frontend/.env):**

```text
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
| Build REAL training data (Austin sensors) | `python scripts/build_real_training_data.py` |
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

- **Coverage:** the network is every motorway/trunk/primary/secondary segment in
  `data/geo/austin_network.geojson` (~3,800 segments, fetched from OSM/Overpass),
  but the **map + predictions show only segments within `DOWNTOWN_RADIUS_KM`
  (default 10) of downtown** (~1,230 segments) — `segments_service.load_display_segments()`.
  This keeps the app on Austin proper (Round Rock/Cedar Park/Manor/Buda are 20-28 km
  out). `load_segments()` stays the FULL network because the offline training-data
  builders assign each sensor reading to its true nearest road; only the serving
  paths (live layer, `ml_model` predictions, geometry, TomTom collector) use the
  filtered set. Widen/narrow via the `DOWNTOWN_RADIUS_KM` env var.
- **Model:** `HistGradientBoostingRegressor` → `data/models/congestion_model.pkl`.
- **Architecture — learned baseline flow + educated-guess overlays.** The model
  learns only the BASELINE traffic flow; weather, federal holidays, and events are
  applied on top as transparent overlays (they are NOT model features), so served
  congestion is `max(0, baseline) * weather_mult * holiday_mult + event_uplift`. This
  is deliberate: the real speed data has no usable weather/event signal (events are 0
  in 100% of rows; weather is weak and sometimes wrong-signed — see
  `docs/radar_ablation.md`) and holidays are too rare to learn, so training them in
  produced unreliable, sometimes-inverted effects. Overlays make them all reliable
  and interpretable. Both multiplicative overlays are computed once per call inside
  `ml_model._run_predictions` (holiday from the date; weather from the condition), so
  every serving path inherits them.
- **Learned features (segment-agnostic, so it generalizes to any road):** road class,
  distance to downtown, hour, day-of-week, weekend, month, `base_pattern` (formula
  baseline), and **`seasonal_level`** — each segment's *real* typical congestion for
  that hour-of-week (the model's strongest feature). Served from
  `data/models/seasonal_prior.json`.
- **Honest, leak-free held-out metric (R² ≈ 0.26, MAE ≈ 8.9).** `seasonal_level`
  is a per-(segment, hour, weekend) target encoding, so computing it over the
  whole dataset before the split leaks held-out targets and inflates R² by an
  amount that scales with per-group density (that is why earlier runs read 0.54
  and a Bluetooth-only run read 0.70 — both inflated, not real skill). The split
  is now done first and `seasonal_level` is rebuilt per fold
  (`backend/etl/training_eval.py`), mirroring how the predictor serves it, so the
  reported R² is a true generalization estimate and is stable across retrains.
- **Regression gate.** `train_model.py` compares the new honest R²/MAE against the
  deployed `point_holdout_r2`/`point_holdout_mae` in `model_meta.json`; a material
  drop (R² > 0.03 or MAE > 0.5) blocks the retrain (exit 2, no artifacts written)
  so the self-updater keeps serving the last good model. Override with
  `ALLOW_ACCURACY_REGRESSION=1` for an intentional feature/baseline change.
- **Shared feature code:** `backend/services/congestion_features.py` is the single
  source of truth used by both the data generator and the live predictor.
- **Training data is REAL** (`scripts/build_real_training_data.py`): ~76k City of
  Austin Bluetooth travel-sensor readings. `scripts/generate_training_data.py`
  (synthetic) remains only as a fallback. Coverage caveat: only ~12 OSM segments
  have direct sensor history; others use the road-class seasonal fallback.
- **Radar source, ablation-verified (`scripts/ablate_radar.py` → `docs/radar_ablation.md`).**
  Radar is dense-but-narrow (300k rows from 13 intersections, 79% of training rows),
  which looked like it might distort the model. A leak-free with/without/downsampled
  ablation disproved that: radar is the best variant on aggregate R² (0.82 vs 0.75),
  per-reading MAE (8.8 vs 12.0), it doubles the High-confidence corridors (22 vs 10),
  and it's the ONLY variant where rain correctly *raises* congestion (+1.4 vs −2.3
  without it). Kept as deployed; the harness trains in-memory and never touches
  `data/models/`. Re-run it to re-verify after a data refresh.
- **Event impact is an explicit overlay** (`backend/etl/event_impact.py`), NOT a
  learned effect: the ablation showed `nearby_event_attendance` is **0 in 100% of
  real training rows**, so the ML model's learned event importance is exactly 0. The
  overlay adds `event_congestion_uplift(signal)` = `min(45, signal/1500)` congestion
  points on top of the ML baseline in `ml_model._run_predictions`, where `signal` is
  the per-segment distance+time-weighted crowd from
  `congestion_features.nearby_event_attendance`. So crowd size sets magnitude while
  proximity+timing pick which roads and when. Both the spatial REACH
  (`event_reach_km`, √attendance, 2.5–15 km) AND the time window
  (`event_time_window_hours`, √attendance, 2.5–6 h) scale with the crowd: a 2k club
  show is a ~3km / ~2.5h local bump, a 15k Moody Center night reaches ~6km and ramps
  in ~3h before, a 100k UT-football Saturday floods ~14km and starts snarling traffic
  ~6h before kickoff, saturating the +45 cap across central Austin. Big games
  therefore back up far more corridors, earlier — handled first, without ignoring the
  small venues. Surfaced as `event_uplift_pct` in the Predicted tooltip. Reversible
  (zero events → zero change); the synthetic generator reuses the same curve.
- **Weather impact is an explicit overlay too**
  (`congestion_features.weather_congestion_multiplier` /
  `WEATHER_CONGESTION_MULTIPLIER`), NOT a learned effect: the real speed data's
  weather signal is weak and per-segment can invert (rain *lowering* congestion), so
  weather was removed from the model and applied as a severity multiplier on the
  baseline. Every condition Open-Meteo's `WEATHER_CODE_MAP` can emit is graded, and
  **ranked for Austin specifically** — the local hazard order is NOT the national
  one. Tier 1 (routes shut down, ×1.8–2.0): black ice / freezing rain ×2.0 (the worst
  — untreated bridges/overpasses like the I-35 upper deck & 360), heavy snow ×1.9,
  freezing drizzle ×1.85, flash-flood heavy rain ×1.8 (Flash Flood Alley low-water
  crossings) — note black ice **outranks hail** here. Tier 2 (high impact, ×1.4–1.7):
  icy fog / hail / snow ×1.7, thunderstorm ×1.6, dense fog ×1.55, light snow ×1.5,
  rain ×1.4. Tier 3 (daily friction, ×1.1–1.3): light rain, drizzle, snow grains.
  Two **temperature escalations** (`weather_congestion_multiplier(condition, temp_f)`,
  threaded from serving) capture Austin's signature risks the label alone misses:
  any liquid precip at ≤34°F becomes black ice (×2.0) even if the API says "Rain",
  and ≥100°F adds heat friction (×1.15, buckled pavement / blowouts). Freezing-rain
  WMO codes (56/57/66/67) were added to `WEATHER_CODE_MAP` (they were missing). A
  coverage test asserts no real condition falls through to 1.0 (the earlier bug:
  only 4 exact labels matched, so fog/snow/thunderstorm silently read as clear).
  Cost of removing weather from the model: honest R² 0.279 → 0.261 (small, within
  gate tolerance), for a correct, interpretable, locally-tuned weather factor.
- **Federal holidays are an overlay too** (`backend/etl/holiday_impact.py`, using the
  `holidays` library): on a weekday holiday the model would still predict a normal
  rush, but most people are off, so a multiplier trims the baseline — tiered by how
  many are actually off. MAJOR holidays (New Year's, Memorial Day, July 4th, Labor
  Day, Thanksgiving, Christmas) → ×0.55; MINOR ones (MLK, Presidents', Juneteenth,
  Columbus, Veterans) → ×0.8; ordinary days ×1.0. Observed dates are honored (a
  Saturday July 4th shifts the day off to Friday). Because it multiplies the
  baseline, it trims the rush peak far more than the already-quiet overnight hours.
  Event surges (a holiday concert) still layer on top via the event overlay.
- **Confidence:** served from the **expected-value interval** — the range for the
  *typical* congestion the app actually displays (`pred ± ev_q`), NOT the spread of
  a single 15-min reading. Interval width maps to a 0-100 score via fixed absolute
  anchors on the expected-value scale (`backend/etl/confidence.py`, full=3 /
  zero=30 pts, anchored to the 15-pt tier bands). Four corrections keep it honest
  (all in `ml_model._segment_confidences`):
    1. **Expected-value calibration (the served signal)** — `train_model.py` calls
       `calibrate_expected_value_interval` (`backend/etl/model_eval.py`) to
       split-conformal fit `ev_q` on held-out (segment, hour, weekend) *bucket
       means* so `pred ± ev_q` covers the true typical value at nominal rate
       (deployed: 80% band ±4.3 pts, **held-out coverage 0.833**; 50% ±1.4, 0.53),
       stored in `congestion_quantiles.pkl` as `ev_q_80`/`ev_q_50`. This is far
       tighter than the per-reading band because the typical value is genuinely
       known that well (bucket MAE ~2.7 vs per-reading ~8.8) — verified on held-out
       buckets, not asserted. Serving prefers `ev_q_80`; older artifacts without it
       fall back to the per-reading q25/q75 `conformal_q` path (lever below).
    2. **Conformal calibration (legacy per-reading band, still computed)** — the
       raw q25/q75 band was too narrow (~0.44 not 0.50); `conformal_q` widens it.
       Must be calibrated on serving-style features (the test fold's prior-lookup
       `seasonal_level`), not training rows — else q comes out ~0.
    3. **Density cap** — a prediction can't read more confident than the real
       history backing it. `seasonal_prior.json` stores per-segment support counts;
       serving resolves a tier (segment→road_class→global) and caps confidence
       (`density_confidence_cap`: dense per-segment→up to 100, road_class→≤70,
       global→≤50).
    4. **Per-corridor modulation** — a single global `ev_q` made every road read the
       same confidence, so the score carried no per-road signal beyond the tier. The
       calibrated average half-width is now redistributed across corridors by each
       one's *learned* per-reading spread (the q75-q25 band from the quantile models),
       bounded so the mean half-width — hence the calibrated coverage — is preserved
       (`confidence.modulated_half_width`, reference `ev_ref_width` in
       `congestion_quantiles.pkl`). Confidence is taken from the TRUE interval
       half-width, not the width after clipping to [0,100] (which used to inflate
       near-empty roads). Net effect: confidence genuinely **falls at rush hour and on
       volatile corridors** and rises on calm ones — city-wide mean ~70 overnight →
       ~57 at the 5 PM peak; the ~18 measured corridors read High, road-class
       fallbacks now spread **50–70** by difficulty instead of a flat 70. Measured
       roads still honestly out-confidence unmeasured ones.
  The separate **accuracy badge** is the wide 80% *per-reading* interval's empirical
  coverage (~0.87). `python scripts/evaluate_model.py` writes the full honest,
  leak-free scorecard (per-reading + aggregate + expected-value coverage) to
  `model_meta.json` and `docs/model_evaluation.md`. Per-segment interval +
  confidence appear in the Predicted +2h tooltip; aggregates in the Forecast panel.
- **Aggregated confidence:** `/api/traffic/corridors/day` returns a per-hour
  `confidence_avg`/`confidence_label` plus a whole-day average (mean of the 24
  hourly city-wide averages); `/api/traffic/corridors/week?start=YYYY-MM-DD`
  rolls 7 days up into a Mon..Sun average. All three paths share
  `ml_model._segment_confidences`. In day-preview the legend shows the whole-day
  average and the TimeSliderPanel shows the per-hour + whole-day score.

### Swapping in real data

The GeoJSON contract never changes, so real data drops in without touching the
frontend:

1. **Real congestion history** → `scripts/build_real_training_data.py` (the
   implemented real-data ETL) pulls City-of-Austin Bluetooth travel-sensor speed
   history (datasets `v7zg-5jg9` + `6yd9-yz29`), derives congestion from speed,
   joins historical weather + curated events, and writes
   `data/training/congestion_history.csv`. Then run `python scripts/train_model.py`.
   No code changes.
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

- **Frontend:** Netlify — base `frontend/`, `npm run build`, publish `build/` (config in `netlify.toml`)
- **Backend:** Hugging Face Docker Space — auto-deployed from `main` via `.github/workflows/deploy-hf.yml`
- **Database:** none required — SQLite + committed artifacts; set `DATABASE_URL` only to use Postgres

## Conventions

- All external API calls go through services/ — never inside route handlers
- All API calls use httpx with `timeout=10.0` and silent fallback on error
- In-memory cache (utils/cache.py) prevents hammering free-tier APIs
- kepler.gl layers are loaded via `dispatch(addDataToMap(...))` — never manipulate kepler state directly
