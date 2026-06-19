# tests/test_etl_segment_assign.py
from backend.etl.segment_assign import nearest_segment


SEGMENTS = [
    {"road_class": "motorway", "centroid_lat": 30.2672, "centroid_lng": -97.7431},
    {"road_class": "secondary", "centroid_lat": 30.40, "centroid_lng": -97.70},
]


def test_picks_closest_segment():
    seg = nearest_segment(30.2670, -97.7430, SEGMENTS)
    assert seg["road_class"] == "motorway"


def test_returns_none_for_empty_segments():
    assert nearest_segment(30.0, -97.0, []) is None
