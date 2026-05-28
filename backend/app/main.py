import sys
import os

# Ensure the project root is importable regardless of working directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from fastapi import FastAPI

from backend.routes.corridors import router as corridors_router
from backend.routes.predictions import router as predictions_router

app = FastAPI(
    title="Austin Congestion Intelligence API",
    description="Live traffic congestion data and ML-powered predictions for Austin, TX.",
    version="1.0.0",
)

app.include_router(corridors_router)
app.include_router(predictions_router)


@app.get("/health")
def health():
    return {"status": "ok"}
