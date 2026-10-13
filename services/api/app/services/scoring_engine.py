"""
Cricket Scoring Engine — pure deterministic domain logic.
Reconstructs scorecards, tracks live state, calculates bowler figures and partnerships.
"""
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from app.schemas.scoring import (
    BatterScorecardFigure,
    BowlerScorecardFigure,
    ExtrasBreakdown,
    FallOfWicketFigure,
    InningsScorecard,
    MatchScorecard,
    PartnershipFigure,
)

BOWLER_CREDITED_WICKETS = {"bowled", "caught", "lbw", "stumped", "hit_wicket"}


def format_overs(legal_balls: int) -> str:
    """Format total legal balls into standard cricket overs notation (e.g. 14.3)."""
    overs = legal_balls // 6
    balls = legal_balls % 6
    return f"{overs}.{balls}"


def calculate_run_rate(runs: int, legal_balls: int) -> float:
    """Calculate run rate per 6 legal deliveries."""
    if legal_balls == 0:
        return 0.0
    return round((runs / (legal_balls / 6.0)), 2)


def calculate_economy(runs_conceded: int, legal_balls: int) -> float:
    """Calculate bowler economy rate per over."""
    if legal_balls == 0:
        return 0.0
    return round((runs_conceded / (legal_balls / 6.0)), 2)


def format_dismissal(
    wicket_type: Optional[str],
    bowler_name: Optional[str],
    fielder_name: Optional[str] = None,
) -> str:
    """Format standard cricket dismissal score line."""
    if not wicket_type:
        return "not out"
    bowler = bowler_name or "Unknown"
    fielder = fielder_name or "Unknown"

    if wicket_type == "bowled":
        return f"b {bowler}"
    elif wicket_type == "caught":
        if fielder_name and fielder_name == bowler_name:
            return f"c & b {bowler}"
        return f"c {fielder} b {bowler}" if fielder_name else f"c sub b {bowler}"
    elif wicket_type == "lbw":
        return f"lbw b {bowler}"
    elif wicket_type == "stumped":
        return f"st {fielder} b {bowler}" if fielder_name else f"st † b {bowler}"
    elif wicket_type == "run_out":
        return f"run out ({fielder})" if fielder_name else "run out"
    elif wicket_type == "hit_wicket":
        return f"hit wicket b {bowler}"
    elif wicket_type == "retired_hurt":
        return "retired hurt"
    elif wicket_type == "retired_out":
        return "retired out"
    elif wicket_type == "handled_ball":
        return "handled the ball"
    elif wicket_type == "obstructing_field":
        return "obstructing the field"
    elif wicket_type == "timed_out":
        return "timed out"
    return f"{wicket_type} b {bowler}"


def evaluate_delivery_legality_and_runs(
    batter_runs: int,
    extra_type: Optional[str],
    extra_runs: int,
) -> Tuple[bool, int]:
    """
    Returns (is_legal, total_runs).
    Wides and no-balls are illegal deliveries in standard limited overs cricket.
    """
    is_legal = extra_type not in ("wide", "no_ball")
    total_runs = batter_runs + extra_runs
    return is_legal, total_runs


def compute_physical_runs_swapped(
    batter_runs: int,
    extra_type: Optional[str],
    extra_runs: int,
    is_boundary: bool,
    runs_completed_before_out: int = 0,
    is_wicket: bool = False,
    wicket_type: Optional[str] = None,
) -> bool:
    """
    Returns True if batsmen physically crossed an odd number of completed runs.
    Boundaries (4, 6) are signaled without running ends exchange.
    """
    if is_wicket and wicket_type == "run_out":
        return (runs_completed_before_out % 2) == 1

    if is_boundary:
        return False

    if extra_type == "wide":
        # First extra run is wide penalty (no running). Any subsequent runs are running.
        running_runs = max(0, extra_runs - 1)
        return (running_runs % 2) == 1

    if extra_type in ("bye", "leg_bye"):
        return (extra_runs % 2) == 1

    if extra_type == "no_ball":
        # Batter runs or running extras
        return (batter_runs % 2) == 1

    # Standard off bat
    return (batter_runs % 2) == 1


