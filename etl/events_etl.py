import os
import pandas as pd
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load .env from the project root (one level up from /etl)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

# Ticketmaster Discovery API endpoint for events
TICKETMASTER_URL = "https://app.ticketmaster.com/discovery/v2/events.json"

# Austin's geographical search boundary (lat/lon bounding box)
AUSTIN_GEO = {
    "city":    "Austin",
    "stateCode": "TX",
    "countryCode": "US",
    "radius":  "20",        # Miles from city center
    "unit":    "miles",
}

# Event classifications that typically generate heavy traffic congestion
HIGH_IMPACT_CLASSIFICATIONS = {
    "Music",
    "Sports",
    "Arts & Theatre",
    "Film",
}

def estimate_congestion_radius_mi(attendance: int) -> float:
    """
    Estimates the surrounding road network congestion radius in miles
    based on approximate event attendance.
    """
    if attendance >= 50000:
        return 5.0   # Major stadium event (e.g., UT football)
    elif attendance >= 20000:
        return 3.5   # Large arena event (e.g., Moody Center concert)
    elif attendance >= 5000:
        return 2.0   # Mid-size venue
    elif attendance >= 1000:
        return 1.0   # Small venue
    else:
        return 0.5   # Minor local event


def fetch_events_data():
    """
    Fetches upcoming events in the Austin metro area from the Ticketmaster API
    for the next 7 days, extracts venue locations, attendance capacities, and event
    classification, then saves an enriched DataFrame to a timestamped CSV.
    """
    api_key = os.getenv("TICKETMASTER_API_KEY")
    if not api_key or "actual" in api_key or api_key == "your_actual_ticketmaster_key_here":
        print("[-] Error: A valid 'TICKETMASTER_API_KEY' must be configured in your .env file.")
        print("    Get a free key at: https://developer.ticketmaster.com/")
        return False

    print(f"[{datetime.now()}] Fetching upcoming Austin events from Ticketmaster API (next 7 days)...")

    # Define the date window for event lookups
    start_dt = datetime.utcnow()
    end_dt = start_dt + timedelta(days=7)

    params = {
        "apikey":       api_key,
        "city":         AUSTIN_GEO["city"],
        "stateCode":    AUSTIN_GEO["stateCode"],
        "countryCode":  AUSTIN_GEO["countryCode"],
        "radius":       AUSTIN_GEO["radius"],
        "unit":         AUSTIN_GEO["unit"],
        "startDateTime": start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endDateTime":   end_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "size":         100,     # Max results per page
        "sort":         "date,asc",
    }

    try:
        response = requests.get(TICKETMASTER_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"[-] Error calling Ticketmaster API: {e}")
        return False

    events_raw = data.get("_embedded", {}).get("events", [])
    if not events_raw:
        print("[!] No upcoming events found in the Austin area for the next 7 days.")
        return False

    print(f" -> {len(events_raw)} upcoming events found. Parsing details...")

    records = []
    for event in events_raw:
        try:
            # --- Event Metadata ---
            event_id = event.get("id")
            event_name = event.get("name", "Unknown Event")
            event_url = event.get("url", "")

            # --- Classification ---
            classifications = event.get("classifications", [{}])
            segment = classifications[0].get("segment", {}).get("name", "Unknown")
            genre = classifications[0].get("genre", {}).get("name", "Unknown")
            is_high_impact = segment in HIGH_IMPACT_CLASSIFICATIONS

            # --- Dates and Times ---
            dates = event.get("dates", {}).get("start", {})
            event_date = dates.get("localDate", None)
            event_time = dates.get("localTime", None)

            # --- Venue Info ---
            venues = event.get("_embedded", {}).get("venues", [{}])
            venue = venues[0] if venues else {}
            venue_name = venue.get("name", "Unknown Venue")
            venue_city = venue.get("city", {}).get("name", "Austin")
            venue_lat = float(venue.get("location", {}).get("latitude", 0) or 0)
            venue_lon = float(venue.get("location", {}).get("longitude", 0) or 0)
            venue_capacity = int(venue.get("upcomingEvents", {}).get("_total", 0) or 0)

            # --- Ticket Sales Pressure (proxy for expected attendance) ---
            price_ranges = event.get("priceRanges", [])
            min_price = price_ranges[0].get("min", None) if price_ranges else None
            max_price = price_ranges[0].get("max", None) if price_ranges else None

            # --- Congestion Impact Estimate ---
            estimated_congestion_radius = estimate_congestion_radius_mi(venue_capacity)

            record = {
                "timestamp":                   datetime.now().isoformat(),
                "event_id":                    event_id,
                "event_name":                  event_name,
                "event_date":                  event_date,
                "event_time_local":            event_time,
                "classification_segment":      segment,
                "genre":                       genre,
                "is_high_traffic_impact":      is_high_impact,
                "venue_name":                  venue_name,
                "venue_city":                  venue_city,
                "venue_latitude":              venue_lat,
                "venue_longitude":             venue_lon,
                "venue_capacity":              venue_capacity,
                "ticket_min_price_usd":        min_price,
                "ticket_max_price_usd":        max_price,
                "est_congestion_radius_mi":    estimated_congestion_radius,
                "event_url":                   event_url,
            }
            records.append(record)
            print(f"    [+] {event_name} | {event_date} {event_time or ''} | "
                  f"{venue_name} | Impact: {'HIGH' if is_high_impact else 'Standard'}")

        except Exception as e:
            print(f"   [!] Error parsing event record: {e}")
            continue

    if not records:
        print("[-] No events could be parsed. Aborting save.")
        return False

    df = pd.DataFrame(records)

    # Sort events chronologically for readability
    df = df.sort_values("event_date").reset_index(drop=True)

    output_dir = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(output_dir, f"austin_events_{timestamp}.csv")

    df.to_csv(file_path, index=False)
    print(f"\n[+] Saved {len(df)} Austin events to {os.path.abspath(file_path)}")
    print(f"    High-traffic-impact events: "
          f"{df['is_high_traffic_impact'].sum()} / {len(df)}")
    return True


if __name__ == "__main__":
    fetch_events_data()
