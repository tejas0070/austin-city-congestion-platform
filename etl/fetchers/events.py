"""
Events fetcher — Ticketmaster Discovery API.

Fetches upcoming Austin events within the next 48 hours (not 7 days) to
keep the local dataset small and the pipeline fast. Returns a list of
Event ORM objects with PostGIS Point venue locations ready for insertion.
"""

import logging
from datetime import datetime, timedelta, timezone

import httpx

from backend.app.geo_models import Event
from ._http import get_json

logger = logging.getLogger(__name__)

TICKETMASTER_URL = "https://app.ticketmaster.com/discovery/v2/events.json"

# Event segments that reliably cause congestion spikes around their venues
HIGH_IMPACT_SEGMENTS = {"Music", "Sports", "Arts & Theatre", "Film"}

# Venue name → specific subtype (checked before generic segment classification)
_VENUE_SUBTYPES: dict[str, str] = {
    "Q2 Stadium": "austin_fc",
    "Darrell K Royal-Texas Memorial Stadium": "ut_football",
    "DKR-Texas Memorial Stadium": "ut_football",
    "Royal-Memorial Stadium": "ut_football",
}

# Keywords in the event name that indicate a festival
_FESTIVAL_KEYWORDS = {
    "ACL", "Austin City Limits", "SXSW", "South by Southwest",
    "Pachanga", "Fun Fun Fun", "Euphoria", "Eeyore", "Blues on the Green",
    "Formula 1", "Grand Prix", "Moto GP",
}


def _classify_subtype(event_name: str, venue_name: str | None, segment: str) -> str:
    """Return the event_subtype string used for Power BI Event Impact filtering."""
    if venue_name and venue_name in _VENUE_SUBTYPES:
        return _VENUE_SUBTYPES[venue_name]
    if any(kw.lower() in event_name.lower() for kw in _FESTIVAL_KEYWORDS):
        return "festival"
    if segment == "Music":
        return "concert"
    if segment == "Sports":
        return "sports_other"
    if segment in {"Arts & Theatre", "Film"}:
        return "arts"
    return "other"


def _congestion_radius_mi(capacity: int) -> float:
    """Estimate road-impact radius in miles from venue capacity / attendance proxy."""
    if capacity >= 50_000:
        return 5.0   # major stadium (UT football, Formula 1)
    if capacity >= 20_000:
        return 3.5   # large arena (Moody Center)
    if capacity >= 5_000:
        return 2.0   # mid-size venue
    if capacity >= 1_000:
        return 1.0   # small venue
    return 0.5


def _parse_start_time(dates: dict) -> datetime:
    """
    Build a UTC-aware datetime from Ticketmaster's localDate + localTime fields.
    Falls back to midnight UTC if time is missing.
    """
    start = dates.get("start", {})
    date_str = start.get("localDate", "")
    time_str = start.get("localTime") or "00:00:00"
    return datetime.fromisoformat(f"{date_str}T{time_str}").replace(tzinfo=timezone.utc)


def _parse_event(raw: dict) -> Event | None:
    """
    Parse one raw Ticketmaster event dict into an Event ORM object.
    Returns None if venue coordinates are missing (can't create a geometry).
    """
    venues = raw.get("_embedded", {}).get("venues", [{}])
    venue  = venues[0] if venues else {}
    loc    = venue.get("location", {})

    try:
        lat = float(loc.get("latitude") or 0)
        lon = float(loc.get("longitude") or 0)
    except (TypeError, ValueError):
        return None

    if lat == 0.0 or lon == 0.0:
        return None   # no usable coordinates

    cls      = (raw.get("classifications") or [{}])[0]
    segment  = cls.get("segment", {}).get("name") or ""
    capacity = int(venue.get("upcomingEvents", {}).get("_total") or 0)
    venue_name = venue.get("name")
    event_name = raw.get("name", "Unknown Event")

    return Event(
        external_id=raw.get("id"),
        name=event_name,
        venue_name=venue_name,
        venue_location=f"SRID=4326;POINT({lon} {lat})",
        start_time=_parse_start_time(raw.get("dates", {})),
        expected_attendance=capacity,
        is_high_impact=segment in HIGH_IMPACT_SEGMENTS,
        est_congestion_radius_mi=_congestion_radius_mi(capacity),
        classification=segment or None,
        event_subtype=_classify_subtype(event_name, venue_name, segment),
    )


async def fetch_events(
    client: httpx.AsyncClient,
    api_key: str,
) -> list[Event]:
    """
    Fetch Austin events starting within the next 48 hours.

    The 48-hour window keeps the local dataset small: full 7-day pulls
    return 100+ events most weeks and slow down insertion and queries.

    Returns:
        List of Event ORM objects with valid venue coordinates.
        Events with missing lat/lon are silently dropped.
    """
    now = datetime.now(timezone.utc)
    end = now + timedelta(hours=48)

    data = await get_json(client, TICKETMASTER_URL, {
        "apikey":        api_key,
        "city":          "Austin",
        "stateCode":     "TX",
        "countryCode":   "US",
        "radius":        "20",
        "unit":          "miles",
        "startDateTime": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endDateTime":   end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "size":          100,
        "sort":          "date,asc",
    })

    raw_events = data.get("_embedded", {}).get("events", [])
    logger.debug("Ticketmaster returned %d events in the 48-hour window", len(raw_events))

    events: list[Event] = []
    for raw in raw_events:
        try:
            event = _parse_event(raw)
            if event is not None:
                events.append(event)
        except Exception as exc:
            logger.warning("skipping unparseable event '%s': %s",
                           raw.get("name", "?"), exc)

    logger.info("events fetcher: %d usable events out of %d returned",
                len(events), len(raw_events))
    return events
