"""
Scoring service — orchestrates delivery logging, innings lifecycle,
idempotency, voiding/corrections, and scorecard reconstruction.
"""
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.core.database import InsForgeClient
from app.core.logging import get_logger
from app.schemas.scoring import (
    DeliveryCreate,
    DeliveryUpdate,
    DeliveryVoidRequest,
    InningsScorecard,
    InningsStartRequest,
    InningsUpdateRequest,
    MatchScorecard,
)
from app.services.scoring_engine import (
    calculate_innings_scorecard,
    compute_match_result,
    determine_next_delivery_state,
    evaluate_delivery_legality_and_runs,
)

logger = get_logger(__name__)


async def _get_players_map(db: InsForgeClient, player_ids: List[str]) -> Dict[str, str]:
    """Fetch display names for a list of player UUIDs."""
    if not player_ids:
        return {}
    distinct_ids = list(set(player_ids))
    players_map = {}
    for p_id in distinct_ids:
        p = await db.select_one("players", {"id": f"eq.{p_id}"})
        if p:
            players_map[p_id] = p.get("display_name") or p.get("full_name") or "Unknown"
    return players_map


async def _get_batting_positions(
    db: InsForgeClient, match_id: str, team_id: str
) -> Dict[str, int]:
    """Get batting positions from confirmed Playing XI."""
    rows = await db.select(
        "playing_xi",
        filters={"match_id": f"eq.{match_id}", "team_id": f"eq.{team_id}"},
    )
    positions = {}
    for r in rows:
        if r.get("batting_position"):
            positions[str(r["player_id"])] = int(r["batting_position"])
    return positions


async def start_innings(
    db: InsForgeClient,
    match_id: str,
    data: InningsStartRequest,
    token: str,
) -> Dict[str, Any]:
    # 1. Verify match exists
    match = await db.select_one("matches", {"id": f"eq.{match_id}"})
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

    if match.get("status") == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Match is already completed"
        )

    # 2. Check if innings already exists
    existing = await db.select_one(
        "innings",
        {"match_id": f"eq.{match_id}", "innings_number": f"eq.{data.innings_number}"},
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Innings {data.innings_number} has already been started",
        )

    # 3. Calculate target for 2nd innings if not provided
    target_runs = data.target_runs
    if data.innings_number == 2 and target_runs is None:
        inn1 = await db.select_one(
            "innings",
            {"match_id": f"eq.{match_id}", "innings_number": "eq.1"},
        )
        if inn1:
            target_runs = inn1.get("total_runs", 0) + 1

    # 4. Insert innings
    innings_payload = {
        "match_id": match_id,
        "innings_number": data.innings_number,
        "batting_team_id": str(data.batting_team_id),
        "bowling_team_id": str(data.bowling_team_id),
        "current_striker_id": str(data.opening_striker_id),
        "current_non_striker_id": str(data.opening_non_striker_id),
        "current_bowler_id": str(data.opening_bowler_id),
        "target_runs": target_runs,
        "total_runs": 0,
        "total_wickets": 0,
        "total_legal_balls": 0,
        "status": "in_progress",
    }
    inserted = await db.insert_as_user("innings", [innings_payload], token)

    # Update match status to live if upcoming
    if match.get("status") == "upcoming":
        await db.update_as_user(
            "matches", {"id": f"eq.{match_id}"}, {"status": "live"}, token
        )

    return inserted[0]


async def get_innings(db: InsForgeClient, innings_id: str) -> Dict[str, Any]:
    innings = await db.select_one("innings", {"id": f"eq.{innings_id}"})
    if not innings:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Innings not found")
    return innings


async def list_innings_for_match(
    db: InsForgeClient, match_id: str
) -> List[Dict[str, Any]]:
    return await db.select(
        "innings",
        filters={"match_id": f"eq.{match_id}"},
        order="innings_number.asc",
    )


