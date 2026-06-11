import os
from datetime import datetime, timedelta, timezone
import httpx
from ..utils.cache import get_cache, set_cache

_UTC = timezone.utc

CACHE_KEY = "events_upcoming"
CACHE_TTL = 3600  # 1 hour

VENUE_COORDS = {
    "austin_fc":    {"lat": 30.3872, "lng": -97.7188, "name": "Q2 Stadium"},
    "ut_football":  {"lat": 30.2836, "lng": -97.7320, "name": "DKR-Texas Memorial Stadium"},
    "moody_center": {"lat": 30.2850, "lng": -97.7280, "name": "Moody Center"},
    "stubbs":       {"lat": 30.2680, "lng": -97.7336, "name": "Stubb's Amphitheater"},
    "acl_live":     {"lat": 30.2639, "lng": -97.7467, "name": "ACL Live at Moody Theater"},
    "convention":   {"lat": 30.2628, "lng": -97.7402, "name": "Austin Convention Center"},
}

# Hardcoded schedules — update each season
AUSTIN_FC_SCHEDULE = [
    {"id": "afc_01", "name": "Austin FC vs LA Galaxy",        "date": "2026-06-14", "time": "19:30"},
    {"id": "afc_02", "name": "Austin FC vs Portland Timbers", "date": "2026-07-05", "time": "20:00"},
    {"id": "afc_03", "name": "Austin FC vs Seattle Sounders", "date": "2026-07-19", "time": "19:30"},
    {"id": "afc_04", "name": "Austin FC vs Colorado Rapids",  "date": "2026-08-02", "time": "19:30"},
]

UT_FOOTBALL_SCHEDULE = [
    {"id": "ut_fb_01", "name": "UT vs UTSA",     "date": "2026-08-30", "time": "18:00"},
    {"id": "ut_fb_02", "name": "UT vs Michigan",  "date": "2026-09-06", "time": "11:00"},
    {"id": "ut_fb_03", "name": "UT vs LSU",       "date": "2026-09-27", "time": "14:30"},
    {"id": "ut_fb_04", "name": "UT vs Oklahoma",  "date": "2026-10-11", "time": "11:00"},
]


async def fetch_upcoming_events(days: int = 30) -> list[dict]:
    cached = get_cache(CACHE_KEY)
    if cached:
        return cached

    events: list[dict] = []
    events.extend(_get_hardcoded_events(AUSTIN_FC_SCHEDULE, "austin_fc", "Sports", 20738, days))
    events.extend(_get_hardcoded_events(UT_FOOTBALL_SCHEDULE, "ut_football", "Sports", 100119, days))
    events.extend(await _fetch_ticketmaster_events(days))

    events.sort(key=lambda e: e["date"])
    set_cache(CACHE_KEY, events, CACHE_TTL)
    return events


def _get_hardcoded_events(
    schedule: list[dict],
    source: str,
    category: str,
    attendance: int,
    days: int,
) -> list[dict]:
    now = datetime.now(_UTC)
    today = now.strftime("%Y-%m-%d")
    cutoff = (now + timedelta(days=days)).strftime("%Y-%m-%d")
    venue = VENUE_COORDS[source]
    return [
        {
            "id": e["id"],
            "source": source,
            "name": e["name"],
            "venue": venue["name"],
            "date": e["date"],
            "time": e["time"],
            "lat": venue["lat"],
            "lng": venue["lng"],
            "category": category,
            "expected_attendance": attendance,
        }
        for e in schedule
        if today <= e["date"] <= cutoff
    ]


async def _fetch_ticketmaster_events(days: int) -> list[dict]:
    api_key = os.environ.get("TICKETMASTER_API_KEY", "")
    if not api_key:
        return []

    now = datetime.now(_UTC)
    start = now.strftime("%Y-%m-%dT00:00:00Z")
    end = (now + timedelta(days=days)).strftime("%Y-%m-%dT23:59:59Z")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://app.ticketmaster.com/discovery/v2/events.json",
                params={
                    "apikey": api_key,
                    "city": "Austin",
                    "stateCode": "TX",
                    "startDateTime": start,
                    "endDateTime": end,
                    "size": 50,
                    "sort": "date,asc",
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return []

    parsed = [_parse_ticketmaster_event(e) for e in data.get("_embedded", {}).get("events", [])]
    return [e for e in parsed if e is not None]


def _parse_ticketmaster_event(raw: dict) -> dict | None:
    try:
        venues = raw.get("_embedded", {}).get("venues", [{}])
        venue = venues[0] if venues else {}
        loc = venue.get("location", {})
        lat = float(loc.get("latitude") or 0)
        lng = float(loc.get("longitude") or 0)
        if not lat or not lng:
            return None

        dates = raw.get("dates", {}).get("start", {})
        segment = (raw.get("classifications") or [{}])[0].get("segment", {}).get("name", "Other")
        if "Music" in segment:
            category = "Music"
        elif "Sports" in segment:
            category = "Sports"
        else:
            category = "Other"

        return {
            "id": raw.get("id", ""),
            "source": "ticketmaster",
            "name": raw.get("name", ""),
            "venue": venue.get("name", ""),
            "date": dates.get("localDate", ""),
            "time": dates.get("localTime", ""),
            "lat": lat,
            "lng": lng,
            "category": category,
            "expected_attendance": None,
        }
    except Exception:
        return None