def calculate_innings_scorecard(
    innings: Dict[str, Any],
    deliveries: List[Dict[str, Any]],
    players_map: Dict[str, str],
    batting_positions: Optional[Dict[str, int]] = None,
    match: Optional[Dict[str, Any]] = None,
) -> InningsScorecard:
    """
    Pure deterministic reconstruction of an innings scorecard from canonical deliveries.
    """
    batting_positions = batting_positions or {}
    match = match or {}

    innings_id = UUID(str(innings["id"]))
    match_id = UUID(str(innings["match_id"]))
    batting_team_id = UUID(str(innings["batting_team_id"]))
    bowling_team_id = UUID(str(innings["bowling_team_id"]))
    batting_team_name = innings.get("batting_team_name") or "Batting Team"
    bowling_team_name = innings.get("bowling_team_name") or "Bowling Team"
    innings_number = int(innings["innings_number"])
    target_runs = innings.get("target_runs")
    if target_runs is not None:
        target_runs = int(target_runs)

    # Accumulators
    total_runs = 0
    total_wickets = 0
    total_legal_balls = 0
    extras = ExtrasBreakdown()

    # Batter trackers: player_id -> stats dict
    batters_dict: Dict[str, Dict[str, Any]] = {}
    # Bowler trackers: player_id -> stats dict
    bowlers_dict: Dict[str, Dict[str, Any]] = {}
    # Bowler over tracker: (bowler_id, over_no) -> { legal_balls, runs_conceded }
    bowler_overs: Dict[Tuple[str, int], Dict[str, int]] = {}

    fall_of_wickets: List[FallOfWicketFigure] = []
    partnerships: List[PartnershipFigure] = []

    # Current partnership tracker
    current_pair: Optional[Tuple[str, str]] = None
    pair_runs = 0
    pair_balls = 0

    # Ensure current batters and bowler from innings state are in dicts even at 0 balls
    init_striker = innings.get("current_striker_id")
    init_non_striker = innings.get("current_non_striker_id")
    init_bowler = innings.get("current_bowler_id")
    for p_id in (init_striker, init_non_striker):
        if p_id:
            pid_str = str(p_id)
            if pid_str not in batters_dict:
                batters_dict[pid_str] = {
                    "player_id": UUID(pid_str),
                    "player_name": players_map.get(pid_str, "Unknown Batter"),
                    "runs": 0,
                    "balls": 0,
                    "fours": 0,
                    "sixes": 0,
                    "is_out": False,
                    "dismissal_text": "not out",
                    "wicket_type": None,
                    "bowler_name": None,
                    "fielder_name": None,
                    "batting_position": batting_positions.get(pid_str),
                }

    if init_bowler:
        bid_str = str(init_bowler)
        if bid_str not in bowlers_dict:
            bowlers_dict[bid_str] = {
                "player_id": UUID(bid_str),
                "player_name": players_map.get(bid_str, "Unknown Bowler"),
                "legal_balls": 0,
                "maidens": 0,
                "runs_conceded": 0,
                "wickets": 0,
                "dots": 0,
                "wides": 0,
                "no_balls": 0,
            }

    # Replay all canonical, non-voided deliveries
    active_deliveries = [d for d in deliveries if not d.get("is_voided", False)]
    active_deliveries.sort(key=lambda d: d.get("sequence_no", 0))

    last_striker_id: Optional[str] = str(init_striker) if init_striker else None
    last_non_striker_id: Optional[str] = str(init_non_striker) if init_non_striker else None
    last_bowler_id: Optional[str] = str(init_bowler) if init_bowler else None

    for d in active_deliveries:
        striker_id = str(d["striker_id"])
        non_striker_id = str(d["non_striker_id"])
        bowler_id = str(d["bowler_id"])
        over_no = int(d["over_no"])

        if not init_striker:
            last_striker_id = str(d.get("next_striker_id") or striker_id)
        if not init_non_striker:
            last_non_striker_id = str(d.get("next_non_striker_id") or non_striker_id)
        if "current_bowler_id" not in innings:
            last_bowler_id = bowler_id

        # Initialize batter records
        for b_id in (striker_id, non_striker_id):
            if b_id not in batters_dict:
                batters_dict[b_id] = {
                    "player_id": UUID(b_id),
                    "player_name": players_map.get(b_id, "Unknown Batter"),
                    "runs": 0,
                    "balls": 0,
                    "fours": 0,
                    "sixes": 0,
                    "is_out": False,
                    "dismissal_text": "not out",
                    "wicket_type": None,
                    "bowler_name": None,
                    "fielder_name": None,
                    "batting_position": batting_positions.get(b_id),
                }

        # Initialize bowler record
        if bowler_id not in bowlers_dict:
            bowlers_dict[bowler_id] = {
                "player_id": UUID(bowler_id),
                "player_name": players_map.get(bowler_id, "Unknown Bowler"),
                "legal_balls": 0,
                "maidens": 0,
                "runs_conceded": 0,
                "wickets": 0,
                "dots": 0,
                "wides": 0,
                "no_balls": 0,
            }

        # Over-tracking dict
        over_key = (bowler_id, over_no)
        if over_key not in bowler_overs:
            bowler_overs[over_key] = {"legal_balls": 0, "runs_conceded": 0}

        batter_runs = int(d.get("batter_runs", 0))
        extra_type = d.get("extra_type")
        extra_runs = int(d.get("extra_runs", 0))
        d_total_runs = batter_runs + extra_runs
        is_legal = bool(d.get("is_legal", True))
        is_boundary = bool(d.get("is_boundary", False))
        is_batter_boundary = bool(d.get("is_batter_boundary", False))
        boundary_type = d.get("boundary_type")
        is_wicket = bool(d.get("is_wicket", False))
        wicket_type = d.get("wicket_type")
        dismissed_id = str(d.get("dismissed_player_id")) if d.get("dismissed_player_id") else None
        fielder_id = str(d.get("fielder_id")) if d.get("fielder_id") else None

        # 1. Update team totals
        total_runs += d_total_runs
        if is_legal:
            total_legal_balls += 1

        # 2. Update extras breakdown
        if extra_type == "wide":
            extras.wides += extra_runs
            extras.total += extra_runs
            bowlers_dict[bowler_id]["wides"] += 1
        elif extra_type == "no_ball":
            extras.no_balls += extra_runs
            extras.total += extra_runs
            bowlers_dict[bowler_id]["no_balls"] += 1
        elif extra_type == "bye":
            extras.byes += extra_runs
            extras.total += extra_runs
        elif extra_type == "leg_bye":
            extras.leg_byes += extra_runs
            extras.total += extra_runs
        elif extra_type == "penalty":
            extras.penalty += extra_runs
            extras.total += extra_runs

        # 3. Update batter stats
        batters_dict[striker_id]["runs"] += batter_runs
        # Balls faced: counts for legal deliveries and no-balls; NOT wides
        if is_legal or extra_type == "no_ball":
            batters_dict[striker_id]["balls"] += 1

        if is_batter_boundary:
            if boundary_type == 4 or (not boundary_type and batter_runs == 4):
                batters_dict[striker_id]["fours"] += 1
            elif boundary_type == 6 or (not boundary_type and batter_runs == 6):
                batters_dict[striker_id]["sixes"] += 1

        # 4. Update bowler stats
        bowler_conceded = batter_runs
        if extra_type in ("wide", "no_ball"):
            bowler_conceded += extra_runs

        bowlers_dict[bowler_id]["runs_conceded"] += bowler_conceded
        bowler_overs[over_key]["runs_conceded"] += bowler_conceded

        if is_legal:
            bowlers_dict[bowler_id]["legal_balls"] += 1
            bowler_overs[over_key]["legal_balls"] += 1

        if is_legal and bowler_conceded == 0:
            bowlers_dict[bowler_id]["dots"] += 1

        # 5. Partnership tracking
        pair = tuple(sorted([striker_id, non_striker_id]))
        if current_pair != pair:
            current_pair = pair
            pair_runs = 0
            pair_balls = 0
        pair_runs += d_total_runs
        if is_legal:
            pair_balls += 1

        # 6. Wicket handling
        if is_wicket and dismissed_id:
            total_wickets += 1
            bowler_name = players_map.get(bowler_id, "Bowler")
            fielder_name = players_map.get(fielder_id, "Fielder") if fielder_id else None

            if dismissed_id in batters_dict:
                batters_dict[dismissed_id]["is_out"] = True
                batters_dict[dismissed_id]["wicket_type"] = wicket_type
                batters_dict[dismissed_id]["bowler_name"] = bowler_name
                batters_dict[dismissed_id]["fielder_name"] = fielder_name
                batters_dict[dismissed_id]["dismissal_text"] = format_dismissal(
                    wicket_type, bowler_name, fielder_name
                )

            # Bowler credit
            if wicket_type in BOWLER_CREDITED_WICKETS:
                bowlers_dict[bowler_id]["wickets"] += 1

            # Fall of wicket
            fall_of_wickets.append(
                FallOfWicketFigure(
                    wicket_number=total_wickets,
                    score=total_runs,
                    overs=format_overs(total_legal_balls),
                    dismissed_player_id=UUID(dismissed_id),
                    dismissed_player_name=players_map.get(dismissed_id, "Unknown Batter"),
                )
            )

            # Record completed partnership
            partnerships.append(
                PartnershipFigure(
                    batter1_id=UUID(pair[0]),
                    batter1_name=players_map.get(pair[0], "Batter"),
                    batter2_id=UUID(pair[1]),
                    batter2_name=players_map.get(pair[1], "Batter"),
                    runs=pair_runs,
                    balls=pair_balls,
                )
            )
            # Reset pair
            current_pair = None
            pair_runs = 0
            pair_balls = 0

    # Calculate maidens for each bowler
    for (b_id, _), over_data in bowler_overs.items():
        if over_data["legal_balls"] == 6 and over_data["runs_conceded"] == 0:
            bowlers_dict[b_id]["maidens"] += 1

    # Format batter figures
    batters_list: List[BatterScorecardFigure] = []
    for b_data in batters_dict.values():
        b_runs = b_data["runs"]
        b_balls = b_data["balls"]
        sr = round((b_runs / b_balls * 100.0), 2) if b_balls > 0 else 0.0
        batters_list.append(
            BatterScorecardFigure(
                player_id=b_data["player_id"],
                player_name=b_data["player_name"],
                runs=b_runs,
                balls=b_balls,
                fours=b_data["fours"],
                sixes=b_data["sixes"],
                strike_rate=sr,
                is_out=b_data["is_out"],
                dismissal_text=b_data["dismissal_text"],
                wicket_type=b_data["wicket_type"],
                bowler_name=b_data["bowler_name"],
                fielder_name=b_data["fielder_name"],
                batting_position=b_data["batting_position"],
            )
        )
    # Sort batters by batting position or order added
    batters_list.sort(key=lambda b: (b.batting_position if b.batting_position is not None else 99))

    # Format bowler figures
    bowlers_list: List[BowlerScorecardFigure] = []
    for b_id, b_data in bowlers_dict.items():
        l_balls = b_data["legal_balls"]
        r_conc = b_data["runs_conceded"]
        bowlers_list.append(
            BowlerScorecardFigure(
                player_id=b_data["player_id"],
                player_name=b_data["player_name"],
                overs=format_overs(l_balls),
                legal_balls=l_balls,
                maidens=b_data["maidens"],
                runs_conceded=r_conc,
                wickets=b_data["wickets"],
                economy=calculate_economy(r_conc, l_balls),
                dots=b_data["dots"],
                wides=b_data["wides"],
                no_balls=b_data["no_balls"],
            )
        )

    # Status & completion reason
    status = innings.get("status", "in_progress")
    completed_reason = innings.get("completed_reason")
    overs_limit = match.get("overs_per_innings")

    if status == "in_progress":
        if total_wickets >= 10:
            status = "completed"
            completed_reason = "all_out"
        elif overs_limit and total_legal_balls >= (overs_limit * 6):
            status = "completed"
            completed_reason = "overs_completed"
        elif target_runs and total_runs >= target_runs:
            status = "completed"
            completed_reason = "target_reached"

    # Current partnership figure
    current_partnership_fig: Optional[PartnershipFigure] = None
    if current_pair and (pair_runs > 0 or pair_balls > 0):
        current_partnership_fig = PartnershipFigure(
            batter1_id=UUID(current_pair[0]),
            batter1_name=players_map.get(current_pair[0], "Batter"),
            batter2_id=UUID(current_pair[1]),
            batter2_name=players_map.get(current_pair[1], "Batter"),
            runs=pair_runs,
            balls=pair_balls,
        )

    # Identify current striker, non-striker, bowler
    cur_striker_fig = next((b for b in batters_list if str(b.player_id) == last_striker_id), None)
    cur_non_striker_fig = next((b for b in batters_list if str(b.player_id) == last_non_striker_id), None)
    cur_bowler_fig = next((bw for bw in bowlers_list if str(bw.player_id) == last_bowler_id), None)

    # Required run rate
    required_rr: Optional[float] = None
    if target_runs and overs_limit and status == "in_progress":
        runs_needed = target_runs - total_runs
        balls_remaining = (overs_limit * 6) - total_legal_balls
        if balls_remaining > 0 and runs_needed > 0:
            required_rr = round((runs_needed / (balls_remaining / 6.0)), 2)

    return InningsScorecard(
        innings_id=innings_id,
        match_id=match_id,
        innings_number=innings_number,
        batting_team_id=batting_team_id,
        batting_team_name=batting_team_name,
        bowling_team_id=bowling_team_id,
        bowling_team_name=bowling_team_name,
        status=status,
        completed_reason=completed_reason,
        total_runs=total_runs,
        total_wickets=total_wickets,
        total_legal_balls=total_legal_balls,
        overs_display=format_overs(total_legal_balls),
        run_rate=calculate_run_rate(total_runs, total_legal_balls),
        target_runs=target_runs,
        required_run_rate=required_rr,
        current_striker=cur_striker_fig,
        current_non_striker=cur_non_striker_fig,
        current_bowler=cur_bowler_fig,
        batters=batters_list,
        bowlers=bowlers_list,
        extras=extras,
        fall_of_wickets=fall_of_wickets,
        partnerships=partnerships,
        current_partnership=current_partnership_fig,
    )


