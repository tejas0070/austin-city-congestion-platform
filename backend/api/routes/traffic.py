from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ...api.dependencies import get_db
from ...db.queries import get_historical_traffic
from ...services.txdot_service import fetch_live_traffic, fetch_incidents
from ...utils.geojson_builder import build_feature_collection

router = APIRouter(prefix="/api/traffic", tags=["traffic"])


@router.get("/live")
async def get_live_traffic():
    """Live traffic speeds from TxDOT, cached 90 s."""
    return await fetch_live_traffic()


@router.get("/historical")
def get_historical(
    hour: int | None = Query(None, ge=0, le=23, description="Filter by hour of day (0-23)"),
    db: Session = Depends(get_db),
):
    """Historical traffic readings from the database, optionally filtered by hour."""
    features = get_historical_traffic(db, hour=hour)
    return build_feature_collection(features)


@router.get("/incidents")
async def get_incidents():
    """Active road incidents from TxDOT."""
    return await fetch_incidents()
