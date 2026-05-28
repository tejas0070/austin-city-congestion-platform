from sqlalchemy import Boolean, Column, Float, Integer, String, DateTime, UniqueConstraint
from sqlalchemy.sql import func

from .database import Base


class TrafficReading(Base):
    __tablename__ = "traffic_readings"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), index=True)
    corridor_name = Column(String, index=True)
    latitude = Column(Float)
    longitude = Column(Float)
    current_speed_mph = Column(Float)
    free_flow_speed_mph = Column(Float)
    current_travel_time_sec = Column(Float)
    free_flow_travel_time_sec = Column(Float)
    confidence_score = Column(Float)
    congestion_index = Column(Float)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WeatherCondition(Base):
    __tablename__ = "weather_conditions"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), index=True)
    zone_name = Column(String, index=True)
    latitude = Column(Float)
    longitude = Column(Float)
    condition_id = Column(Integer)
    condition = Column(String)
    temp_f = Column(Float)
    feels_like_f = Column(Float)
    humidity_pct = Column(Float)
    visibility_mi = Column(Float)
    wind_speed_mph = Column(Float)
    wind_gust_mph = Column(Float)
    rain_1h_mm = Column(Float)
    snow_1h_mm = Column(Float)
    cloud_cover_pct = Column(Float)
    traffic_impact_level = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), index=True)
    event_id = Column(String, unique=True, index=True)
    event_name = Column(String)
    event_date = Column(String)
    event_time_local = Column(String)
    classification_segment = Column(String)
    genre = Column(String)
    is_high_traffic_impact = Column(Boolean)
    venue_name = Column(String)
    venue_city = Column(String)
    venue_latitude = Column(Float)
    venue_longitude = Column(Float)
    venue_capacity = Column(Integer)
    ticket_min_price_usd = Column(Float)
    ticket_max_price_usd = Column(Float)
    est_congestion_radius_mi = Column(Float)
    event_url = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MergedFeature(Base):
    """One row per (timestamp, corridor) with weather and event features joined in."""
    __tablename__ = "merged_features"
    __table_args__ = (UniqueConstraint("timestamp", "corridor_name", name="uq_merged_ts_corridor"),)

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), index=True)
    corridor_name = Column(String, index=True)
    latitude = Column(Float)
    longitude = Column(Float)
    # Traffic
    current_speed_mph = Column(Float)
    free_flow_speed_mph = Column(Float)
    current_travel_time_sec = Column(Float)
    free_flow_travel_time_sec = Column(Float)
    confidence_score = Column(Float)
    congestion_index = Column(Float)
    # Weather join
    nearest_weather_zone = Column(String)
    weather_zone_dist_mi = Column(Float)
    weather_condition_id = Column(Integer)
    weather_condition = Column(String)
    weather_temp_f = Column(Float)
    weather_feels_like_f = Column(Float)
    weather_humidity_pct = Column(Float)
    weather_visibility_mi = Column(Float)
    weather_wind_speed_mph = Column(Float)
    weather_wind_gust_mph = Column(Float)
    weather_rain_1h_mm = Column(Float)
    weather_snow_1h_mm = Column(Float)
    weather_cloud_cover_pct = Column(Float)
    weather_traffic_impact_level = Column(String)
    # Event join
    nearby_event_count = Column(Integer)
    has_high_impact_event = Column(Boolean)
    # Time features
    hour_of_day = Column(Integer)
    day_of_week = Column(Integer)
    is_weekend = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
