# Austin Traffic Intelligence Platform

React 18 + kepler.gl frontend with a FastAPI backend. Visualizes real-time Austin traffic, events, and weather on an interactive Mapbox map.

## Stack

- **Frontend:** React 18, Redux, @kepler.gl/components v3, Mapbox GL JS, Tailwind CSS, Axios
- **Backend:** FastAPI, SQLAlchemy 2.0, PostgreSQL, Alembic, httpx
- **Data:** TxDOT (traffic + incidents), Open-Meteo (weather, free, no key), Ticketmaster (events), Austin 311 (construction)
- **Build:** CRACO (CRA 5 + webpack polyfills for kepler.gl)

## Project Structure

```
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
| Build frontend | `cd frontend && npm run build` |

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
