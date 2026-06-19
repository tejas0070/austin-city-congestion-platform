# Traffic Prediction Confidence on Real Austin Data — Design

**Date:** 2026-06-18
**Status:** Approved (design)

## Summary

The platform already serves an ML congestion prediction (`HistGradientBoostingRegressor`)
as a point estimate per road segment, powering the "Predicted +2h" map layer. This
feature adds **statistical prediction confidence** to those predictions and trains the
whole model on **real City of Austin traffic-sensor data** instead of the current
synthetic data.

Confidence is real uncertainty quantification via **quantile regression**: per-segment
80% prediction intervals, converted to a confidence score, plus a global roll-up.
Displayed in the segment tooltip and the legend. Scope is the **+2h predicted layer
only** (the 24-hour day-prediction surface is out of scope for this cut).

## Goals

- Train on real, free, Austin-specific data (resume-worthy).
- Attach calibrated per-segment confidence to predictions.
- Add **zero** latency to the live request path — all heavy work stays offline.
- Produce defensible metrics (MAE, R², empirical interval coverage) as a portfolio artifact.

## Non-Goals

- Confidence on the day-prediction (24h matrix) surface — later.
- Recurring/scheduled retraining — one-time historical pull for now.
- Visual encoding of confidence on the map (opacity/dashes) — tooltip + legend only.
- Reconstructing the *long tail* of small historical events — only major/mid-size events
  are backfilled (see Section A.6); small live events are still handled at prediction time.

## Architecture Principle: offline-train / online-serve

The hot path is unchanged. The model is trained once into `.pkl` artifacts, loaded into
memory at startup, and predictions are pure in-memory math (ms). Real data only affects
the **offline batch ETL + training**, never the API. This is what keeps "load real data"
from adding any lag.

## Section A — Real-data ETL pipeline (offline)

New script `scripts/build_real_training_data.py`, run manually:

1. **Pull sensor history** from Austin's Socrata portal (reuse existing Socrata client/token).
   Primary source: travel-time / speed sensor dataset (direct congestion signal); fallback:
   radar volume counts. Exact dataset id + schema verified during planning — not hardcoded
   from memory. Paged + written incrementally so memory stays flat over a 12–24 month window.
2. **Derive target `congestion_pct`** from speed:
   `congestion_pct = clamp(100 × (1 − observed_speed / free_flow_speed), 0, 100)`,
   free-flow = the sensor's 85th-percentile speed. (Volume fallback: normalize against the
   sensor's peak/capacity.)
3. **Map each sensor → nearest road segment** (centroid distance vs `austin_network.geojson`)
   to attach `road_class` and `dist_downtown_km`.
4. **Join historical weather** from Open-Meteo's free historical archive API (no key), keyed
   on each reading's date/hour. Time features (hour, dow, weekend, month) derive from the timestamp.
5. **Events (curated historical backfill):** build `data/events/austin_major_events.csv`
   (date, venue lat/lng, attendance) covering the last 12–24 months of significant Austin
   events across a **spread of attendance sizes** — not just the biggest — so the continuous
   `nearby_event_attendance` feature gets resolution across its full range:
   - ~100k UT football (DKR), ~75k ACL / F1 (COTA), ~20k Q2 Stadium (Austin FC),
     ~15k Moody Center, ~5k Moody Amphitheater / smaller venues.
   The ETL joins these the same distance/time-weighted way the live predictor does. Rows with
   no nearby curated event get `0`. Because the feature is continuous and trained across a range
   of sizes, the model learns a **smooth attendance→traffic curve** and **interpolates to small
   future events automatically** — at live time the existing Ticketmaster feed supplies real
   attendance for upcoming events of any size, and a small event yields a proportionally small
   predicted impact. No special-casing of small events is required.
6. **Output** `data/training/congestion_history.csv` with the **identical column contract** used
   today, so `train_model.py` consumes it with no feature-code changes.

## Section B — Training + calibration metrics

`scripts/train_model.py` extends to:

