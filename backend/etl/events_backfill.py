# backend/etl/events_backfill.py
"""Load curated historical Austin events into the event-dict shape the feature
code (`nearby_event_attendance`) expects: lat, lng, expected_attendance, start_dt.
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path


def load_curated_events(csv_path: Path | str) -> list[dict]:
    path = Path(csv_path)
    if not path.exists():
        return []
    events: list[dict] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                start_dt = datetime.strptime(
                    f"{row['date']} {row.get('time', '19:00')[:5]}", "%Y-%m-%d %H:%M"
                )
                events.append({
                    "lat": float(row["lat"]),
                    "lng": float(row["lng"]),
                    "expected_attendance": int(row["attendance"]),
                    "start_dt": start_dt,
                })
            except (KeyError, ValueError):
                continue
    return events
