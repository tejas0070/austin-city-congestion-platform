# Smart City Congestion Platform

A platform for Austin city traffic and event congestion intelligence.

## Workspace Structure

The project is organized as follows:

----
smart-city-congestion-platform/
│
├── data/                  # Data storage
│   ├── raw/               # Unprocessed raw ingestion data
│   └── processed/         # Cleaned and processed datasets
│
├── notebooks/             # Jupyter notebooks for data analysis & prototyping
│
├── backend/               # FastAPI backend application
│   ├── app/               # Core application setup & configuration
│   ├── routes/            # API endpoints & controllers
│   └── services/          # Business logic and database operations
│
├── etl/                   # Extract, Transform, Load data pipelines
│
├── ml/                    # Machine Learning models & predictive traffic analytics
│
├── dashboard/             # Front-end analytical dashboards
│
├── docker/                # Dockerfiles and container configurations
│
├── requirements.txt       # Python dependencies
├── docker-compose.yml     # Multi-container local orchestration config
└── README.md              # Project documentation


## Quick Start (local)

> Prerequisites: Docker Desktop, Python 3.11, git

```bash
# 1. Clone and enter the project
git clone <repo-url>
cd austin-city-congestion-platform

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Add your API keys
cp .env.example .env
# Edit .env — fill in TOMTOM_API_KEY, OPENWEATHER_API_KEY, TICKETMASTER_API_KEY

# 4. Bootstrap everything (DB, migrations, seed data, first ETL run)
bash scripts/setup.sh

# 5. Start the API server
uvicorn backend.app.main:app --reload
```

Then open `http://localhost:8000` — the map will have live data immediately.

### What `setup.sh` does

| Step | Action                                                  |
| ---- | ------------------------------------------------------- |
| 1    | Starts PostGIS via Docker Compose                       |
| 2    | Waits for DB to be healthy                              |
| 3    | Runs Alembic migrations (creates all tables + indexes)  |
| 4    | Seeds road segments                                     |
| 5    | Runs the initial ETL fetch → transform → load cycle     |
| 6    | Pre-computes ML predictions into the DB                 |

Without steps 5–6, the map shows no data on first load.

### API keys required

| Service                | Environment variable      | Free tier |
| ---------------------- | ------------------------- | --------- |
| TomTom Traffic Flow    | `TOMTOM_API_KEY`          | Yes       |
| OpenWeatherMap         | `OPENWEATHER_API_KEY`     | Yes       |
| Ticketmaster Discovery | `TICKETMASTER_API_KEY`    | Yes       |
