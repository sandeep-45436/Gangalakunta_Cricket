"""
Phase 5 — Deterministic Milestone Calculation, Persistence, Recalculation & Highlight Enrichment.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException, status

from app.core.database import InsForgeClient
from app.core.logging import get_logger
from app.schemas.milestones import MILESTONE_THRESHOLDS

logger = get_logger(__name__)

SORTED_THRESHOLDS: Tuple[int, ...] = (50, 100, 150, 200)


def compute_innings_milestones(deliveries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Pure, deterministic function to compute all batter milestones crossed in an innings.
    Rules:
    - Uses ONLY batter_runs (not team runs or extras such as wides, byes, leg-byes, or no-ball penalties).
    - Ignores voided deliveries (is_voided=True).
    - Orders deliveries deterministically by sequence_no ascending.
    - A milestone for threshold T is created on the first active delivery where the batter's
      cumulative batter_runs crosses from < T to >= T.
    - If a single delivery crosses multiple thresholds (impossible in standard cricket unless
      a custom score is entered, e.g. 49 -> 100), each threshold is recorded once.
    """
    active_deliveries = [d for d in deliveries if not d.get("is_voided", False)]
    active_deliveries.sort(key=lambda d: int(d.get("sequence_no", 0)))

    # Per-batter state: player_id -> { runs, balls, fours, sixes, crossed: set }
    batter_stats: Dict[str, Dict[str, Any]] = {}
    computed_milestones: List[Dict[str, Any]] = []

    for d in active_deliveries:
        striker_id = str(d["striker_id"])
        if striker_id not in batter_stats:
            batter_stats[striker_id] = {
                "runs": 0,
                "balls": 0,
                "fours": 0,
                "sixes": 0,
                "crossed": set(),
            }

        state = batter_stats[striker_id]
        prev_runs = state["runs"]
        batter_runs = int(d.get("batter_runs", 0))
        extra_type = d.get("extra_type")
        is_legal = bool(d.get("is_legal", True))
        is_batter_boundary = bool(d.get("is_batter_boundary", False))
        boundary_type = d.get("boundary_type")

        new_runs = prev_runs + batter_runs
        state["runs"] = new_runs

        # Legal balls faced by batter: legal deliveries and no-balls count; wides do not
        if is_legal or extra_type == "no_ball":
            state["balls"] += 1

        if is_batter_boundary:
            if boundary_type == 4 or (not boundary_type and batter_runs == 4):
                state["fours"] += 1
            elif boundary_type == 6 or (not boundary_type and batter_runs == 6):
                state["sixes"] += 1

        for threshold in SORTED_THRESHOLDS:
            if prev_runs < threshold <= new_runs and threshold not in state["crossed"]:
                state["crossed"].add(threshold)
                computed_milestones.append(
                    {
                        "player_id": striker_id,
                        "delivery_id": str(d["id"]),
                        "threshold": threshold,
                        "milestone_type": MILESTONE_THRESHOLDS[threshold],
                        "batter_score": new_runs,
                        "balls_faced": state["balls"],
                        "fours_count": state["fours"],
                        "sixes_count": state["sixes"],
                        "over_display": d.get("display_over"),
                        "bowler_id": str(d["bowler_id"]) if d.get("bowler_id") else None,
                        "boundary_type": boundary_type if is_batter_boundary else None,
                        "sequence_no": int(d.get("sequence_no", 0)),
                    }
                )

    return computed_milestones


