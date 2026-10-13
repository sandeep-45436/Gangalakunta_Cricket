"""
Match service — creation, playing XI management, substitutes.
Enforces business rules:
  1. A match has exactly 2 teams.
  2. Playing XI has exactly 11 distinct players.
  3. A player cannot appear twice in the same team's XI.
  4. Editing squad must not silently change a historical XI.
  5. Only the match owner can mutate.
"""
from typing import Any, Dict, List

from fastapi import HTTPException, status

from app.core.database import InsForgeClient
from app.core.logging import get_logger
from app.schemas.matches import MatchCreate, MatchUpdate, PlayingXISetRequest, SubstituteAdd

logger = get_logger(__name__)


async def create_match(
    db: InsForgeClient,
    data: MatchCreate,
    owner_id: str,
    token: str,
) -> Dict[str, Any]:
    # Validate both teams exist
    for team_entry in data.teams:
        team = await db.select_one("teams", {"id": f"eq.{team_entry.team_id}"})
        if not team:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Team {team_entry.team_id} not found",
            )

    # Create match record
    insert_payload = {
        "owner_id": owner_id,
        "title": data.title,
        "format": data.format,
        "venue": data.venue,
        "scheduled_at": data.scheduled_at.isoformat() if data.scheduled_at else None,
        "overs_per_innings": data.overs_per_innings,
        "status": "upcoming",
    }
    if data.tournament is not None:
        insert_payload["tournament"] = data.tournament

    match_rows = await db.insert_as_user(
        "matches",
        [insert_payload],
        token,
    )
    match = match_rows[0]
    match_id = match["id"]

    # Snapshot team names into match_teams
    team_responses = []
    for team_entry in data.teams:
        team = await db.select_one("teams", {"id": f"eq.{team_entry.team_id}"})
        mt_rows = await db.insert_as_user(
            "match_teams",
            [{
                "match_id": match_id,
                "team_id": str(team_entry.team_id),
                "team_name": team["name"],  # snapshot
                "batting_order": team_entry.batting_order,
            }],
            token,
        )
        team_responses.append(mt_rows[0])

    match["teams"] = team_responses
    return match


async def list_matches(
    db: InsForgeClient,
    owner_id: str,
) -> List[Dict[str, Any]]:
    matches = await db.select(
        "matches",
        filters={"owner_id": f"eq.{owner_id}"},
        order="created_at.desc",
    )
    for m in matches:
        m["teams"] = await db.select(
            "match_teams",
            filters={"match_id": f"eq.{m['id']}"},
            order="batting_order.asc",
        )
    return matches


async def get_match(db: InsForgeClient, match_id: str) -> Dict[str, Any]:
    match = await db.select_one("matches", {"id": f"eq.{match_id}"})
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    match["teams"] = await db.select(
        "match_teams",
        filters={"match_id": f"eq.{match_id}"},
        order="batting_order.asc",
    )
    return match


async def update_match(
    db: InsForgeClient,
    match_id: str,
    data: MatchUpdate,
    token: str,
) -> Dict[str, Any]:
    payload = {k: v for k, v in data.model_dump().items() if v is not None}
    if not payload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    rows = await db.update_as_user("matches", {"id": f"eq.{match_id}"}, payload, token)
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Match not found or not authorized",
        )
    result = rows[0]
    result["teams"] = await db.select(
        "match_teams", filters={"match_id": f"eq.{match_id}"}, order="batting_order.asc"
    )
    return result


async def delete_match(db: InsForgeClient, match_id: str, token: str) -> None:
    match = await db.select_one("matches", {"id": f"eq.{match_id}"})
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")
    await db.delete_as_user("matches", {"id": f"eq.{match_id}"}, token)


async def set_playing_xi(
    db: InsForgeClient,
    match_id: str,
    data: PlayingXISetRequest,
    token: str,
) -> List[Dict[str, Any]]:
    """
    Replace the Playing XI for a team in a match.
    Validates:
      - match exists
      - team is part of the match
      - all 11 players exist and are distinct
    Snapshot: player_name is copied from the players table at selection time.
    Historical immutability: editing the squad (team_players) cannot touch this table.
    """
    team_id = str(data.team_id)

    # Verify match
    match = await db.select_one("matches", {"id": f"eq.{match_id}"})
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

    # Verify team is part of this match
    mt = await db.select_one(
        "match_teams",
        {"match_id": f"eq.{match_id}", "team_id": f"eq.{team_id}"},
    )
    if not mt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team is not part of this match",
        )

    # Validate all players exist and build rows
    xi_rows = []
    for entry in data.players:
        player = await db.select_one("players", {"id": f"eq.{entry.player_id}"})
        if not player:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Player {entry.player_id} not found",
            )
        xi_rows.append({
            "match_id": match_id,
            "team_id": team_id,
            "player_id": str(entry.player_id),
            "player_name": player.get("display_name") or player["full_name"],  # snapshot
            "batting_position": entry.batting_position,
            "is_captain": entry.is_captain,
            "is_wicketkeeper": entry.is_wicketkeeper,
        })

    # Delete existing XI for this match+team, then insert fresh snapshot
    await db.delete_as_user(
        "playing_xi",
        {"match_id": f"eq.{match_id}", "team_id": f"eq.{team_id}"},
        token,
    )
    inserted = await db.insert_as_user("playing_xi", xi_rows, token)
    return inserted


async def get_playing_xi(
    db: InsForgeClient,
    match_id: str,
    team_id: str,
) -> List[Dict[str, Any]]:
    return await db.select(
        "playing_xi",
        filters={"match_id": f"eq.{match_id}", "team_id": f"eq.{team_id}"},
        order="batting_position.asc.nullslast",
    )


async def add_substitute(
    db: InsForgeClient,
    match_id: str,
    data: SubstituteAdd,
    token: str,
) -> Dict[str, Any]:
    # Verify player exists
    player = await db.select_one("players", {"id": f"eq.{data.player_id}"})
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")

    rows = await db.insert_as_user(
        "match_substitutes",
        [{
            "match_id": match_id,
            "team_id": str(data.team_id),
            "player_id": str(data.player_id),
            "player_name": player.get("display_name") or player["full_name"],
            "substitute_type": data.substitute_type,
        }],
        token,
    )
    return rows[0]


async def list_substitutes(
    db: InsForgeClient,
    match_id: str,
) -> List[Dict[str, Any]]:
    return await db.select(
        "match_substitutes",
        filters={"match_id": f"eq.{match_id}"},
        order="declared_at.asc",
    )
