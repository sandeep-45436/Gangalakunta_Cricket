"""Teams and squad management routes."""
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.auth import get_current_user, require_user_id
from app.core.database import InsForgeClient, get_insforge_client
from app.schemas.teams import (
    TeamCreate, TeamUpdate, TeamResponse,
    TeamPlayerAdd, TeamPlayerResponse,
    SquadImportRequest,
)
from app.services import teams as team_svc

router = APIRouter(prefix="/api/teams", tags=["teams"])
_bearer = HTTPBearer(auto_error=True)


@router.post("", response_model=TeamResponse, status_code=201)
async def create_team(
    body: TeamCreate,
    current_user: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> Any:
    owner_id = require_user_id(current_user)
    return await team_svc.create_team(db, body, owner_id, credentials.credentials)


@router.get("", response_model=List[TeamResponse])
async def list_teams(
    current_user: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    mine: bool = Query(True, description="Filter to teams owned by the current user"),
) -> Any:
    owner_id = require_user_id(current_user) if mine else None
    return await team_svc.list_teams(db, owner_id=owner_id)


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: str,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
) -> Any:
    return await team_svc.get_team(db, team_id)


@router.patch("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: str,
    body: TeamUpdate,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> Any:
    return await team_svc.update_team(db, team_id, body, credentials.credentials)


@router.delete("/{team_id}", status_code=204)
async def delete_team(
    team_id: str,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> None:
    await team_svc.delete_team(db, team_id, credentials.credentials)


# ── Squad endpoints ───────────────────────────────────────────────────────────

@router.get("/{team_id}/squad", response_model=List[Dict[str, Any]])
async def list_squad(
    team_id: str,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    active_only: bool = Query(True),
) -> Any:
    return await team_svc.list_squad(db, team_id, active_only=active_only)


@router.post("/{team_id}/squad", status_code=201)
async def add_squad_member(
    team_id: str,
    body: TeamPlayerAdd,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> Any:
    return await team_svc.add_squad_member(
        db, team_id, str(body.player_id), credentials.credentials
    )


@router.delete("/{team_id}/squad/{player_id}", status_code=204)
async def remove_squad_member(
    team_id: str,
    player_id: str,
    _: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> None:
    await team_svc.remove_squad_member(db, team_id, player_id, credentials.credentials)


@router.post("/{team_id}/squad/import")
async def import_squad(
    team_id: str,
    body: SquadImportRequest,
    current_user: Annotated[Dict[str, Any], Depends(get_current_user)],
    db: Annotated[InsForgeClient, Depends(get_insforge_client)],
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> Any:
    owner_id = require_user_id(current_user)
    return await team_svc.import_squad(
        db, team_id, body.players, owner_id, credentials.credentials
    )
