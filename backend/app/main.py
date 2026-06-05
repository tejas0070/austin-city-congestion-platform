import asyncio
import os
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.app.database import Base, engine, init_postgis
from backend.routes.analytics import router as analytics_router
from backend.routes.corridors import router as corridors_router
from backend.routes.geo import router as geo_router
from backend.routes.map_data import router as map_router
from backend.routes.predictions import router as predictions_router

HTML_PATH = os.path.join(os.path.dirname(__file__), "..", "static", "index.html")
REFRESH_INTERVAL_SECONDS = 1800  # 30 minutes


def _run_etl_cycle() -> None:
    """Fetches fresh API data, merges it, and reloads the DB. Runs every 30 min."""
    try:
        print("[*] Scheduled data refresh starting…")
        from etl.run_all_etl import run_all_pipelines
        from etl.transform import transform
        from etl.load_to_db import cache_predictions, load_merged_features
        run_all_pipelines()
        transform()
        load_merged_features()
        cache_predictions()
        print("[+] Scheduled data refresh complete.")
    except Exception as exc:
        print(f"[!] Data refresh error: {exc}")


async def _refresh_loop() -> None:
    while True:
        await asyncio.sleep(REFRESH_INTERVAL_SECONDS)
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _run_etl_cycle)


@asynccontextmanager
async def lifespan(_: FastAPI):
    import backend.app.geo_models  # noqa: F401  # pyright: ignore[reportUnusedImport]
    # Enable PostGIS extension then create any missing tables (idempotent)
    init_postgis()
    Base.metadata.create_all(bind=engine)

    task = asyncio.create_task(_refresh_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Austin Congestion Intelligence API",
    description="Live traffic congestion data and ML-powered predictions for Austin, TX.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(corridors_router)
app.include_router(predictions_router)
app.include_router(map_router)
app.include_router(geo_router)
app.include_router(analytics_router)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def map_page() -> HTMLResponse:
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/health")
def health():
    return {"status": "ok"}
