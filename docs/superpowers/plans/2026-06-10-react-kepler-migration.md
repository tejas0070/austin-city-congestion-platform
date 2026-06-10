# Austin Traffic Intelligence — React + kepler.gl Migration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Streamlit/Folium frontend with React 18 + kepler.gl, reorganize the FastAPI backend to match the spec's layered structure, migrate data sources from TomTom/OpenWeatherMap to TxDOT/Open-Meteo, and start with a fresh PostgreSQL schema.

**Architecture:** React 18 + Redux frontend renders a full-screen kepler.gl map (Mapbox tiles) with a custom 320px Tailwind dark sidebar. FastAPI backend reorganized into `api/routes/`, `db/`, `services/`, and `utils/` layers. All Streamlit, Folium, and ML code is removed. The `data/geo/` GeoJSON files are kept as static assets used by both the frontend and backend.

**Tech Stack:** React 18, Redux, @kepler.gl/components v3, Mapbox GL JS, Tailwind CSS v3, Axios, date-fns, FastAPI, SQLAlchemy 2.0, PostgreSQL, Alembic, httpx, python-dotenv

---

## File Map

### Deleted
- `streamlit_app.py` — Streamlit entry point
- `pages/` — Streamlit pages directory
- `components/` — Streamlit component modules
- `.streamlit/` — Streamlit config
- `ml/` — ML training/prediction (Phase 2; kept as `notebooks/README.md` placeholder)
- `etl/` — Old TomTom/OpenWeather ETL pipeline
- `data/raw/` — Hundreds of old TomTom/event CSVs (fresh data layer)
- `data/processed/` — Old merged_features.csv
- `backend/app/` — Old FastAPI app location
- `backend/routes/` — Old route files
- `backend/services/` — Old service files
- `backend/static/` — Old static HTML
- `alembic/versions/` — All old migrations (fresh schema)
- `cache/` — Old cache files
- `austin_traffic.db` — Old SQLite file
- `=1.13` — Stray file at project root

### Kept
- `data/geo/venues.geojson` — Austin venue GeoJSON
- `data/geo/corridors.geojson` — Road corridor GeoJSON
- `data/geo/hotspots.geojson` — High-risk zone GeoJSON
- `data/geo/simulated_congestion.json` — Prototype/demo data
- `alembic/alembic.ini` — Alembic config
- `alembic/env.py` — Updated to point to new models
- `conftest.py` — pytest config
- `.gitignore` — Updated
- `.env` — Updated with new vars
- `.env.example` — Updated
- `CLAUDE.md` — Rewritten
- `README.md` — Rewritten

### Created
```
backend/
├── __init__.py                        (existing, keep)
├── main.py                            NEW - FastAPI entry point
├── api/
│   ├── __init__.py                    NEW
│   ├── dependencies.py                NEW - DB session injection
│   └── routes/
│       ├── __init__.py                NEW
│       ├── traffic.py                 NEW - /api/traffic/*
│       ├── events.py                  NEW - /api/events/*
│       └── weather.py                 NEW - /api/weather/*
├── db/
│   ├── __init__.py                    NEW
│   ├── database.py                    NEW - SQLAlchemy engine/session
│   ├── models.py                      NEW - ORM models (fresh schema)
│   └── queries.py                     NEW - Reusable query functions
├── services/
│   ├── __init__.py                    NEW
│   ├── txdot_service.py               NEW - TxDOT live traffic + incidents
│   ├── weather_service.py             NEW - Open-Meteo
│   ├── events_service.py              NEW - Ticketmaster + Austin FC + UT
│   └── construction_service.py        NEW - Austin 311 open data
└── utils/
    ├── __init__.py                    NEW
    ├── geojson_builder.py             NEW - Convert rows to GeoJSON
    └── cache.py                       NEW - In-memory TTL cache

requirements.txt                       REWRITE
.env.example                           REWRITE
alembic/versions/20260610_initial.py   NEW migration

notebooks/
└── README.md                          NEW - Phase 2 placeholder

frontend/
├── public/
│   └── index.html                     NEW
├── src/
│   ├── index.js                       NEW - ReactDOM entry + Redux Provider
│   ├── App.js                         NEW - Layout orchestrator
│   ├── index.css                      NEW - Tailwind base + global reset
│   ├── store.js                       NEW - Redux store with keplerGl reducer
│   ├── constants/
│   │   └── austinBounds.js            NEW - Center, zoom, venue list
│   ├── utils/
│   │   ├── colorScales.js             NEW - Speed-to-color mapping
│   │   └── geoHelpers.js              NEW - GeoJSON formatting utilities
│   ├── services/
│   │   ├── api.js                     NEW - Axios instance
│   │   ├── trafficService.js          NEW - Traffic endpoint calls
│   │   └── eventsService.js           NEW - Events endpoint calls
│   ├── hooks/
│   │   ├── useTrafficData.js          NEW - Polls live traffic, loads to kepler.gl
│   │   ├── useEvents.js               NEW - Fetches upcoming events
│   │   └── useWeather.js              NEW - Fetches current weather
│   └── components/
│       ├── MapContainer.jsx           NEW - kepler.gl wrapper
│       ├── Sidebar.jsx                NEW - Full sidebar panel
│       ├── EventCard.jsx              NEW - Single event display
│       ├── LayerToggle.jsx            NEW - Show/hide layer controls
│       ├── TrafficLegend.jsx          NEW - Color scale explanation
│       └── LoadingOverlay.jsx         NEW - Refresh indicator
├── package.json                       NEW
├── tailwind.config.js                 NEW
└── postcss.config.js                  NEW
```

---

## Task 1: Project Cleanup

**Files:**
- Delete: `streamlit_app.py`, `pages/`, `components/`, `.streamlit/`, `ml/`, `etl/`
- Delete: `data/raw/`, `data/processed/`, `backend/app/`, `backend/routes/`, `backend/services/`, `backend/static/`
- Delete: `alembic/versions/*.py`, `cache/`, `austin_traffic.db`, `=1.13`
- Create: `notebooks/README.md`

- [ ] **Step 1: Remove Streamlit and Folium artifacts**

```bash
cd austin-city-congestion-platform
rm -f streamlit_app.py
rm -rf pages components .streamlit
rm -rf ml etl
rm -rf data/raw data/processed
rm -f austin_traffic.db "=1.13"
rm -rf cache __pycache__
```

- [ ] **Step 2: Remove old backend directories**

```bash
rm -rf backend/app backend/routes backend/services backend/static
find backend -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find backend -name "*.pyc" -delete 2>/dev/null || true
```

- [ ] **Step 3: Remove old Alembic migration versions**

```bash
rm -f alembic/versions/*.py
find alembic -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find alembic -name "*.pyc" -delete 2>/dev/null || true
```

- [ ] **Step 4: Create notebooks placeholder**

```bash
mkdir -p notebooks
```

Create `notebooks/README.md`:
```markdown
# Phase 2: ML Exploration

Jupyter notebooks for model training will live here once Phase 1 visualization is complete.

Planned work:
- Exploratory analysis of historical traffic data
- Feature engineering: hour, day_of_week, proximity to venue, weather, event attendance
- Random Forest or XGBoost model for delay score prediction per road segment
- Export model with joblib
```

- [ ] **Step 5: Verify only expected files remain**

```bash
find . -not -path "./.git/*" -not -path "./data/geo/*" -not -path "./.pytest_cache/*" -not -path "./.superpowers/*" -not -path "./docs/*" -not -path "./notebooks/*" -type f | sort
```

Expected to see: `alembic/alembic.ini`, `alembic/env.py`, `alembic/script.py.mako`, `alembic/README`, `backend/__init__.py`, `conftest.py`, `.env`, `.env.example`, `.gitignore`, `CLAUDE.md`, `README.md`, and `data/geo/` files.

- [ ] **Step 6: Commit cleanup**

```bash
git add -A
git commit -m "chore: remove Streamlit/Folium/TomTom stack — replacing with React+kepler.gl"
```

---

## Task 2: Backend DB Layer

**Files:**
- Create: `backend/db/__init__.py`
- Create: `backend/db/database.py`
- Create: `backend/db/models.py`
- Create: `backend/db/queries.py`

- [ ] **Step 1: Create db package**

Create `backend/db/__init__.py`:
```python
```

- [ ] **Step 2: Create database.py**

Create `backend/db/database.py`:
```python
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./dev.db")

if DATABASE_URL.startswith("postgresql"):
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800,
    )
else:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 3: Create models.py**

Create `backend/db/models.py`:
```python
from sqlalchemy import (
    Boolean, Column, Float, Index, Integer,
    String, DateTime, Text, UniqueConstraint,
)
from sqlalchemy.sql import func
from .database import Base


