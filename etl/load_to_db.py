"""
DB Loader — Austin City Congestion Platform

Reads data/processed/merged_features.csv and upserts every row into the
merged_features table.  Run after transform.py.

Also creates all tables defined in backend/app/models.py if they don't exist yet.
Supports both SQLite (local dev, USE_SQLITE=true) and PostgreSQL (Docker/production).
"""

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.app.database import Base, SessionLocal, engine
from backend.app.models import CachedPrediction, MergedFeature

PROCESSED_FILE = os.path.join(
    os.path.dirname(__file__), "..", "data", "processed", "merged_features.csv"
)

_DIALECT = engine.dialect.name  # "sqlite" or "postgresql"

if _DIALECT == "sqlite":
    from sqlalchemy.dialects.sqlite import insert
else:
    from sqlalchemy.dialects.postgresql import insert


def create_tables() -> None:
    print("[*] Creating tables if they don't exist...")
    Base.metadata.create_all(bind=engine)
    print(f"    Done. (dialect: {_DIALECT})")


def load_merged_features() -> bool:
    if not os.path.exists(PROCESSED_FILE):
        print(f"[-] Processed file not found: {PROCESSED_FILE}")
        print("    Run etl/transform.py first.")
        return False

    df = pd.read_csv(PROCESSED_FILE, parse_dates=["timestamp"])
    print(f"[*] Loading {len(df)} rows into merged_features...")

    db = SessionLocal()
    try:
        rows = df.where(pd.notna(df), None).to_dict(orient="records")

        stmt = insert(MergedFeature).values(rows)
        if _DIALECT == "sqlite":
            stmt = stmt.on_conflict_do_nothing()
        else:
            stmt = stmt.on_conflict_do_nothing(
                index_elements=["timestamp", "corridor_name"]
            )
        db.execute(stmt)
        db.commit()
        print(f"[+] {len(rows)} rows loaded successfully.")
        return True
    except Exception as e:
        db.rollback()
        print(f"[-] Load failed: {e}")
        return False
    finally:
        db.close()


def cache_predictions() -> None:
    """Runs ML inference for every corridor and stores results in cached_predictions.

    Called after load_merged_features() so the map endpoint never has to run
    ML inference at request time.
    """
    from backend.services.data_service import get_latest_for_corridor
    from backend.services.ml_service import predict_congestion

    CORRIDORS = [
        "I-35_Downtown",
        "Mopac_Expressway_Downtown",
        "US-183_North",
        "Loop-360_West",
        "Congress_Ave_Downtown",
    ]

    db = SessionLocal()
    try:
        updated = 0
        for corridor_name in CORRIDORS:
            reading = get_latest_for_corridor(db, corridor_name)
            if reading is None:
                continue
            result = predict_congestion(reading)
            row = db.query(CachedPrediction).filter(
                CachedPrediction.corridor_name == corridor_name
            ).first()
            if row is None:
                row = CachedPrediction(corridor_name=corridor_name)
                db.add(row)
            row.predicted_congestion_index = result["predicted_congestion_index"]
            row.congestion_label = result["congestion_label"]
            row.model_ready = result["model_ready"]
            updated += 1
        db.commit()
        print(f"[+] Cached predictions updated for {updated} corridors.")
    except Exception as e:
        db.rollback()
        print(f"[-] Prediction cache failed: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    create_tables()
    load_merged_features()
    cache_predictions()
