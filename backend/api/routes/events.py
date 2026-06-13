from fastapi import APIRouter, Query
from ...services.events_service import fetch_upcoming_events, build_events_geojson

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("/upcoming")
async def get_upcoming_events(
    days: int = Query(30, ge=1, le=90, description="Number of days ahead to fetch")
):
    """Upcoming Austin events from Ticketmaster, Austin FC, and UT Athletics."""
    return await fetch_upcoming_events(days=days)


@router.get("/geojson")
async def get_events_geojson(
    days: int = Query(30, ge=1, le=90, description="Number of days ahead to fetch")
):
    """Upcoming events as GeoJSON venue points (sized by expected attendance)."""
    return await build_events_geojson(days=days)
