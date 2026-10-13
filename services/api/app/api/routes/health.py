"""
Health-check endpoints.

GET /health         — liveness (always fast, no external calls)
GET /health/db      — InsForge database (PostgREST) connectivity
GET /health/storage — InsForge Storage connectivity
"""
from typing import Annotated, Any, Dict

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from app.core.database import InsForgeClient, get_insforge_client
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


@router.get("", summary="Liveness check")
async def health() -> Dict[str, str]:
    return {"status": "ok", "service": "cricket-api"}


@router.get("/db", summary="InsForge database connectivity check")
async def health_db(
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
) -> Any:
    """Pings the InsForge PostgREST endpoint to confirm database is reachable."""
    ok = await db.ping()
    if ok:
        return {"status": "ok", "db": "connected", "provider": "insforge"}
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "error", "db": "unreachable", "provider": "insforge"},
    )


@router.get("/storage", summary="InsForge Storage connectivity check")
async def health_storage(
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
) -> Any:
    ok = await db.storage_ping("cricket-videos")
    if ok:
        return {"status": "ok", "storage": "reachable", "bucket": "cricket-videos"}
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "error", "storage": "unreachable"},
    )
