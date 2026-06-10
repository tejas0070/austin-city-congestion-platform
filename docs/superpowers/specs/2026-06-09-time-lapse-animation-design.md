# Time-Lapse Animation Design
**Date:** 2026-06-09
**Project:** Austin Traffic Intelligence Platform
**Feature:** Animated time-lapse mode for the Live Map tab

---

## Summary

Add a Play/Pause/Rewind/Skip transport control row to the sidebar time controls. When playing, the time slider auto-advances through the full 24-hour day (12:00 AM → 11:30 PM) at 2 seconds per 30-minute step. The animation stops at 11:30 PM and resets the button to Play. The implementation uses Streamlit's `@st.fragment(run_every="2s")` so the map updates are driven by full-app reruns during playback, but the fragment ticks are near-zero-cost when the animation is idle.

---

## Decisions

| Question | Decision |
|---|---|
| End behavior | Stop at 11:30 PM, reset to Play (no loop) |
| Speed | 2 seconds per 30-minute step |
| UI placement | Transport controls row below time display (⏮ ▶/⏸ ⏭) |
| Implementation | `@st.fragment(run_every="2s")` — no `time.sleep` |
| Time range | 48 slots: 12:00 AM through 11:30 PM (full 24-hour coverage) |

---

## Time Steps

`TIME_STEPS` is a list of 48 strings defined once in `components/sidebar.py` and imported where needed:

```
["12:00 AM", "12:30 AM", "1:00 AM", ..., "11:00 PM", "11:30 PM"]
```

- Index 0 → 12:00 AM
- Index 15 → 7:30 AM (preserved default)
- Index 47 → 11:30 PM (`MAX_STEP`)

---

## Architecture

Two keys are added to `st.session_state`:

| Key | Type | Default | Purpose |
|---|---|---|---|
| `time_step` | int (0–47) | 15 | Current time slot index |
| `is_playing` | bool | False | Whether animation is running |

The time controls section of `components/sidebar.py` is extracted into a `@st.fragment(run_every="2s")` function `_time_controls()`.

**Fragment tick logic (runs every 2 seconds):**

```
if is_playing:
    if time_step < MAX_STEP:
        time_step += 1
    else:
        is_playing = False
    st.rerun()   # full-app rerun → map updates
# else: fragment reruns silently, main app does not rerun
```

When `is_playing` is False, the fragment ticks every 2 seconds but takes no action — no state change, no `st.rerun()`. The main app does not rerun and the map stays still. Server cost during idle is near zero.

---

## Component Changes

### `components/sidebar.py`

1. Define `TIME_STEPS` (48-entry list) and `MAX_STEP = 47` as module-level constants.
2. Initialize session state at module top:
   ```python
   st.session_state.setdefault("time_step", 15)
   st.session_state.setdefault("is_playing", False)
   ```
3. Extract `advance_step(time_step: int, is_playing: bool) -> tuple[int, bool]` as a module-level pure function (used by the fragment and by tests).
4. Extract `_time_controls()` as a `@st.fragment(run_every="2s")` function containing:
   - Animation tick logic (see above)
   - Time label display: `TIME_STEPS[st.session_state.time_step]`
   - Time slider (`disabled=True` during playback) synced to `st.session_state.time_step`
   - Transport controls row — three equal columns:
     - **⏮** — sets `time_step = 0`, `is_playing = False`
     - **▶ Play / ⏸ Pause** — toggles `is_playing`
     - **⏭** — sets `time_step = MAX_STEP`, `is_playing = False`
5. In `render_controls()`, call `_time_controls()` then read `st.session_state.time_step` when building the returned `selections` dict (replaces the old slider return value).

### `pages/live_map.py`

No structural changes. Receives `selections["time_step"]` as an int index. Uses `TIME_STEPS[selections["time_step"]]` for any display labels.

### `components/map_builder.py`

No structural changes. Receives `selections` (with `time_step` int), derives the label internally as `TIME_STEPS[selections["time_step"]]`, and uses it to key into `simulated_congestion.json` — same lookup pattern as before.

---

## Data Flow

```
st.session_state.time_step (int)
        │
        ▼
_time_controls() fragment
  - increments on tick when playing
  - calls st.rerun() → full app reruns
        │
        ▼
render_controls() → selections dict
  selections["time_step"] = st.session_state.time_step
        │
        ▼
live_map.render(selections)
  label = TIME_STEPS[selections["time_step"]]
        │
        ▼
map_builder.build_map(selections)
  congestion = simulated_congestion[label]
```

---

## Edge Cases

| Case | Handling |
|---|---|
| User drags slider during playback | Slider is `disabled=True` during playback — not possible |
| Transport buttons during playback | ⏮ and ⏭ set `is_playing = False` before jumping — no tick conflict |
| Fragment tick fires at step 47 | `else` branch sets `is_playing = False`, no increment, no out-of-bounds |
| Missing time slot in `simulated_congestion.json` | Existing fallback in `map_builder.py` handles it — no new code needed |

---

## Tests

New file: `tests/test_time_steps.py`

The tick logic is extracted into a pure function `advance_step(time_step, is_playing)` → `(new_time_step, new_is_playing)` so it can be tested without Streamlit.

Test cases:
- `TIME_STEPS` has exactly 48 entries
- `TIME_STEPS[0]` == `"12:00 AM"`
- `TIME_STEPS[47]` == `"11:30 PM"`
- No duplicate entries in `TIME_STEPS`
- `advance_step(14, True)` → `(15, True)` — normal increment
- `advance_step(47, True)` → `(47, False)` — stop at max
- `advance_step(47, False)` → `(47, False)` — no-op when not playing
- `advance_step(0, False)` → `(0, False)` — idle at start

---

## Files Changed

| File | Change type |
|---|---|
| `components/sidebar.py` | Modify — extract fragment, add transport controls, session state |
| `pages/live_map.py` | Modify — derive time label from `TIME_STEPS[time_step]` |
| `components/map_builder.py` | Modify — accept time label string (already does, minimal change) |
| `tests/test_time_steps.py` | Create — unit tests for TIME_STEPS and tick logic |

No new dependencies. No database changes. No ETL changes.
