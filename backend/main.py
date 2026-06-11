from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.routes.traffic import router as traffic_router
from .api.routes.events import router as events_router
from .api.routes.weather import router as weather_router
from .db.database import engine
from .db import models

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Austin Traffic Intelligence API",
    description="Real-time traffic, events, and weather for Austin TX — feeds the kepler.gl map.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://*.netlify.app",
    ],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(traffic_router)
app.include_router(events_router)
app.include_router(weather_router)


@app.get("/health")
def health():
    return {"status": "ok"}
