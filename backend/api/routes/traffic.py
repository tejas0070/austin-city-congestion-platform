from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..dependencies import get_db
from ...db.queries import get_historical_traffic
from ...services.txdot_service import fetch_live_traffic, fetch_incidents
from ...services.segments_service import build_live_segments, segment_count
from ...services.ml_model import (
    predict_segments,
    predict_day,
    get_model_meta,
    model_is_available,
)
from ...utils.geojson_builder import build_feature_collection

router = APIRouter(prefix="/api/traffic", tags=["traffic"])

# Day-preview is bounded to the events horizon.
_MAX_PREVIEW_DAYS = 90


@router.get("/live")
async def get_live_traffic():
    """Live traffic speeds from TxDOT (point sample), cached 90 s."""
    return await fetch_live_traffic()


@router.get("/historical")
def get_historical(
    hour: int | None = Query(None, ge=0, le=23, description="Filter by hour of day (0-23)"),
    db: Session = Depends(get_db),
):
    """Historical traffic readings from the database, optionally filtered by hour."""
    features = get_historical_traffic(db, hour=hour)
    return build_feature_collection(features)


@router.get("/corridors")
def get_corridors():
    """City-wide live congestion as segment LineStrings (Austin road network)."""
    return build_live_segments()


@router.get("/corridors/predicted")
async def get_corridors_predicted(
    hours_ahead: float = Query(2.0, ge=0, le=24, description="Hours ahead to predict (0 = now)"),
    include_events: bool = Query(True, description="Include upcoming event attendance as a feature"),
):
    """ML-predicted city-wide congestion for a future time window."""
    return await predict_segments(hours_ahead=hours_ahead, include_events=include_events)


@router.get("/corridors/day")
async def get_corridors_day(
    date: str = Query(..., description="Target local date, YYYY-MM-DD"),
    include_events: bool = Query(True, description="Include event attendance as a feature"),
):
    """Whole-day ML congestion: 24 hourly snapshots as a compact per-hour matrix."""
    try:
        target = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be formatted YYYY-MM-DD")

    days_ahead = (target - datetime.now().date()).days
    if days_ahead < 0 or days_ahead > _MAX_PREVIEW_DAYS:
        raise HTTPException(
            status_code=400,
            detail=f"date must be within today..+{_MAX_PREVIEW_DAYS} days",
        )

    if not model_is_available():
        raise HTTPException(status_code=503, detail="Prediction model unavailable")

    return await predict_day(target, include_events=include_events)


@router.get("/model/info")
def get_model_info():
    """Trained model metadata, availability, and network size (for diagnostics)."""
    return {"available": model_is_available(), "segments": segment_count(), **get_model_meta()}


@router.get("/incidents")
async def get_incidents():
    """Active road incidents from TxDOT (falls back to simulated)."""
    return await fetch_incidents()
