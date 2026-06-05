import time

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import CachedPrediction
from backend.services.data_service import get_latest_for_corridor
from backend.services.ml_service import predict_congestion

router = APIRouter(prefix="/api/map", tags=["map"])

_MAP_CACHE: dict = {"data": None, "ts": 0.0}
_CACHE_TTL = 60  # seconds

CORRIDORS = [
    "I-35_Downtown",
    "Mopac_Expressway_Downtown",
    "US-183_North",
    "Loop-360_West",
    "Congress_Ave_Downtown",
]

DISPLAY_NAMES = {
    "I-35_Downtown": "I-35 (Downtown)",
    "Mopac_Expressway_Downtown": "Mopac Expressway (Downtown)",
    "US-183_North": "US-183 (North)",
    "Loop-360_West": "Loop 360 (West)",
    "Congress_Ave_Downtown": "Congress Ave (Downtown)",
}


@router.get("/corridors")
def get_map_corridors(db: Session = Depends(get_db)):
    """Returns all corridors with their latest reading and pre-computed ML prediction.

    Results are cached in-process for 60 seconds so repeat visitors don't pay
    the cost of 5 DB queries + 5 ML inferences on every request.
    """
    now = time.monotonic()
    if _MAP_CACHE["data"] is not None and (now - _MAP_CACHE["ts"]) < _CACHE_TTL:
        return _MAP_CACHE["data"]

    # Try to read pre-computed predictions from the DB first (written during ETL).
    cached_preds: dict[str, CachedPrediction] = {
        row.corridor_name: row
        for row in db.query(CachedPrediction).all()
    }

    results = []
    for corridor_name in CORRIDORS:
        reading = get_latest_for_corridor(db, corridor_name)
        if reading is None:
            continue

        cached = cached_preds.get(corridor_name)
        if cached is not None:
            pred_index = cached.predicted_congestion_index
            pred_label = cached.congestion_label
        else:
            # Fall back to live inference when no pre-computed value exists yet.
            prediction = predict_congestion(reading)
            pred_index = prediction["predicted_congestion_index"]
            pred_label = prediction["congestion_label"]

        results.append({
            "corridor_name": corridor_name,
            "display_name": DISPLAY_NAMES[corridor_name],
            "latitude": reading.latitude,
            "longitude": reading.longitude,
            "current_speed_mph": reading.current_speed_mph,
            "free_flow_speed_mph": reading.free_flow_speed_mph,
            "congestion_index": reading.congestion_index,
            "predicted_congestion_index": pred_index,
            "congestion_label": pred_label,
            "weather_condition": reading.weather_condition,
            "weather_temp_f": reading.weather_temp_f,
            "weather_traffic_impact_level": reading.weather_traffic_impact_level,
            "nearby_event_count": reading.nearby_event_count,
            "has_high_impact_event": reading.has_high_impact_event,
            "timestamp": str(reading.timestamp),
        })

    _MAP_CACHE["data"] = results
    _MAP_CACHE["ts"] = now
    return results
