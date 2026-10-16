"""
Cricket Highlights API — main application entrypoint.
Supports both standalone API mode and full-stack SPA hosting on Vercel (`services.api.app.main:app`).
"""
from contextlib import asynccontextmanager
import json
from pathlib import Path
import sys
import time
from typing import AsyncGenerator

# Ensure `services/api` is on sys.path when imported from repo root (e.g. Vercel `services.api.app.main:app`)
_SERVICE_ROOT = Path(__file__).resolve().parent.parent
if str(_SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SERVICE_ROOT))

from fastapi import FastAPI, HTTPException, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, HTMLResponse  # noqa: E402

from app.api.routes import (  # noqa: E402
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
    ai_capture,
)
from app.core.config import get_settings  # noqa: E402
from app.core.logging import configure_logging, get_logger  # noqa: E402

settings = get_settings()
configure_logging(debug=settings.api_debug)
logger = get_logger(__name__)

_WEB_DIST_DIR = _SERVICE_ROOT.parent.parent / "apps" / "web" / "dist"


def _render_spa_index() -> HTMLResponse:
    """Render apps/web/dist/index.html with runtime InsForge public config injected."""
    import os
    index_file = _WEB_DIST_DIR / "index.html"
    html = index_file.read_text(encoding="utf-8")
    cfg = get_settings()
    runtime_payload = json.dumps({
        "insforgeUrl": cfg.insforge_url,
        "insforgeAnonKey": cfg.insforge_anon_key,
        "apiBaseUrl": os.getenv("VITE_API_BASE_URL", ""),
    })
    script_tag = f"<script>window.__CRICKET_CONFIG__ = {runtime_payload};</script>"
    if "</head>" in html:
        html = html.replace("</head>", f"{script_tag}</head>", 1)
    else:
        html = script_tag + html
    return HTMLResponse(content=html)


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
    allow_origin_regex=r"https://.*\.vercel\.app",
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
app.include_router(ai_capture.router)


@app.get("/", include_in_schema=False)
async def root(request: Request):
    accept = request.headers.get("accept", "")
    if "text/html" in accept and (_WEB_DIST_DIR / "index.html").is_file():
        return _render_spa_index()
    return {
        "service": "cricket-api",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    """Serve static files or React SPA index.html for client-side routes on Vercel."""
    if full_path.startswith(("api/", "health", "docs", "redoc", "openapi.json")):
        raise HTTPException(status_code=404, detail="Not Found")
    candidate = (_WEB_DIST_DIR / full_path).resolve()
    if (
        str(candidate).startswith(str(_WEB_DIST_DIR.resolve()))
        and candidate.is_file()
    ):
        return FileResponse(str(candidate))
    if (_WEB_DIST_DIR / "index.html").is_file():
        return _render_spa_index()
    raise HTTPException(status_code=404, detail="Not Found")