- Keep the existing point model → `data/models/congestion_model.pkl` (drives map coloring; unchanged).
- Train two `HistGradientBoostingRegressor(loss="quantile")` models at `quantile=0.1` and `0.9`
  → 80% interval. Saved as `data/models/congestion_quantiles.pkl` = `{"q10": ..., "q90": ...}`.
- Compute on a held-out **real** test set and write to `model_meta.json`:
  - **MAE**, **R²** (point accuracy).
  - **Interval coverage** — fraction of held-out observations inside the predicted 80% band
    (the calibration metric; target ≈ 0.80).
  - **Width-calibration anchors** — 5th and 95th percentile interval widths, for the
    width→confidence mapping.
- Generate `docs/model_card.md`: dataset size, date range, features, MAE/R²/coverage — portfolio artifact.

## Width → confidence mapping

In `backend/services/congestion_features.py` (single source of truth), `width_to_confidence(width)`:
linearly map interval width between the stored 5th/95th-percentile anchors to a 0–100 score,
**inverted** (tight band → high confidence), clamped to [0, 100]. Labels:
**High ≥ 75, Medium 50–74, Low < 50** (tunable constants).

## Section C — Backend prediction & API contract

`backend/services/ml_model.py` loads the quantile models as startup singletons. Per segment:
- `low = clamp(min(q10, q90), 0, 100)`, `high = clamp(max(q10, q90), 0, 100)` (guards quantile crossing).
- `confidence_pct`, `confidence_label` from `width_to_confidence(high − low)`.

**Per-feature props added to `/api/traffic/corridors/predicted`:**
`congestion_low`, `congestion_high`, `confidence_pct`, `confidence_label`.

**Top-level roll-up on the FeatureCollection:** `confidence_avg`, `confidence_label` (mean across segments).

**Graceful fallback:** if `congestion_quantiles.pkl` is absent, predictions behave exactly as today
and confidence fields are omitted — never an error. Existing 90s cache retained; confidence math is negligible.

## Section D — Frontend display

- **Tooltip** (Predicted +2h layer, `MapContainer.jsx`): predicted congestion, interval (`62–80%`),
  and `Confidence: 82% (High)`.
- **Legend/header** (`TrafficLegend`): global roll-up `Forecast confidence: 82% (High)`, shown only
  when the predicted layer is active.
- Confidence fields absent ⇒ UI omits them, no errors.
- Map color encoding unchanged.

## Section E — Testing (TDD)

- **Unit:** `width_to_confidence()` (tight→high, wide→low, clamping, anchor edges); interval clamping +
  quantile-crossing guard; congestion-target derivation from speed.
- **Contract:** `/predicted` includes new per-feature + roll-up fields; fallback test (quantile models
  absent ⇒ valid response without confidence fields).
- **ETL:** fixture of fake sensor rows ⇒ correct `congestion_history.csv` shape/column contract;
  event-join test — a reading near a curated event's time/venue gets non-zero `nearby_event_attendance`,
  one far away gets `0`.
- 80%+ coverage on new code. (Empirical interval coverage is a model metric from `train_model.py`,
  distinct from test coverage.)

## Files touched

- New: `scripts/build_real_training_data.py`, `data/events/austin_major_events.csv` (curated),
  `docs/model_card.md` (generated).
- Modified: `scripts/train_model.py`, `backend/services/ml_model.py`,
  `backend/services/congestion_features.py`, `frontend/src/components/MapContainer.jsx`,
  `frontend/src/components/TrafficLegend.*`.
- New artifact: `data/models/congestion_quantiles.pkl`; updated `data/models/model_meta.json`,
  regenerated `data/training/congestion_history.csv`.

## Known limitations

- Sensors are point locations, not full network coverage; the model generalizes via
  segment-agnostic features. Per-segment confidence spread reflects real predictability.
- Only major/mid-size historical events are backfilled (curated CSV). The long tail of small
  historical events is treated as 0; small *future* events are still handled live via interpolation
  along the continuous attendance feature.
- Curated event attendance figures are approximate (published/estimated), which is acceptable for
  learning the attendance→traffic curve.
- Exact Socrata dataset id/schema and the speed-vs-volume target path confirmed in planning.
