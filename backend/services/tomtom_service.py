"""TomTom Traffic Flow client — real current speed/congestion per road segment.

Uses the TomTom Flow Segment Data API (free developer tier). Given a point it
returns the current vs free-flow speed for the road there, from which we derive a
real congestion percentage. Keyed by the TOMTOM_API_KEY env var.

Free-tier note: the free plan allows ~2,500 requests/day, so this is used by an
offline collector that samples segments over time (scripts/collect_tomtom_
observations.py) — NOT to refresh all ~3,800 segments live on every request.
"""
from __future__ import annotations

import os

import httpx

FLOW_URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"
_TIMEOUT = 15.0


def tomtom_available() -> bool:
    return bool(os.environ.get("TOMTOM_API_KEY"))


def _congestion_pct(current: float, free_flow: float) -> float:
    """congestion = 100 * (1 - current/free_flow), clamped to [0, 100]."""
    if not free_flow or free_flow <= 0:
        return 0.0
    pct = 100.0 * (1.0 - float(current) / float(free_flow))
    return round(max(0.0, min(100.0, pct)), 1)


def fetch_flow_segment(lat: float, lng: float, client: httpx.Client | None = None) -> dict | None:
    """Real traffic flow at a point: current/free-flow speed, congestion, confidence.

    Returns None when the key is missing or the request fails (callers degrade
    gracefully). `client` may be reused across calls to pool connections.

    Output: {current_speed, free_flow_speed, congestion_pct, confidence,
             road_closure} with speeds in mph.
    """
    api_key = os.environ.get("TOMTOM_API_KEY")
    if not api_key:
        return None

    params = {"point": f"{lat},{lng}", "unit": "MPH", "key": api_key}
    owns_client = client is None
    client = client or httpx.Client(timeout=_TIMEOUT)
    try:
        resp = client.get(FLOW_URL, params=params)
        resp.raise_for_status()
        data = resp.json().get("flowSegmentData")
    except Exception:  # noqa: BLE001 - network/parse error → caller falls back
        return None
    finally:
        if owns_client:
            client.close()

    if not data:
        return None
    current = data.get("currentSpeed")
    free_flow = data.get("freeFlowSpeed")
    if current is None or free_flow is None:
        return None
    return {
        "current_speed": float(current),
        "free_flow_speed": float(free_flow),
        "congestion_pct": _congestion_pct(current, free_flow),
        "confidence": data.get("confidence"),
        "road_closure": bool(data.get("roadClosure", False)),
    }
