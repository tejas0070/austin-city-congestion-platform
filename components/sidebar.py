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


@st.fragment(run_every="2s")
def _time_controls() -> None:
    """
    Fragment that owns the time slider and transport controls.

    Auto-reruns every 2 seconds. When playing, advances time_slot by one
    step and triggers a full-app rerun so the map updates. When idle the
    fragment reruns silently — no state change, no full-app rerun.
    """
    new_slot, new_playing = advance_step(
        st.session_state["time_slot"],
        st.session_state["is_playing"],
    )
    state_changed = (
        new_slot != st.session_state["time_slot"]
        or new_playing != st.session_state["is_playing"]
    )
    if state_changed:
        st.session_state["time_slot"] = new_slot
        st.session_state["is_playing"] = new_playing
        st.rerun()  # full-app rerun so the map layer updates

    st.sidebar.markdown("**Time of Day**")
    st.sidebar.caption(f"**{slot_to_label(st.session_state['time_slot'])}**")

    new_val = st.sidebar.slider(
        "time_slot_slider",
        min_value=0,
        max_value=MAX_SLOT,
        value=st.session_state["time_slot"],
        format="%d",
        label_visibility="collapsed",
        disabled=st.session_state["is_playing"],
        key="time_slider_widget",
    )
    if not st.session_state["is_playing"] and new_val != st.session_state["time_slot"]:
        st.session_state["time_slot"] = new_val
        st.rerun()

    col1, col2, col3 = st.sidebar.columns([1, 1, 1])
    with col1:
        if st.button("⏮", key="btn_rewind", help="Rewind to 12:00 AM", use_container_width=True):
            st.session_state["time_slot"] = 0
            st.session_state["is_playing"] = False
            st.rerun()
    with col2:
        play_label = "⏸ Pause" if st.session_state["is_playing"] else "▶ Play"
        if st.button(play_label, key="btn_play", use_container_width=True):
            st.session_state["is_playing"] = not st.session_state["is_playing"]
            st.rerun()
    with col3:
        if st.button("⏭", key="btn_skip", help="Skip to 11:30 PM"):
            st.session_state["time_slot"] = MAX_SLOT
            st.session_state["is_playing"] = False
            st.rerun()


def render_controls() -> dict:
    """Render sidebar controls and return current selections as a dict."""
    st.session_state.setdefault("time_slot", 34)  # default 5:00 PM
    st.session_state.setdefault("is_playing", False)

    st.sidebar.markdown("## Controls")

    _time_controls()

    day = st.sidebar.selectbox("Day of Week", DAYS, index=0)

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

    time_slot = st.session_state["time_slot"]
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
