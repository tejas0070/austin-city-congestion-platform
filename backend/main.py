import asyncio
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from .api.routes.traffic import router as traffic_router
from .api.routes.events import router as events_router
from .api.routes.weather import router as weather_router
from .middleware import SecurityHeadersMiddleware, RateLimitMiddleware
from .db.database import engine
from .db import models

logger = logging.getLogger("austin_traffic")

models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Austin Traffic Intelligence API",
    description="Real-time traffic, events, and weather for Austin TX — feeds the kepler.gl map.",
    version="2.0.0",
)

# Middleware runs in reverse registration order on the request path, so the LAST
# one added is the OUTERMOST layer. Desired outer→inner:
#   SecurityHeaders → CORS → GZip → RateLimit → routes
# SecurityHeaders outermost guarantees hardening headers land on every response,
# including CORS preflights and 429s. CORS wraps RateLimit so a rejected request
# still carries the headers the browser needs to read the 429.
app.add_middleware(RateLimitMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_origin_regex=r"https://[a-z0-9\-]+\.netlify\.app",
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)
app.add_middleware(SecurityHeadersMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log full detail server-side; return a generic message so stack traces,
    file paths, and DB internals never reach the client."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(traffic_router)
app.include_router(events_router)
app.include_router(weather_router)


@app.on_event("startup")
async def warm_prediction_caches() -> None:
    """Kick off cache warming in the background so startup readiness isn't
    delayed; the first UI load then hits warm prediction caches."""
    from .services.ml_model import warm_caches

    asyncio.create_task(warm_caches())


@app.get("/health")
def health():
    return {"status": "ok"}