async def update_innings_state(
    db: InsForgeClient,
    innings_id: str,
    data: InningsUpdateRequest,
    token: str,
) -> Dict[str, Any]:
    payload = {k: str(v) if isinstance(v, UUID) else v for k, v in data.model_dump().items() if v is not None}
    if not payload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")
    updated = await db.update_as_user("innings", {"id": f"eq.{innings_id}"}, payload, token)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Innings not found")
    return updated[0]


async def record_delivery(
    db: InsForgeClient,
    innings_id: str,
    data: DeliveryCreate,
    token: str,
) -> Dict[str, Any]:
    """
    Records a canonical ball-by-ball delivery.
    Enforces idempotency, calculates over display, updates live innings state.
    """
    innings = await get_innings(db, innings_id)
    if innings.get("status") == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot record delivery on a completed innings",
        )

    match_id = str(innings["match_id"])
    match = await db.select_one("matches", {"id": f"eq.{match_id}"})

    # 1. Idempotency check
    if data.idempotency_key:
        existing = await db.select_one(
            "deliveries",
            {
                "innings_id": f"eq.{innings_id}",
                "idempotency_key": f"eq.{data.idempotency_key}",
            },
        )
        if existing:
            logger.info("Idempotent delivery request matched: %s", data.idempotency_key)
            return existing

    # 2. Get existing deliveries to compute sequence and current legal balls
    existing_deliveries = await db.select(
        "deliveries",
        filters={"innings_id": f"eq.{innings_id}"},
        order="sequence_no.asc",
    )
    sequence_no = len(existing_deliveries) + 1
    legal_balls_so_far = sum(
        1 for d in existing_deliveries if d.get("is_legal") and not d.get("is_voided")
    )

    # 3. Evaluate delivery
    is_legal, total_runs = evaluate_delivery_legality_and_runs(
        batter_runs=data.batter_runs,
        extra_type=data.extra_type,
        extra_runs=data.extra_runs,
    )

    if is_legal:
        cur_legal_ball = legal_balls_so_far + 1
        over_no = (cur_legal_ball - 1) // 6
        ball_in_over = ((cur_legal_ball - 1) % 6) + 1
        display_over = f"{over_no}.{ball_in_over}"
    else:
        over_no = legal_balls_so_far // 6
        ball_in_over = legal_balls_so_far % 6
        suffix = "wd" if data.extra_type == "wide" else "nb"
        display_over = f"{over_no}.{ball_in_over} ({suffix})"

    # 4. Next state calculation
    next_striker, next_non_striker, next_bowler, over_completed = determine_next_delivery_state(
        current_striker_id=data.striker_id,
        current_non_striker_id=data.non_striker_id,
        current_bowler_id=data.bowler_id,
        legal_balls_in_innings=legal_balls_so_far,
        batter_runs=data.batter_runs,
        extra_type=data.extra_type,
        extra_runs=data.extra_runs,
        is_boundary=data.is_boundary,
        is_wicket=data.is_wicket,
        wicket_type=data.wicket_type,
        dismissed_player_id=data.dismissed_player_id,
        runs_completed_before_out=data.runs_completed_before_out,
        next_striker_id=data.next_striker_id,
        next_non_striker_id=data.next_non_striker_id,
    )

    # 5. Insert delivery record
    delivery_row = {
        "innings_id": innings_id,
        "match_id": match_id,
        "sequence_no": sequence_no,
        "over_no": over_no,
        "ball_in_over": ball_in_over,
        "display_over": display_over,
        "striker_id": str(data.striker_id),
        "non_striker_id": str(data.non_striker_id),
        "bowler_id": str(data.bowler_id),
        "batter_runs": data.batter_runs,
        "extra_type": data.extra_type,
        "extra_runs": data.extra_runs,
        "total_runs": total_runs,
        "is_legal": is_legal,
        "is_boundary": data.is_boundary,
        "boundary_type": data.boundary_type,
        "is_batter_boundary": data.is_batter_boundary,
        "is_wicket": data.is_wicket,
        "wicket_type": data.wicket_type,
        "dismissed_player_id": str(data.dismissed_player_id) if data.dismissed_player_id else None,
        "fielder_id": str(data.fielder_id) if data.fielder_id else None,
        "fielder2_id": str(data.fielder2_id) if data.fielder2_id else None,
        "dismissal_delivery_end": data.dismissal_delivery_end,
        "runs_completed_before_out": data.runs_completed_before_out,
        "next_striker_id": str(next_striker) if next_striker else None,
        "next_non_striker_id": str(next_non_striker) if next_non_striker else None,
        "revision_no": 1,
        "is_voided": False,
        "idempotency_key": data.idempotency_key,
        "audit_metadata": data.audit_metadata or {},
    }

    inserted = await db.insert_as_user("deliveries", [delivery_row], token)
    created_delivery = inserted[0]

    # 6. Update running innings state
    new_total_runs = int(innings["total_runs"]) + total_runs
    new_wickets = int(innings["total_wickets"]) + (1 if data.is_wicket else 0)
    new_legal_balls = legal_balls_so_far + (1 if is_legal else 0)

    innings_update: Dict[str, Any] = {
        "total_runs": new_total_runs,
        "total_wickets": new_wickets,
        "total_legal_balls": new_legal_balls,
        "current_striker_id": str(next_striker) if next_striker else None,
        "current_non_striker_id": str(next_non_striker) if next_non_striker else None,
        "current_bowler_id": str(next_bowler) if next_bowler else None,
    }

    # Track extras in innings
    if data.extra_type == "wide":
        innings_update["total_wides"] = int(innings.get("total_wides", 0)) + data.extra_runs
    elif data.extra_type == "no_ball":
        innings_update["total_no_balls"] = int(innings.get("total_no_balls", 0)) + data.extra_runs
    elif data.extra_type == "bye":
        innings_update["total_byes"] = int(innings.get("total_byes", 0)) + data.extra_runs
    elif data.extra_type == "leg_bye":
        innings_update["total_leg_byes"] = int(innings.get("total_leg_byes", 0)) + data.extra_runs
    elif data.extra_type == "penalty":
        innings_update["total_penalty_runs"] = int(innings.get("total_penalty_runs", 0)) + data.extra_runs

    # Innings termination checks
    overs_limit = match.get("overs_per_innings") if match else None
    target_runs = innings.get("target_runs")

    if new_wickets >= 10:
        innings_update["status"] = "completed"
        innings_update["completed_reason"] = "all_out"
    elif overs_limit and new_legal_balls >= (overs_limit * 6):
        innings_update["status"] = "completed"
        innings_update["completed_reason"] = "overs_completed"
    elif target_runs and new_total_runs >= target_runs:
        innings_update["status"] = "completed"
        innings_update["completed_reason"] = "target_reached"

    await db.update_as_user("innings", {"id": f"eq.{innings_id}"}, innings_update, token)

    # If 2nd innings completed, mark match completed
    if innings.get("innings_number") == 2 and innings_update.get("status") == "completed":
        await db.update_as_user("matches", {"id": f"eq.{match_id}"}, {"status": "completed"}, token)

    # Automatic highlight trigger: if delivery qualifies and has a linked marker
    if created_delivery.get("is_batter_boundary") and created_delivery.get("boundary_type") in (4, 6):
        try:
            markers = await db.select(
                "event_markers",
                filters={"delivery_id": f"eq.{created_delivery['id']}", "status": "neq.ignored"},
                limit=1,
            )
            if markers:
                from app.services.highlights import create_or_get_highlight_job
                import asyncio
                asyncio.create_task(
                    create_or_get_highlight_job(
                        db,
                        str(created_delivery["id"]),
                        token,
                        marker_id=str(markers[0]["id"]),
                    )
                )
        except Exception as hl_err:
            logger.warning("Could not auto-trigger highlight on delivery: %s", hl_err)

    # Automatic milestone evaluation & persistence (Phase 5)
    if int(created_delivery.get("batter_runs", 0)) > 0:
        try:
            from app.services.milestones import recalculate_innings_milestones
            await recalculate_innings_milestones(
                db=db,
                innings_id=innings_id,
                token=token,
                reason="Delivery recorded",
            )
        except Exception as ms_err:
            logger.warning("Could not evaluate milestones on delivery: %s", ms_err)

    return created_delivery



