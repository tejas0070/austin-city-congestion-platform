# Austin Traffic Intelligence Platform

Real-time Austin TX traffic visualized on an interactive kepler.gl map with events and weather overlays.

## Stack

| Layer    | Technology                                           |
| -------- | ---------------------------------------------------- |
| Frontend | React 18, Redux, kepler.gl v3, Tailwind CSS, Axios   |
| Backend  | FastAPI, SQLAlchemy 2.0, PostgreSQL, Alembic, httpx  |
| Map      | MapLibre GL JS + Carto Dark Matter (no token needed) |
| Data     | TxDOT, Open-Meteo, Ticketmaster, Austin 311          |
| Build    | CRACO (CRA 5 + webpack polyfills)                    |

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
cp .env.example frontend/.env   # no Mapbox token needed
npm start
```

App opens at <http://localhost:3000>, API at <http://localhost:8000>.

## Environment Variables

**Backend (`.env` at project root):**

| Variable               | Required | Description                  |
| ---------------------- | -------- | ---------------------------- |
| `DATABASE_URL`         | Yes      | PostgreSQL connection string |
| `TICKETMASTER_API_KEY` | No       | Events (free tier)           |
| `SOCRATA_APP_TOKEN`    | No       | Austin 311 rate limit token  |

**Frontend (`frontend/.env`):**

| Variable                 | Required | Description                         |
| ------------------------ | -------- | ----------------------------------- |
| `REACT_APP_API_BASE_URL` | No       | Defaults to <http://localhost:8000> |

> No Mapbox token required. The map uses MapLibre GL JS with the Carto Dark
> Matter style, which is completely free with no API key.

## Features

- Live traffic corridors color-coded green → yellow → red by congestion index
- Baseline and predicted (+2 h) corridor layers
- Live traffic speeds from TxDOT (refreshes every 2 min)
- Incident markers
- Venue pins with event details
- Events calendar sidebar
- Weather widget
- Layer toggle controls
- Map bounds locked to Austin metro area

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
