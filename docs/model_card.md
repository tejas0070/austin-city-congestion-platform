# Congestion Model Card

- **Model:** HistGradientBoostingRegressor (point) + q10/q90 quantile models (80% interval)
- **Training rows:** 382,579
- **Data source:** City of Austin Bluetooth travel sensors (real speed history)
- **Point accuracy:** MAE 9.00 congestion-pts, R squared 0.2640 (leak-free held-out)
- **Interval calibration:** empirical coverage 0.876 (nominal 0.80)
- **Confidence:** interval width mapped to 0-100 via p5/p95 width anchors (3.1 / 29.0)
- **Generated:** 2026-07-09T18:53
