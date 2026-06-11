import httpx
from ..utils.cache import get_cache, set_cache
from ..utils.geojson_builder import build_feature_collection, build_point_feature

AUSTIN_311_URL = "https://data.austintexas.gov/resource/qyfh-gwei.json"
CACHE_KEY = "construction_zones"
CACHE_TTL = 3600  # 1 hour


async def fetch_construction_zones() -> dict:
    cached = get_cache(CACHE_KEY)
    if cached:
        return cached

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                AUSTIN_311_URL,
                params={
                    "$limit": 100,
                    "$where": "sr_type_desc='Roadway Work Zone' AND sr_status_desc='Open'",
                },
            )
            resp.raise_for_status()
            zones = resp.json()
        features = [f for z in zones for f in [_parse_zone(z)] if f]
    except Exception:
        features = []

    result = build_feature_collection(features)
    set_cache(CACHE_KEY, result, CACHE_TTL)
    return result


def _parse_zone(raw: dict) -> dict | None:
    try:
        loc = raw.get("location", {})
        lat = float(loc.get("latitude") or raw.get("latitude") or 0)
        lng = float(loc.get("longitude") or raw.get("longitude") or 0)
        if not lat or not lng:
            return None
        return build_point_feature(
            lat, lng,
            {
                "description": raw.get("sr_description", "Road Work"),
                "status": raw.get("sr_status_desc", "Open"),
                "created_date": raw.get("sr_created_date", ""),
                "closure_type": raw.get("sr_type_desc", "Roadway Work Zone"),
            },
        )
    except Exception:
        return None