class TrafficSegment(Base):
    """Static road segment definitions seeded at startup."""
    __tablename__ = "traffic_segments"

    id = Column(Integer, primary_key=True, index=True)
    segment_id = Column(String, unique=True, index=True, nullable=False)
    road_name = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class HistoricalTrafficReading(Base):
    """Historical traffic speed readings per road segment."""
    __tablename__ = "historical_traffic"
    __table_args__ = (
        Index("ix_hist_segment_ts", "segment_id", "timestamp"),
    )

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), index=True, nullable=False)
    segment_id = Column(String, index=True, nullable=False)
    road_name = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    speed_mph = Column(Float)
    free_flow_speed_mph = Column(Float)
    congestion_level = Column(String)  # green / yellow / red
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class LiveTrafficCache(Base):
    """Most recent TxDOT reading per segment — upserted every 90 s."""
    __tablename__ = "live_traffic_cache"

    id = Column(Integer, primary_key=True, index=True)
    segment_id = Column(String, unique=True, index=True, nullable=False)
    road_name = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    speed_mph = Column(Float)
    free_flow_speed_mph = Column(Float)
    congestion_level = Column(String)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())


class TrafficIncident(Base):
    """Active road incidents from TxDOT or 511 Texas."""
    __tablename__ = "traffic_incidents"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(String, unique=True, index=True, nullable=False)
    incident_type = Column(String)   # accident / closure / construction / hazard
    description = Column(Text)
    severity = Column(Integer)       # 1–4
    latitude = Column(Float)
    longitude = Column(Float)
    start_time = Column(DateTime(timezone=True))
    end_time = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Event(Base):
    """Upcoming Austin events aggregated from all sources."""
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_event_source_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String, nullable=False)
    source = Column(String, nullable=False)  # ticketmaster / austin_fc / ut_athletics
    name = Column(String, nullable=False)
    venue = Column(String)
    event_date = Column(String)   # ISO date "YYYY-MM-DD"
    event_time = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    category = Column(String)              # Sports / Music / Festival
    expected_attendance = Column(Integer, nullable=True)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())


class WeatherSnapshot(Base):
    """Current Austin weather from Open-Meteo — kept last 24 h."""
    __tablename__ = "weather_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), index=True, nullable=False)
    temperature_f = Column(Float)
    precipitation_in = Column(Float)
    wind_speed_mph = Column(Float)
    weather_code = Column(Integer)
    condition = Column(String)
    rain_alert = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 4: Create queries.py**

Create `backend/db/queries.py`:
```python
from sqlalchemy import extract
from sqlalchemy.orm import Session
from .models import HistoricalTrafficReading
from ..utils.geojson_builder import build_point_feature


def get_historical_traffic(
    db: Session,
    hour: int | None = None,
    day_of_week: str | None = None,
    limit: int = 500,
) -> list[dict]:
    """Return historical traffic readings as a list of GeoJSON feature dicts."""
    query = db.query(HistoricalTrafficReading)

    if hour is not None:
        query = query.filter(
            extract("hour", HistoricalTrafficReading.timestamp) == hour
        )

    readings = (
        query.order_by(HistoricalTrafficReading.timestamp.desc())
        .limit(limit)
        .all()
    )

    return [
        build_point_feature(
            r.latitude or 0,
            r.longitude or 0,
            {
                "segment_id": r.segment_id,
                "road_name": r.road_name,
                "speed_mph": r.speed_mph,
                "free_flow_speed_mph": r.free_flow_speed_mph,
                "congestion_level": r.congestion_level,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            },
        )
        for r in readings
        if r.latitude and r.longitude
    ]
```

- [ ] **Step 5: Commit**

```bash
git add backend/db/
git commit -m "feat: add new DB layer — database.py, models.py, queries.py"
```

---

## Task 3: Backend Utils

**Files:**
- Create: `backend/utils/__init__.py`
- Create: `backend/utils/cache.py`
- Create: `backend/utils/geojson_builder.py`

- [ ] **Step 1: Create utils package**

Create `backend/utils/__init__.py`:
```python
```

- [ ] **Step 2: Create cache.py**

Create `backend/utils/cache.py`:
```python
import time
from typing import Any

_cache: dict[str, tuple[Any, float]] = {}


def set_cache(key: str, value: Any, ttl_seconds: int) -> None:
    _cache[key] = (value, time.time() + ttl_seconds)


def get_cache(key: str) -> Any | None:
    entry = _cache.get(key)
    if entry is None:
        return None
    value, expires_at = entry
    if time.time() > expires_at:
        del _cache[key]
        return None
    return value


def clear_cache(key: str) -> None:
    _cache.pop(key, None)
```

- [ ] **Step 3: Create geojson_builder.py**

Create `backend/utils/geojson_builder.py`:
```python
def build_feature_collection(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": features}


def build_point_feature(lat: float, lng: float, properties: dict) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [lng, lat]},
        "properties": properties,
    }


def build_line_feature(coordinates: list[list[float]], properties: dict) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "LineString", "coordinates": coordinates},
        "properties": properties,
    }


def speed_to_congestion_level(speed_mph: float, free_flow_mph: float) -> str:
    if free_flow_mph <= 0:
        return "unknown"
    ratio = speed_mph / free_flow_mph
    if ratio >= 0.75:
        return "green"
    if ratio >= 0.5:
        return "yellow"
    return "red"
```

- [ ] **Step 4: Write unit tests for utils**

Create `tests/test_utils.py`:
```python
from backend.utils.cache import set_cache, get_cache, clear_cache
from backend.utils.geojson_builder import (
    build_feature_collection,
    build_point_feature,
    speed_to_congestion_level,
)


def test_cache_set_and_get():
    set_cache("k", {"v": 1}, ttl_seconds=60)
    assert get_cache("k") == {"v": 1}


def test_cache_miss_returns_none():
    assert get_cache("nonexistent_key_xyz") is None


def test_cache_clear():
    set_cache("del_me", 42, ttl_seconds=60)
    clear_cache("del_me")
    assert get_cache("del_me") is None


def test_build_point_feature_structure():
    feat = build_point_feature(30.26, -97.74, {"speed_mph": 45})
    assert feat["type"] == "Feature"
    assert feat["geometry"]["type"] == "Point"
    assert feat["geometry"]["coordinates"] == [-97.74, 30.26]
    assert feat["properties"]["speed_mph"] == 45


def test_build_feature_collection():
    fc = build_feature_collection([build_point_feature(0, 0, {})])
    assert fc["type"] == "FeatureCollection"
    assert len(fc["features"]) == 1


def test_speed_to_congestion_green():
    assert speed_to_congestion_level(50, 60) == "green"


def test_speed_to_congestion_yellow():
    assert speed_to_congestion_level(35, 60) == "yellow"


def test_speed_to_congestion_red():
    assert speed_to_congestion_level(15, 60) == "red"


def test_speed_to_congestion_zero_free_flow():
    assert speed_to_congestion_level(30, 0) == "unknown"
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_utils.py -v
```

Expected: 8 tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/utils/ tests/test_utils.py
git commit -m "feat: add utils — in-memory TTL cache and GeoJSON builder"
```

---

## Task 4: Backend Services

**Files:**
- Create: `backend/services/__init__.py`
- Create: `backend/services/txdot_service.py`
- Create: `backend/services/weather_service.py`
- Create: `backend/services/events_service.py`
- Create: `backend/services/construction_service.py`

- [ ] **Step 1: Create services package**

Create `backend/services/__init__.py`:
```python
```

- [ ] **Step 2: Create txdot_service.py**

Create `backend/services/txdot_service.py`:
```python
import random
import httpx
from ..utils.cache import get_cache, set_cache
from ..utils.geojson_builder import (
    build_feature_collection,
    build_point_feature,
    speed_to_congestion_level,
)

TXDOT_BASE_URL = "https://api.travelmapping.txdot.gov"
LIVE_CACHE_TTL = 90   # seconds
LIVE_CACHE_KEY = "txdot_live"

AUSTIN_CORRIDORS = [
    {"segment_id": "i35_downtown",    "road_name": "I-35 Downtown",         "lat": 30.2690, "lng": -97.7341},
    {"segment_id": "mopac_downtown",  "road_name": "Mopac Expressway",       "lat": 30.2764, "lng": -97.7735},
    {"segment_id": "us183_north",     "road_name": "US-183 North",           "lat": 30.3877, "lng": -97.7232},
    {"segment_id": "loop360_west",    "road_name": "Loop 360 West",          "lat": 30.3278, "lng": -97.7998},
    {"segment_id": "congress_downtown","road_name": "Congress Ave Downtown", "lat": 30.2672, "lng": -97.7431},
]


