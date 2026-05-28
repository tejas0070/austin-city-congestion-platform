"""
ETL Transform — Austin City Congestion Platform

Merges raw traffic, weather, and events CSVs from data/raw/ into a single
feature table written to data/processed/merged_features.csv.

Join strategy:
  - Traffic ↔ Weather : each corridor is matched to the nearest weather zone
                        (haversine distance on lat/lon).
  - Traffic ↔ Events  : each corridor accumulates a count of events whose
                        venue is within that event's est_congestion_radius_mi.
"""

import glob
import math
import os
from datetime import datetime

import pandas as pd

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
PROCESSED_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "processed")
OUTPUT_FILE = os.path.join(PROCESSED_DIR, "merged_features.csv")

WEATHER_FEATURE_COLS = [
    "condition_id", "condition", "temp_f", "feels_like_f", "humidity_pct",
    "visibility_mi", "wind_speed_mph", "wind_gust_mph", "rain_1h_mm",
    "snow_1h_mm", "cloud_cover_pct", "traffic_impact_level",
]


def haversine_mi(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def load_csvs(prefix: str) -> pd.DataFrame:
    pattern = os.path.join(RAW_DIR, f"{prefix}_*.csv")
    files = sorted(glob.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No CSV files found matching: {pattern}")
    print(f"  [+] {prefix}: {len(files)} file(s)")
    return pd.concat([pd.read_csv(f) for f in files], ignore_index=True)


def attach_nearest_weather(traffic_df: pd.DataFrame, weather_df: pd.DataFrame) -> pd.DataFrame:
    """Joins the most recent weather snapshot to each traffic corridor row by proximity."""
    weather_latest = (
        weather_df
        .sort_values("timestamp")
        .groupby("zone_name", as_index=False)
        .last()
    )

    # Pre-build a list of (zone_name, lat, lon, row) for iteration efficiency
    zones = [
        (row["zone_name"], row["latitude"], row["longitude"], row)
        for _, row in weather_latest.iterrows()
    ]

    enriched_rows = []
    for _, t_row in traffic_df.iterrows():
        best_row = min(
            zones,
            key=lambda z: haversine_mi(t_row["latitude"], t_row["longitude"], z[1], z[2]),
        )
        zone_name, zone_lat, zone_lon, w_row = best_row
        dist = haversine_mi(t_row["latitude"], t_row["longitude"], zone_lat, zone_lon)

        enriched = t_row.to_dict()
        enriched["nearest_weather_zone"] = zone_name
        enriched["weather_zone_dist_mi"] = round(dist, 3)
        for col in WEATHER_FEATURE_COLS:
            enriched[f"weather_{col}"] = w_row[col]
        enriched_rows.append(enriched)

    return pd.DataFrame(enriched_rows)


def attach_event_features(traffic_df: pd.DataFrame, events_df: pd.DataFrame) -> pd.DataFrame:
    """
    For each corridor row, counts how many events have their venue within
    that event's estimated congestion radius, and flags high-impact events.
    """
    events_deduped = (
        events_df
        .sort_values("timestamp")
        .groupby("event_id", as_index=False)
        .last()
    )
    # Normalise bool column — CSV round-trips it as string "True"/"False"
    events_deduped["is_high_traffic_impact"] = (
        events_deduped["is_high_traffic_impact"].astype(str).str.lower() == "true"
    )
    events_deduped["est_congestion_radius_mi"] = pd.to_numeric(
        events_deduped["est_congestion_radius_mi"], errors="coerce"
    ).fillna(0.5)

    # Drop events with missing venue coordinates
    valid_events = events_deduped[
        (events_deduped["venue_latitude"] != 0) | (events_deduped["venue_longitude"] != 0)
    ].copy()

    # Pre-build tuples for fast iteration
    event_tuples = list(
        valid_events[["venue_latitude", "venue_longitude",
                       "est_congestion_radius_mi", "is_high_traffic_impact"]].itertuples(index=False)
    )

    nearby_counts = []
    high_impact_flags = []

    for _, t_row in traffic_df.iterrows():
        count = 0
        high_impact = False
        for e in event_tuples:
            dist = haversine_mi(t_row["latitude"], t_row["longitude"],
                                e.venue_latitude, e.venue_longitude)
            if dist <= e.est_congestion_radius_mi:
                count += 1
                if e.is_high_traffic_impact:
                    high_impact = True
        nearby_counts.append(count)
        high_impact_flags.append(high_impact)

    result = traffic_df.copy()
    result["nearby_event_count"] = nearby_counts
    result["has_high_impact_event"] = high_impact_flags
    return result


def transform() -> bool:
    print("=" * 60)
    print("  Austin Congestion Intelligence — ETL Transform")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    print("\n[1/4] Loading raw CSVs...")
    try:
        traffic_df = load_csvs("tomtom_traffic_flow")
        weather_df = load_csvs("weather_conditions")
        events_df = load_csvs("austin_events")
    except FileNotFoundError as e:
        print(f"[-] {e}")
        return False

    print(f"  Traffic rows : {len(traffic_df)}")
    print(f"  Weather rows : {len(weather_df)}")
    print(f"  Events rows  : {len(events_df)}")

    print("\n[2/4] Attaching nearest weather zone to each corridor reading...")
    traffic_df = attach_nearest_weather(traffic_df, weather_df)

    print("\n[3/4] Counting nearby events per corridor...")
    traffic_df = attach_event_features(traffic_df, events_df)

    print("\n[4/4] Adding time features and saving output...")
    traffic_df["timestamp"] = pd.to_datetime(traffic_df["timestamp"])
    traffic_df["hour_of_day"] = traffic_df["timestamp"].dt.hour
    traffic_df["day_of_week"] = traffic_df["timestamp"].dt.dayofweek  # 0=Mon, 6=Sun
    traffic_df["is_weekend"] = traffic_df["day_of_week"].isin([5, 6]).astype(int)

    os.makedirs(PROCESSED_DIR, exist_ok=True)
    traffic_df.to_csv(OUTPUT_FILE, index=False)

    print(f"\n[+] Saved: {os.path.abspath(OUTPUT_FILE)}")
    print(f"    Rows: {len(traffic_df)}  |  Columns: {len(traffic_df.columns)}")
    print("=" * 60)
    return True


if __name__ == "__main__":
    transform()
