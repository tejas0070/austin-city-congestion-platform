from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class RoadSegment(Base):
    __tablename__ = "road_segments"

    id              = Column(Integer, primary_key=True)
    name            = Column(String,  nullable=True)
    highway_type    = Column(String,  nullable=True)
    speed_limit_mph = Column(Integer, nullable=True)
    osm_id          = Column(Integer, nullable=True)
    corridor_name   = Column(String,  nullable=True, index=True)
    length_m        = Column(Float,   nullable=True)
    geometry        = Column(Geometry("LINESTRING", srid=4326), nullable=False)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())

    observations = relationship(
        "TrafficObservation", back_populates="segment", cascade="all, delete-orphan"
    )
    predictions = relationship(
        "Prediction", back_populates="segment", cascade="all, delete-orphan"
    )


class TrafficObservation(Base):
    __tablename__ = "traffic_observations"
    __table_args__ = (
        UniqueConstraint("segment_id", "timestamp", "source", name="uq_obs_seg_ts_src"),
    )

    id                  = Column(Integer, primary_key=True)
    segment_id          = Column(Integer, ForeignKey("road_segments.id"), nullable=False, index=True)
    timestamp           = Column(DateTime(timezone=True), nullable=False, index=True)
    speed_mph           = Column(Float,   nullable=False)
    free_flow_speed_mph = Column(Float,   nullable=True)
    volume              = Column(Integer, nullable=True)   # vehicles per hour
    congestion_index    = Column(Float,   nullable=True)   # 0.0 free-flow → 1.0 standstill
    source              = Column(String,  nullable=False, default="tomtom")
    created_at          = Column(DateTime(timezone=True), server_default=func.now())

    segment = relationship("RoadSegment", back_populates="observations")


class WeatherSnapshot(Base):
    __tablename__ = "weather_snapshots"

    id                   = Column(Integer, primary_key=True)
    timestamp            = Column(DateTime(timezone=True), nullable=False, index=True)
    location             = Column(Geometry("POINT", srid=4326), nullable=False)
    zone_name            = Column(String, nullable=True)
    temp_f               = Column(Float,  nullable=True)
    precip_1h_mm         = Column(Float,  nullable=True)   # precipitation last hour
    condition            = Column(String, nullable=True)   # e.g. "rain", "fog", "clear"
    wind_speed_mph       = Column(Float,  nullable=True)
    humidity_pct         = Column(Float,  nullable=True)
    traffic_impact_level = Column(String, nullable=True)   # Low / Moderate / High / Severe
    created_at           = Column(DateTime(timezone=True), server_default=func.now())


class Event(Base):
    __tablename__ = "events"

    id                       = Column(Integer, primary_key=True)
    external_id              = Column(String,  unique=True, index=True, nullable=True)
    name                     = Column(String,  nullable=False)
    venue_name               = Column(String,  nullable=True)
    venue_location           = Column(Geometry("POINT", srid=4326), nullable=False)
    start_time               = Column(DateTime(timezone=True), nullable=False, index=True)
    expected_attendance      = Column(Integer, nullable=True)
    is_high_impact           = Column(Boolean, default=False)
    est_congestion_radius_mi = Column(Float,   nullable=True)
    classification           = Column(String,  nullable=True)  # Music / Sports / etc.
    event_subtype            = Column(String,  nullable=True, index=True)  # austin_fc / ut_football / concert / festival / sports_other / other
    created_at               = Column(DateTime(timezone=True), server_default=func.now())


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint("segment_id", "timestamp", "model_version", name="uq_pred_seg_ts_ver"),
    )

    id                        = Column(Integer, primary_key=True)
    segment_id                = Column(Integer, ForeignKey("road_segments.id"), nullable=False, index=True)
    timestamp                 = Column(DateTime(timezone=True), nullable=False, index=True)
    predicted_congestion_score = Column(Float,  nullable=False)  # 0.0 free-flow → 1.0 standstill
    confidence                = Column(Float,   nullable=True)   # 0.0 → 1.0
    model_version             = Column(String,  nullable=False, default="v1")
    created_at                = Column(DateTime(timezone=True), server_default=func.now())

    segment = relationship("RoadSegment", back_populates="predictions")