async def _resync_innings_from_deliveries(
    db: InsForgeClient, innings_id: str, token: str
) -> None:
    """Deterministic recomputation and synchronization of innings state and milestones from active deliveries."""
    innings = await get_innings(db, innings_id)
    deliveries = await db.select(
        "deliveries",
        filters={"innings_id": f"eq.{innings_id}"},
        order="sequence_no.asc",
    )
    active = [d for d in deliveries if not d.get("is_voided")]

    total_runs = sum(int(d.get("total_runs", 0)) for d in active)
    total_wickets = sum(1 for d in active if d.get("is_wicket"))
    total_legal_balls = sum(1 for d in active if d.get("is_legal"))

    wides = sum(int(d.get("extra_runs", 0)) for d in active if d.get("extra_type") == "wide")
    no_balls = sum(int(d.get("extra_runs", 0)) for d in active if d.get("extra_type") == "no_ball")
    byes = sum(int(d.get("extra_runs", 0)) for d in active if d.get("extra_type") == "bye")
    leg_byes = sum(int(d.get("extra_runs", 0)) for d in active if d.get("extra_type") == "leg_bye")
    penalty = sum(int(d.get("extra_runs", 0)) for d in active if d.get("extra_type") == "penalty")

    # Last active delivery state
    last_d = active[-1] if active else None
    current_striker = last_d.get("next_striker_id") if last_d else innings.get("current_striker_id")
    current_non_striker = last_d.get("next_non_striker_id") if last_d else innings.get("current_non_striker_id")

    payload = {
        "total_runs": total_runs,
        "total_wickets": total_wickets,
        "total_legal_balls": total_legal_balls,
        "total_wides": wides,
        "total_no_balls": no_balls,
        "total_byes": byes,
        "total_leg_byes": leg_byes,
        "total_penalty_runs": penalty,
        "current_striker_id": current_striker,
        "current_non_striker_id": current_non_striker,
    }
    await db.update_as_user("innings", {"id": f"eq.{innings_id}"}, payload, token)

    # Recalculate and invalidate/update milestones after score correction or void (Phase 5)
    try:
        from app.services.milestones import recalculate_innings_milestones
        await recalculate_innings_milestones(
            db=db,
            innings_id=innings_id,
            token=token,
            reason="Score correction / voided delivery",
        )
    except Exception as ms_err:
        logger.warning("Could not recalculate milestones after resync: %s", ms_err)


