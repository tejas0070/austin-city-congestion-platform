from fastapi import APIRouter
from ...services.weather_service import fetch_current_weather

router = APIRouter(prefix="/api/weather", tags=["weather"])


@router.get("/current")
async def get_current_weather():
    """Current Austin weather from Open-Meteo, cached 15 min."""
    return await fetch_current_weather()
