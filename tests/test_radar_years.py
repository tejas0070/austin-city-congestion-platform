# tests/test_radar_years.py
"""Multi-year radar pull: parse the year list and stamp rows with their own year.

The dataset spans 2017-2021; 2020-2021 are COVID-distorted, so the default pulls
the pre-COVID years. Each row must be dated by ITS OWN year (not a single global
constant) once multiple years are mixed in one fetch.
"""
from datetime import datetime

from scripts.build_radar_training_data import parse_years, _to_dt, DEFAULT_RADAR_YEARS


def test_parse_years_reads_comma_list():
    assert parse_years("2018, 2019 ,2017") == [2018, 2019, 2017]


def test_parse_years_falls_back_to_default_when_blank():
    assert parse_years("") == DEFAULT_RADAR_YEARS
    assert parse_years("   ") == DEFAULT_RADAR_YEARS


def test_default_excludes_covid_years():
    # 2020 (lockdown) and 2021 (partial recovery) must not be defaults
    assert 2020 not in DEFAULT_RADAR_YEARS
    assert 2021 not in DEFAULT_RADAR_YEARS
    assert all(2017 <= y <= 2019 for y in DEFAULT_RADAR_YEARS)


def test_to_dt_uses_each_rows_own_year():
    row_2018 = {"year": 2018, "month": 6, "day": 15, "hour": 8, "minute": 30}
    row_2019 = {"year": "2019", "month": 3, "day": 2, "hour": 17, "minute": 0}
    assert _to_dt(row_2018) == datetime(2018, 6, 15, 8, 30)
    assert _to_dt(row_2019) == datetime(2019, 3, 2, 17, 0)


def test_to_dt_returns_none_on_bad_row():
    assert _to_dt({"year": 2018, "month": "x"}) is None
    assert _to_dt({}) is None
