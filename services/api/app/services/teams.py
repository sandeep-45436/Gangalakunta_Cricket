"""
Team and squad service — business logic for team/player management.
All DB access goes through InsForgeClient (PostgREST).
"""
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.core.database import InsForgeClient
from app.core.logging import get_logger
from app.schemas.teams import TeamCreate, TeamUpdate, SquadImportEntry

logger = get_logger(__name__)


async def create_team(
    db: InsForgeClient,
    data: TeamCreate,
    owner_id: str,
    token: str,
) -> Dict[str, Any]:
    rows = await db.insert_as_user(
        "teams",
        [{"name": data.name, "short_name": data.short_name,
          "logo_url": data.logo_url, "owner_id": owner_id}],
        token,
    )
    return rows[0]


async def list_teams(
    db: InsForgeClient,
    owner_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    filters: Dict[str, str] = {}
    if owner_id:
        filters["owner_id"] = f"eq.{owner_id}"
    return await db.select("teams", filters=filters, order="created_at.desc")


async def get_team(db: InsForgeClient, team_id: str) -> Dict[str, Any]:
    row = await db.select_one("teams", {"id": f"eq.{team_id}"})
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return row


async def update_team(
    db: InsForgeClient,
    team_id: str,
    data: TeamUpdate,
    token: str,
) -> Dict[str, Any]:
    payload = {k: v for k, v in data.model_dump().items() if v is not None}
    if not payload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    rows = await db.update_as_user("teams", {"id": f"eq.{team_id}"}, payload, token)
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found or not authorized")
    return rows[0]


async def delete_team(db: InsForgeClient, team_id: str, token: str) -> None:
    """
    Safeguard (Spec 2.3): Team deletions must not silently destroy completed-match history.
    Reject deletion with 409 Conflict if the team has completed matches or scored innings.
    """
    mt_rows = await db.select("match_teams", filters={"team_id": f"eq.{team_id}"})
    for mt in mt_rows:
        m_id = mt.get("match_id")
        if m_id:
            match = await db.select_one("matches", {"id": f"eq.{m_id}"})
            inns = await db.select("innings", filters={"match_id": f"eq.{m_id}"}, limit=1)
            if (match and match.get("status") == "completed") or inns:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cannot delete team with completed or scored match history; historical scorecards must be preserved.",
                )
    for mt in mt_rows:
        m_id = mt.get("match_id")
        if m_id:
            await db.delete_as_user("matches", {"id": f"eq.{m_id}"}, token)
    await db.delete_as_user("team_players", {"team_id": f"eq.{team_id}"}, token)
    await db.delete_as_user("teams", {"id": f"eq.{team_id}"}, token)


async def add_squad_member(
    db: InsForgeClient,
    team_id: str,
    player_id: str,
    token: str,
) -> Dict[str, Any]:
    # Verify player exists
    player = await db.select_one("players", {"id": f"eq.{player_id}"})
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
    # Check for duplicate
    existing = await db.select_one(
        "team_players",
        {"team_id": f"eq.{team_id}", "player_id": f"eq.{player_id}"},
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Player is already in this team's squad",
        )
    rows = await db.insert_as_user(
        "team_players",
        [{"team_id": team_id, "player_id": player_id}],
        token,
    )
    return rows[0]


async def list_squad(
    db: InsForgeClient,
    team_id: str,
    active_only: bool = True,
) -> List[Dict[str, Any]]:
    filters: Dict[str, str] = {"team_id": f"eq.{team_id}"}
    if active_only:
        filters["is_active"] = "eq.true"
    return await db.select(
        "team_players",
        select="*,players(*)",
        filters=filters,
        order="joined_at.asc",
    )


async def remove_squad_member(
    db: InsForgeClient,
    team_id: str,
    player_id: str,
    token: str,
) -> None:
    await db.delete_as_user(
        "team_players",
        {"team_id": f"eq.{team_id}", "player_id": f"eq.{player_id}"},
        token,
    )


async def import_squad(
    db: InsForgeClient,
    team_id: str,
    entries: List[SquadImportEntry],
    owner_id: str,
    token: str,
) -> Dict[str, Any]:
    """
    Bulk import: create player profiles + add to squad.
    Skips players whose full_name already exists for this owner to avoid duplicates.
    Returns counts of created and skipped entries.
    """
    created, skipped = 0, 0
    errors: List[str] = []

    for entry in entries:
        # Check if this owner already has a player with this full_name
        existing_player = await db.select_one(
            "players",
            {"owner_id": f"eq.{owner_id}", "full_name": f"eq.{entry.full_name}"},
        )
        if existing_player:
            player_id = existing_player["id"]
        else:
            try:
                rows = await db.insert_as_user(
                    "players",
                    [{
                        "owner_id": owner_id,
                        "full_name": entry.full_name,
                        "display_name": entry.display_name,
                        "batting_style": entry.batting_style,
                        "bowling_style": entry.bowling_style,
                        "role": entry.role,
                        "jersey_number": entry.jersey_number,
                    }],
                    token,
                )
                player_id = rows[0]["id"]
            except Exception as exc:
                errors.append(f"Failed to create player '{entry.full_name}': {exc}")
                continue

        # Check squad duplicate
        in_squad = await db.select_one(
            "team_players",
            {"team_id": f"eq.{team_id}", "player_id": f"eq.{player_id}"},
        )
        if in_squad:
            skipped += 1
            continue

        try:
            await db.insert_as_user(
                "team_players",
                [{"team_id": team_id, "player_id": player_id}],
                token,
            )
            created += 1
        except Exception as exc:
            errors.append(f"Failed to add '{entry.full_name}' to squad: {exc}")

    return {"created": created, "skipped": skipped, "errors": errors}
