# Austin Traffic Intelligence Platform

Interactive geospatial web app that visualizes real-time Austin traffic, events, and weather. Built with React 18 + kepler.gl.

## Live Demo

_Deploy URL will appear here after Netlify deploy._

## Tech Stack

| Layer | Technology |
| ----- | ---------- |
| Frontend | React 18, Redux, kepler.gl v3, Mapbox GL JS, Tailwind CSS |
| Backend | FastAPI, SQLAlchemy, PostgreSQL |
| Data | TxDOT, Open-Meteo, Ticketmaster, Austin 311 |

## Getting Started

### Prerequisites

- Node.js 18+
- Python 3.11+
- PostgreSQL (or `DATABASE_URL` pointing to Supabase)
- Mapbox public token

### Backend

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in DATABASE_URL
alembic upgrade head
uvicorn backend.main:app --reload
```

### Frontend

```bash
cd frontend
cp .env.example .env   # fill in REACT_APP_MAPBOX_TOKEN
npm install
npm start
```

## Data Sources

- **TxDOT** — live traffic speeds and incidents
- **Open-Meteo** — current weather (free, no key required)
- **Ticketmaster** — concerts and events
- **Austin 311** — roadway work zones

## Features

- Live traffic layer (TxDOT, refreshes every 2 min)
- Historical traffic layer by time of day
- Incident markers
- Venue pins with event details
- Events calendar sidebar
- Weather widget
- Layer toggle controls
