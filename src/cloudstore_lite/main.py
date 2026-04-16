from contextlib import asynccontextmanager

from fastapi import FastAPI

from cloudstore_lite.config import get_settings
from cloudstore_lite.db import init_db
from cloudstore_lite.schemas import HealthStatus


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    settings.storage_root.mkdir(parents=True, exist_ok=True)
    init_db()
    yield


app = FastAPI(title="CloudStore-Lite", version="0.1.0", lifespan=lifespan)


@app.get("/health/live", response_model=HealthStatus, tags=["health"])
def liveness() -> HealthStatus:
    return HealthStatus(status="ok")


@app.get("/health/ready", response_model=HealthStatus, tags=["health"])
def readiness() -> HealthStatus:
    return HealthStatus(status="ok")
