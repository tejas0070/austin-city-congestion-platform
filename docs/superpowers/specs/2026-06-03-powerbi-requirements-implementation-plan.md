# Implementation Plan: Power BI Requirements Gap Fill
**Date:** 2026-06-03
**Project:** Austin Traffic Intelligence Platform

---

## Context

A gap analysis against the full product requirements revealed that the data foundation is solid (TomTom + OpenWeatherMap + Ticketmaster all wired up, PostgreSQL + PostGIS running) but the analytics layer needed to drive Power BI dashboards is almost entirely absent. This plan builds that layer in six ordered phases.

Each phase is independently deployable. Power BI can start connecting after Phase 1.

---

## Phase 1 — Analytics API Router (Power BI foundation)

**What:** Create `backend/routes/analytics.py` with flat, tabular endpoints that Power BI can consume via its Web connector. All responses are `list[dict]` with scalar values only — no geometry, no nested objects.

**Endpoints to build:**

| Endpoint | Response shape | Powers |
|---|---|---|
| `GET /api/analytics/congestion-by-hour` | `[{corridor_name, hour_of_day, avg_congestion, avg_speed, sample_count}]` | Executive Overview daily trend, rush hour chart |
| `GET /api/analytics/congestion-by-day` | `[{corridor_name, day_of_week, day_name, avg_congestion, avg_speed}]` | Executive Overview day-of-week bar |
| `GET /api/analytics/top-congested` | `[{corridor_name, avg_congestion, max_congestion, avg_speed, rank}]` | Executive Overview top corridors KPI |
| `GET /api/analytics/current-snapshot` | `[{corridor_name, congestion_index, current_speed_mph, predicted_congestion_index, congestion_label, timestamp}]` | Executive Overview live KPI cards |
| `GET /api/analytics/weather-impact` | `[{weather_condition, rain_bucket_mm, avg_congestion, avg_speed, sample_count}]` | Weather Impact dashboard |
| `GET /api/analytics/event-impact` | `[{event_subtype, has_event, avg_congestion, avg_speed, sample_count}]` | Event Impact dashboard |
| `GET /api/analytics/forecast` | `[{corridor_name, forecast_hour, predicted_congestion_index, confidence_low, confidence_high, congestion_label}]` | Predictive dashboard |

**Files to create/modify:**
- `backend/routes/analytics.py` — new router
- `backend/app/main.py` — register `analytics_router`
- `backend/services/analytics_service.py` — SQLAlchemy aggregation queries
- `ml/predict.py` — add `predict_with_confidence()` returning `(index, low, high)`

**Key implementation notes:**
- All queries run against `merged_features` table (already populated each ETL cycle)
- Use SQLAlchemy `func.avg()`, `func.max()`, `func.count()` with `group_by()` — do not do aggregation in Python
- Forecast endpoint: for each future hour (0–N), synthesize a feature vector using current weather + event data + projected `hour_of_day`/`day_of_week`, run through `predict_with_confidence()`
- Add `analytics_router` to `app.include_router()` in `main.py`

---

## Phase 2 — Event Subtype Classification

**What:** Tag each Ticketmaster event with a specific subtype so the Event Impact dashboard can break down Austin FC vs UT football vs ACL vs SXSW vs generic concerts.

**Files to modify:**
- `backend/app/geo_models.py` — add `event_subtype = Column(String, nullable=True)` to `Event`
- `etl/fetchers/events.py` — add `_classify_subtype(event_name, venue_name, segment)` function
- `etl/load_to_db.py` — ensure upsert writes `event_subtype`
- New Alembic migration for the `event_subtype` column

