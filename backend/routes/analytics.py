"""
Analytics API — flat, aggregated endpoints for Power BI.

All responses are list[dict] with scalar values only (no geometry, no nested
objects). Power BI's Web connector can parse these directly.

Connect Power BI via:
  Get Data → Web → http://localhost:8000/api/analytics/<endpoint>
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.services.analytics_service import (
    get_congestion_by_day,
    get_congestion_by_hour,
    get_current_snapshot,
    get_event_impact,
    get_event_impact_by_subtype,
    get_forecast,
    get_top_congested,
    get_weather_impact,
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

_VALID_CORRIDORS = {
    "I-35_Downtown",
    "Mopac_Expressway_Downtown",
    "US-183_North",
    "Loop-360_West",
    "Congress_Ave_Downtown",
}


@router.get("/congestion-by-hour")
def congestion_by_hour(db: Session = Depends(get_db)) -> list[dict]:
    """Average congestion and speed per corridor, hour of day, and day of week.

    Power BI use: rush hour heatmap, daily trend line, Executive Overview.
    Columns: corridor_name, hour_of_day, day_of_week, day_name,
             avg_congestion, avg_speed_mph, sample_count
    """
    return get_congestion_by_hour(db)


@router.get("/congestion-by-day")
def congestion_by_day(db: Session = Depends(get_db)) -> list[dict]:
    """Average and max congestion per corridor per day of week.

    Power BI use: weekday vs weekend bar chart, Executive Overview.
    Columns: corridor_name, day_of_week, day_name,
             avg_congestion, max_congestion, avg_speed_mph, sample_count
    """
    return get_congestion_by_day(db)


@router.get("/top-congested")
def top_congested(db: Session = Depends(get_db)) -> list[dict]:
    """Corridors ranked by average congestion index, highest first.

    Power BI use: Executive Overview KPI card, hotspot ranking table.
    Columns: rank, corridor_name, avg_congestion, max_congestion,
             avg_speed_mph, sample_count
    """
    return get_top_congested(db)


@router.get("/current-snapshot")
def current_snapshot(db: Session = Depends(get_db)) -> list[dict]:
    """Latest live reading plus pre-computed ML prediction for every corridor.

    Power BI use: Executive Overview live KPI cards, Hotspot map.
    Columns: corridor_name, timestamp, current_speed_mph, free_flow_speed_mph,
             congestion_index, predicted_congestion_index, congestion_label,
             weather_condition, weather_temp_f, weather_rain_1h_mm,
             weather_traffic_impact_level, nearby_event_count, has_high_impact_event
    """
    rows = get_current_snapshot(db)
    if not rows:
        raise HTTPException(status_code=404, detail="No corridor data found. Run the ETL pipeline first.")
    return rows


@router.get("/weather-impact")
def weather_impact(db: Session = Depends(get_db)) -> list[dict]:
    """Average congestion grouped by weather condition and rain intensity.

    Power BI use: Weather Impact dashboard — rainfall vs congestion scatter,
    condition comparison bar chart.
    Columns: weather_condition, rain_bucket, avg_congestion, avg_speed_mph,
             avg_temp_f, avg_wind_speed_mph, sample_count
    """
    rows = get_weather_impact(db)
    if not rows:
        raise HTTPException(status_code=404, detail="No weather data found. Run the ETL pipeline first.")
    return rows


@router.get("/event-impact")
def event_impact(db: Session = Depends(get_db)) -> list[dict]:
    """Average congestion grouped by event presence and high-impact flag per corridor.

    Power BI use: Event Impact dashboard — before/during congestion comparison.
    Columns: corridor_name, has_any_event, has_high_impact_event,
             avg_congestion, avg_speed_mph, avg_event_count, sample_count
    """
    rows = get_event_impact(db)
    if not rows:
        raise HTTPException(status_code=404, detail="No event impact data found. Run the ETL pipeline first.")
    return rows


@router.get("/event-impact-by-subtype")
def event_impact_by_subtype(db: Session = Depends(get_db)) -> list[dict]:
    """Congestion metrics broken down by event subtype (austin_fc, ut_football, concert, etc.).

    Power BI use: Event Impact dashboard — compare Austin FC vs UT Football vs
    concerts vs festivals. Requires at least one ETL run after Phase 2 deploy.
    Columns: event_subtype, corridor_name, avg_congestion, avg_speed_mph,
             event_count, sample_count
    """
    rows = get_event_impact_by_subtype(db)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No event subtype data found. Run the ETL pipeline after deploying Phase 2.",
        )
    return rows


@router.get("/forecast")
def forecast(
    corridor: str = Query(..., description="Corridor name, e.g. I-35_Downtown"),
    hours_ahead: int = Query(6, ge=1, le=24, description="Hours to forecast (1–24)"),
    db: Session = Depends(get_db),
) -> list[dict]:
    """ML congestion forecast for a corridor for the next N hours.

    Synthesises future feature vectors using current weather + event data
    and steps hour_of_day / day_of_week forward. Requires a trained model.

    Power BI use: Predictive dashboard — forecast line with confidence band.
    Columns: corridor_name, forecast_hour, forecast_time, hour_of_day,
             day_of_week, day_name, predicted_congestion_index,
             confidence_low, confidence_high, congestion_label
    """
    if corridor not in _VALID_CORRIDORS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown corridor '{corridor}'. Valid values: {sorted(_VALID_CORRIDORS)}",
        )
    rows = get_forecast(db, corridor, hours_ahead)
    if not rows:
        raise HTTPException(
            status_code=503,
            detail="Forecast unavailable. Either no corridor data exists or the ML model has not been trained yet.",
        )
    return rows


@router.get("/forecast/all-corridors")
def forecast_all(
    hours_ahead: int = Query(6, ge=1, le=24, description="Hours to forecast (1–24)"),
    db: Session = Depends(get_db),
) -> list[dict]:
    """ML forecast for all corridors for the next N hours.

    Power BI use: Predictive dashboard — multi-corridor comparison,
    high-risk zone identification.
    """
    from ml.predict import model_loaded
    if not model_loaded():
        raise HTTPException(status_code=503, detail="ML model not trained yet. Run python ml/train.py.")

    results = []
    for corridor in sorted(_VALID_CORRIDORS):
        rows = get_forecast(db, corridor, hours_ahead)
        results.extend(rows)
    return results
