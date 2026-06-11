def build_point_feature(lat: float, lng: float, properties: dict) -> dict:
    """Return a GeoJSON Feature with Point geometry.

    Coordinates are ordered [lng, lat] per RFC 7946.
    """
    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [lng, lat],
        },
        "properties": properties,
    }


def build_line_feature(coordinates: list[list[float]], properties: dict) -> dict:
    """Return a GeoJSON Feature with LineString geometry.

    coordinates is a list of [lng, lat] pairs per RFC 7946.
    """
    return {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": coordinates,
        },
        "properties": properties,
    }


def build_feature_collection(features: list[dict]) -> dict:
    """Return a GeoJSON FeatureCollection wrapping the given feature list."""
    return {
        "type": "FeatureCollection",
        "features": features,
    }


def speed_to_congestion_level(speed_mph: float, free_flow_mph: float) -> str:
    """Return a congestion level string based on speed relative to free-flow speed.

    Returns:
        "green"  — speed >= 70% of free_flow_mph
        "yellow" — speed >= 40% of free_flow_mph (but < 70%)
        "red"    — speed <  40% of free_flow_mph
        "green"  — safe default when free_flow_mph <= 0
    """
    if free_flow_mph <= 0:
        return "green"
    ratio = speed_mph / free_flow_mph
    if ratio >= 0.70:
        return "green"
    if ratio >= 0.40:
        return "yellow"
    return "red"
