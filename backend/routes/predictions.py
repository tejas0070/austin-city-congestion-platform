from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.services.data_service import get_latest_for_corridor
from backend.services.ml_service import predict_congestion

router = APIRouter(prefix="/api/predictions", tags=["predictions"])


@router.get("/{corridor_name}")
def predict_for_corridor(corridor_name: str, db: Session = Depends(get_db)):
    """
    Returns the ML-predicted congestion index for the given corridor,
    based on its most recent feature snapshot.
    """
    reading = get_latest_for_corridor(db, corridor_name)
    if reading is None:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for corridor '{corridor_name}'.",
        )

    prediction = predict_congestion(reading)
    return {
        "corridor_name": corridor_name,
        "timestamp": reading.timestamp,
        "current_speed_mph": reading.current_speed_mph,
        "congestion_index_actual": reading.congestion_index,
        **prediction,
    }
