# Time-Lapse Animation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add transport controls (⏮ ▶/⏸ ⏭) to the sidebar that animate the time slider through all 48 thirty-minute slots (12:00 AM → 11:30 PM) at 2 seconds per step, stopping and resetting at the end.

**Architecture:** Two session state keys (`time_slot`, `is_playing`) drive the animation. A `@st.fragment(run_every="2s")` function `_time_controls()` owns the time slider and transport buttons. On each 2-second tick it calls `advance_step()` — a pure function — and if the step changed it calls `st.rerun()` to trigger a full-app map update. When idle the fragment ticks silently without touching the main app.

**Tech Stack:** Streamlit ≥ 1.35 (`@st.fragment`, `st.rerun()`), pytest

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `components/sidebar.py` | Modify | Add `MAX_SLOT`, rename `_slot_to_label` → `slot_to_label`, add `advance_step()`, add `_time_controls()` fragment, update `render_controls()` |
| `tests/test_time_steps.py` | Create | Unit tests for `slot_to_label()` and `advance_step()` |
| `pages/live_map.py` | No change | Already reads `selections["time_slot"]` as int |
| `components/map_builder.py` | No change | Already uses `selections["time_slot"]` as int array index |

---

## Task 1: Pure functions and tests

**Files:**
- Create: `tests/test_time_steps.py`
- Modify: `components/sidebar.py`

- [ ] **Step 1: Write the failing test file**

Create `tests/test_time_steps.py` with this content:

```python
import pytest
from components.sidebar import slot_to_label, advance_step, MAX_SLOT


def test_slot_to_label_start():
    assert slot_to_label(0) == "12:00 AM"


def test_slot_to_label_end():
    assert slot_to_label(47) == "11:30 PM"


def test_slot_to_label_default():
    assert slot_to_label(34) == "5:00 PM"


def test_slot_to_label_midnight_half():
    assert slot_to_label(1) == "12:30 AM"


def test_slot_to_label_noon():
    assert slot_to_label(24) == "12:00 PM"


def test_all_labels_unique():
    labels = [slot_to_label(i) for i in range(MAX_SLOT + 1)]
    assert len(labels) == len(set(labels))


def test_max_slot_is_47():
    assert MAX_SLOT == 47


def test_advance_step_normal_increment():
    assert advance_step(34, True) == (35, True)


def test_advance_step_stop_at_max():
    assert advance_step(47, True) == (47, False)


def test_advance_step_noop_when_not_playing():
    assert advance_step(47, False) == (47, False)


def test_advance_step_idle_at_start():
    assert advance_step(0, False) == (0, False)


def test_advance_step_near_end():
    assert advance_step(46, True) == (47, True)
```

- [ ] **Step 2: Run tests — expect ImportError**

```
pytest tests/test_time_steps.py -v
```

Expected: `ImportError: cannot import name 'slot_to_label' from 'components.sidebar'`

- [ ] **Step 3: Add `MAX_SLOT`, `slot_to_label()`, and `advance_step()` to sidebar.py**

In `components/sidebar.py`, make these changes:

**a)** Replace the existing `_slot_to_label` function with `slot_to_label` (remove leading underscore) and add `MAX_SLOT` and `advance_step` right below the constants block. Replace everything from line 14 to line 41 with:

```python
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
```

- [ ] **Step 4: Run tests — expect all pass**

```
pytest tests/test_time_steps.py -v
```

Expected: 13 passed

- [ ] **Step 5: Syntax check**

```
python -m py_compile components/sidebar.py
```

Expected: no output (clean)

- [ ] **Step 6: Commit**

```bash
git add tests/test_time_steps.py components/sidebar.py
git commit -m "feat: add slot_to_label, advance_step, MAX_SLOT to sidebar"
```

---

## Task 2: Session state, fragment, and updated render_controls

**Files:**
- Modify: `components/sidebar.py`

- [ ] **Step 1: Replace `render_controls()` and add `_time_controls()` fragment**

Replace everything from the `def render_controls()` line (line 43 in the original, now shifted slightly) through the end of `render_controls()` with the following. Keep `render_stats()` intact below — do not touch it.

```python
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
    if new_val != st.session_state["time_slot"]:
        st.session_state["time_slot"] = new_val
        st.rerun()

    col1, col2, col3 = st.sidebar.columns([1, 2, 1])
    with col1:
        if st.button("⏮", key="btn_rewind", help="Rewind to 12:00 AM"):
            st.session_state["time_slot"] = 0
            st.session_state["is_playing"] = False
            st.rerun()
    with col2:
        play_label = "⏸ Pause" if st.session_state["is_playing"] else "▶ Play"
        if st.button(play_label, key="btn_play", use_container_width=True):
            st.session_state["is_playing"] = not st.session_state["is_playing"]
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
```

- [ ] **Step 2: Syntax check**

```
python -m py_compile components/sidebar.py
```

Expected: no output (clean)

- [ ] **Step 3: Run existing tests to confirm nothing broke**

```
pytest tests/test_time_steps.py -v
```

Expected: 13 passed

- [ ] **Step 4: Syntax check all app files**

```
python -m py_compile streamlit_app.py pages/live_map.py components/map_builder.py
```

Expected: no output (clean)

- [ ] **Step 5: Commit**

```bash
git add components/sidebar.py
git commit -m "feat: add time-lapse transport controls with fragment animation"
```

---

## Task 3: Visual verification

- [ ] **Step 1: Start the app**

```
streamlit run streamlit_app.py
```

Open `http://localhost:8501` in a browser.

- [ ] **Step 2: Verify transport controls appear**

In the sidebar under "Controls", you should see:
- A bold "Time of Day" label
- A caption showing "5:00 PM" (the default, slot 34)
- A slider (draggable)
- Three buttons in a row: ⏮ on the left, ▶ Play (wide) in the centre, ⏭ on the right

- [ ] **Step 3: Verify Play advances the slider**

Click **▶ Play**. The button label should change to **⏸ Pause**. Within 2 seconds the time caption should advance to the next 30-minute slot and the map congestion colours should update. Confirm it advances one slot every ~2 seconds.

- [ ] **Step 4: Verify Pause stops the animation**

While playing, click **⏸ Pause**. The animation should stop immediately on the current slot. The button label reverts to **▶ Play**.

- [ ] **Step 5: Verify slider is disabled during playback**

Click Play again. Try dragging the time slider — it should not move while the animation is running.

- [ ] **Step 6: Verify stop at 11:30 PM**

Click **⏭** to jump to slot 47 (11:30 PM), then click **▶ Play**. The animation should not advance past 11:30 PM. The button should reset to **▶ Play** automatically.

- [ ] **Step 7: Verify rewind**

While at any slot, click **⏮**. The caption should immediately show "12:00 AM" and the slider should jump to the far left.

- [ ] **Step 8: Run full test suite**

```
pytest -v
```

Expected: all tests pass (including the 13 in `test_time_steps.py`)

- [ ] **Step 9: Final commit**

```bash
git add -A
git commit -m "test: verify time-lapse animation — all checks pass"
```
