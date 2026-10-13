"""
API routes for Phase 4 — Highlights & Video Processing Pipeline.
Includes both `/api/highlights/trigger` and `/api/highlights/process` (Cross-phase Spec 2.1).
"""
from typing import Annotated, Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth import get_current_user
from app.core.database import InsForgeClient, get_insforge_client
from app.schemas.highlights import (
    HighlightJobResponse,
    HighlightTriggerRequest,
    PlayerHighlightReel,
    PlayerHighlightResponse,
    ReprocessHighlightRequest,
)
from app.services import highlights as highlights_service

router = APIRouter(tags=["highlights"])
_bearer = HTTPBearer(auto_error=True)


@router.post(
    "/api/highlights/trigger",
    response_model=PlayerHighlightResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger highlight extraction for a qualifying delivery and marker",
)
@router.post(
    "/api/highlights/process",
    response_model=PlayerHighlightResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue an eligible highlight for background FFmpeg extraction (Spec 2.1)",
)
async def trigger_highlight(
    data: HighlightTriggerRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[Dict[str, Any], Depends(get_current_user)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
):
    """
    Validates delivery qualification (batter-credited 4 or 6) and marker,
    derives player ID from striker_id, and dispatches background FFmpeg extraction.
    """
    return await highlights_service.create_or_get_highlight_job(
        db=db,
        delivery_id=str(data.delivery_id),
        token=credentials.credentials,
        marker_id=str(data.marker_id) if data.marker_id else None,
        config_before_sec=data.config_before_sec,
        config_after_sec=data.config_after_sec,
        background_tasks=background_tasks,
    )


@router.post(
    "/api/highlights/{highlight_id}/reprocess",
    response_model=PlayerHighlightResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Reprocess a highlight with corrected marker or adjusted trim ranges",
)
async def reprocess_highlight(
    highlight_id: UUID,
    data: ReprocessHighlightRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[Dict[str, Any], Depends(get_current_user)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
):
    """
    Idempotently bumps the highlight version and triggers reprocessing.
    """
    return await highlights_service.reprocess_highlight(
        db=db,
        highlight_id=str(highlight_id),
        token=credentials.credentials,
        data=data,
        background_tasks=background_tasks,
    )


@router.get(
    "/api/highlights/jobs/{job_id}",
    response_model=HighlightJobResponse,
    summary="Get operator-visible status for a background highlight job",
)
async def get_highlight_job_status(
    job_id: UUID,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
):
    return await highlights_service.get_highlight_job(db=db, job_id=str(job_id))


@router.get(
    "/api/players/{player_id}/highlights",
    response_model=PlayerHighlightReel,
    summary="Get player's published highlight reel",
)
async def get_player_highlights(
    player_id: UUID,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
):
    return await highlights_service.get_player_highlight_reel(
        db=db, player_id=str(player_id)
    )


@router.get(
    "/api/matches/{match_id}/highlights",
    response_model=List[PlayerHighlightResponse],
    summary="Get all highlights for a match",
)
async def get_match_highlights(
    match_id: UUID,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
):
    return await highlights_service.get_match_highlights(
        db=db, match_id=str(match_id)
    )
