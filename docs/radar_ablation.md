# Radar data ablation

Leak-free held-out comparison of data-source variants, plus the learned weather/event responses the product is meant to explain. All variants use the identical split + per-fold `seasonal_level` rebuild + model as the deployed trainer.

| Metric | Baseline (BT+Radar+TT) | No radar (BT+TT) | Radar capped (BT+Radar*+TT) |
| --- | --- | --- | --- |
| Rows | 380979 | 80979 | 161367 |
| Segments | 2595 | 2592 | 2592 |
| Dense corridors (>= 12) | 22 | 10 | 10 |
| **Aggregate R2** | 0.821 | 0.752 | 0.717 |
| Aggregate MAE | 2.48 | 3.93 | 4.20 |
| Aggregate tier-acc | 0.838 | 0.804 | 0.749 |
| Aggregate buckets | 909 | 331 | 334 |
| Per-reading MAE | 8.80 | 12.04 | 11.25 |
| Per-reading R2 | 0.279 | 0.247 | 0.197 |
| Per-reading tier-acc | 0.680 | 0.486 | 0.552 |
| EV interval q (80%) | 4.12 | 6.58 | 6.62 |
| EV coverage (80%) | 0.822 | 0.789 | 0.772 |
| MAE reduction vs naive | 0.239 | 0.171 | 0.152 |
| **Rain delta (Clear->Heavy)** | 1.36 | -2.29 | 0.79 |
| Storm delta (Clear->Storm) | 1.08 | -4.13 | -1.79 |
| **Event delta (0->20k)** | 0.00 | 0.00 | 0.00 |
| Weather importance (MAE+) | 0.252 | 0.197 | 0.259 |
| Event importance (MAE+) | 0.000 | 0.000 | 0.000 |

## Conclusion: keep radar

The prior worry was that radar (79% of rows from 13 intersections) distorted the
model. The ablation disproves it. Radar is the best variant on every honest axis:

- **Aggregate accuracy** R² 0.82 vs 0.75 (none) / 0.72 (capped); MAE 2.5 vs 3.9 / 4.2.
- **Per-reading accuracy** MAE 8.8 vs 12.0 / 11.3 — an apples-to-apples slice that
  is not affected by bucket-population differences, and still favors radar.
- **Weather has the right SIGN only with radar** (+1.4 pts Clear→Heavy Rain). Drop
  radar and the model learns rain *reduces* congestion (−2.3), which is nonsense —
  the arterial/TomTom data alone is too sparse to pin the weather response down.
- **Dense High-confidence corridors** 22 vs 10 — radar doubles the map coverage
  that can honestly read "High".

Honest caveat: aggregate R² is measured over each variant's own ≥5-reading buckets
(909 vs ~330), so part of the gap is that radar adds many well-sampled buckets, not
pure model skill. The per-reading and weather-sign results are not subject to that
caveat and point the same way, so the decision is robust.

**Decision:** keep radar as deployed; no pipeline change. Documented here so the
choice is defensible ("I A/B-tested my densest source and the data justified it").

## Separate finding: the event feature is dead

`nearby_event_attendance` is **0 in 100% of training rows** (the real sensor
history windows contain no curated events), so its learned importance is exactly
0.000 and the "20k concert" counterfactual moves congestion by 0.00 in every
variant. The model **cannot forecast event impact today** — this is a data/feature
gap, not a radar issue, and is addressed separately (event-impact overlay).
