"""
Geospatial API routes — PostGIS-backed endpoints.

All distance calculations use ST_DWithin on the geography cast so that
the radius parameter is always in metres, regardless of SRID units.

Route ordering rule: static paths (near-event, near-point, near) are
declared BEFORE parameterised paths (/{id}) in each group, otherwise
FastAPI tries to parse the literal string as an integer and returns 422.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from geoalchemy2 import Geography
from geoalchemy2.shape import to_shape
from sqlalchemy import cast, func
from sqlalchemy.orm import Session

# Reusable geography type for meter-accurate ST_DWithin / ST_Distance queries.
# PostGIS requires a ::geography cast; _as_geo() does not exist.
_GEO = Geography(srid=4326)


def _as_geo(col):
    """Cast a SQLAlchemy geometry *column* to geography (used in WHERE clauses)."""
    return cast(col, _GEO)


def _val_geo(wkb_element):
    """
    Convert a loaded ORM geometry value (WKBElement) to a geography parameter.

    When an ORM instance is loaded from the DB its geometry is a WKBElement.
    Passing that through cast() makes GeoAlchemy2 wrap it in ST_GeogFromText()
    which expects WKT, not WKB, causing a parse error.  Converting to WKT first
    and using ST_GeogFromText explicitly avoids this.
    """
    wkt = f"SRID=4326;{to_shape(wkb_element).wkt}"
    return func.ST_GeogFromText(wkt)

from backend.app.database import get_db
from backend.app.geo_models import (
    Event,
    Prediction,
    RoadSegment,
    TrafficObservation,
    WeatherSnapshot,
)

router = APIRouter(prefix="/api/geo", tags=["geospatial"])


# ── serialisers ────────────────────────────────────────────────────────────────

def _segment_to_dict(seg: RoadSegment) -> dict[str, Any]:
    geojson = to_shape(seg.geometry).__geo_interface__
    return {
        "id": seg.id,
        "osm_id": seg.osm_id,
        "name": seg.name,
        "highway_type": seg.highway_type,
        "corridor_name": seg.corridor_name,
        "length_m": seg.length_m,
        "geometry": geojson,
    }


def _observation_to_dict(obs: TrafficObservation) -> dict[str, Any]:
    return {
        "id": obs.id,
        "segment_id": obs.segment_id,
        "timestamp": obs.timestamp.isoformat(),
        "speed_mph": obs.speed_mph,
        "free_flow_speed_mph": obs.free_flow_speed_mph,
        "volume": obs.volume,
        "congestion_index": obs.congestion_index,
        "source": obs.source,
    }


def _weather_to_dict(w: WeatherSnapshot) -> dict[str, Any]:
    pt = to_shape(w.location)
    return {
        "id": w.id,
        "timestamp": w.timestamp.isoformat(),
        "longitude": pt.x,
        "latitude": pt.y,
        "zone_name": w.zone_name,
        "temp_f": w.temp_f,
        "precip_1h_mm": w.precip_1h_mm,
        "condition": w.condition,
        "wind_speed_mph": w.wind_speed_mph,
        "humidity_pct": w.humidity_pct,
        "traffic_impact_level": w.traffic_impact_level,
    }


def _event_to_dict(ev: Event) -> dict[str, Any]:
    pt = to_shape(ev.venue_location)
    return {
        "id": ev.id,
        "external_id": ev.external_id,
        "name": ev.name,
        "venue_name": ev.venue_name,
        "longitude": pt.x,
        "latitude": pt.y,
        "start_time": ev.start_time.isoformat(),
        "expected_attendance": ev.expected_attendance,
        "is_high_impact": ev.is_high_impact,
        "est_congestion_radius_mi": ev.est_congestion_radius_mi,
        "classification": ev.classification,
        "event_subtype": ev.event_subtype,
    }


def _prediction_to_dict(p: Prediction) -> dict[str, Any]:
    return {
        "id": p.id,
        "segment_id": p.segment_id,
        "timestamp": p.timestamp.isoformat(),
        "predicted_congestion_score": p.predicted_congestion_score,
        "confidence": p.confidence,
        "model_version": p.model_version,
    }


def _wkt_point(lat: float, lon: float) -> str:
    return f"SRID=4326;POINT({lon} {lat})"


# ── road segments ──────────────────────────────────────────────────────────────

@router.get("/road-segments")
def list_road_segments(
    corridor: str | None = Query(None, description="Filter by corridor_name"),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Road segments, optionally filtered by corridor name."""
    q = db.query(RoadSegment)
    if corridor:
        q = q.filter(RoadSegment.corridor_name == corridor)
    return [_segment_to_dict(s) for s in q.limit(limit).all()]


