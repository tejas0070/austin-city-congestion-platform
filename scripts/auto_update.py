#!/usr/bin/env python3
"""One-shot self-update — collect real data, retrain, and hot-reload the model.

Designed to be run on a schedule (Windows Task Scheduler / cron). Safe to run
often: TomTom collection is hard-capped to the free daily budget (a no-op once
exhausted), retrains use the cached Bluetooth/radar rows so they're fast, and the
running API hot-reloads the new model on its next prediction — no restart needed.

Pipeline:
    1. collect_tomtom_observations.py   real per-segment congestion (budget-guarded)
    2. build_tomtom_training_data.py     observations -> feature rows
    3. finalize (cached) or full rebuild combine all real sources + seasonal prior
    4. train_model.py                    retrain the model + quantiles

Run from the project root:
    python scripts/auto_update.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
BLUETOOTH_CACHE = ROOT / "data" / "training" / "_bluetooth_rows.csv"


def _run(*args: str) -> int:
    print(f"\n$ {PY} {' '.join(args)}", flush=True)
    return subprocess.run([PY, *args], cwd=str(ROOT)).returncode


def main() -> int:
    # 1. Collect real readings. Exit code 2 means the daily budget is fully spent
    #    (nothing new collected) — only then do we skip the rest to avoid a
    #    redundant retrain on unchanged data. Any other outcome proceeds normally.
    if _run("scripts/collect_tomtom_observations.py") == 2:
        print("\nDaily TomTom budget already spent — no new data; skipping retrain.")
        return 0

    # 2. Convert the accumulated observations into feature rows.
    _run("scripts/build_tomtom_training_data.py")

    # 3. Rebuild the combined training set. Fast path reuses the cached static
    #    Bluetooth rows; first run (no cache) does the one-time full pull.
    if BLUETOOTH_CACHE.exists():
        rc = _run("-m", "backend.etl.training_finalize")
    else:
        print("\n[init] No Bluetooth cache yet — doing the one-time full build.")
        rc = _run("scripts/build_real_training_data.py")
    if rc != 0:
        print("[ERROR] Training-set rebuild failed; skipping retrain.")
        return rc

    # 4. Retrain. The API hot-reloads the new artifacts on its next request.
    rc = _run("scripts/train_model.py")
    if rc == 0:
        print("\n✅ Self-update complete. The running API will serve the new model "
              "automatically (mtime hot-reload).")
    return rc


if __name__ == "__main__":
    sys.exit(main())
