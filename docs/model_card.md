# Congestion Model Card

- **Model:** HistGradientBoostingRegressor (point) + q10/q90 quantile models (80% interval)
- **Training rows:** 277,390
- **Data source:** City of Austin Bluetooth travel sensors (real speed history)
- **Point accuracy:** MAE 7.17 congestion-pts, R squared 0.5438
- **Interval calibration:** empirical coverage 0.901 (nominal 0.80)
- **Confidence:** interval width mapped to 0-100 via p5/p95 width anchors (3.2 / 28.3)
- **Generated:** 2026-06-29T16:05
