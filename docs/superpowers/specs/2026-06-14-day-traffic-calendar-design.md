# Day-Preview Traffic: Event Calendar + Time Slider

**Date:** 2026-06-14
**Status:** Approved design, pending implementation plan

## Overview

Add a way to explore Austin's **predicted congestion across a whole day**, launched
from an **event calendar**. The user opens a month-grid calendar, clicks a day
(typically one with an event), and the map enters a "day-preview" mode driven by a
bottom **time slider**: drag or press play to watch predicted congestion change hour
by hour, with a 24-hour citywide congestion curve for at-a-glance shape.

This builds on work already shipped in the prior session (congestion-coloured
live/predicted layers, "as of"/"for" time captions, and the date-grouped events
list). Those are **not** rebuilt here.

## Goals

- Preview predicted traffic for **any day** within a bounded horizon, hour by hour.
- Reach it through an **event calendar**, so event days are easy to inspect.
- Make "how congestion changes over the day" legible via a **play animation** and a
  **24-hour congestion curve**.
- Use **real hourly forecast weather** when available; fall back to a current-weather
  proxy only beyond the forecast horizon, and upgrade automatically as forecasts arrive.

## Non-Goals / Out of Scope

- Per-segment exact congestion **percentage per hour** in tooltips (only the
  green/yellow/red level/index per hour). Easy follow-up if wanted.
- Editing or adding events.
- Changing the Live Traffic layer's behavior (it always shows "now").
- Historical (past) day playback — range is today forward.

## UX Design

### Two modes

- **Default mode (unchanged):** Live Traffic = now; Predicted = existing +2h forecast;
  no slider on screen.
- **Day-preview mode (new):** entered by picking a day in the calendar. A time-slider
  panel appears at the bottom; the **Predicted** layer now shows the selected day at the
  selected hour. Live Traffic still shows "now". Exit via ✕ on the panel → back to default.

### Event calendar (overlay month grid)

- Opened by a **"Calendar"** button in the Sidebar's Events tab.
- Large centered overlay over a dimmed map; ◀ ▶ to change month; ✕ to close.
- Each day cell shows its events as colored chips (blue = Sports, purple = Music,
  green = Other); a ring marks "today".
- Bounded to **today … +90 days** (matches the events horizon). Months outside the
  range still render; days outside the range are not selectable.
- Clicking a selectable day: closes the overlay, enters day-preview mode for that date,
  and opens the slider at a default hour (8 AM, or the current hour if the day is today).
- Data source: existing `GET /api/events/upcoming` fetched across the full **90-day**
  horizon (today the events list is fetched for 30 days — bump to 90 so the calendar's
  later months show their event chips).

### Time-slider panel (bottom overlay)

Left → right: selected date label · **▶ Play / ⏸** · draggable **hourly** handle (0–23) ·
current-hour label (e.g. "5:00 PM") · selected-hour weather (e.g. "72°F · Clear"). Above
the track: the **24-hour citywide congestion curve** — 24 bars coloured green/yellow/red
by `avg_level`, with a white marker at the current hour. Clicking the curve jumps to that
hour. Play auto-advances ~1 hour / 600 ms and loops; dragging/clicking sets the hour
directly. Map predicted colors update as the hour changes.

## Technical Design

### Backend

**1. Refactor (no behavior change).** Extract the core of `predict_segments()` in
`backend/services/ml_model.py` into `predict_for_datetime(target_dt, weather=None,
include_events=True, events=None)` that builds feature rows for an **absolute** datetime,
using the supplied `weather` dict (and pre-fetched `events`) when given, else fetching
current weather/events itself. The existing `/corridors/predicted` calls it with
`now + hours_ahead`, preserving the current response. The day endpoint computes weather
**per hour** and passes it in, so the 24-call loop fetches events/forecast once, not 24×.

**2. Hourly forecast weather.** Add to `backend/services/weather_service.py`:

- `fetch_hourly_forecast(target_date)` → calls Open-Meteo
  `hourly=temperature_2m,precipitation,weather_code` with `forecast_days` up to **16**
  (the API max), `temperature_unit=fahrenheit`, `precipitation_unit=inch`. Returns a
  `dict[hour 0–23] -> {weather_code, temperature_f, precipitation_in, condition}` for the
  requested date if it falls within the forecast horizon, else `None`. Cached ~15 min,
  with silent fallback (returns `None`) on error — consistent with existing service style.

**3. New endpoint:** `GET /api/traffic/corridors/day?date=YYYY-MM-DD&include_events=true`

For each of the 24 hours of `date`:
- weather = forecast hour if `fetch_hourly_forecast` has it, else the current-weather
  proxy (`fetch_current_weather`) — same proxy the +2h path already uses.
- run `predict_for_datetime` for that hour with the day's events.

Returns a **compact** payload (geometry once + per-hour index matrix):

