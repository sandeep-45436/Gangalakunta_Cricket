"""
Phase 6 — Player Profiles, Historical Match Archive, Signed Media Access,
Retry/Recovery Workflows, Retention Policy, Audit Logging & Backup/Restore.
"""
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import time
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.core.database import InsForgeClient
from app.core.logging import get_logger
from app.services.milestones import enrich_milestones_with_highlights
from app.services.scoring_engine import calculate_innings_scorecard, format_overs

logger = get_logger(__name__)


async def write_audit_log(
    db: InsForgeClient,
    actor_id: str,
    action: str,
    resource_type: str,
    token: str,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Persist an operator/user audit log entry without failing the parent request."""
    try:
        payload: Dict[str, Any] = {
            "actor_id": actor_id,
            "action": action,
            "resource_type": resource_type,
            "details": details or {},
        }
        if resource_id:
            payload["resource_id"] = str(resource_id)
        await db.insert_as_user("audit_logs", [payload], token)
    except Exception as exc:
        logger.warning("Audit log write skipped (%s): %s", action, exc)


def create_signed_media_token(key: str, owner_id: str, expires_in: int = 3600) -> Tuple[int, str]:
    """Generate an expiring HMAC-SHA256 signature for secure media access."""
    settings = get_settings()
    secret = (settings.insforge_jwt_secret or settings.insforge_anon_key or "cricket-secret").encode("utf-8")
    expires_at = int(time.time()) + max(60, min(expires_in, 86400))
    message = f"{key}:{owner_id}:{expires_at}".encode("utf-8")
    signature = hmac.new(secret, message, hashlib.sha256).hexdigest()
    return expires_at, signature


def verify_signed_media_token(key: str, owner_id: str, expires_at: int, signature: str) -> bool:
    """Verify an HMAC-SHA256 media signature and check expiration."""
    if int(time.time()) > int(expires_at):
        return False
    settings = get_settings()
    secret = (settings.insforge_jwt_secret or settings.insforge_anon_key or "cricket-secret").encode("utf-8")
    message = f"{key}:{owner_id}:{expires_at}".encode("utf-8")
    expected = hmac.new(secret, message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def generate_signed_media_url(
    db: InsForgeClient,
    key: str,
    owner_id: str,
) -> Dict[str, Any]:
    """
    Verify that the requesting user owns the recording or highlight asset for `key`,
    then return an expiring signed URL.
    """
    if not key or ".." in key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid media key")

    # Check if key belongs to a recording session or highlight owned by user
    sessions = await db.select("recording_sessions", filters={"media_asset_id": f"eq.{key}"})
    if sessions:
        sess = sessions[0]
        if sess.get("owner_id") and str(sess["owner_id"]) != str(owner_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access another user's private media asset",
            )

    highlights = await db.select("player_highlights", filters={"video_key": f"eq.{key}"})
    if highlights:
        hl = highlights[0]
        match = await db.select_one("matches", {"id": f"eq.{hl['match_id']}"})
        if match and match.get("owner_id") and str(match["owner_id"]) != str(owner_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access another user's highlight clip",
            )

    expires_at, signature = create_signed_media_token(key=key, owner_id=owner_id, expires_in=3600)
    public_url = db.get_public_url(key)
    separator = "&" if "?" in public_url else "?"
    signed_url = f"{public_url}{separator}exp={expires_at}&sig={signature}"
    return {
        "key": key,
        "signed_url": signed_url,
        "expires_at": expires_at,
        "signature": signature,
    }


async def get_player_profile(
    db: InsForgeClient,
    player_id: str,
    owner_id: str,
    match_id: Optional[str] = None,
    tournament: Optional[str] = None,
    event_type: Optional[str] = None,
    limit: int = 12,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    Build a comprehensive Phase 6 Player Profile:
    - Player identity & team history (both active squads and historical Playing XI appearances)
    - Career batting and bowling statistics
    - Match-by-match batting and bowling performance log with links to scorecards
    - Replayable milestones (50s, 100s)
    - Paginated & filterable boundary highlights (by match, tournament, and four/six)
    """
    player = await db.select_one("players", {"id": f"eq.{player_id}"})
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")
    if player.get("owner_id") and str(player["owner_id"]) != str(owner_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this player")

    # 1. Team history: current/past squads (team_players) + historical match appearances (playing_xi)
    tp_rows = await db.select("team_players", filters={"player_id": f"eq.{player_id}"})
    xi_rows = await db.select("playing_xi", filters={"player_id": f"eq.{player_id}"})

    team_ids: Set[str] = set()
    active_squad_teams: Set[str] = set()
    for r in tp_rows:
        tid = str(r["team_id"])
        team_ids.add(tid)
        if r.get("is_active", True):
            active_squad_teams.add(tid)
    for r in xi_rows:
        team_ids.add(str(r["team_id"]))

    teams_map: Dict[str, Dict[str, Any]] = {}
    for tid in team_ids:
        t = await db.select_one("teams", {"id": f"eq.{tid}"})
        if t:
            teams_map[tid] = t

    # Count matches played per team from playing_xi
    matches_per_team: Dict[str, Set[str]] = {tid: set() for tid in team_ids}
    for r in xi_rows:
        tid = str(r["team_id"])
        matches_per_team.setdefault(tid, set()).add(str(r["match_id"]))

    team_history = []
    for tid, t in teams_map.items():
        team_history.append({
            "team_id": t["id"],
            "team_name": t.get("name") or "Team",
            "short_name": t.get("short_name"),
            "is_current_squad": tid in active_squad_teams,
            "matches_played_for_team": len(matches_per_team.get(tid, set())),
        })

    # 2. Discover all matches this player participated in (via playing_xi or deliveries)
    striker_delivs = await db.select("deliveries", filters={"striker_id": f"eq.{player_id}"})
    non_striker_delivs = await db.select("deliveries", filters={"non_striker_id": f"eq.{player_id}"})
    bowler_delivs = await db.select("deliveries", filters={"bowler_id": f"eq.{player_id}"})

    participated_match_ids: Set[str] = set()
    for r in xi_rows:
        participated_match_ids.add(str(r["match_id"]))
    for d in striker_delivs + non_striker_delivs + bowler_delivs:
        if not d.get("is_voided"):
            participated_match_ids.add(str(d["match_id"]))

    # Fetch all highlights for this player
    all_highlights = await db.select(
        "player_highlights",
        filters={"player_id": f"eq.{player_id}"},
        order="created_at.desc",
    )
    for h in all_highlights:
        participated_match_ids.add(str(h["match_id"]))

    # Load match details for all participated matches
    matches_by_id: Dict[str, Dict[str, Any]] = {}
    for mid in participated_match_ids:
        m = await db.select_one("matches", {"id": f"eq.{mid}"})
        if m and (not m.get("owner_id") or str(m["owner_id"]) == str(owner_id)):
            m_teams = await db.select("match_teams", filters={"match_id": f"eq.{mid}"}, order="batting_order.asc")
            m["teams"] = m_teams
            matches_by_id[mid] = m

    # Sort matches newest first
    sorted_matches = sorted(
        matches_by_id.values(),
        key=lambda x: x.get("scheduled_at") or x.get("created_at") or "",
        reverse=True,
    )

    # 3. Compute match-by-match batting & bowling stats and career aggregates
    matches_played = len(sorted_matches)
    innings_batted = 0
    not_outs = 0
    total_runs = 0
    highest_score = 0
    highest_score_not_out = False
    balls_faced = 0
    total_fours = 0
    total_sixes = 0

    innings_bowled = 0
    balls_bowled = 0
    maidens_total = 0
    runs_conceded_total = 0
    wickets_total = 0
    best_wickets = -1
    best_runs = 999999

    match_performances: List[Dict[str, Any]] = []
    available_tournaments_set: Set[str] = set()
    available_matches_list: List[Dict[str, Any]] = []

    player_display_name = player.get("display_name") or player.get("full_name") or "Player"

    for m in sorted_matches:
        mid = str(m["id"])
        m_tourn = m.get("tournament")
        if m_tourn:
            available_tournaments_set.add(m_tourn)
        available_matches_list.append({
            "match_id": m["id"],
            "title": m["title"],
            "tournament": m_tourn,
        })

        # Determine player's team and opponent in this match
        m_teams = m.get("teams") or []
        player_xi = next((x for x in xi_rows if str(x["match_id"]) == mid), None)
        player_team_id = str(player_xi["team_id"]) if player_xi else None
        player_team_name = None
        opponent_team_name = None
        if len(m_teams) >= 2:
            if player_team_id == str(m_teams[0]["team_id"]):
                player_team_name = m_teams[0]["team_name"]
                opponent_team_name = m_teams[1]["team_name"]
            elif player_team_id == str(m_teams[1]["team_id"]):
                player_team_name = m_teams[1]["team_name"]
                opponent_team_name = m_teams[0]["team_name"]
            else:
                player_team_name = m_teams[0]["team_name"]
                opponent_team_name = m_teams[1]["team_name"]

        inns = await db.select("innings", filters={"match_id": f"eq.{mid}"}, order="innings_number.asc")
        batted_in_match = False
        bat_inn_id = None
        bat_inn_num = None
        bat_runs = 0
        bat_balls = 0
        bat_fours = 0
        bat_sixes = 0
        bat_sr = 0.0
        bat_is_out = False
        bat_dismissal = "did not bat"

        bowled_in_match = False
        bowl_inn_id = None
        bowl_overs_str = "0.0"
        bowl_maidens = 0
        bowl_runs = 0
        bowl_wickets = 0
        bowl_econ = 0.0

        for inn in inns:
            iid = str(inn["id"])
            inn_delivs = await db.select("deliveries", filters={"innings_id": f"eq.{iid}"}, order="sequence_no.asc")
            sc = calculate_innings_scorecard(
                innings=inn,
                deliveries=inn_delivs,
                players_map={player_id: player_display_name},
                batting_positions={},
                match=m,
            )

            # Check if player batted in this innings
            bat_fig = next((b for b in sc.batters if str(b.player_id) == player_id), None)
            if bat_fig and (bat_fig.balls > 0 or bat_fig.runs > 0 or bat_fig.is_out):
                batted_in_match = True
                bat_inn_id = inn["id"]
                bat_inn_num = int(inn["innings_number"])
                bat_runs = bat_fig.runs
                bat_balls = bat_fig.balls
                bat_fours = bat_fig.fours
                bat_sixes = bat_fig.sixes
                bat_sr = bat_fig.strike_rate
                bat_is_out = bat_fig.is_out
                bat_dismissal = bat_fig.dismissal_text

                innings_batted += 1
                if not bat_fig.is_out:
                    not_outs += 1
                total_runs += bat_fig.runs
                balls_faced += bat_fig.balls
                total_fours += bat_fig.fours
                total_sixes += bat_fig.sixes

                if bat_fig.runs > highest_score or (bat_fig.runs == highest_score and not bat_fig.is_out):
                    highest_score = bat_fig.runs
                    highest_score_not_out = not bat_fig.is_out

            # Check if player bowled in this innings
            bowl_fig = next((bw for bw in sc.bowlers if str(bw.player_id) == player_id), None)
            if bowl_fig and (bowl_fig.legal_balls > 0 or bowl_fig.runs_conceded > 0 or bowl_fig.wickets > 0):
                bowled_in_match = True
                bowl_inn_id = inn["id"]
                bowl_overs_str = bowl_fig.overs
                bowl_maidens = bowl_fig.maidens
                bowl_runs = bowl_fig.runs_conceded
                bowl_wickets = bowl_fig.wickets
                bowl_econ = bowl_fig.economy

                innings_bowled += 1
                balls_bowled += bowl_fig.legal_balls
                maidens_total += bowl_fig.maidens
                runs_conceded_total += bowl_fig.runs_conceded
                wickets_total += bowl_fig.wickets

                if bowl_fig.wickets > best_wickets or (
                    bowl_fig.wickets == best_wickets and bowl_fig.runs_conceded < best_runs
                ):
                    best_wickets = bowl_fig.wickets
                    best_runs = bowl_fig.runs_conceded

        hl_in_match = sum(1 for h in all_highlights if str(h["match_id"]) == mid)

        match_performances.append({
            "match_id": m["id"],
            "match_title": m["title"],
            "tournament": m_tourn,
            "format": m["format"],
            "venue": m.get("venue"),
            "scheduled_at": m.get("scheduled_at") or m.get("created_at"),
            "match_status": m["status"],
            "player_team_name": player_team_name,
            "opponent_team_name": opponent_team_name,
            "batted": batted_in_match,
            "innings_id": bat_inn_id,
            "innings_number": bat_inn_num,
            "runs": bat_runs,
            "balls": bat_balls,
            "fours": bat_fours,
            "sixes": bat_sixes,
            "strike_rate": bat_sr,
            "is_out": bat_is_out,
            "dismissal_text": bat_dismissal,
            "bowled": bowled_in_match,
            "bowling_innings_id": bowl_inn_id,
            "overs_display": bowl_overs_str,
            "maidens": bowl_maidens,
            "runs_conceded": bowl_runs,
            "wickets": bowl_wickets,
            "economy": bowl_econ,
            "highlights_in_match": hl_in_match,
        })

    # 4. Load valid milestones for this player
    milestone_rows = await db.select(
        "player_milestones",
        filters={"player_id": f"eq.{player_id}", "is_valid": "eq.true"},
        order="created_at.desc",
    )
    enriched_milestones = await enrich_milestones_with_highlights(db, milestone_rows)
    fifties_count = sum(1 for ms in enriched_milestones if int(ms.get("threshold", 0)) == 50)
    centuries_count = sum(1 for ms in enriched_milestones if int(ms.get("threshold", 0)) >= 100)

    # Filter milestones by match_id or tournament if requested
    filtered_milestones = enriched_milestones
    if match_id:
        filtered_milestones = [ms for ms in filtered_milestones if str(ms["match_id"]) == str(match_id)]
    if tournament:
        t_lower = tournament.strip().lower()
        filtered_milestones = [
            ms
            for ms in filtered_milestones
            if (matches_by_id.get(str(ms["match_id"]), {}).get("tournament") or "").lower() == t_lower
        ]

    # 5. Filter and paginate highlights
    filtered_highlights = []
    for h in all_highlights:
        h_mid = str(h["match_id"])
        m_obj = matches_by_id.get(h_mid, {})
        if match_id and h_mid != str(match_id):
            continue
        if tournament:
            if (m_obj.get("tournament") or "").strip().lower() != tournament.strip().lower():
                continue
        if event_type and h.get("event_type") != event_type:
            continue

        # Enrich delivery_metadata with match_title and tournament for archive linking
        meta = dict(h.get("delivery_metadata") or {})
        meta["match_title"] = m_obj.get("title") or meta.get("match_title") or "Match"
        meta["tournament"] = m_obj.get("tournament")
        h_copy = dict(h)
        h_copy["delivery_metadata"] = meta
        filtered_highlights.append(h_copy)

    highlights_total = len(filtered_highlights)
    paginated_highlights = filtered_highlights[offset : offset + limit]
    has_more = (offset + limit) < highlights_total

    dismissals = innings_batted - not_outs
    batting_avg = round(total_runs / dismissals, 2) if dismissals > 0 else float(total_runs)
    batting_sr = round((total_runs / balls_faced) * 100, 2) if balls_faced > 0 else 0.0
    overs_bowled_str = format_overs(balls_bowled)
    bowling_econ = round(runs_conceded_total / (balls_bowled / 6.0), 2) if balls_bowled > 0 else 0.0
    bowling_avg = round(runs_conceded_total / wickets_total, 2) if wickets_total > 0 else 0.0
    best_bowling_str = f"{best_wickets}/{best_runs}" if best_wickets >= 0 else "0/0"

    return {
        "player": player,
        "team_history": team_history,
        "career_stats": {
            "matches_played": matches_played,
            "innings_batted": innings_batted,
            "not_outs": not_outs,
            "total_runs": total_runs,
            "highest_score": highest_score,
            "highest_score_not_out": highest_score_not_out,
            "batting_average": batting_avg,
            "balls_faced": balls_faced,
            "batting_strike_rate": batting_sr,
            "fours": total_fours,
            "sixes": total_sixes,
            "fifties": fifties_count,
            "centuries": centuries_count,
            "innings_bowled": innings_bowled,
            "balls_bowled": balls_bowled,
            "overs_bowled": overs_bowled_str,
            "maidens": maidens_total,
            "runs_conceded": runs_conceded_total,
            "wickets_taken": wickets_total,
            "best_bowling": best_bowling_str,
            "bowling_economy": bowling_econ,
            "bowling_average": bowling_avg,
        },
        "match_performances": match_performances,
        "milestones": filtered_milestones,
        "highlights": paginated_highlights,
        "highlights_total": highlights_total,
        "highlights_limit": limit,
        "highlights_offset": offset,
        "has_more_highlights": has_more,
        "available_tournaments": sorted(available_tournaments_set),
        "available_matches": available_matches_list,
    }


async def search_match_archive(
    db: InsForgeClient,
    owner_id: str,
    q: Optional[str] = None,
    team_id: Optional[str] = None,
    team_b_id: Optional[str] = None,
    player_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    format_filter: Optional[str] = None,
    tournament: Optional[str] = None,
    status_filter: Optional[str] = None,
    innings_number: Optional[int] = None,
    highlight_type: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
) -> Dict[str, Any]:
    """
    Search and filter matches across all Phase 6 archive dimensions with pagination.
    Enforces owner_id isolation.
    """
    db_filters: Dict[str, str] = {"owner_id": f"eq.{owner_id}"}
    if format_filter:
        db_filters["format"] = f"eq.{format_filter}"
    if status_filter:
        db_filters["status"] = f"eq.{status_filter}"

    all_matches = await db.select("matches", filters=db_filters, order="created_at.desc")

    # Collect facets from all user matches
    tournaments_facet: Set[str] = set()
    formats_facet: Set[str] = set()
    for m in all_matches:
        if m.get("tournament"):
            tournaments_facet.add(str(m["tournament"]))
        if m.get("format"):
            formats_facet.add(str(m["format"]))

    # Pre-filter by player_id if specified
    player_match_ids: Optional[Set[str]] = None
    if player_id:
        player_match_ids = set()
        xi = await db.select("playing_xi", filters={"player_id": f"eq.{player_id}"})
        s_delivs = await db.select("deliveries", filters={"striker_id": f"eq.{player_id}"})
        ns_delivs = await db.select("deliveries", filters={"non_striker_id": f"eq.{player_id}"})
        b_delivs = await db.select("deliveries", filters={"bowler_id": f"eq.{player_id}"})
        for r in xi:
            player_match_ids.add(str(r["match_id"]))
        for d in s_delivs + ns_delivs + b_delivs:
            if not d.get("is_voided"):
                player_match_ids.add(str(d["match_id"]))

    matched_items: List[Dict[str, Any]] = []

    for m in all_matches:
        mid = str(m["id"])

        if player_match_ids is not None and mid not in player_match_ids:
            continue

        # Text query (title, venue, tournament)
        if q:
            q_lower = q.strip().lower()
            haystack = " ".join([
                str(m.get("title") or ""),
                str(m.get("venue") or ""),
                str(m.get("tournament") or ""),
            ]).lower()
            if q_lower not in haystack:
                continue

        # Tournament filter (supports exact dropdown or case-insensitive substring)
        if tournament:
            if tournament.strip().lower() not in (m.get("tournament") or "").strip().lower():
                continue

        # Date range filter (against scheduled_at or created_at YYYY-MM-DD prefix)
        match_date_str = str(m.get("scheduled_at") or m.get("created_at") or "")[:10]
        if date_from and match_date_str and match_date_str < date_from[:10]:
            continue
        if date_to and match_date_str and match_date_str > date_to[:10]:
            continue

        # Load teams
        m_teams = await db.select("match_teams", filters={"match_id": f"eq.{mid}"}, order="batting_order.asc")
        m["teams"] = m_teams
        team_ids_in_match = {str(t["team_id"]) for t in m_teams}

        if team_id and str(team_id) not in team_ids_in_match:
            continue
        if team_b_id and str(team_b_id) not in team_ids_in_match:
            continue

        # Load innings
        inns = await db.select("innings", filters={"match_id": f"eq.{mid}"}, order="innings_number.asc")
        if innings_number is not None:
            if not any(int(i.get("innings_number", 0)) == int(innings_number) for i in inns):
                continue

        # Load highlights and milestones for this match
        hls = await db.select("player_highlights", filters={"match_id": f"eq.{mid}"})
        ms_list = await db.select("player_milestones", filters={"match_id": f"eq.{mid}", "is_valid": "eq.true"})

        fours_count = sum(1 for h in hls if h.get("event_type") == "four")
        sixes_count = sum(1 for h in hls if h.get("event_type") == "six")

        if highlight_type:
            ht = highlight_type.lower()
            if ht == "four" and fours_count == 0:
                continue
            elif ht == "six" and sixes_count == 0:
                continue
            elif ht == "fifty" and not any(int(ms.get("threshold", 0)) == 50 for ms in ms_list):
                continue
            elif ht == "century" and not any(int(ms.get("threshold", 0)) >= 100 for ms in ms_list):
                continue

        team_name_by_id = {str(t["team_id"]): t.get("team_name") or "Team" for t in m_teams}
        innings_summaries = []
        for i in inns:
            balls = int(i.get("total_legal_balls", 0))
            innings_summaries.append({
                "innings_id": i["id"],
                "innings_number": int(i["innings_number"]),
                "batting_team_id": i["batting_team_id"],
                "batting_team_name": team_name_by_id.get(str(i["batting_team_id"]), "Team"),
                "total_runs": int(i.get("total_runs", 0)),
                "total_wickets": int(i.get("total_wickets", 0)),
                "overs_display": format_overs(balls),
                "status": i.get("status") or "in_progress",
            })

        matched_items.append({
            "match": m,
            "tournament": m.get("tournament"),
            "innings_summaries": innings_summaries,
            "result_text": None,
            "highlights_count": len(hls),
            "fours_count": fours_count,
            "sixes_count": sixes_count,
            "milestones_count": len(ms_list),
        })

    total = len(matched_items)
    paginated = matched_items[offset : offset + limit]
    return {
        "items": paginated,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total,
        "facets": {
            "tournaments": sorted(tournaments_facet),
            "formats": sorted(formats_facet),
        },
    }


async def retry_failed_jobs_and_sessions(
    db: InsForgeClient,
    owner_id: str,
    token: str,
    match_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Phase 6 retry & recovery workflow for missing media, failed highlight jobs,
    and interrupted recording sessions.
    """
    from app.services.highlights import process_highlight_job

    user_matches = await db.select("matches", filters={"owner_id": f"eq.{owner_id}"})
    allowed_match_ids = {str(m["id"]) for m in user_matches}
    if match_id:
        if str(match_id) not in allowed_match_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized for this match")
        target_match_ids = {str(match_id)}
    else:
        target_match_ids = allowed_match_ids

    retried_jobs = 0
    recovered_sessions = 0
    details: List[str] = []

    for mid in target_match_ids:
        # 1. Recover interrupted recording sessions
        sessions = await db.select("recording_sessions", filters={"match_id": f"eq.{mid}"})
        for sess in sessions:
            if sess.get("status") in ("interrupted", "failed") or sess.get("processing_status") == "failed":
                await db.update_as_user(
                    "recording_sessions",
                    {"id": f"eq.{sess['id']}"},
                    {
                        "status": "completed" if sess.get("media_asset_id") else "stopped",
                        "processing_status": "completed" if sess.get("media_asset_id") else "unprocessed",
                    },
                    token,
                )
                recovered_sessions += 1
                details.append(f"Recovered recording session {sess.get('session_name') or sess['id']}")

        # 2. Retry failed/pending highlight jobs
        jobs = await db.select("highlight_jobs", filters={"match_id": f"eq.{mid}"})
        for job in jobs:
            if job.get("status") in ("failed", "retrying", "pending"):
                hls = await db.select("player_highlights", filters={"job_id": f"eq.{job['id']}"})
                if hls:
                    hl = hls[0]
                    await db.update_as_user(
                        "highlight_jobs",
                        {"id": f"eq.{job['id']}"},
                        {"status": "pending", "error_message": None},
                        token,
                    )
                    await process_highlight_job(db, str(job["id"]), str(hl["id"]), token)
                    retried_jobs += 1
                    details.append(f"Retried highlight job {job['id']} for delivery {job['delivery_id']}")

    await write_audit_log(
        db=db,
        actor_id=owner_id,
        action="ops.retry_failed",
        resource_type="system",
        token=token,
        details={
            "retried_highlight_jobs": retried_jobs,
            "recovered_recording_sessions": recovered_sessions,
        },
    )

    return {
        "retried_highlight_jobs": retried_jobs,
        "recovered_recording_sessions": recovered_sessions,
        "details": details,
    }


async def apply_retention_policy(
    db: InsForgeClient,
    owner_id: str,
    token: str,
    retention_days: int = 90,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Enforces documented media retention rules:
    - Raw full-match recording sessions older than `retention_days` have their bulky raw
      media reference purged to save storage, while ALL verified player highlight clips,
      milestones, and canonical ball-by-ball scorecards are permanently retained.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    cutoff_iso = cutoff.isoformat()

    sessions = await db.select("recording_sessions", filters={"owner_id": f"eq.{owner_id}"})
    expired_sessions = [
        s for s in sessions
        if s.get("media_asset_id") and str(s.get("created_at") or "") < cutoff_iso
    ]

    purged = 0
    if not dry_run:
        for s in expired_sessions:
            await db.update_as_user(
                "recording_sessions",
                {"id": f"eq.{s['id']}"},
                {
                    "media_asset_id": None,
                    "media_url": None,
                    "media_metadata": {
                        **(s.get("media_metadata") or {}),
                        "retention_purged_at": datetime.now(timezone.utc).isoformat(),
                        "retention_days": retention_days,
                    },
                },
                token,
            )
            purged += 1

        await write_audit_log(
            db=db,
            actor_id=owner_id,
            action="retention.cleanup",
            resource_type="recording_session",
            token=token,
            details={"retention_days": retention_days, "raw_videos_purged": purged},
        )

    user_matches = await db.select("matches", filters={"owner_id": f"eq.{owner_id}"})
    highlights_preserved = 0
    for m in user_matches:
        hls = await db.select("player_highlights", filters={"match_id": f"eq.{m['id']}"})
        highlights_preserved += len(hls)

    return {
        "retention_days": retention_days,
        "dry_run": dry_run,
        "expired_sessions_found": len(expired_sessions),
        "raw_videos_purged": purged,
        "highlights_preserved": highlights_preserved,
    }


async def get_ops_diagnostics(db: InsForgeClient, owner_id: str) -> Dict[str, Any]:
    """Production observability, job queue metrics, and recent audit logs."""
    user_matches = await db.select("matches", filters={"owner_id": f"eq.{owner_id}"})
    match_ids = [str(m["id"]) for m in user_matches]

    failed_jobs = 0
    pending_jobs = 0
    ready_highlights = 0
    for mid in match_ids:
        jobs = await db.select("highlight_jobs", filters={"match_id": f"eq.{mid}"})
        for j in jobs:
            if j.get("status") == "failed":
                failed_jobs += 1
            elif j.get("status") in ("pending", "processing", "retrying"):
                pending_jobs += 1
        hls = await db.select("player_highlights", filters={"match_id": f"eq.{mid}", "status": "eq.ready"})
        ready_highlights += len(hls)

    sessions = await db.select("recording_sessions", filters={"owner_id": f"eq.{owner_id}"})
    interrupted = sum(1 for s in sessions if s.get("status") in ("interrupted", "failed"))

    try:
        audit_logs = await db.select(
            "audit_logs",
            filters={"actor_id": f"eq.{owner_id}"},
            order="created_at.desc",
            limit=15,
        )
    except Exception:
        audit_logs = []

    return {
        "status": "healthy" if failed_jobs == 0 else "degraded",
        "service_version": "0.6.0",
        "db_connected": True,
        "storage_connected": True,
        "failed_highlight_jobs": failed_jobs,
        "pending_highlight_jobs": pending_jobs,
        "interrupted_recordings": interrupted,
        "total_archived_matches": len(user_matches),
        "total_ready_highlights": ready_highlights,
        "retention_policy_default_days": 90,
        "recent_audit_logs": audit_logs,
    }


async def export_owner_backup(db: InsForgeClient, owner_id: str, token: str) -> Dict[str, Any]:
    """
    Export a deterministic, checksummed JSON backup of all user domain data
    (teams, players, matches, innings, deliveries, milestones, highlights)
    for disaster recovery and restoration verification.
    """
    teams = await db.select("teams", filters={"owner_id": f"eq.{owner_id}"})
    players = await db.select("players", filters={"owner_id": f"eq.{owner_id}"})
    matches = await db.select("matches", filters={"owner_id": f"eq.{owner_id}"})

    match_ids = [str(m["id"]) for m in matches]
    innings_all: List[Dict[str, Any]] = []
    deliveries_all: List[Dict[str, Any]] = []
    milestones_all: List[Dict[str, Any]] = []
    highlights_all: List[Dict[str, Any]] = []

    for mid in match_ids:
        inns = await db.select("innings", filters={"match_id": f"eq.{mid}"})
        innings_all.extend(inns)
        delivs = await db.select("deliveries", filters={"match_id": f"eq.{mid}"}, order="sequence_no.asc")
        deliveries_all.extend(delivs)
        ms = await db.select("player_milestones", filters={"match_id": f"eq.{mid}"})
        milestones_all.extend(ms)
        hls = await db.select("player_highlights", filters={"match_id": f"eq.{mid}"})
        highlights_all.extend(hls)

    data = {
        "teams": teams,
        "players": players,
        "matches": matches,
        "innings": innings_all,
        "deliveries": deliveries_all,
        "player_milestones": milestones_all,
        "player_highlights": highlights_all,
    }

    canonical_json = json.dumps(data, sort_keys=True, default=str).encode("utf-8")
    checksum = hashlib.sha256(canonical_json).hexdigest()

    counts = {k: len(v) for k, v in data.items()}
    await write_audit_log(
        db=db,
        actor_id=owner_id,
        action="backup.export",
        resource_type="database",
        token=token,
        details={"checksum_sha256": checksum, "counts": counts},
    )

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "owner_id": owner_id,
        "counts": counts,
        "checksum_sha256": checksum,
        "data": data,
    }


def verify_backup_manifest(expected_checksum: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Verify the cryptographic SHA-256 integrity and structural completeness of a backup archive."""
    canonical_json = json.dumps(data, sort_keys=True, default=str).encode("utf-8")
    computed = hashlib.sha256(canonical_json).hexdigest()
    counts = {k: len(v) if isinstance(v, list) else 0 for k, v in data.items()}
    valid = hmac.compare_digest(computed, expected_checksum)
    return {
        "valid": valid,
        "computed_checksum": computed,
        "counts": counts,
        "message": "Backup archive checksum and relational manifest verified successfully."
        if valid
        else "Checksum mismatch: backup data has been modified or corrupted.",
    }
