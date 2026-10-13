"""Player profile routes."""
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth import get_current_user, require_user_id
from app.core.database import InsForgeClient, get_insforge_client
from app.schemas.players import PlayerCreate, PlayerUpdate, PlayerResponse
from app.services import players as player_svc

router = APIRouter(prefix="/api/players", tags=["players"])
_bearer = HTTPBearer(auto_error=True)


@router.post("", response_model=PlayerResponse, status_code=201)
async def create_player(
    body: PlayerCreate,
    current_user: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> Any:
    owner_id = require_user_id(current_user)
    return await player_svc.create_player(db, body, owner_id, credentials.credentials)


@router.get("", response_model=List[PlayerResponse])
async def list_players(
    current_user: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    mine: bool = Query(True),
    search: Optional[str] = Query(None, max_length=100),
) -> Any:
    owner_id = require_user_id(current_user) if mine else None
    return await player_svc.list_players(db, owner_id=owner_id, search=search)


@router.get("/{player_id}", response_model=PlayerResponse)
async def get_player(
    player_id: str,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
) -> Any:
    return await player_svc.get_player(db, player_id)


@router.patch("/{player_id}", response_model=PlayerResponse)
async def update_player(
    player_id: str,
    body: PlayerUpdate,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> Any:
    return await player_svc.update_player(db, player_id, body, credentials.credentials)


@router.delete("/{player_id}", status_code=204)
async def delete_player(
    player_id: str,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> None:
    await player_svc.delete_player(db, player_id, credentials.credentials)
