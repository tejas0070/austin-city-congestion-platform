"""
DB Loader — Austin City Congestion Platform

Reads data/processed/merged_features.csv and upserts every row into the
merged_features PostgreSQL table.  Run after transform.py.

Also creates all tables defined in backend/app/models.py if they don't exist yet.
"""

import os
import sys

import pandas as pd
from sqlalchemy.dialects.postgresql import insert

# Allow imports from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.app.database import Base, SessionLocal, engine
from backend.app.models import MergedFeature

PROCESSED_FILE = os.path.join(
    os.path.dirname(__file__), "..", "data", "processed", "merged_features.csv"
)


def create_tables() -> None:
    print("[*] Creating tables if they don't exist...")
    Base.metadata.create_all(bind=engine)
    print("    Done.")


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

        # Use PostgreSQL upsert — on conflict (timestamp, corridor_name) do nothing
        # to avoid duplicate loads on re-runs.
        stmt = insert(MergedFeature).values(rows)
        stmt = stmt.on_conflict_do_nothing(index_elements=["timestamp", "corridor_name"])
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


if __name__ == "__main__":
    create_tables()
    load_merged_features()
