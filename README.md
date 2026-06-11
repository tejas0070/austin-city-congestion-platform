# Austin Traffic Intelligence Platform

Real-time Austin TX traffic visualized on an interactive kepler.gl map with events and weather overlays.

## Stack

| Layer    | Technology                                          |
| -------- | --------------------------------------------------- |
| Frontend | React 18, Redux, kepler.gl v3, Tailwind CSS, Axios  |
| Backend  | FastAPI, SQLAlchemy 2.0, PostgreSQL, Alembic, httpx |
| Data     | TxDOT, Open-Meteo, Ticketmaster, Austin 311         |
| Build    | CRACO (CRA 5 + webpack polyfills)                   |

## Quick Start

### Prerequisites

- Python 3.11+
- Node 18+
- PostgreSQL (local or Supabase)

### Backend

```bash
cd austin-city-congestion-platform
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # fill in DATABASE_URL and any API keys
alembic upgrade head
uvicorn backend.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
# copy .env.example values to frontend/.env and set REACT_APP_MAPBOX_TOKEN
npm start
```

App opens at <http://localhost:3000>, API at <http://localhost:8000>.

## Environment Variables

**Backend (`.env` at project root):**

| Variable                | Required | Description                     |
| ----------------------- | -------- | ------------------------------- |
| `DATABASE_URL`          | Yes      | PostgreSQL connection string    |
| `TICKETMASTER_API_KEY`  | No       | Events (free tier)              |
| `SOCRATA_APP_TOKEN`     | No       | Austin 311 rate limit token     |

**Frontend (`frontend/.env`):**

| Variable                  | Required | Description                          |
| ------------------------- | -------- | ------------------------------------ |
| `REACT_APP_MAPBOX_TOKEN`  | Yes\*    | Mapbox token for kepler.gl basemap   |
| `REACT_APP_API_BASE_URL`  | No       | Defaults to <http://localhost:8000>  |

\*kepler.gl renders without a token but shows a blank basemap.

## Features

- Live traffic layer (TxDOT, refreshes every 2 min)
- Historical traffic layer by time of day
- Incident markers
- Venue pins with event details
- Events calendar sidebar
- Weather widget
- Layer toggle controls

## Data Sources

- **TxDOT** — live traffic speeds and incidents
- **Open-Meteo** — current weather (free, no key required)
- **Ticketmaster** — concerts and events
- **Austin 311** — roadway work zones

## Deployment

- **Frontend:** `npm run build` in `frontend/`, deploy `build/` to Netlify
- **Backend:** Deploy to Render/Railway with `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
- **Database:** Supabase free tier — set `DATABASE_URL` in environment

## Tests

```bash
# Backend
pytest

# Frontend utils
cd frontend && npm test
```