def determine_next_delivery_state(
    current_striker_id: UUID,
    current_non_striker_id: UUID,
    current_bowler_id: UUID,
    legal_balls_in_innings: int,
    batter_runs: int,
    extra_type: Optional[str],
    extra_runs: int,
    is_boundary: bool,
    is_wicket: bool,
    wicket_type: Optional[str] = None,
    dismissed_player_id: Optional[UUID] = None,
    runs_completed_before_out: int = 0,
    next_striker_id: Optional[UUID] = None,
    next_non_striker_id: Optional[UUID] = None,
) -> Tuple[UUID, UUID, Optional[UUID], bool]:
    """
    Determines next (striker_id, non_striker_id, next_bowler_id, is_over_complete).
    Handles:
      - Physical run swapping (odd runs)
      - End of over swap (6 legal balls)
      - Wickets (replacing dismissed batter with incoming batter)
      - Bowler over completion
    """
    is_legal, _ = evaluate_delivery_legality_and_runs(batter_runs, extra_type, extra_runs)
    new_legal_balls = legal_balls_in_innings + (1 if is_legal else 0)
    over_completed = is_legal and (new_legal_balls % 6 == 0)

    # 1. Step 1: Did batters cross during the delivery?
    swapped_on_run = compute_physical_runs_swapped(
        batter_runs=batter_runs,
        extra_type=extra_type,
        extra_runs=extra_runs,
        is_boundary=is_boundary,
        runs_completed_before_out=runs_completed_before_out,
        is_wicket=is_wicket,
        wicket_type=wicket_type,
    )

    s_id = current_striker_id
    ns_id = current_non_striker_id

    if swapped_on_run:
        s_id, ns_id = ns_id, s_id

    # 2. Step 2: Wicket replacement
    if is_wicket and dismissed_player_id:
        if next_striker_id and next_non_striker_id:
            s_id = next_striker_id
            ns_id = next_non_striker_id
        elif next_striker_id:
            # Explicit new striker
            if dismissed_player_id == s_id:
                s_id = next_striker_id
            else:
                ns_id = s_id
                s_id = next_striker_id
        elif next_non_striker_id:
            ns_id = next_non_striker_id
        else:
            # If no new batter specified yet (waiting for input), keep position marked
            pass

    # 3. Step 3: End of over switch
    if over_completed:
        # At the end of an over, the batsmen switch ends
        s_id, ns_id = ns_id, s_id
        # Bowler must change — bowler_id becomes None or requires bowler rotation
        next_bowler = None
    else:
        next_bowler = current_bowler_id

    return s_id, ns_id, next_bowler, over_completed


def compute_match_result(
    match: Dict[str, Any],
    innings_list: List[InningsScorecard],
) -> Tuple[Optional[UUID], Optional[str]]:
    """
    Computes match winner and result text based on innings scorecards.
    """
    if len(innings_list) < 2:
        return None, "Match in progress"

    inn1 = innings_list[0]
    inn2 = innings_list[1]

    if inn2.status != "completed":
        return None, "2nd Innings in progress"

    target = inn1.total_runs + 1
    inn2_runs = inn2.total_runs
    inn2_wickets = inn2.total_wickets

    if inn2_runs >= target:
        wickets_won = 10 - inn2_wickets
        winner_id = inn2.batting_team_id
        result = f"{inn2.batting_team_name} won by {wickets_won} wickets"
        return winner_id, result
    elif inn2_runs == (target - 1):
        return None, "Match tied"
    else:
        runs_won = (target - 1) - inn2_runs
        winner_id = inn1.batting_team_id
        result = f"{inn1.batting_team_name} won by {runs_won} runs"
        return winner_id, result
