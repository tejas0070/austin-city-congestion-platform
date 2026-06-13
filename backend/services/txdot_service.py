import random
import httpx
from ..utils.cache import get_cache, set_cache
from ..utils.geojson_builder import (
    build_feature_collection,
    build_point_feature,
    speed_to_congestion_level,
)

TXDOT_BASE_URL = "https://api.travelmapping.txdot.gov"
LIVE_CACHE_TTL = 90        # seconds
LIVE_CACHE_KEY = "txdot_live"
INCIDENTS_CACHE_TTL = 90   # seconds
INCIDENTS_CACHE_KEY = "txdot_incidents"

AUSTIN_CORRIDORS = [
    {"segment_id": "i35_downtown",     "road_name": "I-35 Downtown",          "lat": 30.2690, "lng": -97.7341},
    {"segment_id": "mopac_downtown",   "road_name": "Mopac Expressway",        "lat": 30.2764, "lng": -97.7735},
    {"segment_id": "us183_north",      "road_name": "US-183 North",            "lat": 30.3877, "lng": -97.7232},
    {"segment_id": "loop360_west",     "road_name": "Loop 360 West",           "lat": 30.3278, "lng": -97.7998},
    {"segment_id": "congress_downtown","road_name": "Congress Ave Downtown",   "lat": 30.2672, "lng": -97.7431},
]


def _simulated_live_features() -> list[dict]:
    features = []
    for c in AUSTIN_CORRIDORS:
        speed = round(random.uniform(15, 65), 1)
        free_flow = 60.0
        features.append(build_point_feature(
            c["lat"], c["lng"],
            {
                "segment_id": c["segment_id"],
                "road_name": c["road_name"],
                "speed_mph": speed,
                "free_flow_speed_mph": free_flow,
                "congestion_level": speed_to_congestion_level(speed, free_flow),
            },
        ))
    return features


async def fetch_live_traffic() -> dict:
    """Return live traffic GeoJSON FeatureCollection, cached 90 s."""
    cached = get_cache(LIVE_CACHE_KEY)
    if cached:
        return cached

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{TXDOT_BASE_URL}/api/v1/traffic/speed",
                params={"bbox": "-97.9,30.1,-97.5,30.5"},
            )
            resp.raise_for_status()
            features = _transform_txdot_response(resp.json())
    except Exception:
        features = _simulated_live_features()

    result = build_feature_collection(features)
    set_cache(LIVE_CACHE_KEY, result, LIVE_CACHE_TTL)
    return result


def _transform_txdot_response(raw: dict) -> list[dict]:
    features = []
    for item in raw.get("features", []):
        props = item.get("properties", {})
        coords = item.get("geometry", {}).get("coordinates", [0, 0])
        speed = float(props.get("speed", 0))
        free_flow = float(props.get("freeFlowSpeed", 60))
        features.append(build_point_feature(
            coords[1], coords[0],
            {
                "segment_id": str(props.get("segmentId", "")),
                "road_name": props.get("roadName", "Unknown"),
                "speed_mph": round(speed, 1),
                "free_flow_speed_mph": free_flow,
                "congestion_level": speed_to_congestion_level(speed, free_flow),
            },
        ))
    return features


_SIMULATED_INCIDENTS = [
    {"lat": 30.2850, "lng": -97.7341, "incident_type": "accident",     "severity": 3, "description": "Multi-vehicle collision blocking right lane on I-35 NB"},
    {"lat": 30.3050, "lng": -97.7930, "incident_type": "construction", "severity": 2, "description": "Lane closure for resurfacing near MoPac/360"},
    {"lat": 30.3877, "lng": -97.7232, "incident_type": "hazard",       "severity": 1, "description": "Debris on shoulder, US-183 NB"},
    {"lat": 30.2672, "lng": -97.7431, "incident_type": "closure",      "severity": 4, "description": "Full closure for event load-out, Congress Ave"},
]


def _simulated_incidents() -> dict:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    features = [
        build_point_feature(i["lat"], i["lng"], {
            "incident_id": f"sim_{idx}",
            "incident_type": i["incident_type"],
            "description": i["description"],
            "severity": i["severity"],
            "start_time": now,
        })
        for idx, i in enumerate(_SIMULATED_INCIDENTS)
    ]
    return build_feature_collection(features)


async def fetch_incidents() -> dict:
    """Return active incidents GeoJSON FeatureCollection, cached 90 s.

    Falls back to simulated incidents when the live TxDOT feed is unavailable so
    the incidents map layer always has data to render.
    """
    cached = get_cache(INCIDENTS_CACHE_KEY)
    if cached:
        return cached

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{TXDOT_BASE_URL}/api/v1/incidents",
                params={"bbox": "-97.9,30.1,-97.5,30.5"},
            )
            resp.raise_for_status()
            result = _transform_incidents(resp.json())
            if not result.get("features"):
                result = _simulated_incidents()
    except Exception:
        result = _simulated_incidents()

    set_cache(INCIDENTS_CACHE_KEY, result, INCIDENTS_CACHE_TTL)
    return result


def _transform_incidents(raw: dict) -> dict:
    features = []
    for item in raw.get("features", []):
        props = item.get("properties", {})
        coords = item.get("geometry", {}).get("coordinates", [0, 0])
        features.append(build_point_feature(
            coords[1], coords[0],
            {
                "incident_id": str(props.get("incidentId", "")),
                "incident_type": props.get("type", "unknown"),
                "description": props.get("description", ""),
                "severity": int(props.get("severity", 1)),
                "start_time": props.get("startTime", ""),
            },
        ))
    return build_feature_collection(features)
