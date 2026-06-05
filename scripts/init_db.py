"""
Database initialisation script.

Run once (or any time) to:
  1. Check that geoalchemy2 and shapely are installed
  2. Create the target PostgreSQL database if it does not exist
  3. Verify the connection to that database
  4. Enable the PostGIS extension
  5. Create all five geospatial tables (idempotent — safe to re-run)
  6. Print a row-count summary

Usage (from the project root):
    pip install geoalchemy2 shapely        # if not done yet
    python scripts/init_db.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Step 0: dependency check ───────────────────────────────────────────────────
for pkg, install_name in [("geoalchemy2", "geoalchemy2>=0.14"), ("shapely", "shapely>=2.0")]:
    try:
        __import__(pkg)
    except ImportError:
        print(f"\n[ERROR] '{pkg}' is not installed.")
        print(f"  Fix:  pip install {install_name}\n")
        sys.exit(1)

from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError, ProgrammingError


def _divider():
    print("-" * 56)


def _load_env() -> dict:
    """Load .env and return the Postgres connection params."""
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

    use_sqlite = os.getenv("USE_SQLITE", "false").lower() == "true"
    if use_sqlite:
        print("\n[ERROR] USE_SQLITE=true — this script requires PostgreSQL.")
        print("  Set USE_SQLITE=false in your .env file.\n")
        sys.exit(1)

    missing = [v for v in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")
               if not os.getenv(v)]
    if missing:
        print(f"\n[ERROR] Missing .env variables: {', '.join(missing)}\n")
        sys.exit(1)

    return {
        "host":     os.environ["DB_HOST"],
        "port":     os.environ["DB_PORT"],
        "name":     os.environ["DB_NAME"],
        "user":     os.environ["DB_USER"],
        "password": os.environ["DB_PASSWORD"],
    }


def _ensure_database_exists(cfg: dict) -> None:
    """
    Connect to the postgres maintenance database and CREATE the target
    database if it does not already exist.
    """
    maintenance_url = (
        f"postgresql://{cfg['user']}:{cfg['password']}"
        f"@{cfg['host']}:{cfg['port']}/postgres"
    )
    try:
        maint = create_engine(maintenance_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
        with maint.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": cfg["name"]},
            ).scalar()

            if exists:
                print(f"  Database '{cfg['name']}' already exists.")
            else:
                # Database names with hyphens must be double-quoted in SQL
                conn.execute(text(f'CREATE DATABASE "{cfg["name"]}"'))
                print(f"  Database '{cfg['name']}' created.")
        maint.dispose()
    except OperationalError as exc:
        print(f"\n[ERROR] Cannot connect to PostgreSQL at {cfg['host']}:{cfg['port']}")
        print(f"  Detail: {exc.orig}")
        print("\n  Check that:")
        print("  • PostgreSQL is running  (try: docker-compose up db -d)")
        print("  • DB_HOST / DB_PORT / DB_USER / DB_PASSWORD in .env are correct\n")
        sys.exit(1)


def _make_engine(cfg: dict):
    url = (
        f"postgresql://{cfg['user']}:{cfg['password']}"
        f"@{cfg['host']}:{cfg['port']}/{cfg['name']}"
    )
    return create_engine(url, pool_pre_ping=True, pool_size=3, max_overflow=5)


def _enable_postgis(engine) -> str:
    """Enable PostGIS extension and return its version string."""
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.commit()
        version = conn.execute(text("SELECT PostGIS_Lib_Version()")).scalar()
    return version


def _create_tables(engine) -> None:
    """
    Import geo_models (registers all five models with Base.metadata)
    then call create_all so SQLAlchemy emits CREATE TABLE IF NOT EXISTS
    for each one.
    """
    from backend.app.database import Base
    import backend.app.geo_models  # noqa: F401  # pyright: ignore[reportUnusedImport]

    Base.metadata.create_all(bind=engine)


TABLE_NAMES = [
    "road_segments",
    "traffic_observations",
    "weather_snapshots",
    "events",
    "predictions",
]


def main() -> None:
    _divider()
    print("  Austin Traffic Predictor — Database Init")
    _divider()

    # 0. Load env
    cfg = _load_env()
    print(f"\n  Target database: {cfg['host']}:{cfg['port']}/{cfg['name']}")
    print(f"  User:            {cfg['user']}\n")

    # 1. Create database if needed
    print("[1/4] Ensuring database exists…")
    _ensure_database_exists(cfg)

    # 2. Connect to target database
    print("\n[2/4] Connecting to target database…")
    engine = _make_engine(cfg)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"  Connected to '{cfg['name']}' successfully.")
    except OperationalError as exc:
        print(f"\n[ERROR] Connection to '{cfg['name']}' failed: {exc.orig}\n")
        sys.exit(1)

    # 3. Enable PostGIS
    print("\n[3/4] Enabling PostGIS extension…")
    try:
        version = _enable_postgis(engine)
        print(f"  PostGIS {version} is active.")
    except ProgrammingError as exc:
        print(f"\n[ERROR] PostGIS extension could not be enabled: {exc.orig}")
        print("  Your PostgreSQL instance must include PostGIS.")
        print("  If using Docker, run:  docker-compose up db -d\n")
        sys.exit(1)

    # 4. Create tables
    print("\n[4/4] Creating tables…")
    try:
        _create_tables(engine)
    except Exception as exc:
        print(f"\n[ERROR] create_all() failed: {exc}\n")
        sys.exit(1)

    inspector = inspect(engine)
    existing = set(inspector.get_table_names())

    all_ok = True
    for table in TABLE_NAMES:
        ok = table in existing
        all_ok = all_ok and ok
        mark = "[OK]" if ok else "[!!]"
        note = "" if ok else "  <- MISSING"
        print(f"  {mark}  {table}{note}")

    # 5. Row-count summary
    _divider()
    print("\n  Row counts:\n")
    with engine.connect() as conn:
        for table in TABLE_NAMES:
            if table in existing:
                n = conn.execute(text(f'SELECT COUNT(*) FROM "{table}"')).scalar()
                print(f"    {table:32s} {n:>8,} rows")
            else:
                print(f"    {table:32s}   (missing)")

    _divider()
    if all_ok:
        print("\n  All tables created. Database is ready.\n")
        print("  Next: populate tables via the ETL pipeline:")
        print("    python etl/run_all_etl.py")
        print("    python etl/transform.py")
        print("    python etl/load_to_db.py\n")
    else:
        print("\n  Some tables are missing — check the errors above.\n")
        sys.exit(1)

    engine.dispose()


if __name__ == "__main__":
    main()