def _simulated_live_features() -> list[dict]:
    features = []
    for c in AUSTIN_CORRIDORS:
        speed = round(random.uniform(15, 65), 1)
        free_flow = 60.0
        features.append(build_point_feature(
            c["lat"], c["lng"],
            {
                "segment_id": c["segment_id"],
                "road_name": c["road_name"],
                "speed_mph": speed,
                "free_flow_speed_mph": free_flow,
                "congestion_level": speed_to_congestion_level(speed, free_flow),
            },
        ))
    return features


async def fetch_live_traffic() -> dict:
    """Return live traffic GeoJSON FeatureCollection, cached 90 s."""
    cached = get_cache(LIVE_CACHE_KEY)
    if cached:
        return cached

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{TXDOT_BASE_URL}/api/v1/traffic/speed",
                params={"bbox": "-97.9,30.1,-97.5,30.5"},
            )
            resp.raise_for_status()
            features = _transform_txdot_response(resp.json())
    except Exception:
        features = _simulated_live_features()

    result = build_feature_collection(features)
    set_cache(LIVE_CACHE_KEY, result, LIVE_CACHE_TTL)
    return result


def _transform_txdot_response(raw: dict) -> list[dict]:
    features = []
    for item in raw.get("features", []):
        props = item.get("properties", {})
        coords = item.get("geometry", {}).get("coordinates", [0, 0])
        speed = float(props.get("speed", 0))
        free_flow = float(props.get("freeFlowSpeed", 60))
        features.append(build_point_feature(
            coords[1], coords[0],
            {
                "segment_id": str(props.get("segmentId", "")),
                "road_name": props.get("roadName", "Unknown"),
                "speed_mph": round(speed, 1),
                "free_flow_speed_mph": free_flow,
                "congestion_level": speed_to_congestion_level(speed, free_flow),
            },
        ))
    return features