**Classification logic in `_classify_subtype()`:**
```python
AUSTIN_FC_VENUES = {"Q2 Stadium"}
UT_FOOTBALL_VENUES = {"Darrell K Royal-Texas Memorial Stadium"}
FESTIVAL_KEYWORDS = {"ACL", "Austin City Limits", "SXSW", "South by Southwest",
                     "Pachanga", "Fun Fun Fun", "Euphoria"}

if venue_name in AUSTIN_FC_VENUES: return "austin_fc"
if venue_name in UT_FOOTBALL_VENUES: return "ut_football"
if any(kw in event_name for kw in FESTIVAL_KEYWORDS): return "festival"
if segment == "Music": return "concert"
if segment == "Sports": return "sports_other"
return "other"
```

**Also add `event_subtype` filter to `GET /api/analytics/event-impact`** so Power BI can slice by type.

---

## Phase 3 — Holiday Flag in Transform

**What:** Add an `is_holiday` boolean column to `MergedFeature` using the `holidays` Python package. This lets Power BI compare holiday vs non-holiday congestion and the ML model can use it as a feature.

**Files to modify:**
- `requirements.txt` — add `holidays>=0.46`
- `etl/transform.py` — in `transform()`, after computing `is_weekend`, add:
  ```python
  import holidays
  tx_holidays = holidays.US(state="TX", years=traffic_df["timestamp"].dt.year.unique())
  traffic_df["is_holiday"] = traffic_df["timestamp"].dt.date.apply(
      lambda d: d in tx_holidays
  ).astype(int)
  ```
- `backend/app/models.py` — add `is_holiday = Column(Integer, default=0)` to `MergedFeature`
- `ml/train.py` — add `"is_holiday"` to `NUMERIC_FEATURES`
- `ml/predict.py` — add `"is_holiday"` to the feature dict (default 0)
- `backend/services/ml_service.py` — pass `is_holiday` from the `MergedFeature` row
- New Alembic migration for the `is_holiday` column

---

## Phase 4 — ML Confidence Intervals

**What:** `RandomForestRegressor` contains individual tree predictions. Computing std deviation across trees gives a natural confidence band. Surface this in `CachedPrediction` and the analytics forecast endpoint.

**Files to modify:**
- `ml/predict.py` — add `predict_with_confidence()`:
  ```python
  def predict_with_confidence(features: dict) -> tuple[float, float, float]:
      """Returns (index, confidence_low, confidence_high) using RF tree std dev."""
      _load_artifacts()
      row = _build_row(features)  # refactor existing predict() to share this
      tree_preds = [tree.predict(row)[0] for tree in _model.estimators_]
      mean = float(np.mean(tree_preds))
      std = float(np.std(tree_preds))
      low = round(max(0.0, mean - std), 4)
      high = round(min(1.0, mean + std), 4)
      return round(mean, 4), low, high
  ```
- `backend/app/models.py` — add `confidence_low` and `confidence_high` columns to `CachedPrediction`
- `etl/load_to_db.py` — update `cache_predictions()` to call `predict_with_confidence()` and store the band
- `backend/routes/analytics.py` — forecast endpoint returns `confidence_low`/`confidence_high`
- New Alembic migration for the two new columns

---

## Phase 5 — Road Construction Fetcher

**What:** Add a construction/lane closure data source. Austin's open data portal (`data.austintexas.gov`) provides 311 service requests and the Austin Transportation department publishes active construction via Socrata API.

**Files to create:**
- `etl/fetchers/construction.py` — async fetcher hitting `data.austintexas.gov/resource/i26j-xy8s.json` (Austin 311 Street-related complaints) or the TxDOT 511 feed
- `backend/app/models.py` — add `RoadClosure` table:
  ```python
  class RoadClosure(Base):
      __tablename__ = "road_closures"
      id = Column(Integer, primary_key=True)
      corridor_name = Column(String, nullable=True, index=True)
      description = Column(String)
      start_date = Column(DateTime(timezone=True))
      end_date = Column(DateTime(timezone=True), nullable=True)
      is_active = Column(Boolean, default=True)
      source = Column(String, default="austin_311")
      created_at = Column(DateTime(timezone=True), server_default=func.now())
  ```
