import os
import sys
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import pool, engine_from_config

# ── path setup ────────────────────────────────────────────────────────────────
# Make project root importable so `backend.*` imports work from any directory.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ── load .env before importing database module ────────────────────────────────
load_dotenv(dotenv_path=os.path.join(PROJECT_ROOT, ".env"))

# ── import Base and the live DATABASE_URL ─────────────────────────────────────
from backend.db.database import Base, DATABASE_URL  # noqa: E402

# ── register every model with Base.metadata ───────────────────────────────────
# Importing the models module is enough — the class bodies call Base's
# metaclass, which adds each table to Base.metadata.
import backend.db.models  # noqa: F401, E402

# ── Alembic config ────────────────────────────────────────────────────────────
config = context.config

# Wire the URL from .env into Alembic — never stored in alembic.ini
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Set up Python logging as declared in alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# This is what Alembic diffs against when generating migrations
target_metadata = Base.metadata


# ── migration runners ─────────────────────────────────────────────────────────

def run_migrations_offline() -> None:
    """
    Emit SQL to stdout without a live connection.
    Used by `alembic upgrade --sql` to preview what SQL will run.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations against a live database connection.
    Used by `alembic upgrade head` (the normal workflow).
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # one connection per migration run, no pooling
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
