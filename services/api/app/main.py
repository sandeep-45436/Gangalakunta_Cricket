"""
Cricket Highlights API — main application entrypoint.
"""
from contextlib import asynccontextmanager
import time
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    auth,
    health,
    teams,
    players,
    matches,
    scoring,
    recording,
    highlights,
    milestones,
    archive,
)
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(debug=settings.api_debug)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info(
        "Cricket Highlights API starting — InsForge project: %s",
        settings.insforge_url,
    )
    yield
    logger.info("Cricket Highlights API shutting down")


app = FastAPI(
    title="Cricket Highlights API",
    description=(
        "Backend API for the Cricket Highlights platform. "
        "Manages teams, squads, matches, ball-by-ball scoring, "
        "player-specific video highlights, replayable milestones, "
        "and searchable historical archives."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
    response.headers["X-Process-Time-Ms"] = str(elapsed_ms)
    return response


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(teams.router)
app.include_router(players.router)
app.include_router(matches.router)
app.include_router(scoring.router)
app.include_router(recording.router)
app.include_router(highlights.router)
app.include_router(milestones.router)
app.include_router(archive.router)


@app.get("/", include_in_schema=False)
async def root() -> dict:
    return {
        "service": "cricket-api",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
