import os
import sys

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

USE_SQLITE = os.getenv("USE_SQLITE", "false").lower() == "true"

if USE_SQLITE:
    DATABASE_URL = "sqlite:///./austin_traffic.db"
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    _missing = [v for v in ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")
                if not os.getenv(v)]
    if _missing:
        print(f"[ERROR] Missing required environment variables: {', '.join(_missing)}", file=sys.stderr)
        print("[ERROR] Check your .env file. Set USE_SQLITE=true to run without PostgreSQL.", file=sys.stderr)
        sys.exit(1)

    DB_HOST = os.environ["DB_HOST"]
    DB_PORT = os.environ["DB_PORT"]
    DB_NAME = os.environ["DB_NAME"]
    DB_USER = os.environ["DB_USER"]
    DB_PASSWORD = os.environ["DB_PASSWORD"]
    DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,      # drops stale connections before use
        pool_size=5,             # keep 5 connections ready
        max_overflow=10,         # allow up to 10 extra under load
        pool_timeout=30,         # raise after 30 s if no connection available
        pool_recycle=1800,       # recycle connections every 30 min
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def init_postgis() -> None:
    """Enable the PostGIS extension. No-op when running SQLite (local dev)."""
    if USE_SQLITE:
        return
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.commit()


def test_connection() -> bool:
    """Return True if the database is reachable, False otherwise."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        print(f"[ERROR] Database connection failed: {exc}", file=sys.stderr)
        return False


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
