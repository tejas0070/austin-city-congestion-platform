from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.services.data_service import get_corridor_history, get_latest_readings

router = APIRouter(prefix="/api/corridors", tags=["corridors"])


@router.get("/current")
def current_readings(db: Session = Depends(get_db)):
    """Latest congestion snapshot for every monitored corridor."""
    rows = get_latest_readings(db)
    if not rows:
        raise HTTPException(status_code=404, detail="No corridor data found.")
    return [_serialize(r) for r in rows]


@router.get("/{corridor_name}/history")
def corridor_history(
    corridor_name: str,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Recent readings for a specific corridor (newest first)."""
    rows = get_corridor_history(db, corridor_name, limit=limit)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for corridor '{corridor_name}'.",
        )
    return [_serialize(r) for r in rows]


def _serialize(r) -> dict:
    return {
        "timestamp": r.timestamp,
        "corridor_name": r.corridor_name,
        "current_speed_mph": r.current_speed_mph,
        "free_flow_speed_mph": r.free_flow_speed_mph,
        "congestion_index": r.congestion_index,
        "weather_condition": r.weather_condition,
        "weather_temp_f": r.weather_temp_f,
        "weather_traffic_impact_level": r.weather_traffic_impact_level,
        "nearby_event_count": r.nearby_event_count,
        "has_high_impact_event": r.has_high_impact_event,
    }