async def void_delivery(
    db: InsForgeClient,
    delivery_id: str,
    data: DeliveryVoidRequest,
    token: str,
) -> Dict[str, Any]:
    """Void a delivery and safely resync all dependent innings stats."""
    d = await db.select_one("deliveries", {"id": f"eq.{delivery_id}"})
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery not found")

    if d.get("is_voided"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Delivery is already voided"
        )

    updated_rows = await db.update_as_user(
        "deliveries",
        {"id": f"eq.{delivery_id}"},
        {
            "is_voided": True,
            "voided_reason": data.reason,
            "revision_no": int(d.get("revision_no", 1)) + 1,
        },
        token,
    )
    innings_id = str(d["innings_id"])
    await _resync_innings_from_deliveries(db, innings_id, token)
    return updated_rows[0]


async def update_delivery(
    db: InsForgeClient,
    delivery_id: str,
    data: DeliveryUpdate,
    token: str,
) -> Dict[str, Any]:
    """Edit delivery fields with version increment and scorecard resync."""
    d = await db.select_one("deliveries", {"id": f"eq.{delivery_id}"})
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery not found")

    update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
    if "correction_reason" in update_dict:
        reason = update_dict.pop("correction_reason")
        audit = d.get("audit_metadata") or {}
        audit["last_correction_reason"] = reason
        update_dict["audit_metadata"] = audit

    # Recompute legality and total runs if batter_runs or extra_runs changed
    b_runs = update_dict.get("batter_runs", d["batter_runs"])
    e_type = update_dict.get("extra_type", d["extra_type"])
    e_runs = update_dict.get("extra_runs", d["extra_runs"])

    is_legal, total_runs = evaluate_delivery_legality_and_runs(b_runs, e_type, e_runs)
    update_dict["is_legal"] = is_legal
    update_dict["total_runs"] = total_runs
    update_dict["revision_no"] = int(d.get("revision_no", 1)) + 1

    updated_rows = await db.update_as_user(
        "deliveries", {"id": f"eq.{delivery_id}"}, update_dict, token
    )
    innings_id = str(d["innings_id"])
    await _resync_innings_from_deliveries(db, innings_id, token)
    return updated_rows[0]


