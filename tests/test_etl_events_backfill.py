# tests/test_etl_events_backfill.py
from datetime import datetime
from pathlib import Path
from backend.etl.events_backfill import load_curated_events


def test_load_curated_events(tmp_path: Path):
    csv = tmp_path / "events.csv"
    csv.write_text(
        "date,time,venue,lat,lng,attendance\n"
        "2017-09-16,18:30,ut_football,30.2836,-97.7320,100119\n",
        encoding="utf-8",
    )
    events = load_curated_events(csv)
    assert len(events) == 1
    ev = events[0]
    assert ev["lat"] == 30.2836
    assert ev["lng"] == -97.7320
    assert ev["expected_attendance"] == 100119
    assert ev["start_dt"] == datetime(2017, 9, 16, 18, 30)


def test_load_curated_events_missing_file_returns_empty(tmp_path: Path):
    assert load_curated_events(tmp_path / "nope.csv") == []
