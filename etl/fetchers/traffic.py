"""
Traffic fetcher — TomTom Traffic Flow Segment API.

Fetches real-time speed data for each monitored Austin corridor concurrently
and returns a list of TrafficObservation ORM objects. Each observation is
linked to a road_segments row via the segment_id foreign key, so the
pipeline must supply a corridor_name → segment_id mapping before calling.
"""

import asyncio
import logging
from datetime import datetime, timezone

import httpx

from backend.app.geo_models import TrafficObservation
from ._http import get_json

logger = logging.getLogger(__name__)

TOMTOM_FLOW_URL = (
    "https://api.tomtom.com/traffic/services/4"
    "/flowSegmentData/absolute/10/json"
)

# Representative monitoring point per corridor.
# TomTom returns the flow segment that contains the given lat/lon,
# so these don't need to be precise road centroids.
CORRIDOR_POINTS: dict[str, tuple[float, float]] = {
    "I-35_Downtown":             (30.2690, -97.7341),
    "Mopac_Expressway_Downtown": (30.2764, -97.7735),
    "US-183_North":              (30.3722, -97.7248),
    "Loop-360_West":             (30.2982, -97.8080),
    "Congress_Ave_Downtown":     (30.2682, -97.7428),
}


async def _fetch_corridor(
    client: httpx.AsyncClient,
    api_key: str,
    corridor_name: str,
    lat: float,
    lon: float,
    segment_id: int,
) -> TrafficObservation | None:
    """
    Fetch flow data for one corridor point and return a TrafficObservation.
    Returns None if TomTom returns no segment data for the given point.
    """
    data = await get_json(client, TOMTOM_FLOW_URL, {
        "key":       api_key,
        "point":     f"{lat},{lon}",
        "unit":      "MPH",
        "thickness": 10,
    })

    flow = data.get("flowSegmentData")
    if not flow:
        logger.warning("no flow data for corridor %s", corridor_name)
        return None

    current_mph   = float(flow.get("currentSpeed", 0))
    free_flow_mph = float(flow.get("freeFlowSpeed", 0))
    congestion    = (
        round(1.0 - (current_mph / free_flow_mph), 4)
        if free_flow_mph > 0 else None
    )

    logger.debug("%s: %.0f / %.0f mph  congestion=%.2f",
                 corridor_name, current_mph, free_flow_mph, congestion or 0)

    return TrafficObservation(
        segment_id=segment_id,
        timestamp=datetime.now(timezone.utc),
        speed_mph=current_mph,
        free_flow_speed_mph=free_flow_mph,
        volume=None,          # TomTom Flow API does not expose volume counts
        congestion_index=congestion,
        source="tomtom",
    )


async def fetch_all_corridors(
    client: httpx.AsyncClient,
    api_key: str,
    corridor_segments: dict[str, int],
) -> list[TrafficObservation]:
    """
    Fetch all corridor speed readings concurrently.

    Args:
        client:            Shared AsyncClient.
        api_key:           TomTom API key from .env.
        corridor_segments: Maps corridor_name → road_segments.id.
                           Corridors missing from this map are skipped.

    Returns:
        List of TrafficObservation objects (one per successfully fetched corridor).
    """
    tasks = {
        corridor_name: _fetch_corridor(
            client, api_key, corridor_name, lat, lon,
            corridor_segments[corridor_name],
        )
        for corridor_name, (lat, lon) in CORRIDOR_POINTS.items()
        if corridor_name in corridor_segments
    }

    if not tasks:
        logger.warning(
            "No corridor segments found in road_segments. "
            "Run etl/seed_road_segments.py first."
        )
        return []

    results = await asyncio.gather(*tasks.values(), return_exceptions=True)

    observations: list[TrafficObservation] = []
    for corridor_name, result in zip(tasks.keys(), results):
        if isinstance(result, Exception):
            logger.warning("traffic fetch failed for %s: %s", corridor_name, result)
        elif result is not None:
            observations.append(result)

    return observations
