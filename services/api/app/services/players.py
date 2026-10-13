"""Player profile service."""
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status

from app.core.database import InsForgeClient
from app.schemas.players import PlayerCreate, PlayerUpdate


async def create_player(
    db: InsForgeClient,
    data: PlayerCreate,
    owner_id: str,
    token: str,
) -> Dict[str, Any]:
    payload = data.model_dump()
    payload["owner_id"] = owner_id
    rows = await db.insert_as_user("players", [payload], token)
    return rows[0]


async def list_players(
    db: InsForgeClient,
    owner_id: Optional[str] = None,
    search: Optional[str] = None,
) -> List[Dict[str, Any]]:
    filters: Dict[str, str] = {}
    if owner_id:
        filters["owner_id"] = f"eq.{owner_id}"
    if search:
        # PostgREST ilike filter
        filters["full_name"] = f"ilike.*{search}*"
    return await db.select("players", filters=filters, order="full_name.asc", limit=500)


async def get_player(db: InsForgeClient, player_id: str) -> Dict[str, Any]:
    row = await db.select_one("players", {"id": f"eq.{player_id}"})
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
    return row


async def update_player(
    db: InsForgeClient,
    player_id: str,
    data: PlayerUpdate,
    token: str,
) -> Dict[str, Any]:
    payload = {k: v for k, v in data.model_dump().items() if v is not None}
    if not payload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    rows = await db.update_as_user("players", {"id": f"eq.{player_id}"}, payload, token)
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found or not authorized",
        )
    return rows[0]


async def delete_player(db: InsForgeClient, player_id: str, token: str) -> None:
    """
    Safeguard (Spec 2.3): Player deletions must not silently destroy completed-match history.
    Reject deletion with 409 Conflict if the player has recorded deliveries or completed match appearances.
    """
    striker_delivs = await db.select("deliveries", filters={"striker_id": f"eq.{player_id}"}, limit=1)
    bowler_delivs = await db.select("deliveries", filters={"bowler_id": f"eq.{player_id}"}, limit=1)
    if striker_delivs or bowler_delivs:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete player with recorded match deliveries; completed-match history and highlights must be preserved.",
        )

    xi_rows = await db.select("playing_xi", filters={"player_id": f"eq.{player_id}"})
    for xi in xi_rows:
        m = await db.select_one("matches", {"id": f"eq.{xi['match_id']}"})
        if m and m.get("status") == "completed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot delete player who appeared in a completed match; historical records must be preserved.",
            )

    await db.delete_as_user("player_highlights", {"player_id": f"eq.{player_id}"}, token)
    await db.delete_as_user("highlight_jobs", {"player_id": f"eq.{player_id}"}, token)
    await db.delete_as_user("playing_xi", {"player_id": f"eq.{player_id}"}, token)
    await db.delete_as_user("team_players", {"player_id": f"eq.{player_id}"}, token)
    await db.delete_as_user("players", {"id": f"eq.{player_id}"}, token)
