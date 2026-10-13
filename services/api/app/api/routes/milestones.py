"""
API routes for Phase 5 — Score Animations & Replayable Milestones.
"""
from typing import Annotated, Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth import get_current_user
from app.core.database import InsForgeClient, get_insforge_client
from app.schemas.milestones import MilestoneResponse, PlayerMilestoneSummary
from app.services import milestones as milestones_service

router = APIRouter(tags=["milestones"])
_bearer = HTTPBearer(auto_error=True)


@router.get(
    "/api/matches/{match_id}/milestones",
    response_model=List[MilestoneResponse],
    summary="List all valid batting milestones achieved in a match",
)
async def list_match_milestones(
    match_id: UUID,
    current_user: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    include_invalid: bool = Query(default=False),
):
    return await milestones_service.get_match_milestones(
        db=db, match_id=str(match_id), include_invalid=include_invalid
    )


@router.get(
    "/api/innings/{innings_id}/milestones",
    response_model=List[MilestoneResponse],
    summary="List all valid batting milestones achieved in an innings",
)
async def list_innings_milestones(
    innings_id: UUID,
    current_user: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    include_invalid: bool = Query(default=False),
):
    return await milestones_service.get_innings_milestones(
        db=db, innings_id=str(innings_id), include_invalid=include_invalid
    )


@router.post(
    "/api/innings/{innings_id}/milestones/recalculate",
    response_model=List[MilestoneResponse],
    summary="Deterministically recalculate and synchronize milestones for an innings",
)
async def recalculate_milestones(
    innings_id: UUID,
    current_user: Annotated[Dict[str, Any], Depends(get_current_user)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
):
    return await milestones_service.recalculate_innings_milestones(
        db=db,
        innings_id=str(innings_id),
        token=credentials.credentials,
        reason="Manual / scorecard recalculation",
    )


@router.get(
    "/api/players/{player_id}/milestones",
    response_model=PlayerMilestoneSummary,
    summary="Get a player's career milestone achievements and replayable celebrations",
)
async def get_player_milestones(
    player_id: UUID,
    current_user: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
):
    return await milestones_service.get_player_milestones(
        db=db, player_id=str(player_id)
    )


@router.get(
    "/api/milestones/{milestone_id}",
    response_model=MilestoneResponse,
    summary="Get a single milestone event with highlight clip availability",
)
async def get_milestone(
    milestone_id: UUID,
    current_user: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
):
    return await milestones_service.get_milestone_by_id(
        db=db, milestone_id=str(milestone_id)
    )
