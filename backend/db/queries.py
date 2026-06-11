from sqlalchemy import extract
from sqlalchemy.orm import Session
from .models import HistoricalTrafficReading
from ..utils.geojson_builder import build_point_feature


def get_historical_traffic(
    db: Session,
    hour: int | None = None,
    limit: int = 500,
) -> list[dict]:
    """Return historical traffic readings as a list of GeoJSON feature dicts."""
    query = db.query(HistoricalTrafficReading)

    if hour is not None:
        query = query.filter(
            extract("hour", HistoricalTrafficReading.timestamp) == hour
        )

    readings = (
        query.order_by(HistoricalTrafficReading.timestamp.desc())
        .limit(limit)
        .all()
    )

    return [
        build_point_feature(
            r.latitude or 0,
            r.longitude or 0,
            {
                "segment_id": r.segment_id,
                "road_name": r.road_name,
                "speed_mph": r.speed_mph,
                "free_flow_speed_mph": r.free_flow_speed_mph,
                "congestion_level": r.congestion_level,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            },
        )
        for r in readings
        if r.latitude is not None and r.longitude is not None
    ]
