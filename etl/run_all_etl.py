"""
Master ETL Runner — Austin City Congestion Platform
Orchestrates all three data ingestion pipelines in sequence:
  1. TomTom  → Real-time traffic flow speeds per corridor
  2. OpenWeatherMap → Weather conditions & traffic impact classification
  3. Ticketmaster  → Upcoming Austin events with congestion radius estimates
"""
import sys
import os
from datetime import datetime

# Ensure the project root is on the path so relative imports work
sys.path.insert(0, os.path.dirname(__file__))

from traffic_etl import fetch_tomtom_traffic
from weather_etl import fetch_weather_data
from events_etl  import fetch_events_data


def run_all_pipelines():
    print("=" * 60)
    print("  Austin Congestion Intelligence — ETL Pipeline Runner")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    results = {}

    print("\n[1/3] TOMTOM TRAFFIC FLOW")
    print("-" * 40)
    results["tomtom_traffic"] = fetch_tomtom_traffic()

    print("\n[2/3] OPENWEATHERMAP CONDITIONS")
    print("-" * 40)
    results["weather"]        = fetch_weather_data()

    print("\n[3/3] TICKETMASTER EVENTS")
    print("-" * 40)
    results["events"]         = fetch_events_data()

    # --- Summary ---
    print("\n" + "=" * 60)
    print("  Pipeline Summary")
    print("=" * 60)
    for pipeline, success in results.items():
        status = "SUCCESS [OK]" if success else "FAILED / SKIPPED [--]"
        print(f"  {pipeline:<25} {status}")
    print("=" * 60)
    print(f"  Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


if __name__ == "__main__":
    run_all_pipelines()
