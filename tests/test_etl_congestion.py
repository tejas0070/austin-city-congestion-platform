# tests/test_etl_congestion.py
from backend.etl.congestion import free_flow_speed, congestion_pct_from_speed


def test_free_flow_is_high_percentile():
    speeds = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    # 85th percentile ~ 86.5; allow a tolerance for the percentile method
    assert 80 <= free_flow_speed(speeds) <= 95


def test_free_flow_none_when_empty():
    assert free_flow_speed([]) is None


def test_congestion_zero_at_free_flow():
    assert congestion_pct_from_speed(60.0, free_flow=60.0) == 0.0


def test_congestion_high_when_slow():
    # 15 mph on a 60 mph free-flow road -> 75% congested
    assert congestion_pct_from_speed(15.0, free_flow=60.0) == 75.0


def test_congestion_clamped_and_guards_zero_free_flow():
    assert congestion_pct_from_speed(80.0, free_flow=60.0) == 0.0  # faster than free-flow
    assert congestion_pct_from_speed(10.0, free_flow=0.0) == 0.0   # bad free-flow -> 0, no crash
