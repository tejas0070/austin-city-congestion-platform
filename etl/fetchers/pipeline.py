"""
Async ETL pipeline — runs weather, traffic, and events fetchers concurrently.

All three API calls fire at the same time using asyncio.gather so total
wall time is roughly equal to the slowest single API call rather than the
sum of all of them. On a typical run this cuts fetch time from ~15 s to ~3 s.

Usage:
    python -m etl.fetchers.pipeline          # run and write to DB
    python -m etl.fetchers.pipeline --dry-run # fetch only, no DB writes
"""

import asyncio
import logging
import os
import sys
import time
from dataclasses import dataclass

import httpx
from dotenv import load_dotenv

# ── project path ──────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

from sqlalchemy.orm import Session

from backend.app.database import SessionLocal
from backend.app.geo_models import Event, RoadSegment, TrafficObservation, WeatherSnapshot
from .weather import fetch_all_zones
from .traffic import fetch_all_corridors
from .events import fetch_events

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pipeline")


# ── config ────────────────────────────────────────────────────────────────────

def _require_key(name: str) -> str:
    value = os.getenv(name, "")
    if not value or value.startswith("your_"):
        raise EnvironmentError(
            f"Missing or placeholder API key: {name}. "
            "Add a real key to your .env file."
        )
    return value


# ── DB helpers ────────────────────────────────────────────────────────────────

def _get_corridor_segment_ids(db: Session) -> dict[str, int]:
    """
    Return the first road_segments.id for each corridor_name.
    Traffic observations reference segment rows, so we need this mapping
    before fetching. Returns empty dict if road_segments hasn't been seeded.
    """
    rows = (
        db.query(RoadSegment.corridor_name, RoadSegment.id)
        .filter(RoadSegment.corridor_name.isnot(None))
        .order_by(RoadSegment.corridor_name, RoadSegment.id)
        .all()
    )
    # Keep the lowest segment ID per corridor (first segment of that road)
    mapping: dict[str, int] = {}
    for corridor_name, seg_id in rows:
        if corridor_name not in mapping:
            mapping[corridor_name] = seg_id
    return mapping


def _write_weather(db: Session, snapshots: list[WeatherSnapshot]) -> int:
    for snap in snapshots:
        db.add(snap)
    db.commit()
    return len(snapshots)


def _write_traffic(db: Session, observations: list[TrafficObservation]) -> int:
    for obs in observations:
        db.add(obs)
    db.commit()
    return len(observations)


def _write_events(db: Session, events: list[Event]) -> int:
    """Insert events, skipping any whose external_id already exists."""
    existing_ids = {row[0] for row in db.query(Event.external_id).all()}
    new_events   = [e for e in events if e.external_id not in existing_ids]
    for event in new_events:
        db.add(event)
    db.commit()
    return len(new_events)


# ── result summary ─────────────────────────────────────────────────────────────

@dataclass
class PipelineResult:
    weather_inserted:  int
    traffic_inserted:  int
    events_inserted:   int
    elapsed_seconds:   float

    def log(self) -> None:
        logger.info(
            "Pipeline complete in %.1fs  |  "
            "weather=%d  traffic=%d  events=%d",
            self.elapsed_seconds,
            self.weather_inserted,
            self.traffic_inserted,
            self.events_inserted,
        )


# ── main pipeline ─────────────────────────────────────────────────────────────

async def run_pipeline(dry_run: bool = False) -> PipelineResult:
    """
    Fetch weather, traffic, and events concurrently then write to PostgreSQL.

    Args:
        dry_run: If True, fetches data but skips all database writes.
                 Useful for testing API connectivity without touching the DB.

    Returns:
        PipelineResult with row counts and wall-clock time.
    """
    t0 = time.perf_counter()

    # Load API keys — fail fast before any network calls
    weather_key    = _require_key("OPENWEATHER_API_KEY")
    traffic_key    = _require_key("TOMTOM_API_KEY")
    events_key     = _require_key("TICKETMASTER_API_KEY")

    # Look up corridor → segment_id mapping (needed by traffic fetcher)
    db = SessionLocal()
    try:
        corridor_segments = _get_corridor_segment_ids(db)
    finally:
        db.close()

    if not corridor_segments:
        logger.warning(
            "road_segments table is empty — traffic observations will be skipped. "
            "Run: python etl/seed_road_segments.py"
        )

    logger.info("Starting concurrent fetch  (weather=5 zones, traffic=%d corridors, events=48h)",
                len(corridor_segments))

    # One shared client for all requests — connection pooling, keep-alive
    async with httpx.AsyncClient(
        headers={"User-Agent": "austin-traffic-predictor/1.0"},
        follow_redirects=True,
    ) as client:
        weather_task  = fetch_all_zones(client, weather_key)
        traffic_task  = fetch_all_corridors(client, traffic_key, corridor_segments)
        events_task   = fetch_events(client, events_key)

        # All three fire simultaneously — total time ≈ slowest individual call
        snapshots, observations, events = await asyncio.gather(
            weather_task,
            traffic_task,
            events_task,
            return_exceptions=False,
        )

    logger.info(
        "Fetch complete  |  weather=%d  traffic=%d  events=%d",
        len(snapshots), len(observations), len(events),
    )

    # Write to database
    w_count = t_count = e_count = 0
    if not dry_run:
        db = SessionLocal()
        try:
            w_count = _write_weather(db, snapshots)
            t_count = _write_traffic(db, observations)
            e_count = _write_events(db, events)
        finally:
            db.close()
    else:
        logger.info("dry-run mode: skipping database writes")

    result = PipelineResult(
        weather_inserted=w_count,
        traffic_inserted=t_count,
        events_inserted=e_count,
        elapsed_seconds=round(time.perf_counter() - t0, 2),
    )
    result.log()
    return result


# ── CLI entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    asyncio.run(run_pipeline(dry_run=dry_run))
