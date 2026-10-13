"""Match, Playing XI and substitutes routes."""
from typing import Annotated, Any, Dict, List

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth import get_current_user, require_user_id
from app.core.database import InsForgeClient, get_insforge_client
from app.schemas.matches import (
    MatchCreate, MatchUpdate, MatchResponse,
    PlayingXISetRequest, PlayingXIEntryResponse,
    SubstituteAdd, SubstituteResponse,
)
from app.services import matches as match_svc

router = APIRouter(prefix="/api/matches", tags=["matches"])
_bearer = HTTPBearer(auto_error=True)


@router.post("", response_model=MatchResponse, status_code=201)
async def create_match(
    body: MatchCreate,
    current_user: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> Any:
    owner_id = require_user_id(current_user)
    return await match_svc.create_match(db, body, owner_id, credentials.credentials)


@router.get("", response_model=List[MatchResponse])
async def list_matches(
    current_user: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
) -> Any:
    owner_id = require_user_id(current_user)
    return await match_svc.list_matches(db, owner_id)


@router.get("/{match_id}", response_model=MatchResponse)
async def get_match(
    match_id: str,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
) -> Any:
    return await match_svc.get_match(db, match_id)


@router.patch("/{match_id}", response_model=MatchResponse)
async def update_match(
    match_id: str,
    body: MatchUpdate,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> Any:
    return await match_svc.update_match(db, match_id, body, credentials.credentials)


@router.delete("/{match_id}", status_code=204)
async def delete_match(
    match_id: str,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> None:
    await match_svc.delete_match(db, match_id, credentials.credentials)


# ── Playing XI ────────────────────────────────────────────────────────────────

@router.put("/{match_id}/playing-xi", response_model=List[PlayingXIEntryResponse])
async def set_playing_xi(
    match_id: str,
    body: PlayingXISetRequest,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> Any:
    return await match_svc.set_playing_xi(db, match_id, body, credentials.credentials)


@router.get("/{match_id}/playing-xi/{team_id}", response_model=List[PlayingXIEntryResponse])
async def get_playing_xi(
    match_id: str,
    team_id: str,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
) -> Any:
    return await match_svc.get_playing_xi(db, match_id, team_id)


# ── Substitutes ───────────────────────────────────────────────────────────────

@router.post("/{match_id}/substitutes", response_model=SubstituteResponse, status_code=201)
async def add_substitute(
    match_id: str,
    body: SubstituteAdd,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> Any:
    return await match_svc.add_substitute(db, match_id, body, credentials.credentials)


@router.get("/{match_id}/substitutes", response_model=List[SubstituteResponse])
async def list_substitutes(
    match_id: str,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
) -> Any:
    return await match_svc.list_substitutes(db, match_id)
