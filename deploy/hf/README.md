---
title: Austin Traffic Intelligence API
emoji: 🚗
colorFrom: indigo
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# Austin Traffic Intelligence — API

FastAPI backend serving live Austin congestion corridors plus ML congestion
**forecasts** (predicted / day / week) with a calibrated confidence signal. Runs
entirely on committed model artifacts + SQLite — no external database.

Health: `/health` · API under `/api/…` · docs at `/docs`.

**Auto-synced** (runtime subset only) from
[github.com/tejas0070/austin-city-congestion-platform](https://github.com/tejas0070/austin-city-congestion-platform)
by a GitHub Action, so every model retrain redeploys here automatically.
