from sqlalchemy import (
    Boolean, CheckConstraint, Column, Date, Float, Index, Integer,
    String, DateTime, Text, Time, UniqueConstraint,
)
from sqlalchemy.sql import func
from .database import Base


class TrafficSegment(Base):
    """Static road segment definitions seeded at startup."""
    __tablename__ = "traffic_segments"

    id = Column(Integer, primary_key=True, index=True)
    segment_id = Column(String, unique=True, index=True, nullable=False)
    road_name = Column(String, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class HistoricalTrafficReading(Base):
    """Historical traffic speed readings per road segment."""
    __tablename__ = "historical_traffic"
    __table_args__ = (
        Index("ix_hist_segment_ts", "segment_id", "timestamp"),
    )

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), index=True, nullable=False)
    segment_id = Column(String, index=True, nullable=False)
    road_name = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    speed_mph = Column(Float)
    free_flow_speed_mph = Column(Float)
    congestion_level = Column(String)  # green / yellow / red
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class LiveTrafficCache(Base):
    """Most recent TxDOT reading per segment — upserted every 90 s."""
    __tablename__ = "live_traffic_cache"

    id = Column(Integer, primary_key=True, index=True)
    segment_id = Column(String, unique=True, index=True, nullable=False)
    road_name = Column(String)
    latitude = Column(Float)
    longitude = Column(Float)
    speed_mph = Column(Float)
    free_flow_speed_mph = Column(Float)
    congestion_level = Column(String)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())


class TrafficIncident(Base):
    """Active road incidents from TxDOT or 511 Texas."""
    __tablename__ = "traffic_incidents"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(String, unique=True, index=True, nullable=False)
    incident_type = Column(String)   # accident / closure / construction / hazard
    description = Column(Text)
    severity = Column(Integer, CheckConstraint("severity BETWEEN 1 AND 4"))  # 1–4
    latitude = Column(Float)
    longitude = Column(Float)
    start_time = Column(DateTime(timezone=True))
    end_time = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Event(Base):
    """Upcoming Austin events aggregated from all sources."""
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_event_source_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String, nullable=False)
    source = Column(String, nullable=False)  # ticketmaster / austin_fc / ut_athletics
    name = Column(String, nullable=False)
    venue = Column(String)
    event_date = Column(Date)
    event_time = Column(Time)
    latitude = Column(Float)
    longitude = Column(Float)
    category = Column(String)              # Sports / Music / Festival
    expected_attendance = Column(Integer, nullable=True)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())


class WeatherSnapshot(Base):
    """Current Austin weather from Open-Meteo — kept last 24 h."""
    __tablename__ = "weather_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), index=True, nullable=False)
    temperature_f = Column(Float)
    precipitation_in = Column(Float)
    wind_speed_mph = Column(Float)
    weather_code = Column(Integer)
    condition = Column(String)
    rain_alert = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