async def get_scorecard(db: InsForgeClient, innings_id: str) -> InningsScorecard:
    """Build full deterministic scorecard for an innings, preserving historical team and player snapshots."""
    innings = await get_innings(db, innings_id)
    match_id = str(innings["match_id"])
    match = await db.select_one("matches", {"id": f"eq.{match_id}"})

    # Prefer historical snapshot from match_teams so renaming a team later does not rewrite past scorecards
    match_team_rows = await db.select("match_teams", filters={"match_id": f"eq.{match_id}"})
    mt_name_map = {str(r["team_id"]): r.get("team_name") for r in match_team_rows if r.get("team_name")}

    bat_tid = str(innings["batting_team_id"])
    bowl_tid = str(innings["bowling_team_id"])

    if bat_tid in mt_name_map:
        innings["batting_team_name"] = mt_name_map[bat_tid]
    else:
        batting_team = await db.select_one("teams", {"id": f"eq.{bat_tid}"})
        innings["batting_team_name"] = batting_team.get("name") if batting_team else "Batting Team"

    if bowl_tid in mt_name_map:
        innings["bowling_team_name"] = mt_name_map[bowl_tid]
    else:
        bowling_team = await db.select_one("teams", {"id": f"eq.{bowl_tid}"})
        innings["bowling_team_name"] = bowling_team.get("name") if bowling_team else "Bowling Team"

    deliveries = await db.select(
        "deliveries",
        filters={"innings_id": f"eq.{innings_id}"},
        order="sequence_no.asc",
    )

    # Collect player IDs for names lookup
    player_ids = set()
    for f in ("current_striker_id", "current_non_striker_id", "current_bowler_id"):
        if innings.get(f):
            player_ids.add(str(innings[f]))

    for d in deliveries:
        for f in ("striker_id", "non_striker_id", "bowler_id", "dismissed_player_id", "fielder_id"):
            if d.get(f):
                player_ids.add(str(d[f]))

    # Prefer historical player_name snapshots from playing_xi for this match
    xi_rows = await db.select("playing_xi", filters={"match_id": f"eq.{match_id}"})
    snapshot_players_map = {
        str(r["player_id"]): r.get("player_name")
        for r in xi_rows
        if r.get("player_id") and r.get("player_name")
    }

    missing_pids = [pid for pid in player_ids if pid not in snapshot_players_map]
    live_players_map = await _get_players_map(db, missing_pids)
    players_map = {**live_players_map, **snapshot_players_map}

    batting_positions = await _get_batting_positions(
        db, match_id, str(innings["batting_team_id"])
    )

    return calculate_innings_scorecard(
        innings=innings,
        deliveries=deliveries,
        players_map=players_map,
        batting_positions=batting_positions,
        match=match or {},
    )


async def get_match_scorecard(db: InsForgeClient, match_id: str) -> MatchScorecard:
    """Build complete match scorecard across all innings with result."""
    match = await db.select_one("matches", {"id": f"eq.{match_id}"})
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

    innings_rows = await list_innings_for_match(db, match_id)
    scorecards = []
    for inn in innings_rows:
        sc = await get_scorecard(db, str(inn["id"]))
        scorecards.append(sc)

    winner_id, result_text = compute_match_result(match, scorecards)

    return MatchScorecard(
        match_id=UUID(match_id),
        title=match["title"],
        format=match["format"],
        status=match["status"],
        overs_per_innings=match.get("overs_per_innings"),
        winner_team_id=winner_id,
        result_text=result_text,
        innings=scorecards,
    )
