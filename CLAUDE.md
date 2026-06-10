# Austin Traffic Intelligence Platform

React 18 + kepler.gl frontend with a FastAPI backend. Visualizes real-time Austin traffic, events, and weather on an interactive Mapbox map.

## Stack

- **Frontend:** React 18, Redux, @kepler.gl/components v3, Mapbox GL JS, Tailwind CSS, Axios
- **Backend:** FastAPI, SQLAlchemy 2.0, PostgreSQL, Alembic, httpx
- **Data:** TxDOT (traffic + incidents), Open-Meteo (weather, free, no key), Ticketmaster (events), Austin 311 (construction)

## Project Structure (in progress — React migration)

```
frontend/              React 18 + kepler.gl app (being built)
backend/               FastAPI backend (being restructured)
  main.py              FastAPI entry point
  api/routes/          /api/traffic, /api/events, /api/weather
  db/                  SQLAlchemy models + queries
  services/            TxDOT, Open-Meteo, Ticketmaster, Austin 311
  utils/               GeoJSON builder + in-memory TTL cache
data/geo/              Static Austin GeoJSON (venues, corridors, hotspots)
notebooks/             Phase 2: ML model training (placeholder)
alembic/               DB migrations
```

## Environment Variables

**Backend (.env at project root):**

```
DATABASE_URL=postgresql://user:password@localhost:5432/austin_traffic
TICKETMASTER_API_KEY=
SOCRATA_APP_TOKEN=
```

**Frontend (frontend/.env):**

```
REACT_APP_MAPBOX_TOKEN=your_mapbox_token_here
REACT_APP_API_BASE_URL=http://localhost:8000
```

## Commands

| Task | Command |
| ---- | ------- |
| Start backend | `uvicorn backend.main:app --reload` |
| Start frontend | `cd frontend && npm start` |
| Run DB migrations | `alembic upgrade head` |
| Run Python tests | `pytest` |
| Run JS tests | `cd frontend && npm test` |

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
