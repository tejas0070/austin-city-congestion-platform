# tests/test_weather_impact.py
"""Weather-severity overlay on the learned baseline.

The model learns only the baseline traffic flow; weather is applied on top as a
transparent severity multiplier (Clear x1.0 .. Storm x1.7), because the real speed
data carries only a weak, sometimes wrong-signed weather signal. These tests lock
the multiplier's shape and prove the serving path makes BAD weather reliably raise
the presented congestion (the previous learned feature could invert it).
"""
from datetime import datetime

import pytest

from backend.services.congestion_features import (
    weather_congestion_multiplier,
    NUMERIC_FEATURES,
)


# --- the multiplier ---------------------------------------------------------

def test_clear_is_neutral():
    assert weather_congestion_multiplier("Clear") == 1.0


def test_worse_weather_multiplies_more():
    m = weather_congestion_multiplier
    assert m("Clear") < m("Light Rain") < m("Rain") < m("Heavy Rain")
    assert m("Heavy Rain") >= 1.8  # flash flooding is a severe Austin multiplier


def test_unknown_condition_is_neutral():
    assert weather_congestion_multiplier("Foggy Mystery") == 1.0


def test_every_real_condition_is_classified():
    """Regression guard for the original bug: every label the weather service can
    emit must have an explicit multiplier, not silently fall through to 1.0."""
    from backend.services.weather_service import WEATHER_CODE_MAP
    from backend.services.congestion_features import WEATHER_CONGESTION_MULTIPLIER
    missing = set(WEATHER_CODE_MAP.values()) - set(WEATHER_CONGESTION_MULTIPLIER)
    assert not missing, f"weather conditions with no multiplier: {sorted(missing)}"


def test_austin_severity_ordering():
    """Austin's hazard order: ice > flooding > snow/hail/fog > light precip. Ice is
    the worst because the city has no ice infrastructure — worse than hail."""
    from backend.services.congestion_features import WEATHER_CONGESTION_MULTIPLIER
    m = weather_congestion_multiplier
    assert m("Overcast") == 1.0
    # light friction < fog/thunderstorm < flooding < ice
    assert m("Light Rain") < m("Fog") < m("Heavy Rain") < m("Freezing Rain")
    # for Austin, black ice outranks hail (the national intuition is reversed)
    assert m("Freezing Rain") > m("Thunderstorm with Hail")
    # freezing rain (black ice) is the single most severe condition on the board
    assert m("Freezing Rain") == max(WEATHER_CONGESTION_MULTIPLIER.values())


def test_black_ice_escalation_below_freezing():
    """Liquid precip at/below freezing is treated as black ice regardless of label —
    Austin's most disruptive condition (untreated bridges/overpasses)."""
    from backend.services.congestion_features import BLACK_ICE_MULTIPLIER
    warm_rain = weather_congestion_multiplier("Rain", temperature_f=60.0)
    icy_rain = weather_congestion_multiplier("Rain", temperature_f=30.0)
    assert icy_rain == BLACK_ICE_MULTIPLIER
    assert icy_rain > warm_rain
    # a dry freezing morning (no precip) is NOT black ice
    assert weather_congestion_multiplier("Clear", temperature_f=28.0) == 1.0


def test_extreme_heat_adds_friction():
    from backend.services.congestion_features import EXTREME_HEAT_MULTIPLIER
    assert weather_congestion_multiplier("Clear", temperature_f=104.0) == EXTREME_HEAT_MULTIPLIER
    assert weather_congestion_multiplier("Clear", temperature_f=85.0) == 1.0


def test_weather_is_not_a_learned_feature():
    # weather must be an overlay, NOT trained into the model
    for f in ("weather_code", "temperature_f", "precipitation_in"):
        assert f not in NUMERIC_FEATURES


# --- serving path: bad weather reliably raises congestion -------------------

def test_bad_weather_raises_presented_congestion():
    from backend.services import ml_model
    if not ml_model.model_is_available():
        pytest.skip("model not trained in this environment")
    from backend.services.congestion_features import weather_congestion_multiplier as wm

    when = datetime(2026, 7, 8, 17, 0)  # ordinary Wed 5 PM (no holiday)
    _, _, clear = ml_model._run_predictions(when, 0, 78.0, 0.0, [], wm("Clear", 78.0))
    _, _, rain = ml_model._run_predictions(when, 63, 66.0, 0.15, [], wm("Rain", 66.0))
    _, _, heavy = ml_model._run_predictions(when, 65, 62.0, 0.45, [], wm("Heavy Rain", 62.0))

    # Every segment gets monotonically worse as the weather worsens, never better.
    assert all(r >= c for c, r in zip(clear, rain))
    assert all(h >= r for r, h in zip(rain, heavy))
    # and on average the effect is clearly positive (not a wash)
    assert sum(rain) > sum(clear)
    assert sum(heavy) > sum(rain)
