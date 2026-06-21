# Forecast Model Panel — Confidence & Congestion over Time

**Date:** 2026-06-21
**Status:** Approved design, ready for implementation planning

## Problem

The backend computes a whole-day average forecast confidence and a 7-day
(Mon–Sun) rollup (added in the prior session), but the UI surfaces almost none
of it: only a single legend line and a couple of badges in the day-preview
panel. The week rollup has a service function (`fetchWeekConfidence`) and a
backend endpoint (`/api/traffic/corridors/week`) but **no UI at all**.

Users should be able to:

1. See **how confident** the model is, as measurable numbers, at two time
   scales (across a day, and across a week).
2. See **how accurate** the model is — the defensible ~90% figure.
3. See **congestion** alongside confidence, kept visually distinct, so they can
   read how each metric changes over time (e.g. confidence dips when congestion
   spikes at rush hour).

## Goal

An always-on **Forecast Model panel** in the sidebar (under the traffic legend)
that presents model accuracy, plus day-scale and week-scale readouts that each
split **Confidence** and **Congestion** into separate number+graph displays.

## Non-Goals

- No changes to the map layers, kepler datasets, or the existing
  Predicted/Live/Day-preview map behavior.
- No new model training or change to how confidence/congestion are computed.
- Not surfacing MAE (±11%) or R² (0.20) in the UI — by decision, only the
  coverage-based accuracy and the confidence/congestion scores are shown.

## Definitions (honest framing)

