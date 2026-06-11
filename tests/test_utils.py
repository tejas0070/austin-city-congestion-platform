import time
import pytest

from backend.utils.cache import clear_cache, get_cache, set_cache
from backend.utils.geojson_builder import (
    build_feature_collection,
    build_line_feature,
    build_point_feature,
    speed_to_congestion_level,
)


# ---------------------------------------------------------------------------
# Cache tests
# ---------------------------------------------------------------------------


def setup_function():
    """Ensure a clean cache state before each test function."""
    clear_cache()


def test_cache_hit_on_fresh_entry():
    # Arrange
    set_cache("city", "Austin", ttl_seconds=60)

    # Act
    result = get_cache("city")

    # Assert
    assert result == "Austin"


def test_cache_miss_on_expired_entry():
    # Arrange
    set_cache("stale", "data", ttl_seconds=0)
    time.sleep(0.01)  # ensure time.time() > expires_at

    # Act
    result = get_cache("stale")

    # Assert
    assert result is None


def test_cache_miss_on_absent_key():
    # Arrange — nothing set for "missing"

    # Act
    result = get_cache("missing")

    # Assert
    assert result is None


def test_clear_cache_empties_all_entries():
    # Arrange
    set_cache("a", 1)
    set_cache("b", 2)

    # Act
    clear_cache()

    # Assert
    assert get_cache("a") is None
    assert get_cache("b") is None


# ---------------------------------------------------------------------------
# GeoJSON builder tests
# ---------------------------------------------------------------------------


def test_build_point_feature_structure():
    # Arrange
    lat, lng = 30.2672, -97.7431
    props = {"name": "Congress Ave"}

    # Act
    feature = build_point_feature(lat, lng, props)

    # Assert
    assert feature["type"] == "Feature"
    assert feature["geometry"]["type"] == "Point"
    # RFC 7946: coordinates are [lng, lat]
    assert feature["geometry"]["coordinates"] == [lng, lat]
    assert feature["properties"] == props


def test_build_line_feature_structure():
    # Arrange
    coords = [[-97.7431, 30.2672], [-97.7400, 30.2700]]
    props = {"road": "I-35"}

    # Act
    feature = build_line_feature(coords, props)

    # Assert
    assert feature["type"] == "Feature"
    assert feature["geometry"]["type"] == "LineString"
    assert feature["geometry"]["coordinates"] == coords
    assert feature["properties"] == props


def test_build_feature_collection_structure():
    # Arrange
    point = build_point_feature(30.2672, -97.7431, {"id": 1})
    line = build_line_feature([[-97.7431, 30.2672], [-97.74, 30.27]], {"id": 2})

    # Act
    collection = build_feature_collection([point, line])

    # Assert
    assert collection["type"] == "FeatureCollection"
    assert len(collection["features"]) == 2
    assert collection["features"][0] is point
    assert collection["features"][1] is line


@pytest.mark.parametrize(
    "speed_mph, free_flow_mph, expected",
    [
        (65.0, 70.0, "green"),   # 92.9% — green
        (35.0, 70.0, "yellow"),  # 50%   — yellow
        (20.0, 70.0, "red"),     # 28.6% — red
        (0.0, 0.0, "green"),     # zero free-flow — safe default
    ],
)
def test_speed_to_congestion_level(speed_mph, free_flow_mph, expected):
    # Act
    result = speed_to_congestion_level(speed_mph, free_flow_mph)

    # Assert
    assert result == expected
