# tests/test_display_segments.py
"""Downtown display filter: map + predictions cover only segments within
DOWNTOWN_RADIUS_KM, while load_segments() stays the full network for training."""
from backend.services import segments_service as ss


def test_display_is_within_radius_and_subset_of_full():
    full = ss.load_segments()
    disp = ss.load_display_segments()
    assert 0 < len(disp) <= len(full)
    # every displayed segment is within the radius
    assert all(s["dist_downtown_km"] <= ss.DOWNTOWN_RADIUS_KM for s in disp)
    # nothing beyond the radius leaks into the display set
    disp_ids = {s["segment_id"] for s in disp}
    assert all(
        s["dist_downtown_km"] > ss.DOWNTOWN_RADIUS_KM
        for s in full
        if s["segment_id"] not in disp_ids
    )


def test_full_network_retained_for_training():
    # load_segments() must still expose the far metro roads (training assignment
    # needs the true nearest road, not a closer in-radius one).
    full = ss.load_segments()
    assert any(s["dist_downtown_km"] > ss.DOWNTOWN_RADIUS_KM for s in full)


def test_segment_count_reflects_display():
    assert ss.segment_count() == len(ss.load_display_segments())