async def fetch_incidents() -> dict:
    """Return active incidents GeoJSON FeatureCollection."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{TXDOT_BASE_URL}/api/v1/incidents",
                params={"bbox": "-97.9,30.1,-97.5,30.5"},
            )
            resp.raise_for_status()
            return _transform_incidents(resp.json())
    except Exception:
        return build_feature_collection([])


def _transform_incidents(raw: dict) -> dict:
    features = []
    for item in raw.get("features", []):
        props = item.get("properties", {})
        coords = item.get("geometry", {}).get("coordinates", [0, 0])
        features.append(build_point_feature(
            coords[1], coords[0],
            {
                "incident_id": str(props.get("incidentId", "")),
                "incident_type": props.get("type", "unknown"),
                "description": props.get("description", ""),
                "severity": int(props.get("severity", 1)),
                "start_time": props.get("startTime", ""),
            },
        ))
    return build_feature_collection(features)
```

- [ ] **Step 3: Create weather_service.py**

Create `backend/services/weather_service.py`:
```python
import httpx
from ..utils.cache import get_cache, set_cache

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
AUSTIN_LAT = 30.2672
AUSTIN_LNG = -97.7431
CACHE_TTL = 900   # 15 minutes
CACHE_KEY = "weather_current"

WEATHER_CODE_MAP: dict[int, str] = {
    0: "Clear",
    1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
    45: "Fog", 48: "Icy Fog",
    51: "Light Drizzle", 53: "Drizzle", 55: "Heavy Drizzle",
    61: "Light Rain", 63: "Rain", 65: "Heavy Rain",
    71: "Light Snow", 73: "Snow", 75: "Heavy Snow",
    80: "Rain Showers", 81: "Rain Showers", 82: "Heavy Rain Showers",
    95: "Thunderstorm", 96: "Thunderstorm with Hail", 99: "Thunderstorm with Hail",
}


async def fetch_current_weather() -> dict:
    """Return current Austin weather from Open-Meteo, cached 15 min."""
    cached = get_cache(CACHE_KEY)
    if cached:
        return cached

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(OPEN_METEO_URL, params={
                "latitude": AUSTIN_LAT,
                "longitude": AUSTIN_LNG,
                "current": "temperature_2m,precipitation,wind_speed_10m,weather_code",
                "temperature_unit": "fahrenheit",
                "wind_speed_unit": "mph",
                "precipitation_unit": "inch",
            })
            resp.raise_for_status()
            current = resp.json()["current"]
        result = {
            "temperature_f": current.get("temperature_2m"),
            "precipitation_in": current.get("precipitation"),
            "wind_speed_mph": current.get("wind_speed_10m"),
            "weather_code": current.get("weather_code"),
            "condition": WEATHER_CODE_MAP.get(current.get("weather_code", 0), "Unknown"),
            "rain_alert": (current.get("precipitation") or 0) > 0.004,
        }
    except Exception:
        result = {
            "temperature_f": 78.0,
            "precipitation_in": 0.0,
            "wind_speed_mph": 10.0,
            "weather_code": 0,
            "condition": "Clear",
            "rain_alert": False,
        }

    set_cache(CACHE_KEY, result, CACHE_TTL)
    return result
```

- [ ] **Step 4: Create events_service.py**

Create `backend/services/events_service.py`:
```python
import os
from datetime import datetime, timedelta
import httpx
from ..utils.cache import get_cache, set_cache

CACHE_KEY = "events_upcoming"
CACHE_TTL = 3600  # 1 hour

VENUE_COORDS = {
    "austin_fc":    {"lat": 30.3872, "lng": -97.7188, "name": "Q2 Stadium"},
    "ut_football":  {"lat": 30.2836, "lng": -97.7320, "name": "DKR-Texas Memorial Stadium"},
    "moody_center": {"lat": 30.2850, "lng": -97.7280, "name": "Moody Center"},
    "stubbs":       {"lat": 30.2680, "lng": -97.7336, "name": "Stubb's Amphitheater"},
    "acl_live":     {"lat": 30.2639, "lng": -97.7467, "name": "ACL Live at Moody Theater"},
    "convention":   {"lat": 30.2628, "lng": -97.7402, "name": "Austin Convention Center"},
}

# Hardcoded schedules — update these each season
AUSTIN_FC_SCHEDULE = [
    {"id": "afc_01", "name": "Austin FC vs LA Galaxy",        "date": "2026-06-14", "time": "19:30"},
    {"id": "afc_02", "name": "Austin FC vs Portland Timbers", "date": "2026-07-05", "time": "20:00"},
    {"id": "afc_03", "name": "Austin FC vs Seattle Sounders", "date": "2026-07-19", "time": "19:30"},
    {"id": "afc_04", "name": "Austin FC vs Colorado Rapids",  "date": "2026-08-02", "time": "19:30"},
]

UT_FOOTBALL_SCHEDULE = [
    {"id": "ut_fb_01", "name": "UT vs UTSA",     "date": "2026-08-30", "time": "18:00"},
    {"id": "ut_fb_02", "name": "UT vs Michigan",  "date": "2026-09-06", "time": "11:00"},
    {"id": "ut_fb_03", "name": "UT vs LSU",       "date": "2026-09-27", "time": "14:30"},
    {"id": "ut_fb_04", "name": "UT vs Oklahoma",  "date": "2026-10-11", "time": "11:00"},
]


async def fetch_upcoming_events(days: int = 30) -> list[dict]:
    cached = get_cache(CACHE_KEY)
    if cached:
        return cached

    events: list[dict] = []
    events.extend(_get_hardcoded_events(AUSTIN_FC_SCHEDULE, "austin_fc", "Sports", 20738, days))
    events.extend(_get_hardcoded_events(UT_FOOTBALL_SCHEDULE, "ut_football", "Sports", 100119, days))
    events.extend(await _fetch_ticketmaster_events(days))

    events.sort(key=lambda e: e["date"])
    set_cache(CACHE_KEY, events, CACHE_TTL)
    return events


def _get_hardcoded_events(
    schedule: list[dict],
    source: str,
    category: str,
    attendance: int,
    days: int,
) -> list[dict]:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    cutoff = (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%d")
    venue = VENUE_COORDS[source]
    return [
        {
            "id": e["id"],
            "source": source,
            "name": e["name"],
            "venue": venue["name"],
            "date": e["date"],
            "time": e["time"],
            "lat": venue["lat"],
            "lng": venue["lng"],
            "category": category,
            "expected_attendance": attendance,
        }
        for e in schedule
        if today <= e["date"] <= cutoff
    ]


async def _fetch_ticketmaster_events(days: int) -> list[dict]:
    api_key = os.environ.get("TICKETMASTER_API_KEY", "")
    if not api_key:
        return []

    start = datetime.utcnow().strftime("%Y-%m-%dT00:00:00Z")
    end = (datetime.utcnow() + timedelta(days=days)).strftime("%Y-%m-%dT23:59:59Z")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://app.ticketmaster.com/discovery/v2/events.json",
                params={
                    "apikey": api_key,
                    "city": "Austin",
                    "stateCode": "TX",
                    "startDateTime": start,
                    "endDateTime": end,
                    "size": 50,
                    "sort": "date,asc",
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    parsed = [_parse_ticketmaster_event(e) for e in data.get("_embedded", {}).get("events", [])]
    return [e for e in parsed if e is not None]


def _parse_ticketmaster_event(raw: dict) -> dict | None:
    try:
        venues = raw.get("_embedded", {}).get("venues", [{}])
        venue = venues[0] if venues else {}
        loc = venue.get("location", {})
        lat = float(loc.get("latitude") or 0)
        lng = float(loc.get("longitude") or 0)
        if not lat or not lng:
            return None

        dates = raw.get("dates", {}).get("start", {})
        segment = (raw.get("classifications") or [{}])[0].get("segment", {}).get("name", "Other")
        if "Music" in segment:
            category = "Music"
        elif "Sports" in segment:
            category = "Sports"
        else:
            category = "Other"

        return {
            "id": raw.get("id", ""),
            "source": "ticketmaster",
            "name": raw.get("name", ""),
            "venue": venue.get("name", ""),
            "date": dates.get("localDate", ""),
            "time": dates.get("localTime", ""),
            "lat": lat,
            "lng": lng,
            "category": category,
            "expected_attendance": None,
        }
    except Exception:
        return None
```

- [ ] **Step 5: Create construction_service.py**

Create `backend/services/construction_service.py`:
```python
import httpx
from ..utils.cache import get_cache, set_cache
from ..utils.geojson_builder import build_feature_collection, build_point_feature

AUSTIN_311_URL = "https://data.austintexas.gov/resource/qyfh-gwei.json"
CACHE_KEY = "construction_zones"
CACHE_TTL = 3600  # 1 hour


async def fetch_construction_zones() -> dict:
    cached = get_cache(CACHE_KEY)
    if cached:
        return cached

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                AUSTIN_311_URL,
                params={
                    "$limit": 100,
                    "$where": "sr_type_desc='Roadway Work Zone' AND sr_status_desc='Open'",
                },
            )
            resp.raise_for_status()
            zones = resp.json()
        features = [f for z in zones for f in [_parse_zone(z)] if f]
    except Exception:
        features = []

    result = build_feature_collection(features)
    set_cache(CACHE_KEY, result, CACHE_TTL)
    return result


def _parse_zone(raw: dict) -> dict | None:
    try:
        loc = raw.get("location", {})
        lat = float(loc.get("latitude") or raw.get("latitude") or 0)
        lng = float(loc.get("longitude") or raw.get("longitude") or 0)
        if not lat or not lng:
            return None
        return build_point_feature(
            lat, lng,
            {
                "description": raw.get("sr_description", "Road Work"),
                "status": raw.get("sr_status_desc", "Open"),
                "created_date": raw.get("sr_created_date", ""),
                "closure_type": raw.get("sr_type_desc", "Roadway Work Zone"),
            },
        )
    except Exception:
        return None
```

- [ ] **Step 6: Write service unit tests**

Create `tests/test_services.py`:
```python
import pytest
from unittest.mock import patch, AsyncMock
from backend.services.txdot_service import fetch_live_traffic, fetch_incidents
from backend.services.weather_service import fetch_current_weather
from backend.services.events_service import fetch_upcoming_events
from backend.utils.cache import clear_cache


@pytest.mark.asyncio
async def test_fetch_live_traffic_falls_back_to_simulated():
    clear_cache("txdot_live")
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=Exception("network error")
        )
        result = await fetch_live_traffic()

    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 5  # one per corridor
    assert result["features"][0]["properties"]["segment_id"] == "i35_downtown"


@pytest.mark.asyncio
async def test_fetch_incidents_returns_empty_on_error():
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=Exception("network error")
        )
        result = await fetch_incidents()

    assert result["type"] == "FeatureCollection"
    assert result["features"] == []


@pytest.mark.asyncio
async def test_fetch_weather_falls_back_to_defaults():
    clear_cache("weather_current")
    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            side_effect=Exception("network error")
        )
        result = await fetch_current_weather()

    assert result["condition"] == "Clear"
    assert result["rain_alert"] is False
    assert result["temperature_f"] == 78.0


@pytest.mark.asyncio
async def test_fetch_events_returns_hardcoded_when_no_api_key():
    clear_cache("events_upcoming")
    import os
    os.environ.pop("TICKETMASTER_API_KEY", None)
    result = await fetch_upcoming_events(days=365)
    assert isinstance(result, list)
    sources = {e["source"] for e in result}
    assert "austin_fc" in sources or "ut_football" in sources
```

- [ ] **Step 7: Install pytest-asyncio and run tests**

```bash
pip install pytest-asyncio
pytest tests/test_services.py -v
```

Expected: 4 tests pass.

- [ ] **Step 8: Commit**

```bash
git add backend/services/ tests/test_services.py
git commit -m "feat: add backend services — TxDOT, Open-Meteo, Ticketmaster, Austin 311"
```

---

## Task 5: Backend API Routes

**Files:**
- Create: `backend/api/__init__.py`
- Create: `backend/api/dependencies.py`
- Create: `backend/api/routes/__init__.py`
- Create: `backend/api/routes/traffic.py`
- Create: `backend/api/routes/events.py`
- Create: `backend/api/routes/weather.py`

- [ ] **Step 1: Create api packages**

Create `backend/api/__init__.py`:
```python
```

Create `backend/api/routes/__init__.py`:
```python
```

- [ ] **Step 2: Create dependencies.py**

Create `backend/api/dependencies.py`:
```python
from ..db.database import get_db

__all__ = ["get_db"]
```

- [ ] **Step 3: Create traffic.py routes**

Create `backend/api/routes/traffic.py`:
```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ...api.dependencies import get_db
from ...db.queries import get_historical_traffic
from ...services.txdot_service import fetch_live_traffic, fetch_incidents
from ...utils.geojson_builder import build_feature_collection

router = APIRouter(prefix="/api/traffic", tags=["traffic"])


@router.get("/live")
async def get_live_traffic():
    """Live traffic speeds from TxDOT, cached 90 s."""
    return await fetch_live_traffic()


@router.get("/historical")
def get_historical(
    hour: int | None = Query(None, ge=0, le=23, description="Filter by hour of day (0–23)"),
    db: Session = Depends(get_db),
):
    """Historical traffic readings from the database, optionally filtered by hour."""
    features = get_historical_traffic(db, hour=hour)
    return build_feature_collection(features)


@router.get("/incidents")
async def get_incidents():
    """Active road incidents from TxDOT."""
    return await fetch_incidents()
```

- [ ] **Step 4: Create events.py routes**

Create `backend/api/routes/events.py`:
```python
from fastapi import APIRouter, Query
from ...services.events_service import fetch_upcoming_events

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("/upcoming")
async def get_upcoming_events(
    days: int = Query(30, ge=1, le=90, description="Number of days ahead to fetch")
):
    """Upcoming Austin events from Ticketmaster, Austin FC, and UT Athletics."""
    return await fetch_upcoming_events(days=days)
```

- [ ] **Step 5: Create weather.py routes**

Create `backend/api/routes/weather.py`:
```python
from fastapi import APIRouter
from ...services.weather_service import fetch_current_weather

router = APIRouter(prefix="/api/weather", tags=["weather"])


@router.get("/current")
async def get_current_weather():
    """Current Austin weather from Open-Meteo, cached 15 min."""
    return await fetch_current_weather()
```

- [ ] **Step 6: Commit**

```bash
git add backend/api/
git commit -m "feat: add API routes — /api/traffic, /api/events, /api/weather"
```

---

## Task 6: Backend Main App

**Files:**
- Create: `backend/main.py`

- [ ] **Step 1: Create main.py**

Create `backend/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.routes.traffic import router as traffic_router
from .api.routes.events import router as events_router
from .api.routes.weather import router as weather_router
from .db.database import engine
from .db import models

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Austin Traffic Intelligence API",
    description="Real-time traffic, events, and weather for Austin TX — feeds the kepler.gl map.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://*.netlify.app",
    ],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(traffic_router)
app.include_router(events_router)
app.include_router(weather_router)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 2: Smoke-test the backend**

```bash
uvicorn backend.main:app --reload --port 8000
```

Then in a separate terminal:
```bash
curl http://localhost:8000/health
# Expected: {"status":"ok"}

curl http://localhost:8000/api/traffic/live
# Expected: {"type":"FeatureCollection","features":[...5 corridor points...]}

curl http://localhost:8000/api/weather/current
# Expected: {"temperature_f":...,"condition":"Clear",...}

curl "http://localhost:8000/api/events/upcoming?days=365"
# Expected: [...list of Austin FC and UT football events...]
```

- [ ] **Step 3: Commit**

```bash
git add backend/main.py
git commit -m "feat: add FastAPI main app with CORS — all routes wired"
```

---

## Task 7: Backend Config Files

**Files:**
- Rewrite: `requirements.txt`
- Rewrite: `.env.example`
- Update: `alembic/env.py`

- [ ] **Step 1: Rewrite requirements.txt**

```
fastapi>=0.111
uvicorn[standard]>=0.30
sqlalchemy>=2.0
psycopg2-binary>=2.9
alembic>=1.13
httpx>=0.27
python-dotenv>=1.0
pydantic>=2.0
pytest>=8.0
pytest-asyncio>=0.23
```

- [ ] **Step 2: Rewrite .env.example**

```
# ── Backend .env ───────────────────────────────────────────────────────────────
DATABASE_URL=postgresql://user:password@localhost:5432/austin_traffic

# Optional — raises Austin 311 rate limit
SOCRATA_APP_TOKEN=

# Required for Ticketmaster events (free tier)
TICKETMASTER_API_KEY=

# Optional — TxDOT enhanced feed access
TXDOT_API_KEY=

# ── Frontend .env (place in frontend/.env) ─────────────────────────────────────
# REACT_APP_MAPBOX_TOKEN=your_mapbox_token_here
# REACT_APP_API_BASE_URL=http://localhost:8000
```

- [ ] **Step 3: Update alembic/env.py**

Open `alembic/env.py` and replace the `target_metadata` section with:

Find this block (exact wording varies, find the `target_metadata =` line and the import above it):
```python
# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = None
```

Replace with:
```python
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.db.database import Base  # noqa: E402
from backend.db import models  # noqa: F401, E402 — registers all ORM models

target_metadata = Base.metadata
```

Also ensure `load_dotenv()` is called near the top of `env.py` — find `from alembic import context` and add after it:
```python
from dotenv import load_dotenv
load_dotenv()
```

- [ ] **Step 4: Reinstall dependencies**

```bash
pip install -r requirements.txt
```

- [ ] **Step 5: Create new Alembic migration**

```bash
alembic revision --autogenerate -m "initial schema v2"
```

Then run it:
```bash
alembic upgrade head
```

Expected output: 6 tables created — `traffic_segments`, `historical_traffic`, `live_traffic_cache`, `traffic_incidents`, `events`, `weather_snapshots`.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .env.example alembic/
git commit -m "feat: update requirements, env template, Alembic migration for new schema"
```

---

## Task 8: Frontend Scaffold

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/public/index.html`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/src/index.css`

- [ ] **Step 1: Create frontend/package.json**

Create `frontend/package.json`:
```json
{
  "name": "austin-traffic-frontend",
  "version": "1.0.0",
  "private": true,
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-redux": "^9.1.0",
    "redux": "^5.0.1",
    "@kepler.gl/components": "^3.1.0",
    "@kepler.gl/reducers": "^3.1.0",
    "@kepler.gl/actions": "^3.1.0",
    "@kepler.gl/processors": "^3.1.0",
    "@kepler.gl/styles": "^3.1.0",
    "@kepler.gl/constants": "^3.1.0",
    "mapbox-gl": "^2.15.0",
    "date-fns": "^3.6.0",
    "axios": "^1.7.0"
  },
  "devDependencies": {
    "react-scripts": "5.0.1",
    "tailwindcss": "^3.4.0",
    "autoprefixer": "^10.4.0",
    "postcss": "^8.4.0"
  },
  "scripts": {
    "start": "react-scripts start",
    "build": "react-scripts build",
    "test": "react-scripts test --watchAll=false"
  },
  "browserslist": {
    "production": [">0.2%", "not dead", "not op_mini all"],
    "development": ["last 1 chrome version", "last 1 firefox version", "last 1 safari version"]
  }
}
```

- [ ] **Step 2: Create public/index.html**

Create `frontend/public/index.html`:
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Austin Traffic Intelligence</title>
</head>
<body>
  <div id="root"></div>
</body>
</html>
```

- [ ] **Step 3: Create tailwind.config.js**

Create `frontend/tailwind.config.js`:
```js
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        'gray-850': '#1a1f2e',
        'gray-950': '#0d1117',
      },
    },
  },
  plugins: [],
};
```

- [ ] **Step 4: Create postcss.config.js**

Create `frontend/postcss.config.js`:
```js
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 5: Create src/index.css**

Create `frontend/src/index.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

*, *::before, *::after {
  box-sizing: border-box;
}

html, body, #root {
  height: 100%;
  width: 100%;
  margin: 0;
  padding: 0;
  overflow: hidden;
  background-color: #0d1117;
}
```

- [ ] **Step 6: Install dependencies**

```bash
cd frontend
npm install
```

Expected: `node_modules/` created, no errors.

- [ ] **Step 7: Commit**

```bash
cd ..
git add frontend/package.json frontend/public/ frontend/tailwind.config.js frontend/postcss.config.js frontend/src/index.css
git commit -m "feat: scaffold React frontend — package.json, Tailwind, HTML shell"
```

---

## Task 9: Frontend Redux Store

**Files:**
- Create: `frontend/src/store.js`
- Create: `frontend/src/index.js`

- [ ] **Step 1: Create store.js**

Create `frontend/src/store.js`:
```js
import { createStore, combineReducers, applyMiddleware, compose } from 'redux';
import keplerGlReducer from '@kepler.gl/reducers';
import { enhanceReduxMiddleware } from '@kepler.gl/middleware';

const reducers = combineReducers({
  keplerGl: keplerGlReducer,
});

const middlewares = enhanceReduxMiddleware([]);

const composeEnhancers =
  (typeof window !== 'undefined' && window.__REDUX_DEVTOOLS_EXTENSION_COMPOSE__) || compose;

const store = createStore(
  reducers,
  {},
  composeEnhancers(applyMiddleware(...middlewares))
);

export default store;
```

- [ ] **Step 2: Create index.js**

Create `frontend/src/index.js`:
```jsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import { Provider } from 'react-redux';
import store from './store';
import App from './App';
import './index.css';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <Provider store={store}>
    <App />
  </Provider>
);
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/store.js frontend/src/index.js
git commit -m "feat: add Redux store with keplerGl reducer"
```

---

## Task 10: Frontend Constants & Utils

**Files:**
- Create: `frontend/src/constants/austinBounds.js`
- Create: `frontend/src/utils/colorScales.js`
- Create: `frontend/src/utils/geoHelpers.js`

- [ ] **Step 1: Create austinBounds.js**

Create `frontend/src/constants/austinBounds.js`:
```js
export const AUSTIN_CENTER = { lat: 30.2672, lng: -97.7431 };
export const AUSTIN_ZOOM = 11;
export const AUSTIN_BBOX = [-97.9, 30.1, -97.5, 30.5];

export const VENUES = [
  { id: 'dkr',        name: 'DKR Memorial Stadium',     lat: 30.2836, lng: -97.7320, type: 'sports'  },
  { id: 'q2',         name: 'Q2 Stadium',                lat: 30.3872, lng: -97.7188, type: 'sports'  },
  { id: 'moody',      name: 'Moody Center',              lat: 30.2850, lng: -97.7280, type: 'music'   },
  { id: 'stubbs',     name: "Stubb's Amphitheater",      lat: 30.2680, lng: -97.7336, type: 'music'   },
  { id: 'acl_live',   name: 'ACL Live at Moody Theater', lat: 30.2639, lng: -97.7467, type: 'music'   },
  { id: 'convention', name: 'Austin Convention Center',  lat: 30.2628, lng: -97.7402, type: 'festival'},
  { id: 'cota',       name: 'Circuit of the Americas',   lat: 30.1328, lng: -97.6411, type: 'sports'  },
];
```

- [ ] **Step 2: Create colorScales.js**

Create `frontend/src/utils/colorScales.js`:
```js
export const CONGESTION_COLORS = {
  green:   '#22c55e',
  yellow:  '#eab308',
  red:     '#ef4444',
  unknown: '#6b7280',
};

export function speedToColor(speedMph, freeFlowMph) {
  if (!freeFlowMph || freeFlowMph <= 0) return CONGESTION_COLORS.unknown;
  const ratio = speedMph / freeFlowMph;
  if (ratio >= 0.75) return CONGESTION_COLORS.green;
  if (ratio >= 0.50) return CONGESTION_COLORS.yellow;
  return CONGESTION_COLORS.red;
}

export function speedToRgb(speedMph, freeFlowMph) {
  const hex = speedToColor(speedMph, freeFlowMph).slice(1);
  return [
    parseInt(hex.slice(0, 2), 16),
    parseInt(hex.slice(2, 4), 16),
    parseInt(hex.slice(4, 6), 16),
  ];
}
```

- [ ] **Step 3: Create geoHelpers.js**

Create `frontend/src/utils/geoHelpers.js`:
```js
export function featureCollectionToKeplerDataset(geojson, id, label) {
  return {
    info: { id, label },
    data: geojson,
  };
}

export function eventsToGeoJSON(events) {
  return {
    type: 'FeatureCollection',
    features: events.map(event => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [event.lng, event.lat] },
      properties: {
        id: event.id,
        name: event.name,
        venue: event.venue,
        date: event.date,
        time: event.time,
        category: event.category,
      },
    })),
  };
}

export function venuesToGeoJSON(venues) {
  return {
    type: 'FeatureCollection',
    features: venues.map(v => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [v.lng, v.lat] },
      properties: { id: v.id, name: v.name, type: v.type },
    })),
  };
}
```

- [ ] **Step 4: Write JS unit tests**

Create `frontend/src/utils/__tests__/colorScales.test.js`:
```js
import { speedToColor, CONGESTION_COLORS } from '../colorScales';

test('returns green when speed is 75% or more of free flow', () => {
  expect(speedToColor(50, 60)).toBe(CONGESTION_COLORS.green);
});

test('returns yellow when speed is between 50% and 75% of free flow', () => {
  expect(speedToColor(35, 60)).toBe(CONGESTION_COLORS.yellow);
});

test('returns red when speed is under 50% of free flow', () => {
  expect(speedToColor(20, 60)).toBe(CONGESTION_COLORS.red);
});

test('returns unknown when free flow is zero', () => {
  expect(speedToColor(30, 0)).toBe(CONGESTION_COLORS.unknown);
});
```

Create `frontend/src/utils/__tests__/geoHelpers.test.js`:
```js
import { venuesToGeoJSON, eventsToGeoJSON, featureCollectionToKeplerDataset } from '../geoHelpers';

const mockVenue = { id: 'v1', name: 'Test Venue', lat: 30.2, lng: -97.7, type: 'music' };
const mockEvent = { id: 'e1', name: 'Concert', venue: 'Test', date: '2026-07-01', time: '20:00', category: 'Music', lat: 30.2, lng: -97.7 };

test('venuesToGeoJSON produces valid FeatureCollection', () => {
  const fc = venuesToGeoJSON([mockVenue]);
  expect(fc.type).toBe('FeatureCollection');
  expect(fc.features[0].geometry.coordinates).toEqual([-97.7, 30.2]);
});

test('eventsToGeoJSON produces valid FeatureCollection', () => {
  const fc = eventsToGeoJSON([mockEvent]);
  expect(fc.features[0].properties.name).toBe('Concert');
});

test('featureCollectionToKeplerDataset returns kepler dataset shape', () => {
  const fc = venuesToGeoJSON([mockVenue]);
  const ds = featureCollectionToKeplerDataset(fc, 'test-id', 'Test Label');
  expect(ds.info.id).toBe('test-id');
  expect(ds.info.label).toBe('Test Label');
  expect(ds.data).toBe(fc);
});
```

- [ ] **Step 5: Run frontend unit tests**

```bash
cd frontend
npm test -- --watchAll=false
```

Expected: 7 tests pass.

- [ ] **Step 6: Commit**

```bash
cd ..
git add frontend/src/constants/ frontend/src/utils/
git commit -m "feat: add frontend constants, color scales, and GeoJSON helpers"
```

---

## Task 11: Frontend API Services

**Files:**
- Create: `frontend/src/services/api.js`
- Create: `frontend/src/services/trafficService.js`
- Create: `frontend/src/services/eventsService.js`
- Create: `frontend/.env`

- [ ] **Step 1: Create frontend/.env**

Create `frontend/.env`:
```
REACT_APP_MAPBOX_TOKEN=your_mapbox_token_here
REACT_APP_API_BASE_URL=http://localhost:8000
```

> Note: Replace `your_mapbox_token_here` with your actual Mapbox public token. Get one at mapbox.com/account/access-tokens.

- [ ] **Step 2: Create api.js**

Create `frontend/src/services/api.js`:
```js
import axios from 'axios';

const BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 10000,
});

export default api;
```

- [ ] **Step 3: Create trafficService.js**

Create `frontend/src/services/trafficService.js`:
```js
import api from './api';

export async function fetchLiveTraffic() {
  const { data } = await api.get('/api/traffic/live');
  return data;
}

export async function fetchHistoricalTraffic(hour) {
  const params = hour !== undefined ? { hour } : {};
  const { data } = await api.get('/api/traffic/historical', { params });
  return data;
}

export async function fetchIncidents() {
  const { data } = await api.get('/api/traffic/incidents');
  return data;
}
```

- [ ] **Step 4: Create eventsService.js**

Create `frontend/src/services/eventsService.js`:
```js
import api from './api';

export async function fetchUpcomingEvents(days = 30) {
  const { data } = await api.get('/api/events/upcoming', { params: { days } });
  return data;
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/services/ frontend/.env
git commit -m "feat: add frontend API service layer — axios instance, traffic, events"
```

---

## Task 12: Frontend Hooks

**Files:**
- Create: `frontend/src/hooks/useTrafficData.js`
- Create: `frontend/src/hooks/useEvents.js`
- Create: `frontend/src/hooks/useWeather.js`

- [ ] **Step 1: Create useTrafficData.js**

Create `frontend/src/hooks/useTrafficData.js`:
```js
import { useEffect, useState, useCallback } from 'react';
import { useDispatch } from 'react-redux';
import { addDataToMap } from '@kepler.gl/actions';
import { fetchLiveTraffic, fetchHistoricalTraffic, fetchIncidents } from '../services/trafficService';
import { featureCollectionToKeplerDataset } from '../utils/geoHelpers';

const POLL_INTERVAL_MS = 2 * 60 * 1000; // 2 minutes

export function useTrafficData(layerVisibility) {
  const dispatch = useDispatch();
  const [isLoading, setIsLoading] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [live, historical, incidents] = await Promise.all([
        layerVisibility.live      ? fetchLiveTraffic()       : null,
        layerVisibility.historical ? fetchHistoricalTraffic() : null,
        layerVisibility.incidents  ? fetchIncidents()         : null,
      ]);

      const datasets = [];
      if (live)       datasets.push(featureCollectionToKeplerDataset(live,       'live-traffic',       'Live Traffic'));
      if (historical) datasets.push(featureCollectionToKeplerDataset(historical, 'historical-traffic', 'Historical Traffic'));
      if (incidents)  datasets.push(featureCollectionToKeplerDataset(incidents,  'incidents',          'Incidents'));

      if (datasets.length > 0) {
        dispatch(addDataToMap({ datasets, options: { centerMap: false } }));
      }
      setLastUpdated(new Date());
    } catch (err) {
      console.error('[useTrafficData] Failed to load traffic data', err);
    } finally {
      setIsLoading(false);
    }
  }, [dispatch, layerVisibility.live, layerVisibility.historical, layerVisibility.incidents]);

  useEffect(() => {
    loadData();
    const id = setInterval(loadData, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [loadData]);

  return { isLoading, lastUpdated };
}
```

- [ ] **Step 2: Create useEvents.js**

Create `frontend/src/hooks/useEvents.js`:
```js
import { useState, useEffect } from 'react';
import { fetchUpcomingEvents } from '../services/eventsService';

export function useEvents() {
  const [events, setEvents] = useState([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    setIsLoading(true);
    fetchUpcomingEvents(30)
      .then(setEvents)
      .catch(err => console.error('[useEvents] Failed to load events', err))
      .finally(() => setIsLoading(false));
  }, []);

  return { events, isLoading };
}
```

- [ ] **Step 3: Create useWeather.js**

Create `frontend/src/hooks/useWeather.js`:
```js
import { useState, useEffect } from 'react';
import api from '../services/api';

const POLL_INTERVAL_MS = 15 * 60 * 1000; // 15 minutes

export function useWeather() {
  const [weather, setWeather] = useState(null);

  useEffect(() => {
    const load = () => {
      api.get('/api/weather/current')
        .then(({ data }) => setWeather(data))
        .catch(err => console.error('[useWeather] Failed to load weather', err));
    };
    load();
    const id = setInterval(load, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, []);

  return { weather };
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/
git commit -m "feat: add React hooks — useTrafficData (2-min poll), useEvents, useWeather"
```

---

## Task 13: Frontend Components

**Files:**
- Create: `frontend/src/components/MapContainer.jsx`
- Create: `frontend/src/components/Sidebar.jsx`
- Create: `frontend/src/components/EventCard.jsx`
- Create: `frontend/src/components/LayerToggle.jsx`
- Create: `frontend/src/components/TrafficLegend.jsx`
- Create: `frontend/src/components/LoadingOverlay.jsx`

- [ ] **Step 1: Create MapContainer.jsx**

Create `frontend/src/components/MapContainer.jsx`:
```jsx
import React, { useEffect } from 'react';
import { connect } from 'react-redux';
import KeplerGl from '@kepler.gl/components';
import { addDataToMap } from '@kepler.gl/actions';
import { venuesToGeoJSON, featureCollectionToKeplerDataset } from '../utils/geoHelpers';
import { AUSTIN_CENTER, AUSTIN_ZOOM, VENUES } from '../constants/austinBounds';

const MAPBOX_TOKEN = process.env.REACT_APP_MAPBOX_TOKEN;
const SIDEBAR_WIDTH = 320;

function MapContainer({ dispatch, selectedVenue }) {
  useEffect(() => {
    const venueGeoJSON = venuesToGeoJSON(VENUES);
    dispatch(addDataToMap({
      datasets: [featureCollectionToKeplerDataset(venueGeoJSON, 'venues', 'Venues')],
      options: { centerMap: true },
      config: {
        mapState: {
          latitude: AUSTIN_CENTER.lat,
          longitude: AUSTIN_CENTER.lng,
          zoom: AUSTIN_ZOOM,
        },
        mapStyle: { styleType: 'dark' },
      },
    }));
  }, [dispatch]);

  return (
    <KeplerGl
      id="austin-traffic"
      mapboxApiAccessToken={MAPBOX_TOKEN}
      width={window.innerWidth - SIDEBAR_WIDTH}
      height={window.innerHeight}
    />
  );
}

const mapStateToProps = state => ({ keplerGl: state.keplerGl });
export default connect(mapStateToProps)(MapContainer);
```

- [ ] **Step 2: Create EventCard.jsx**

Create `frontend/src/components/EventCard.jsx`:
```jsx
import React from 'react';
import { format, parseISO } from 'date-fns';

const CATEGORY_COLORS = {
  Sports:  'bg-blue-600',
  Music:   'bg-purple-600',
  Festival:'bg-orange-600',
  Other:   'bg-gray-600',
};

function EventCard({ event, onClick }) {
  const dateStr = event.date ? format(parseISO(event.date), 'MMM d') : '';
  const badgeClass = CATEGORY_COLORS[event.category] || CATEGORY_COLORS.Other;

  return (
    <button
      onClick={onClick}
      className="w-full text-left mb-2 p-2 rounded bg-gray-800 hover:bg-gray-750 transition-colors focus:outline-none focus:ring-1 focus:ring-blue-500"
    >
      <div className="flex items-start gap-2">
        <span className={`mt-0.5 px-1.5 py-0.5 rounded text-white text-xs font-medium flex-shrink-0 ${badgeClass}`}>
          {event.category}
        </span>
        <div className="min-w-0">
          <p className="text-white text-sm font-medium truncate">{event.name}</p>
          <p className="text-gray-400 text-xs truncate">{event.venue}</p>
          <p className="text-gray-500 text-xs">
            {dateStr}{event.time ? ` · ${event.time}` : ''}
          </p>
        </div>
      </div>
    </button>
  );
}

export default EventCard;
```

- [ ] **Step 3: Create LayerToggle.jsx**

Create `frontend/src/components/LayerToggle.jsx`:
```jsx
import React from 'react';

const LAYER_LABELS = {
  historical: 'Historical Traffic',
  live:       'Live Traffic',
  incidents:  'Incidents',
  venues:     'Venues',
};

function LayerToggle({ layers, onToggle }) {
  return (
    <div className="space-y-1.5">
      {Object.entries(layers).map(([key, visible]) => (
        <button
          key={key}
          onClick={() => onToggle(key)}
          className="flex items-center justify-between w-full py-0.5 focus:outline-none"
        >
          <span className={`text-sm transition-colors ${visible ? 'text-white' : 'text-gray-500'}`}>
            {LAYER_LABELS[key]}
          </span>
          <span
            className={`w-8 h-4 rounded-full transition-colors ${visible ? 'bg-blue-500' : 'bg-gray-700'}`}
          />
        </button>
      ))}
    </div>
  );
}

export default LayerToggle;
```

- [ ] **Step 4: Create TrafficLegend.jsx**

Create `frontend/src/components/TrafficLegend.jsx`:
```jsx
import React from 'react';

function TrafficLegend() {
  return (
    <div>
      <h3 className="text-gray-400 text-xs font-semibold uppercase tracking-wide mb-2">
        Speed Legend
      </h3>
      <div className="space-y-1.5">
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-green-500 flex-shrink-0" />
          <span className="text-gray-300 text-xs">Free flow (&gt;45 mph)</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-yellow-500 flex-shrink-0" />
          <span className="text-gray-300 text-xs">Moderate (25–45 mph)</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-full bg-red-500 flex-shrink-0" />
          <span className="text-gray-300 text-xs">Congested (&lt;25 mph)</span>
        </div>
      </div>
    </div>
  );
}

export default TrafficLegend;
```

- [ ] **Step 5: Create LoadingOverlay.jsx**

Create `frontend/src/components/LoadingOverlay.jsx`:
```jsx
import React from 'react';

function LoadingOverlay() {
  return (
    <div className="absolute top-4 right-4 bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 flex items-center gap-2 z-10">
      <span className="w-2 h-2 bg-blue-400 rounded-full animate-pulse" />
      <span className="text-gray-300 text-sm">Updating traffic…</span>
    </div>
  );
}

export default LoadingOverlay;
```

- [ ] **Step 6: Create Sidebar.jsx**

Create `frontend/src/components/Sidebar.jsx`:
```jsx
import React from 'react';
import { format } from 'date-fns';
import EventCard from './EventCard';
import LayerToggle from './LayerToggle';
import TrafficLegend from './TrafficLegend';

function Sidebar({ events, weather, layerVisibility, onLayerToggle, onEventClick, lastUpdated }) {
  const today = format(new Date(), 'yyyy-MM-dd');
  const todayEvents    = events.filter(e => e.date === today);
  const upcomingEvents = events.filter(e => e.date > today);

  return (
    <div className="w-80 h-screen bg-gray-900 border-r border-gray-800 flex flex-col overflow-hidden flex-shrink-0">
      {/* Header */}
      <div className="p-4 border-b border-gray-800">
        <h1 className="text-white font-bold text-lg leading-tight">Austin Traffic Intelligence</h1>
        {lastUpdated && (
          <p className="text-gray-500 text-xs mt-0.5">
            Updated {format(lastUpdated, 'h:mm a')}
          </p>
        )}
      </div>

      {/* Weather strip */}
      {weather && (
        <div className="px-4 py-2 border-b border-gray-800 bg-gray-850">
          <div className="flex items-center justify-between">
            <span className="text-gray-300 text-sm">{weather.condition}</span>
            <span className="text-white text-sm font-medium">
              {weather.temperature_f != null ? `${Math.round(weather.temperature_f)}°F` : '—'}
            </span>
          </div>
          {weather.rain_alert && (
            <p className="text-yellow-400 text-xs mt-0.5">Rain detected — expect delays</p>
          )}
        </div>
      )}

      {/* Layer toggles */}
      <div className="px-4 py-3 border-b border-gray-800">
        <h2 className="text-gray-400 text-xs font-semibold uppercase tracking-wide mb-2">Layers</h2>
        <LayerToggle layers={layerVisibility} onToggle={onLayerToggle} />
      </div>

      {/* Events list */}
      <div className="flex-1 overflow-y-auto">
        {todayEvents.length > 0 && (
          <div className="px-4 pt-3 pb-1">
            <h2 className="text-yellow-400 text-xs font-semibold uppercase tracking-wide mb-2">
              Today ({todayEvents.length})
            </h2>
            {todayEvents.map(event => (
              <EventCard key={event.id} event={event} onClick={() => onEventClick(event)} />
            ))}
          </div>
        )}

        <div className="px-4 pt-3 pb-2">
          <h2 className="text-gray-400 text-xs font-semibold uppercase tracking-wide mb-2">
            Upcoming ({upcomingEvents.length})
          </h2>
          {upcomingEvents.length === 0 && (
            <p className="text-gray-600 text-xs">No events in the next 30 days.</p>
          )}
          {upcomingEvents.slice(0, 25).map(event => (
            <EventCard key={event.id} event={event} onClick={() => onEventClick(event)} />
          ))}
        </div>
      </div>

      {/* Legend */}
      <div className="p-4 border-t border-gray-800">
        <TrafficLegend />
      </div>
    </div>
  );
}

export default Sidebar;
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/
git commit -m "feat: add all React components — MapContainer, Sidebar, EventCard, LayerToggle, TrafficLegend, LoadingOverlay"
```

---

## Task 14: Frontend App.js + Wiring

**Files:**
- Create: `frontend/src/App.js`

- [ ] **Step 1: Create App.js**

Create `frontend/src/App.js`:
```jsx
import React, { useState } from 'react';
import MapContainer from './components/MapContainer';
import Sidebar from './components/Sidebar';
import LoadingOverlay from './components/LoadingOverlay';
import { useTrafficData } from './hooks/useTrafficData';
import { useEvents } from './hooks/useEvents';
import { useWeather } from './hooks/useWeather';

const DEFAULT_LAYERS = {
  historical: true,
  live:       true,
  incidents:  true,
  venues:     true,
};

function App() {
  const [layerVisibility, setLayerVisibility] = useState(DEFAULT_LAYERS);
  const [selectedVenue, setSelectedVenue] = useState(null);

  const { isLoading, lastUpdated } = useTrafficData(layerVisibility);
  const { events } = useEvents();
  const { weather } = useWeather();

  function handleLayerToggle(key) {
    setLayerVisibility(prev => ({ ...prev, [key]: !prev[key] }));
  }

  return (
    <div className="flex h-screen w-screen overflow-hidden">
      <Sidebar
        events={events}
        weather={weather}
        layerVisibility={layerVisibility}
        onLayerToggle={handleLayerToggle}
        onEventClick={setSelectedVenue}
        lastUpdated={lastUpdated}
      />
      <div className="flex-1 relative">
        <MapContainer selectedVenue={selectedVenue} />
        {isLoading && <LoadingOverlay />}
      </div>
    </div>
  );
}

export default App;
```

- [ ] **Step 2: Run the frontend**

In one terminal, start the backend:
```bash
uvicorn backend.main:app --reload --port 8000
```

In another terminal:
```bash
cd frontend
npm start
```

Expected: Browser opens at `http://localhost:3000`. You should see:
- A dark sidebar on the left (320px) with weather strip, layer toggles, events section, legend
- A full-height kepler.gl map on the right, centered on Austin
- The backend serving data (check browser Network tab for `/api/traffic/live` 200 responses)

- [ ] **Step 3: Commit**

```bash
cd ..
git add frontend/src/App.js
git commit -m "feat: wire App.js — integrates all hooks, sidebar, map container"
```

---

## Task 15: Update Docs and Config

**Files:**
- Rewrite: `CLAUDE.md`
- Update: `.gitignore`
- Rewrite: `README.md`

- [ ] **Step 1: Update .gitignore**

Open `.gitignore` and add/confirm these entries:
```gitignore
# Python
__pycache__/
*.pyc
*.pyo
.env
*.db
.pytest_cache/

# Node / React
frontend/node_modules/
frontend/build/
frontend/.env
frontend/.env.local
frontend/.env.production

# Misc
.DS_Store
*.log
```

- [ ] **Step 2: Rewrite CLAUDE.md**

Replace the entire content of `CLAUDE.md` with:
```markdown
# Austin Traffic Intelligence Platform

React 18 + kepler.gl frontend with a FastAPI backend. Visualizes real-time Austin traffic, events, and weather on an interactive map.

## Stack

- **Frontend:** React 18, Redux, @kepler.gl/components v3, Mapbox GL JS, Tailwind CSS, Axios
- **Backend:** FastAPI, SQLAlchemy 2.0, PostgreSQL, Alembic, httpx
- **Data:** TxDOT (traffic + incidents), Open-Meteo (weather, free), Ticketmaster (events), Austin 311 (construction)

## Structure

```
frontend/src/
  store.js                  Redux store — keplerGl reducer
  App.js                    Layout orchestrator (sidebar + map)
  constants/austinBounds.js Map center, zoom, venue definitions
  utils/colorScales.js      Speed → color mapping
  utils/geoHelpers.js       GeoJSON formatting for kepler.gl datasets
  services/api.js           Axios instance (REACT_APP_API_BASE_URL)
  hooks/useTrafficData.js   Polls /api/traffic/live every 2 min, dispatches addDataToMap
  hooks/useEvents.js        Fetches /api/events/upcoming
  hooks/useWeather.js       Fetches /api/weather/current every 15 min
  components/MapContainer   kepler.gl wrapper + venue layer on mount
  components/Sidebar        Events calendar + weather + layer toggles + legend

backend/
  main.py                   FastAPI app — CORS, router mounting
  api/routes/traffic.py     GET /api/traffic/live|historical|incidents
  api/routes/events.py      GET /api/events/upcoming?days=30
  api/routes/weather.py     GET /api/weather/current
  db/models.py              SQLAlchemy models (fresh schema)
  services/txdot_service.py TxDOT live traffic + incidents (simulated fallback)
  services/weather_service  Open-Meteo (simulated fallback)
  services/events_service   Ticketmaster + Austin FC + UT hardcoded schedules
  utils/cache.py            In-memory TTL cache (no Redis dependency)
  utils/geojson_builder.py  Row → GeoJSON feature helpers
```

## Environment Variables

**backend/.env** (at project root):
```
DATABASE_URL=postgresql://user:password@localhost:5432/austin_traffic
TICKETMASTER_API_KEY=
SOCRATA_APP_TOKEN=
```

**frontend/.env** (inside frontend/):
```
REACT_APP_MAPBOX_TOKEN=your_mapbox_token_here
REACT_APP_API_BASE_URL=http://localhost:8000
```

## Commands

| Task | Command |
|------|---------|
| Start backend | `uvicorn backend.main:app --reload` |
| Start frontend | `cd frontend && npm start` |
| Run DB migrations | `alembic upgrade head` |
| Run Python tests | `pytest` |
| Run JS tests | `cd frontend && npm test` |
| Install Python deps | `pip install -r requirements.txt` |
| Install JS deps | `cd frontend && npm install` |

## Data Sources

| Source | Endpoint | Key Required |
|--------|----------|-------------|
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
- Layer visibility is owned by React state in App.js — toggling re-triggers the hooks
```

- [ ] **Step 3: Commit all doc changes**

```bash
git add CLAUDE.md .gitignore README.md
git commit -m "docs: rewrite CLAUDE.md and .gitignore for new React+kepler.gl stack"
```

---

## Verification Checklist

After all tasks are complete:

- [ ] `uvicorn backend.main:app --reload` starts without errors
- [ ] `GET /health` returns `{"status":"ok"}`
- [ ] `GET /api/traffic/live` returns GeoJSON FeatureCollection with 5 corridor features
- [ ] `GET /api/weather/current` returns JSON with `condition`, `temperature_f`, `rain_alert`
- [ ] `GET /api/events/upcoming?days=365` returns at least Austin FC and UT Football events
- [ ] `GET /api/traffic/incidents` returns GeoJSON FeatureCollection (empty ok if TxDOT unreachable)
- [ ] `cd frontend && npm start` opens browser at localhost:3000 without compile errors
- [ ] Sidebar visible on left, kepler.gl map visible on right, centered on Austin
- [ ] Weather strip appears at top of sidebar
- [ ] Layer toggles visible and clickable
- [ ] Events list populated in sidebar
- [ ] Traffic legend visible at bottom of sidebar
- [ ] Loading overlay appears briefly then disappears
- [ ] `pytest` passes (backend unit tests)
- [ ] `cd frontend && npm test` passes (frontend unit tests)
- [ ] `alembic upgrade head` applies migration cleanly
