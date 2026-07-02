# Congestion Model Card

- **Model:** HistGradientBoostingRegressor (point) + q10/q90 quantile models (80% interval)
- **Training rows:** 382,179
- **Data source:** City of Austin Bluetooth travel sensors (real speed history)
- **Point accuracy:** MAE 9.09 congestion-pts, R squared 0.2364 (leak-free held-out)
- **Interval calibration:** empirical coverage 0.875 (nominal 0.80)
- **Confidence:** interval width mapped to 0-100 via p5/p95 width anchors (2.9 / 29.6)
- **Generated:** 2026-07-01T22:05