async def _fetch_context_metadata(
    db: InsForgeClient,
    innings: Dict[str, Any],
    player_ids: List[str],
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Fetch match, team names, and player display names for rich milestone metadata."""
    match_id = str(innings["match_id"])
    match = await db.select_one("matches", {"id": f"eq.{match_id}"}) or {}
    batting_team = await db.select_one("teams", {"id": f"eq.{innings['batting_team_id']}"}) or {}
    bowling_team = await db.select_one("teams", {"id": f"eq.{innings['bowling_team_id']}"}) or {}

    players_map: Dict[str, str] = {}
    for pid in set(player_ids):
        if not pid:
            continue
        p = await db.select_one("players", {"id": f"eq.{pid}"})
        if p:
            players_map[pid] = p.get("display_name") or p.get("full_name") or "Batter"

    innings_context = {
        "match_title": match.get("title") or "Match",
        "format": match.get("format") or "T20",
        "innings_number": int(innings.get("innings_number", 1)),
        "batting_team_name": batting_team.get("name") or "Batting Team",
        "bowling_team_name": bowling_team.get("name") or "Bowling Team",
    }
    return innings_context, players_map


async def recalculate_innings_milestones(
    db: InsForgeClient,
    innings_id: str,
    token: str,
    reason: str = "Score correction / recalculation",
) -> List[Dict[str, Any]]:
    """
    Recomputes all milestones for an innings from canonical non-voided deliveries
    and synchronizes the `player_milestones` table:
    - Invalidates any existing valid milestone that is no longer crossed or crossed on a different delivery.
    - Updates existing valid milestone if score/balls changed on the same delivery.
    - Creates new valid milestone rows for newly crossed thresholds.
    """
    innings = await db.select_one("innings", {"id": f"eq.{innings_id}"})
    if not innings:
        return []

    match_id = str(innings["match_id"])
    deliveries = await db.select(
        "deliveries",
        filters={"innings_id": f"eq.{innings_id}"},
        order="sequence_no.asc",
    )

    computed = compute_innings_milestones(deliveries)
    expected_by_key: Dict[Tuple[str, int], Dict[str, Any]] = {
        (m["player_id"], int(m["threshold"])): m for m in computed
    }

    # Fetch existing valid milestones in DB for this innings
    try:
        existing_valid = await db.select(
            "player_milestones",
            filters={"innings_id": f"eq.{innings_id}", "is_valid": "eq.true"},
        )
    except Exception as exc:
        logger.warning("Could not query player_milestones for innings %s: %s", innings_id, exc)
        return []

    existing_by_key: Dict[Tuple[str, int], Dict[str, Any]] = {
        (str(row["player_id"]), int(row["threshold"])): row for row in existing_valid
    }

    # Collect player IDs needed for metadata
    all_pids: List[str] = []
    for m in computed:
        all_pids.append(m["player_id"])
        if m.get("bowler_id"):
            all_pids.append(m["bowler_id"])

    innings_context, players_map = await _fetch_context_metadata(db, innings, all_pids)
    now_iso = datetime.now(timezone.utc).isoformat()

    # 1. Check existing valid milestones: invalidate if removed or delivery_id changed
    for key, row in list(existing_by_key.items()):
        expected = expected_by_key.get(key)
        if expected is None or str(row["delivery_id"]) != str(expected["delivery_id"]):
            await db.update_as_user(
                "player_milestones",
                {"id": f"eq.{row['id']}"},
                {
                    "is_valid": False,
                    "invalidated_reason": reason,
                    "updated_at": now_iso,
                },
                token,
            )
            existing_by_key.pop(key, None)

    # 2. Insert or update expected valid milestones
    active_rows: List[Dict[str, Any]] = []
    for key, expected in expected_by_key.items():
        player_id = expected["player_id"]
        bowler_id = expected.get("bowler_id")
        metadata = {
            **innings_context,
            "player_name": players_map.get(player_id, "Batter"),
            "bowler_name": players_map.get(bowler_id, "Bowler") if bowler_id else None,
            "boundary_type": expected.get("boundary_type"),
            "strike_rate": round((expected["batter_score"] / expected["balls_faced"]) * 100, 2)
            if expected["balls_faced"] > 0
            else 0.0,
        }

        if key in existing_by_key:
            row = existing_by_key[key]
            # Check if score or stats changed due to an earlier delivery edit
            needs_update = (
                int(row.get("batter_score", 0)) != int(expected["batter_score"])
                or int(row.get("balls_faced", 0)) != int(expected["balls_faced"])
                or int(row.get("fours_count", 0)) != int(expected["fours_count"])
                or int(row.get("sixes_count", 0)) != int(expected["sixes_count"])
                or row.get("over_display") != expected.get("over_display")
            )
            if needs_update:
                updated = await db.update_as_user(
                    "player_milestones",
                    {"id": f"eq.{row['id']}"},
                    {
                        "batter_score": expected["batter_score"],
                        "balls_faced": expected["balls_faced"],
                        "fours_count": expected["fours_count"],
                        "sixes_count": expected["sixes_count"],
                        "over_display": expected["over_display"],
                        "metadata": metadata,
                        "updated_at": now_iso,
                    },
                    token,
                )
                active_rows.append(updated[0] if updated else row)
            else:
                active_rows.append(row)
        else:
            payload = {
                "match_id": match_id,
                "innings_id": innings_id,
                "player_id": player_id,
                "delivery_id": expected["delivery_id"],
                "threshold": expected["threshold"],
                "milestone_type": expected["milestone_type"],
                "batter_score": expected["batter_score"],
                "balls_faced": expected["balls_faced"],
                "fours_count": expected["fours_count"],
                "sixes_count": expected["sixes_count"],
                "over_display": expected["over_display"],
                "is_valid": True,
                "animation_version": 1,
                "metadata": metadata,
            }
            inserted = await db.insert_as_user("player_milestones", [payload], token)
            if inserted:
                active_rows.append(inserted[0])

    return await enrich_milestones_with_highlights(db, active_rows)


async def enrich_milestones_with_highlights(
    db: InsForgeClient, milestones: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Attach associated video highlight clip status & URLs (`highlight_id`, `highlight_status`,
    `highlight_video_url`, `highlight_thumbnail_url`) to each milestone record.
    Never returns a dead link; explicitly reports 'unavailable', 'pending', 'processing', 'failed', or 'ready'.
    """
    if not milestones:
        return []

    enriched: List[Dict[str, Any]] = []
    for m in milestones:
        item = dict(m)
        delivery_id = str(item["delivery_id"])
        player_id = str(item["player_id"])

        # Ensure player_name is present in metadata
        meta = dict(item.get("metadata") or {})
        if not meta.get("player_name"):
            player = await db.select_one("players", {"id": f"eq.{player_id}"})
            if player:
                meta["player_name"] = player.get("display_name") or player.get("full_name") or "Batter"
        item["metadata"] = meta

        # Check player_highlights for this delivery
        hl = await db.select_one("player_highlights", {"delivery_id": f"eq.{delivery_id}"})
        if hl:
            item["highlight_id"] = hl.get("id")
            hl_status = hl.get("status") or "pending"
            if hl_status == "ready" and hl.get("video_url"):
                item["highlight_status"] = "ready"
                item["highlight_video_url"] = hl.get("video_url")
                item["highlight_thumbnail_url"] = hl.get("thumbnail_url")
            elif hl_status in ("pending", "processing", "failed"):
                item["highlight_status"] = hl_status
                item["highlight_video_url"] = None
                item["highlight_thumbnail_url"] = hl.get("thumbnail_url")
            else:
                item["highlight_status"] = "unavailable"
                item["highlight_video_url"] = None
                item["highlight_thumbnail_url"] = None
        else:
            item["highlight_id"] = None
            item["highlight_status"] = "unavailable"
            item["highlight_video_url"] = None
            item["highlight_thumbnail_url"] = None

        enriched.append(item)

    return enriched


async def get_match_milestones(
    db: InsForgeClient, match_id: str, include_invalid: bool = False
) -> List[Dict[str, Any]]:
    filters: Dict[str, str] = {"match_id": f"eq.{match_id}"}
    if not include_invalid:
        filters["is_valid"] = "eq.true"
    rows = await db.select("player_milestones", filters=filters, order="created_at.asc")
    return await enrich_milestones_with_highlights(db, rows)


async def get_innings_milestones(
    db: InsForgeClient, innings_id: str, include_invalid: bool = False
) -> List[Dict[str, Any]]:
    filters: Dict[str, str] = {"innings_id": f"eq.{innings_id}"}
    if not include_invalid:
        filters["is_valid"] = "eq.true"
    rows = await db.select("player_milestones", filters=filters, order="created_at.asc")
    return await enrich_milestones_with_highlights(db, rows)


async def get_player_milestones(db: InsForgeClient, player_id: str) -> Dict[str, Any]:
    player = await db.select_one("players", {"id": f"eq.{player_id}"})
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")

    rows = await db.select(
        "player_milestones",
        filters={"player_id": f"eq.{player_id}", "is_valid": "eq.true"},
        order="created_at.desc",
    )
    enriched = await enrich_milestones_with_highlights(db, rows)
    fifties = sum(1 for r in enriched if int(r.get("threshold", 0)) == 50)
    centuries = sum(1 for r in enriched if int(r.get("threshold", 0)) == 100)
    one_fifties = sum(1 for r in enriched if int(r.get("threshold", 0)) == 150)
    double_centuries = sum(1 for r in enriched if int(r.get("threshold", 0)) == 200)

    return {
        "player_id": player["id"],
        "player_name": player.get("display_name") or player.get("full_name") or "Player",
        "total_milestones": len(enriched),
        "fifties_count": fifties,
        "centuries_count": centuries,
        "one_fifties_count": one_fifties,
        "double_centuries_count": double_centuries,
        "milestones": enriched,
    }


async def get_milestone_by_id(db: InsForgeClient, milestone_id: str) -> Dict[str, Any]:
    row = await db.select_one("player_milestones", {"id": f"eq.{milestone_id}"})
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Milestone not found")
    enriched = await enrich_milestones_with_highlights(db, [row])
    return enriched[0]
