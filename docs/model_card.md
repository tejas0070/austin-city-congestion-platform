# Congestion Model Card

- **Model:** HistGradientBoostingRegressor (point) + q10/q90 quantile models (80% interval)
- **Training rows:** 120,000
- **Data source:** City of Austin Bluetooth travel sensors (real speed history)
- **Point accuracy:** MAE 11.03 congestion-pts, R squared 0.2061
- **Interval calibration:** empirical coverage 0.902 (nominal 0.80)
- **Confidence:** interval width mapped to 0-100 via p5/p95 width anchors (24.0 / 51.5)
- **Generated:** 2026-06-19T17:51
