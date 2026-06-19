# tests/test_etl_sensor_locations.py
from backend.etl.sensor_locations import normalize_reader_key, build_reader_location_map


def test_normalize_reader_key_is_case_and_space_insensitive():
    assert normalize_reader_key("Lamar_Braker") == "lamarbraker"
    assert normalize_reader_key("US 290 HWY", "WILLIAM CANNON DR") == "us290hwywilliamcannondr"


def test_build_map_keys_on_reader_id_and_street_pair():
    records = [
        {
            "reader_id": "us290_wm_cannon",
            "primary_st": "US 290 HWY",
            "cross_st": "WILLIAM CANNON DR",
            "location": {"type": "Point", "coordinates": [-97.86483, 30.234057]},
        }
    ]
    m = build_reader_location_map(records)
    # reachable by normalized reader_id and by normalized street pair
    assert m[normalize_reader_key("us290_wm_cannon")] == (30.234057, -97.86483)
    assert m[normalize_reader_key("US 290 HWY", "WILLIAM CANNON DR")] == (30.234057, -97.86483)


def test_build_map_skips_records_without_coordinates():
    records = [{"reader_id": "x", "primary_st": "A", "cross_st": "B"}]
    assert build_reader_location_map(records) == {}