- Wire into `etl/fetchers/pipeline.py` alongside the existing three fetchers
- Add `GET /api/analytics/road-closures` endpoint returning active closures flat for Power BI
- New Alembic migration

**Note:** If the Socrata API requires a token, add `AUSTIN_DATA_API_KEY` to `.env.example`.

---

## Phase 6 — PostgreSQL Analytics Views (Power BI DirectQuery)

**What:** For users who prefer Power BI DirectQuery over the Web connector (faster, no import step), create materialized/regular views in PostgreSQL that pre-aggregate the data. Power BI can connect directly to these.

**SQL views to create (via Alembic `op.execute()`):**

```sql
-- Average congestion by corridor and hour of day
CREATE OR REPLACE VIEW vw_congestion_by_hour AS
SELECT corridor_name, hour_of_day, day_of_week,
       AVG(congestion_index) AS avg_congestion,
       AVG(current_speed_mph) AS avg_speed,
       COUNT(*) AS sample_count
FROM merged_features
GROUP BY corridor_name, hour_of_day, day_of_week;

-- Weather bucket analysis
CREATE OR REPLACE VIEW vw_weather_impact AS
SELECT weather_condition,
       CASE
           WHEN weather_rain_1h_mm = 0    THEN 'No Rain'
           WHEN weather_rain_1h_mm < 2.5  THEN 'Light'
           WHEN weather_rain_1h_mm < 7.6  THEN 'Moderate'
           ELSE 'Heavy'
       END AS rain_bucket,
       AVG(congestion_index) AS avg_congestion,
       AVG(current_speed_mph) AS avg_speed,
       COUNT(*) AS sample_count
FROM merged_features
GROUP BY weather_condition, rain_bucket;

-- Event impact comparison
CREATE OR REPLACE VIEW vw_event_impact AS
SELECT has_high_impact_event, nearby_event_count > 0 AS has_any_event,
       AVG(congestion_index) AS avg_congestion,
       AVG(current_speed_mph) AS avg_speed,
       COUNT(*) AS sample_count
FROM merged_features
GROUP BY has_high_impact_event, has_any_event;
```

**Files to modify:**
- Create a new Alembic migration that runs the `CREATE OR REPLACE VIEW` statements
- Add a section to `docs/powerbi_connection_guide.md` explaining how to connect Power BI DirectQuery to these views

---

## Implementation Order

| Phase | Effort | Power BI unblocked? | Build first? |
|---|---|---|---|
| 1 — Analytics API | Medium | Yes — all 5 tabs | ✅ Yes |
| 2 — Event subtype | Small | Event Impact tab | After Phase 1 |
| 3 — Holiday flag | Small | Executive + Event tabs | After Phase 2 |
| 4 — Confidence intervals | Small | Predictive tab | After Phase 3 |
| 5 — Construction fetcher | Large | Hotspot tab | After Phase 4 |
| 6 — DB views | Small | All tabs (DirectQuery) | After Phase 5 |

---

## Verification

After each phase:

1. `python -m py_compile backend/**/*.py` — no syntax errors
2. `pytest` — existing tests pass
3. `flake8 .` — no lint errors
4. Hit the new endpoint manually: `curl http://localhost:8000/api/analytics/congestion-by-hour`
5. Open Power BI Desktop → Get Data → Web → paste the endpoint URL → verify the table loads with correct columns and types
6. After Phase 6: Power BI → Get Data → PostgreSQL → connect to `localhost:5432/austin-traffic-predictor` → verify views appear in the navigator

---

## Power BI Connection Reference

**Web connector (REST API):**
```
Base URL: http://localhost:8000/api/analytics/
Endpoints: congestion-by-hour, congestion-by-day, top-congested, current-snapshot,
           weather-impact, event-impact, forecast
```

**DirectQuery (after Phase 6):**
```
Server:   localhost
Port:     5432
Database: austin-traffic-predictor
User:     postgres
Views:    vw_congestion_by_hour, vw_weather_impact, vw_event_impact
```
