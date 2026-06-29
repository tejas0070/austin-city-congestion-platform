"""Hard daily-request budget for TomTom, so the free tier is never exceeded.

TomTom's free plan allows ~2,500 requests/day. This tracks usage per calendar day
in a small JSON file and exposes the remaining allowance. Every TomTom caller must
reserve from here BEFORE making requests, so the cap can never be overshot — no
matter how often the collector is run or how the live layer is used.

The default ceiling is deliberately set below 2,500 to leave headroom.
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

USAGE_PATH = Path(__file__).resolve().parents[2] / "data" / "models" / "tomtom_usage.json"

# Stay safely under the real free-tier ceiling (2,500/day). Override with env.
DAILY_LIMIT = int(os.environ.get("TOMTOM_DAILY_LIMIT", "2400"))


def _load() -> dict:
    if USAGE_PATH.exists():
        try:
            return json.loads(USAGE_PATH.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - corrupt file → treat as empty
            return {}
    return {}


def _today() -> str:
    return date.today().isoformat()


def used_today() -> int:
    """Requests already spent today (0 after midnight rolls the counter)."""
    data = _load()
    return int(data.get("count", 0)) if data.get("date") == _today() else 0


def remaining_today() -> int:
    """How many requests are still allowed today under the hard ceiling."""
    return max(0, DAILY_LIMIT - used_today())


def reserve(requested: int) -> int:
    """Reserve up to `requested` calls, never exceeding today's remaining budget.

    Records the grant immediately (so the ceiling holds even if the caller
    crashes mid-batch) and returns the number actually granted (may be 0).
    """
    if requested <= 0:
        return 0
    granted = min(requested, remaining_today())
    if granted <= 0:
        return 0
    USAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    USAGE_PATH.write_text(
        json.dumps({"date": _today(), "count": used_today() + granted}),
        encoding="utf-8",
    )
    return granted
