import os
import pandas as pd
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load .env from the project root (one level up from /etl)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# TomTom Traffic Flow Segment API base URL
TOMTOM_FLOW_URL = "https://api.tomtom.com/traffic/services/4/flowSegmentData/absolute/10/json"

# Key Austin traffic corridors to monitor (Name -> (Latitude, Longitude))
AUSTIN_CORRIDORS = {
    "I-35_Downtown":              (30.2690, -97.7341),
    "Mopac_Expressway_Downtown":  (30.2764, -97.7735),
    "US-183_North":               (30.3722, -97.7248),
    "Loop-360_West":              (30.2982, -97.8080),
    "Congress_Ave_Downtown":      (30.2682, -97.7428),
}

def fetch_tomtom_traffic():
    """
    Fetches real-time traffic flow segment data from TomTom API for key Austin corridors,
    processes the results into a Pandas DataFrame, and saves them to a timestamped CSV file.
    """
    api_key = os.getenv("TOMTOM_API_KEY")
    if not api_key or "actual" in api_key or api_key == "your_actual_tomtom_key_here":
        print("[-] Error: A valid 'TOMTOM_API_KEY' must be configured in your .env file.")
        print("    Please get a free API key at developer.tomtom.com and add it to your .env file.")
        return False

    print(f"[{datetime.now()}] Initializing TomTom live traffic flow extraction for Austin corridors...")

    records = []

    for corridor_name, (lat, lon) in AUSTIN_CORRIDORS.items():
        print(f" -> Fetching data for {corridor_name} ({lat}, {lon})...")

        params = {
            "key": api_key,
            "point": f"{lat},{lon}",
            "unit": "MPH",
            "thickness": 10,
        }

        try:
            response = requests.get(TOMTOM_FLOW_URL, params=params, timeout=10)
            response.raise_for_status()
            flow_data = response.json().get("flowSegmentData", {})
            if not flow_data:
                print(f"   [!] No flow data returned for {corridor_name}.")
                continue

            record = {
                "timestamp":                 datetime.now().isoformat(),
                "corridor_name":             corridor_name,
                "latitude":                  lat,
                "longitude":                 lon,
                "current_speed_mph":         flow_data.get("currentSpeed"),
                "free_flow_speed_mph":       flow_data.get("freeFlowSpeed"),
                "current_travel_time_sec":   flow_data.get("currentTravelTime"),
                "free_flow_travel_time_sec": flow_data.get("freeFlowTravelTime"),
                "confidence_score":          flow_data.get("confidence"),
            }
            records.append(record)
            print(f"    [+] Speed: {record['current_speed_mph']} MPH | "
                  f"Free-Flow: {record['free_flow_speed_mph']} MPH | "
                  f"Confidence: {record['confidence_score']}")

        except Exception as e:
            print(f"   [!] Error collecting data for {corridor_name}: {e}")

    if not records:
        print("[-] No traffic records collected. Aborting save.")
        return False

    df = pd.DataFrame(records)

    # Calculate congestion index: 1 = fully congested, 0 = free-flowing
    df["congestion_index"] = (
        1 - (df["current_speed_mph"] / df["free_flow_speed_mph"])
    ).clip(lower=0).round(4)

    output_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(output_dir, f"tomtom_traffic_flow_{timestamp}.csv")

    df.to_csv(file_path, index=False)
    print(f"\n[+] Saved {len(df)} corridor readings to {os.path.abspath(file_path)}")
    return True


if __name__ == "__main__":
    fetch_tomtom_traffic()
