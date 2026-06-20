# Congestion Model Card

- **Model:** HistGradientBoostingRegressor (point) + q10/q90 quantile models (80% interval)
- **Training rows:** 120,000
- **Data source:** City of Austin Bluetooth travel sensors (real speed history)
- **Point accuracy:** MAE 11.00 congestion-pts, R squared 0.1988
- **Interval calibration:** empirical coverage 0.898 (nominal 0.80)
- **Confidence:** interval width mapped to 0-100 via p5/p95 width anchors (22.0 / 52.9)
- **Generated:** 2026-06-20T00:29