```jsonc
{
  "date": "2026-06-14",
  "weather_source": "forecast", // "forecast" | "proxy" | "mixed"
  "segments": { /* GeoJSON FeatureCollection: geometry + segment_id, road_name, road_class */ },
  "hours": [
    { "hour": 0, "label": "12:00 AM", "predicted_for": "2026-06-14T00:00",
      "avg_pct": 8.1, "avg_level": "green",
      "temperature_f": 71.0, "condition": "Clear", "weather_source": "forecast" }
    // …24 entries…
  ],
  "series": [ [0,1,2,/* …3831 ints… */], /* hour 0 */ /* …24 arrays… */ ]
}
```

- `series[h][i]` = congestion_index (0/1/2) for segment *i* at hour *h* → drives color.
- `hours[h].avg_pct` / `avg_level` → drives the bottom curve.
- `hours[h]` weather fields → slider weather readout; `weather_source` lets the UI flag
  proxy vs real forecast.

**Why compact, not 24 GeoJSONs:** 24 full FeatureCollections ≈ 30–48 MB; geometry-once +
a 24×3831 index matrix ≈ ~2 MB. The frontend rebuilds the colored layer per hour locally.

**Caching:** cache the day response keyed by `date` (TTL ~15 min). Because both the day
cache and the forecast cache expire on ~15-min cycles, a day that was computed with the
**proxy** automatically **upgrades to real forecast** once it enters the 16-day window —
no extra plumbing. `weather_source` reflects what was used at compute time.

**Limits / errors:** `date` must be within **today … +90 days** → else **400**. Missing
model file → **503** with a clear message. Open-Meteo failure → forecast treated as
unavailable (proxy fallback), never a hard error.

### Frontend

**State (App-level):** `previewDate` (null = default mode), `previewHour` (0–23),
`isPlaying`. `previewDate !== null` ⇒ day-preview mode.

**Hook `hooks/useDayPrediction.js`** — `useDayPrediction(previewDate)` fetches
`/corridors/day` only when a date is set; returns `{ segments, hours, series, weatherSource,
loading, error }`. Provides a memoized `buildHourFC(segments, series[hour])` that stamps
each feature's `congestion_index` for the chosen hour.

**MapContainer** — in day-preview mode, the **Predicted** layer's dataset is fed
`buildHourFC(...)` for `previewHour` via `updateVisData` (geometry loaded once). In default
mode it shows the existing +2h prediction, unchanged. Live layer untouched. Per-hour FCs
are memoized so scrubbing/playback are smooth.

**Play loop** — `setInterval` advances `previewHour` (wraps 23→0) ~every 600 ms; cleared on
pause/unmount/mode-exit.

### Files

**New**

- `frontend/src/components/EventCalendar.jsx` — month-grid overlay.
- `frontend/src/components/TimeSliderPanel.jsx` — bottom panel (date, play/pause, slider,
  hour + weather label).
- `frontend/src/components/CongestionCurve.jsx` — 24-bar day curve + marker.
- `frontend/src/hooks/useDayPrediction.js`
- `frontend/src/utils/calendar.js` — pure month-grid math + events-by-day index.

**Changed**

- `frontend/src/App.js` — owns preview state; wires calendar ↔ slider ↔ map.
- `frontend/src/components/MapContainer.jsx` — day-preview feeding of the Predicted layer.
- `frontend/src/components/Sidebar.jsx` — "Calendar" button in the Events tab.
- `frontend/src/services/trafficService.js` — `fetchDayPrediction(date)`.
- `frontend/src/utils/datetime.js` — hour-label helper if not already present.
- `backend/services/ml_model.py` — refactor + `predict_for_datetime`, day assembly.
- `backend/services/weather_service.py` — `fetch_hourly_forecast`.
- `backend/api/routes/traffic.py` — new `/corridors/day` route + date validation.

### Testing

- **Backend (pytest):**
  - `predict_for_datetime` parity: same output as the old `+2h` path for an equivalent time.
  - `/corridors/day` shape: 24 hours, `len(series) == 24`, each row length `== segment_count`,
    indices ∈ {0,1,2}, `avg_pct`/`avg_level` present, `weather_source` ∈ {forecast, proxy, mixed}.
  - Date-range validation: out-of-range → 400.
  - `fetch_hourly_forecast` with mocked Open-Meteo (in-window → per-hour dict; beyond 16 days
    → None; HTTP error → None).
- **Frontend (pure-function unit tests):**
  - `utils/calendar.js`: month-grid layout (week alignment, month boundaries, leap handling),
    events-by-day index.
  - `buildHourFC`: stamps the correct index per segment for a given hour.

### Performance

- One model `.predict` over ~92k rows per uncached day (~sub-second to ~2 s), then cached.
- ~2 MB payload; per-hour relayer is local; play throttled to hourly steps so the map isn't
  thrashed.

## Assumptions & Limitations

- Predicted congestion reflects **typical patterns + nearby event attendance + weather**;
  it is a model estimate, not a live measurement of the future.
- Weather is **real hourly forecast within ~16 days**, current-weather **proxy** beyond that;
  the slider flags which via `weather_source`.
- Range is **today … +90 days**.
