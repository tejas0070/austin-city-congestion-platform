#!/usr/bin/env bash
# setup.sh — One-shot bootstrap for Austin Traffic Intelligence (local dev)
#
# Usage: bash scripts/setup.sh
#
# What this does:
#   1. Copies .env.example → .env (if .env doesn't exist yet)
#   2. Starts Docker Compose (PostGIS + any other services)
#   3. Waits until PostgreSQL is healthy
#   4. Runs Alembic migrations (creates/updates all tables including indexes)
#   5. Seeds road segments
#   6. Runs the initial ETL cycle so the DB has data before first page load
#   7. Prints the local URL

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()    { echo -e "${GREEN}[setup]${NC} $*"; }
warn()    { echo -e "${YELLOW}[setup]${NC} $*"; }
error()   { echo -e "${RED}[setup]${NC} $*" >&2; exit 1; }

# ── 1. Environment file ──────────────────────────────────────────────────────
if [[ ! -f .env ]]; then
  if [[ -f .env.example ]]; then
    cp .env.example .env
    warn ".env created from .env.example — fill in your API keys before continuing."
    warn "  Required: TOMTOM_API_KEY, OPENWEATHER_API_KEY, TICKETMASTER_API_KEY"
    echo
    read -rp "Press Enter once you have added your API keys to .env, or Ctrl-C to cancel…"
  else
    error ".env not found and no .env.example to copy from. Create .env manually."
  fi
else
  info ".env already exists — skipping copy."
fi

# ── 2. Docker Compose ────────────────────────────────────────────────────────
info "Starting Docker services…"
docker compose up -d

# ── 3. Wait for PostgreSQL ───────────────────────────────────────────────────
info "Waiting for PostgreSQL to be ready…"
MAX_WAIT=60
WAITED=0
until docker compose exec -T db pg_isready -U postgres -d "austin-traffic-predictor" &>/dev/null; do
  if [[ $WAITED -ge $MAX_WAIT ]]; then
    error "PostgreSQL did not become ready within ${MAX_WAIT}s. Check 'docker compose logs db'."
  fi
  sleep 2
  WAITED=$((WAITED + 2))
done
info "PostgreSQL is ready."

# ── 4. Alembic migrations ────────────────────────────────────────────────────
info "Running database migrations…"
python -m alembic upgrade head

# ── 5. Seed road segments ────────────────────────────────────────────────────
info "Seeding road segments…"
python etl/seed_road_segments.py

# ── 6. Initial ETL cycle ─────────────────────────────────────────────────────
info "Running initial ETL cycle (fetch → transform → load → cache predictions)…"
python etl/run_all_etl.py
python -c "from etl.transform import transform; transform()"
python -c "from etl.load_to_db import load_merged_features, cache_predictions; load_merged_features(); cache_predictions()"

# ── 7. Done ───────────────────────────────────────────────────────────────────
echo
echo -e "${GREEN}✓ Setup complete!${NC}"
echo "  Open: http://localhost:8000"
echo
echo "To start the API server:"
echo "  uvicorn backend.app.main:app --reload"
echo
echo "Or run everything in Docker:"
echo "  docker compose up"