- **Accuracy** = `empirical_coverage` from `model_meta.json` (0.898 → "90%
  accurate"). Means: the model's 80% prediction interval contains the real
  value ~90% of the time. UI tooltip must state this plainly — NOT "90% of
  predictions are exactly right."
- **Confidence** = the interval-width-derived score already implemented
  (`backend/etl/confidence.py`, `width_to_confidence`). High/Medium/Low bands at
  75 / 50. Rendered in **blue** so it never visually competes with traffic colors.
- **Congestion** = predicted congestion percent / level (green/yellow/red),
  the existing traffic metric.

## Visual Design (approved)

Reference mockup: `.superpowers/brainstorm/1536-1782070855/content/model-card-v4.html`
(approved iteration; earlier iterations v1–v3 in the same brainstorm session show
the path to it).

A vertical stack in the sidebar, top to bottom:

1. **Model header card** — "Forecast model" label + a green **"90% accurate"**
   badge (hover tooltip explains coverage).
2. **Day card** — header "Day · <date>", then two stacked, divider-separated
   sections:
   - **◆ Confidence** (blue): big number + High/Med/Low pill + sub-note
     ("range L–H%") + a 24-hour bar graph (one bar per hour, blue).
   - **▮ Congestion** (g/y/r): big number + level pill + sub-note
     ("peak N% · <hour>") + a 24-hour bar graph (per-hour, colored by level).
3. **Week card** — header "Week · <Mon>–<Sun> · Mon–Sun", then two
   divider-separated sections:
   - **◆ Confidence · avg N%** (blue): 7 day-bars, each with its % above and a
     weekday letter below; selected day outlined.
   - **▮ Congestion · avg <level>** (g/y/r): 7 day-bars, each with its % and
     weekday letter; selected day outlined.

**Layout invariants:**

- **Text never overlaps a graph.** Numbers and labels live in their own rows
  above/below the bars; bars are laid out with normal flow + fixed heights, not
  with text absolutely positioned over them.
- Confidence is always blue; congestion always uses the green/yellow/red ramp.
- Bar **height encodes the metric's percentage**; congestion color encodes the
  congestion level (height and color agree for congestion, height-only for
  confidence).

## Scope & Behavior

- **Day card** reflects `previewDate ?? today`. In live view it shows today; when
  a day is previewed it shows that day. The intra-day graphs use the per-hour
  values already returned by `predict_day`.
- **Week card** shows the **Mon–Sun week containing `previewDate ?? today`**.
  Selecting a day in the calendar switches the week if the day falls in a
  different Mon–Sun window, and highlights the selected day. The week refetches
  **only when the Monday changes** — not on hour-scrub.
- **Week day-bars are clickable** → call the existing `handleSelectDay(iso)` so
  clicking a bar previews that day (and updates the highlight). Both the
  confidence row and congestion row share the same selected-day highlight.

## Architecture

### Backend (small additions)

All changes live in `backend/services/ml_model.py` (+ one route test file).

1. **`predict_day`** — add top-level `congestion_avg` (rounded mean of the 24
   hourly `avg_pct`) and `congestion_level` (`congestion_level(congestion_avg)`).
   Per-hour `avg_pct` / `avg_level` and per-hour `confidence_avg`, plus the
   whole-day `confidence_avg`, already exist.
2. **`predict_week`** — for each day entry include `congestion_avg` and
   `congestion_level` (taken from that day's `predict_day` result), and add a
   week-level `congestion_avg` / `congestion_level` (mean of the 7 daily
   congestion averages). Per-day and week `confidence_avg`/`confidence_label`
   already exist. When a day lacks data its congestion fields are omitted, mirroring
   the existing confidence-absent handling.
3. **`/api/traffic/model/info`** — no change; already returns
   `empirical_coverage`. Frontend derives `accuracyPct = round(coverage * 100)`.

### Frontend

**Hooks**

- `useModelInfo()` — fetches `/api/traffic/model/info` once on mount; exposes
  `{ accuracyPct, available, loading }`. `accuracyPct = round(empirical_coverage
  * 100)`, or `null` when missing.
- `useWeekConfidence(anchorISO)` — derives the Monday of the anchor's week via
  `weekBounds`, calls `fetchWeekConfidence(mondayISO)`; exposes
  `{ days, confidenceAvg, confidenceLabel, congestionAvg, congestionLevel,
  loading, error }`. Refetches only when the derived Monday changes. Catches the
  horizon 400 (see Errors) and surfaces it as a flag rather than throwing.
- Day data reuses the existing **`useDayPrediction`**, now called with
  `previewDate ?? today` so the day card is always populated. (Today's call adds
  one cached day-prediction fetch on load.)

**Utils (pure, unit-tested)**

- `weekBounds(dateISO)` → `{ mondayISO, days: string[7] }` (Mon-first week
  containing the date). Lives in `utils/` near `calendar.js`.
- Shared color mappings: extract `confidenceColor(label)` and reuse the existing
  congestion `LEVEL_COLOR` (from `CongestionCurve`) / `colorScales` into a small
  shared module so cards and existing components agree.

**Components (small, presentational)**

- `MiniBars` — generic bar strip. Props: `bars: { heightPct, color, topLabel?,
  bottomLabel?, selected? }[]`, optional `onSelect(index)`, optional `axis`.
  Renders label rows separate from bars (enforces the no-overlap invariant).
  Used for both the 24-hour and 7-day graphs.
- `MetricReadout` — props: `label`, `value`, `pill`, `subNote`, `bars`. Renders
  the number row + the `MiniBars` graph.
- `ModelAccuracyBadge` — props: `accuracyPct`. The green badge + tooltip.
- `DayModelCard` — props: day data (`{ date, confidenceAvg, confidenceLabel,
  congestionAvg, congestionLevel, hours }`). Composes two `MetricReadout`s.
- `WeekModelCard` — props: week data + `selectedISO` + `onSelectDay`. Composes
  two `MetricReadout`s (7-bar), wiring bar clicks to `onSelectDay`.
- `ModelPanel` — stacks `ModelAccuracyBadge` + `DayModelCard` + `WeekModelCard`;
  rendered in `Sidebar` under `TrafficLegend`.

**Wiring**

`App` already owns `previewDate`. It computes `anchorISO = previewDate ?? today`,
passes `day = useDayPrediction(anchorISO)`, `week = useWeekConfidence(anchorISO)`,
and `accuracy = useModelInfo()` down through `Sidebar` into `ModelPanel`. Bar
clicks in `WeekModelCard` call the existing `handleSelectDay`.

### Data Flow

```
App (previewDate)
  ├─ anchorISO = previewDate ?? today
  ├─ useModelInfo() ───────────────► accuracyPct
  ├─ useDayPrediction(anchorISO) ──► day hours + day confidence/congestion avgs
  └─ useWeekConfidence(anchorISO) ─► 7 days + week confidence/congestion avgs
        │
        └─ weekBounds(anchorISO).mondayISO ─► fetchWeekConfidence(monday)
  Sidebar → ModelPanel → { ModelAccuracyBadge, DayModelCard, WeekModelCard }
        WeekModelCard.onSelectDay → App.handleSelectDay(iso)
```

## Loading & Cost

- Day and week predictions are heavy on a cold cache (server caches each
  `predict_day` 15 min; `predict_week` reuses those). First load can take a few
  seconds.
- The accuracy badge and any already-resolved numbers render immediately; each
  graph shows a **shimmer placeholder** until its data arrives.
- The week refetches **only when the Monday changes**, so hour-scrubbing and
  same-week day changes don't re-trigger the 7-day computation.

## Error Handling & Edge Cases

- **No quantiles** (confidence absent): confidence number shows "—", its graph
  is hidden; congestion still renders. (Quantile models exist today; this is
  defensive.)
- **Horizon edge**: if `previewDate` is so far out that its Monday exceeds the
  +90-day window, `/week` returns 400. `useWeekConfidence` catches it and sets an
  `unavailable` flag; `WeekModelCard` hides its body with a small note
  ("Week unavailable this far ahead"). The day card still works.
- **Week/day fetch error**: cards show a subtle inline error and keep the rest
  of the panel functional. Errors are never swallowed silently.
- **Layout invariant** (restated as an acceptance criterion): no text element is
  rendered over a bar graph in any state, at the sidebar's fixed width.

## Testing

**Backend**

- Extend `predict_day` tests: assert `congestion_avg` / `congestion_level`
  present and in range; `congestion_avg` equals mean of hourly `avg_pct`.
- Extend `predict_week` tests: each day has `congestion_avg` / `congestion_level`;
  week-level congestion equals mean of daily congestion averages.
- `/api/traffic/corridors/week` route validation (past `start`, out-of-range
  `start`, malformed `start`) mirroring the existing day-route tests.

**Frontend**

- `weekBounds` unit tests (Mon-first window; week boundaries; year/month
  rollover).
- `MiniBars` / `MetricReadout` pure-render tests, including the no-text-overlap
  structure (labels in separate rows from bars).
- Scope logic: `previewDate ?? today → Monday` selection and "refetch only when
  Monday changes".

## Open Questions

None. Accuracy stat (coverage only), card split (confidence vs congestion at day
and week), week scope (follows previewed day), and the no-overlap layout
constraint are all decided.