@router.get("/road-segments/near-event/{event_id}")
def segments_near_event(
    event_id: int,
    radius_m: float = Query(1000.0, description="Search radius in metres"),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Road segments within radius_m metres of an event venue (ST_DWithin geography)."""
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    segments = (
        db.query(RoadSegment)
        .filter(
            func.ST_DWithin(
                _as_geo(RoadSegment.geometry),
                _val_geo(event.venue_location),   # loaded WKB → WKT → geography
                radius_m,
            )
        )
        .all()
    )
    return [_segment_to_dict(s) for s in segments]


@router.get("/road-segments/near-point")
def segments_near_point(
    lat: float = Query(..., description="Latitude (WGS-84)"),
    lon: float = Query(..., description="Longitude (WGS-84)"),
    radius_m: float = Query(1000.0, description="Search radius in metres"),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Road segments within radius_m metres of an arbitrary lat/lon."""
    wkt = _wkt_point(lat, lon)
    segments = (
        db.query(RoadSegment)
        .filter(
            func.ST_DWithin(
                _as_geo(RoadSegment.geometry),
                func.ST_GeogFromText(wkt),
                radius_m,
            )
        )
        .all()
    )
    return [_segment_to_dict(s) for s in segments]


@router.get("/road-segments/{segment_id}")
def get_road_segment(segment_id: int, db: Session = Depends(get_db)) -> dict:
    """Single road segment by ID."""
    seg = db.get(RoadSegment, segment_id)
    if not seg:
        raise HTTPException(status_code=404, detail="Segment not found")
    return _segment_to_dict(seg)


# ── traffic observations ───────────────────────────────────────────────────────

@router.get("/traffic-observations/near-event/{event_id}")
def observations_near_event(
    event_id: int,
    radius_m: float = Query(1000.0),
    limit: int = Query(200, le=1000),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Latest observation per road segment within radius_m metres of an event venue."""
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    latest = (
        db.query(
            TrafficObservation.segment_id,
            func.max(TrafficObservation.timestamp).label("max_ts"),
        )
        .group_by(TrafficObservation.segment_id)
        .subquery()
    )

    rows = (
        db.query(TrafficObservation)
        .join(
            latest,
            (TrafficObservation.segment_id == latest.c.segment_id)
            & (TrafficObservation.timestamp == latest.c.max_ts),
        )
        .join(RoadSegment, RoadSegment.id == TrafficObservation.segment_id)
        .filter(
            func.ST_DWithin(
                _as_geo(RoadSegment.geometry),
                _val_geo(event.venue_location),
                radius_m,
            )
        )
        .limit(limit)
        .all()
    )
    return [_observation_to_dict(r) for r in rows]


@router.get("/traffic-observations/{segment_id}")
def get_observations(
    segment_id: int,
    limit: int = Query(50, le=500),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Latest traffic observations for a road segment, newest first."""
    if not db.get(RoadSegment, segment_id):
        raise HTTPException(status_code=404, detail="Segment not found")
    rows = (
        db.query(TrafficObservation)
        .filter(TrafficObservation.segment_id == segment_id)
        .order_by(TrafficObservation.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [_observation_to_dict(r) for r in rows]


# ── weather snapshots ──────────────────────────────────────────────────────────

@router.get("/weather-snapshots/near")
def weather_near_point(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_m: float = Query(25_000.0, description="Default 25 km"),
    limit: int = Query(10, le=50),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Most recent weather snapshots within radius_m metres, ordered nearest first."""
    wkt = _wkt_point(lat, lon)
    rows = (
        db.query(WeatherSnapshot)
        .filter(
            func.ST_DWithin(
                _as_geo(WeatherSnapshot.location),
                func.ST_GeogFromText(wkt),
                radius_m,
            )
        )
        .order_by(
            func.ST_Distance(
                _as_geo(WeatherSnapshot.location),
                func.ST_GeogFromText(wkt),
            )
        )
        .limit(limit)
        .all()
    )
    return [_weather_to_dict(r) for r in rows]


# ── events ─────────────────────────────────────────────────────────────────────

@router.get("/events")
def list_events(
    after: datetime | None = Query(None, description="ISO-8601 — return events starting after this time"),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Upcoming events, optionally filtered by start time."""
    q = db.query(Event).order_by(Event.start_time)
    if after:
        q = q.filter(Event.start_time >= after)
    return [_event_to_dict(e) for e in q.limit(limit).all()]


@router.get("/events/near-segment/{segment_id}")
def events_near_segment(
    segment_id: int,
    radius_m: float = Query(1000.0),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Events whose venue is within radius_m metres of a road segment."""
    seg = db.get(RoadSegment, segment_id)
    if not seg:
        raise HTTPException(status_code=404, detail="Segment not found")
    events = (
        db.query(Event)
        .filter(
            func.ST_DWithin(
                _as_geo(Event.venue_location),
                _val_geo(seg.geometry),
                radius_m,
            )
        )
        .order_by(Event.start_time)
        .all()
    )
    return [_event_to_dict(e) for e in events]


@router.get("/events/{event_id}")
def get_event(event_id: int, db: Session = Depends(get_db)) -> dict:
    """Single event by ID."""
    ev = db.get(Event, event_id)
    if not ev:
        raise HTTPException(status_code=404, detail="Event not found")
    return _event_to_dict(ev)


# ── predictions ────────────────────────────────────────────────────────────────

@router.get("/predictions/near-event/{event_id}")
def predictions_near_event(
    event_id: int,
    radius_m: float = Query(1000.0),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Latest stored prediction per road segment within radius_m metres of an event."""
    event = db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    latest = (
        db.query(
            Prediction.segment_id,
            func.max(Prediction.timestamp).label("max_ts"),
        )
        .group_by(Prediction.segment_id)
        .subquery()
    )

    rows = (
        db.query(Prediction)
        .join(
            latest,
            (Prediction.segment_id == latest.c.segment_id)
            & (Prediction.timestamp == latest.c.max_ts),
        )
        .join(RoadSegment, RoadSegment.id == Prediction.segment_id)
        .filter(
            func.ST_DWithin(
                _as_geo(RoadSegment.geometry),
                _val_geo(event.venue_location),
                radius_m,
            )
        )
        .limit(limit)
        .all()
    )
    return [_prediction_to_dict(r) for r in rows]


@router.get("/predictions/{segment_id}")
def get_predictions(
    segment_id: int,
    limit: int = Query(24, le=168, description="Max 168 = 1 week of hourly forecasts"),
    db: Session = Depends(get_db),
) -> list[dict]:
    """Stored congestion predictions for a road segment, ordered by forecast timestamp."""
    if not db.get(RoadSegment, segment_id):
        raise HTTPException(status_code=404, detail="Segment not found")
    rows = (
        db.query(Prediction)
        .filter(Prediction.segment_id == segment_id)
        .order_by(Prediction.timestamp)
        .limit(limit)
        .all()
    )
    return [_prediction_to_dict(r) for r in rows]
