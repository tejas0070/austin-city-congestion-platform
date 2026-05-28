# Project

Smart City Congestion Intelligence Platform — Predicts Austin traffic congestion using live traffic, weather, and event data with analytics dashboards and machine learning forecasts.

# Stack

* Python 3.11
* FastAPI
* PostgreSQL
* Pandas, Scikit-learn, SQLAlchemy, Requests, Plotly
* Docker + Docker Compose
* Power BI
* Deployed locally with Docker (GCP deployment planned later)

# Structure

* `etl/` — API data collection and cleaning scripts
* `backend/` — FastAPI backend and API routes
* `ml/` — congestion prediction models and training scripts
* `dashboard/` — Power BI files and exported visuals
* `data/` — raw and processed datasets
* `tests/` — API and pipeline tests
* `docs/` — architecture notes and setup guides

# Commands

* Dev: `docker-compose up --build`
* Build: `docker build -t congestion-platform .`
* Test: `pytest`
* Lint: `flake8 .`

# Verification

After every change, run in this order:

* `python -m py_compile backend/**/*.py` — fix syntax/type errors
* `pytest` — fix failing tests
* `flake8 .` — fix lint errors

# Conventions

* Use FastAPI routers for all API endpoints
* Store configuration in `.env` files
* Use snake_case for Python files and database columns
* Keep ETL, ML, and backend logic separated

For machine learning workflows, see `docs/ml_pipeline.md`

# Don't

* Don’t hardcode API keys. Use environment variables instead.
* Don’t mix dashboard logic into backend services. Keep layers separated.
* Don’t train models directly inside API routes. Use offline training scripts instead.
