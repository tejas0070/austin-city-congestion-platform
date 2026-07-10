# Results & Methodology

A production machine-learning system that forecasts Austin traffic congestion with
**calibrated uncertainty**, trained on **~382,000 real City-of-Austin sensor
readings** and evaluated with a **leak-free, regression-gated** pipeline.

The emphasis of this project is engineering rigor: honest evaluation, calibrated
confidence, and a fully automated data → train → serve → retrain loop — not a
single headline number. Every figure below is reproducible with
`python scripts/evaluate_model.py`.

---

## Headline results

The app forecasts the **typical congestion for each corridor by hour-of-week** —
exactly the quantity users act on. Measured on a leak-free hold-out set of **907
corridor-hours** never seen in training:

| Metric | Result | What it means |
| ------ | ------ | ------------- |
| **R² 0.74** | explains 74% of variance in typical congestion | strong pattern-level accuracy |
| **MAE 2.7 / 100** | avg. error under 3 congestion-points | tight on a 0–100 scale |
| **Tier accuracy 85%** | green / yellow / red classified correctly | matches what users see on the map |
| **Within ±10 pts 95%** | forecast lands within 10 points 95% of the time | reliably close |
| **80% intervals → ~80% coverage** | calibrated prediction intervals | trustworthy uncertainty, not a guess |

**Uncertainty is calibrated, not decorative.** Each forecast ships with a
prediction interval, and an 80% interval empirically contains the truth ~80% of
the time on held-out data — verified, not assumed.

---

## What the model predicts (and why the granularity matters)

Traffic has two very different questions hiding inside it:

1. **"What will this exact road read in the next 15 minutes?"** — dominated by
   short-term noise (a light cycle, one stalled car). Largely *unpredictable*.
2. **"What does this corridor typically look like at 5pm on a Thursday?"** —
   a stable, learnable pattern. This is what the app forecasts and what commuters
   actually plan around.

This project targets question 2, and reports **both** granularities honestly:

| Granularity | R² | MAE | Use |
| ----------- | -- | --- | --- |
| **Typical congestion** (per corridor × hour-of-week) | **0.74** | **2.7** | what the product delivers |
| Individual 15-min reading (hard target) | 0.26 | 9.0 | reported for transparency |

A variance decomposition confirms the individual-reading target is **~70%
irreducible short-term noise** (explainable ceiling R² ≈ 0.29), so the model
operates *near the theoretical ceiling* on that target. Recognizing this and
forecasting at the level where the signal is real is a deliberate design choice,
not a limitation worked around.

---

## Methodology — the rigor behind the numbers

### 1. Leak-free evaluation
The model's strongest feature, `seasonal_level`, is a per-(segment, hour, weekend)
target encoding. Computing it over the whole dataset **before** the train/test
split leaks held-out targets and inflates R² — an earlier build read an
impressive-but-false 0.70 this way. The pipeline now **splits first, then rebuilds
`seasonal_level` per fold**, mirroring how the live predictor serves it. The
reported R² is a true generalization estimate that is stable across retrains.
*(`backend/etl/training_eval.py`)*

 
### 2. Regression gate
Every retrain compares its honest leak-free R²/MAE against the deployed model and
**refuses to ship a materially worse one** (exit code, no artifacts written), so
the autonomous retrain loop can never degrade the live model.
*(`scripts/train_model.py`)*

### 3. Conformal-calibrated confidence
Confidence is an **expected-value prediction interval** — the range for the
*typical* value the app displays — split-conformal calibrated on held-out corridor
means so `prediction ± q` covers the truth at the nominal rate (deployed: 80%
interval ±3.9 pts → 80% empirical coverage). *(`backend/etl/confidence.py`)*

### 4. Density-aware confidence
Interval width alone would make **unmeasured** roads look confident. A **density
cap** ties each road's maximum confidence to how much real history backs it, so a
road-class fallback can never out-confidence a genuinely measured corridor. This
fixes the classic "most confident where it knows least" pathology.

### 5. Transparent context overlays
Weather, federal holidays, and event crowds are applied as **interpretable
multipliers on top of the learned baseline**, not as model features — an
ablation-driven decision after finding the raw speed data carried no reliable
weather/event signal (events were absent in ~100% of rows). This keeps every
adjustment explainable and prevents unreliable learned effects.
*(see [radar_ablation.md](radar_ablation.md))*

---

## Engineering highlights

- **End-to-end ownership:** live-feed ETL (City of Austin Socrata, TomTom, Open-Meteo,
  OSM Overpass) → feature engineering → training + quantile calibration →
  evaluation harness → FastAPI API → kepler.gl geospatial UI → free-tier deploy.
- **Autonomous & safe:** a scheduled job collects fresh real-world data, retrains,
  and redeploys every 6 hours — inside a hard free-tier API budget, and gated so a
  worse model is rejected automatically.
- **Zero-cost production:** SQLite + committed artifacts + free hosting; the app
  runs out of the box with no database to install and no paid keys.
- **Reproducible science:** one command regenerates the full scorecard into
  `model_meta.json` and `docs/model_evaluation.md`, versioned with the model.

---

## Scope

Built and validated as a focused, honest system — with clear paths to scale:

- **Grounded in real patterns.** The forecast leans on genuine historical
  seasonality per corridor; the ML layer adds generalization to roads without
  direct history, the context overlays, and the calibrated intervals on top.
- **Deepest where the data is richest.** ~18 corridors have direct per-segment
  history and read the highest confidence; the rest fall back to road-class
  averages — and the density cap makes that distinction explicit and honest.
- **Natural next steps:** a live prediction-vs-realized validation loop, broader
  per-segment ground truth as the autonomous collector accumulates depth, and an
  empirically-calibrated (vs. hand-set) weather/event overlay.

---

## Reproduce

```bash
python scripts/build_real_training_data.py   # pull + merge real Austin data
python scripts/train_model.py                # train + calibrate (regression-gated)
python scripts/evaluate_model.py             # write the honest, leak-free scorecard
```

Outputs land in [`model_evaluation.md`](model_evaluation.md) and
`data/models/model_meta.json`. Full model details: [model_card.md](model_card.md).
