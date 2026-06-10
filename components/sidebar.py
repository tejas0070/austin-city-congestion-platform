"""
Sidebar controls and stats panel.

Call render_controls() to draw all interactive widgets and get back a
plain dict of the user's current selections. Call render_stats() to
draw the stats block below the controls.
"""

from __future__ import annotations

import streamlit as st


DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
WEATHER_OPTIONS = ["Clear", "Rain", "Heavy Rain", "Storm"]

WEATHER_MULTIPLIERS = {
    "Clear": 1.0,
    "Rain": 1.20,
    "Heavy Rain": 1.45,
    "Storm": 1.70,
}

# Weather impact score (0–10) per condition
WEATHER_IMPACT_SCORES = {
    "Clear": 0,
    "Rain": 3,
    "Heavy Rain": 6,
    "Storm": 9,
}

MAX_SLOT = 47  # slot 47 = 11:30 PM; 48 total slots covering 12:00 AM–11:30 PM


def slot_to_label(slot: int) -> str:
    """Convert 0-based 30-min slot to readable label, e.g. slot 34 → '5:00 PM'."""
    hour = slot // 2
    minute = "30" if slot % 2 else "00"
    period = "AM" if hour < 12 else "PM"
    display_hour = hour if hour <= 12 else hour - 12
    display_hour = 12 if display_hour == 0 else display_hour
    return f"{display_hour}:{minute} {period}"


def advance_step(time_slot: int, is_playing: bool) -> tuple[int, bool]:
    """
    Pure tick function for the animation loop.

    Returns (new_slot, new_is_playing). When the end is reached,
    is_playing becomes False and the slot stays at MAX_SLOT.
    """
    if not is_playing:
        return time_slot, False
    if time_slot < MAX_SLOT:
        return time_slot + 1, True
    return MAX_SLOT, False


def render_controls() -> dict:
    """Render sidebar controls and return current selections as a dict."""
    st.sidebar.markdown("## Controls")

    time_slot = st.sidebar.slider(
        "Time of Day",
        min_value=0,
        max_value=47,
        value=34,  # default 5:00 PM
        format="%d",
        help="Each step is 30 minutes. Slot 0 = 12:00 AM, slot 34 = 5:00 PM.",
    )
    st.sidebar.caption(f"Selected: **{slot_to_label(time_slot)}**")

    day = st.sidebar.selectbox("Day of Week", DAYS, index=0)  # Monday default

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Active Events**")
    events = {
        "austin_fc": st.sidebar.toggle("Austin FC Match", value=False),
        "ut_football": st.sidebar.toggle("UT Football", value=False),
        "sxsw": st.sidebar.toggle("SXSW", value=False),
        "acl": st.sidebar.toggle("ACL Festival", value=False),
        "downtown": st.sidebar.toggle("Downtown Event", value=False),
    }

    st.sidebar.markdown("---")
    weather = st.sidebar.selectbox("Weather Condition", WEATHER_OPTIONS, index=0)

    return {
        "time_slot": time_slot,
        "time_label": slot_to_label(time_slot),
        "day": day,
        "day_index": DAYS.index(day),
        "events": events,
        "weather": weather,
        "weather_multiplier": WEATHER_MULTIPLIERS[weather],
        "weather_impact_score": WEATHER_IMPACT_SCORES[weather],
    }


def render_stats(stats: dict) -> None:
    """
    Render the stats block in the sidebar.

    Expected keys in stats:
        avg_speed_mph       float
        congestion_index    float  0–100
        top_corridors       list[dict]  keys: name, congestion
        delay_severity      str   "Low" / "Moderate" / "Severe"
        weather_impact      int   0–10
    """
    st.sidebar.markdown("---")
    st.sidebar.markdown("## Current Stats")

    avg_speed = stats.get("avg_speed_mph", 0)
    cong_idx = stats.get("congestion_index", 0)
    delay = stats.get("delay_severity", "Low")
    weather_impact = stats.get("weather_impact", 0)

    # Colour the delay badge
    delay_color = {"Low": "green", "Moderate": "orange", "Severe": "red"}.get(delay, "gray")

    st.sidebar.metric("Avg City Speed", f"{avg_speed:.0f} mph")
    st.sidebar.metric("Congestion Index", f"{cong_idx:.0f} / 100")

    st.sidebar.markdown(
        f"**Delay Severity:** "
        f"<span style='color:{delay_color};font-weight:bold'>{delay}</span>",
        unsafe_allow_html=True,
    )
    st.sidebar.metric("Weather Impact Score", f"{weather_impact} / 10")

    top = stats.get("top_corridors", [])
    if top:
        st.sidebar.markdown("**Top Congested Corridors**")
        for i, corridor in enumerate(top[:3], 1):
            name = corridor.get("name", "").replace("_", " ")
            val = corridor.get("congestion", 0)
            bar_width = int(val)
            st.sidebar.markdown(
                f"{i}. {name}  "
                f"<span style='color:#e05252;font-weight:bold'>{val:.0f}</span>",
                unsafe_allow_html=True,
            )
