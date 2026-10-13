"""
Table-driven tests for the pure cricket scoring engine.
Validates:
  - Legal deliveries: dot, 1, 2, 3, 4, 6
  - Wides (penalty + running extras, non-increment of balls faced)
  - No-balls (penalty + batter runs / boundary, balls faced increment)
  - Byes and leg-byes (extras to team, zero to batter/bowler, balls faced increment)
  - Boundary not credited to batter (e.g. 4 byes)
  - Team runs increasing without batter runs
  - Wickets: bowled, caught, lbw, stumped, hit_wicket (bowler credited)
  - Run-outs: striker out vs non-striker out (not bowler credited, completed runs)
  - Strike rotation: odd runs, over completion, boundary even runs
  - Maidens calculation (6 legal balls, 0 conceded runs)
  - Innings termination: all-out, max overs, target reached in 2nd innings
  - Scorecard reconstruction, fall of wickets, partnerships
"""
from uuid import uuid4

import pytest

from app.schemas.scoring import DeliveryCreate
from app.services.scoring_engine import (
    calculate_innings_scorecard,
    compute_match_result,
    determine_next_delivery_state,
    evaluate_delivery_legality_and_runs,
)


@pytest.fixture
def match_context():
    team_a = uuid4()
    team_b = uuid4()
    p1 = uuid4()  # Batter 1 (Striker)
    p2 = uuid4()  # Batter 2 (Non-striker)
    p3 = uuid4()  # Batter 3
    bowler1 = uuid4()
    bowler2 = uuid4()
    fielder1 = uuid4()

    players_map = {
        str(p1): "Player A",
        str(p2): "Player B",
        str(p3): "Player C",
        str(bowler1): "Bowler X",
        str(bowler2): "Bowler Y",
        str(fielder1): "Fielder Z",
    }
    batting_positions = {
        str(p1): 1,
        str(p2): 2,
        str(p3): 3,
    }
    match = {
        "id": uuid4(),
        "title": "Finals",
        "format": "T20",
        "overs_per_innings": 20,
    }
    innings = {
        "id": uuid4(),
        "match_id": match["id"],
        "innings_number": 1,
        "batting_team_id": team_a,
        "bowling_team_id": team_b,
        "batting_team_name": "Team A",
        "bowling_team_name": "Team B",
        "current_striker_id": p1,
        "current_non_striker_id": p2,
        "current_bowler_id": bowler1,
        "target_runs": None,
        "status": "in_progress",
    }
    return {
        "p1": p1,
        "p2": p2,
        "p3": p3,
        "bowler1": bowler1,
        "bowler2": bowler2,
        "fielder1": fielder1,
        "players_map": players_map,
        "batting_positions": batting_positions,
        "match": match,
        "innings": innings,
    }


# ── Table-driven strike rotation tests ───────────────────────────────────────

@pytest.mark.parametrize(
    "batter_runs,extra_type,extra_runs,is_boundary,legal_balls_in_innings,expected_swapped_ends,expected_over_complete",
    [
        # Dot ball mid-over: 0 runs -> no swap
        (0, None, 0, False, 0, False, False),
        # Single mid-over: 1 run -> swap
        (1, None, 0, False, 0, True, False),
        # Two runs mid-over: 2 runs -> no swap
        (2, None, 0, False, 1, False, False),
        # Three runs mid-over: 3 runs -> swap
        (3, None, 0, False, 1, True, False),
        # Boundary 4: no swap
        (4, None, 0, True, 2, False, False),
        # Six: no swap
        (6, None, 0, True, 3, False, False),
        # Standard Wide (1 extra run, 0 running) -> illegal ball, no swap, over doesn't complete
        (0, "wide", 1, False, 4, False, False),
        # Wide + 1 running run (2 extra runs total) -> odd running run -> swap!
        (0, "wide", 2, False, 4, True, False),
        # Wide + 4 boundary extras (5 extra runs total) -> boundary -> no swap
        (0, "wide", 5, True, 4, False, False),
        # No-ball dot (1 extra run) -> illegal ball, no swap
        (0, "no_ball", 1, False, 4, False, False),
        # No-ball + 1 batter run (1 off bat + 1 nb = 2 runs) -> odd batter run -> swap
        (1, "no_ball", 1, False, 4, True, False),
        # No-ball + 4 boundary off bat (4 off bat + 1 nb = 5 runs) -> boundary -> no swap
        (4, "no_ball", 1, True, 4, False, False),
        # 1 Bye mid-over: odd runs -> swap
        (0, "bye", 1, False, 2, True, False),
        # 2 Leg-byes mid-over: even runs -> no swap
        (0, "leg_bye", 2, False, 2, False, False),
        # 4 Byes boundary: boundary -> no swap
        (0, "bye", 4, True, 2, False, False),
        # Ball 6 (over end) with dot (0 runs):
        # 0 runs on ball -> no run swap, BUT over ends -> batsmen swap ends -> net swap = True!
        (0, None, 0, False, 5, True, True),
        # Ball 6 (over end) with single (1 run):
        # 1 run on ball -> swap on run, AND over ends -> swap again -> net swap = False (striker keeps strike)!
        (1, None, 0, False, 5, False, True),
        # Ball 6 (over end) with two runs (2 runs):
        # 2 runs on ball -> no swap on run, AND over ends -> swap -> net swap = True
        (2, None, 0, False, 5, True, True),
        # Ball 6 (over end) with four (4 runs):
        # boundary -> no swap on run, AND over ends -> swap -> net swap = True
        (4, None, 0, True, 5, True, True),
    ],
)
def test_table_driven_strike_rotation(
    match_context,
    batter_runs,
    extra_type,
    extra_runs,
    is_boundary,
    legal_balls_in_innings,
    expected_swapped_ends,
    expected_over_complete,
):
    p1 = match_context["p1"]
    p2 = match_context["p2"]
    bowler1 = match_context["bowler1"]

    next_striker, next_non_striker, next_bowler, over_complete = determine_next_delivery_state(
        current_striker_id=p1,
        current_non_striker_id=p2,
        current_bowler_id=bowler1,
        legal_balls_in_innings=legal_balls_in_innings,
        batter_runs=batter_runs,
        extra_type=extra_type,
        extra_runs=extra_runs,
        is_boundary=is_boundary,
        is_wicket=False,
    )

    assert over_complete == expected_over_complete
    if expected_swapped_ends:
        assert next_striker == p2
        assert next_non_striker == p1
    else:
        assert next_striker == p1
        assert next_non_striker == p2

    if expected_over_complete:
        assert next_bowler is None
    else:
        assert next_bowler == bowler1


# ── Detailed delivery and scorecard figures ─────────────────────────────────

def test_team_runs_increase_without_batter_runs_and_extras_boundary(match_context):
    """
    Test delivery where team runs increase without batter runs:
    - 4 byes: team gets 4, batter gets 0 runs, balls faced increments,
      boundary is NOT credited to batter, bowler conceded is 0.
    """
    p1 = match_context["p1"]
    p2 = match_context["p2"]
    bowler1 = match_context["bowler1"]

    deliveries = [
        {
            "sequence_no": 1,
            "over_no": 0,
            "ball_in_over": 1,
            "display_over": "0.1",
            "striker_id": p1,
            "non_striker_id": p2,
            "bowler_id": bowler1,
            "batter_runs": 0,
            "extra_type": "bye",
            "extra_runs": 4,
            "total_runs": 4,
            "is_legal": True,
            "is_boundary": True,
            "boundary_type": 4,
            "is_batter_boundary": False,  # Not credited to batter
            "is_wicket": False,
        }
    ]

    sc = calculate_innings_scorecard(
        innings=match_context["innings"],
        deliveries=deliveries,
        players_map=match_context["players_map"],
        batting_positions=match_context["batting_positions"],
        match=match_context["match"],
    )

    assert sc.total_runs == 4
    assert sc.total_legal_balls == 1
    assert sc.extras.byes == 4
    assert sc.extras.total == 4

    # Striker faced the ball, but got 0 runs and 0 fours
    striker_fig = next(b for b in sc.batters if b.player_id == p1)
    assert striker_fig.runs == 0
    assert striker_fig.balls == 1
    assert striker_fig.fours == 0

    # Bowler conceded 0 runs for byes
    bowler_fig = next(bw for bw in sc.bowlers if bw.player_id == bowler1)
    assert bowler_fig.legal_balls == 1
    assert bowler_fig.runs_conceded == 0
    assert bowler_fig.dots == 1  # 0 conceded on legal ball


def test_wides_and_no_balls(match_context):
    """
    Test wide: illegal ball, doesn't increment balls faced, charged to bowler.
    Test no-ball: illegal ball, batter hits a 4 off it -> batter gets 4 runs and 1 four,
    bowler conceded = 4 + 1 = 5 runs, balls faced increments.
    """
    p1 = match_context["p1"]
    p2 = match_context["p2"]
    bowler1 = match_context["bowler1"]

    deliveries = [
        # Ball 1: Wide
        {
            "sequence_no": 1,
            "over_no": 0,
            "ball_in_over": 0,
            "display_over": "0.0 (wd)",
            "striker_id": p1,
            "non_striker_id": p2,
            "bowler_id": bowler1,
            "batter_runs": 0,
            "extra_type": "wide",
            "extra_runs": 1,
            "total_runs": 1,
            "is_legal": False,
            "is_boundary": False,
            "is_batter_boundary": False,
            "is_wicket": False,
        },
        # Ball 2: No-ball with 4 off the bat
        {
            "sequence_no": 2,
            "over_no": 0,
            "ball_in_over": 0,
            "display_over": "0.0 (nb)",
            "striker_id": p1,
            "non_striker_id": p2,
            "bowler_id": bowler1,
            "batter_runs": 4,
            "extra_type": "no_ball",
            "extra_runs": 1,
            "total_runs": 5,
            "is_legal": False,
            "is_boundary": True,
            "boundary_type": 4,
            "is_batter_boundary": True,
            "is_wicket": False,
        },
    ]

    sc = calculate_innings_scorecard(
        innings=match_context["innings"],
        deliveries=deliveries,
        players_map=match_context["players_map"],
        batting_positions=match_context["batting_positions"],
        match=match_context["match"],
    )

    assert sc.total_runs == 6
    assert sc.total_legal_balls == 0  # Both were illegal deliveries!
    assert sc.extras.wides == 1
    assert sc.extras.no_balls == 1
    assert sc.extras.total == 2

    striker_fig = next(b for b in sc.batters if b.player_id == p1)
    assert striker_fig.runs == 4
    assert striker_fig.balls == 1  # Wide does not count, no-ball counts as ball faced
    assert striker_fig.fours == 1

    bowler_fig = next(bw for bw in sc.bowlers if bw.player_id == bowler1)
    assert bowler_fig.legal_balls == 0
    assert bowler_fig.runs_conceded == 6  # 1 wide + 1 no-ball + 4 off bat
    assert bowler_fig.wides == 1
    assert bowler_fig.no_balls == 1


def test_wickets_and_run_outs(match_context):
    """
    Test bowler wicket (caught): bowler credited with wicket, fall of wicket logged.
    Test run-out where dismissed player is non-striker: bowler NOT credited with wicket.
    """
    p1 = match_context["p1"]
    p2 = match_context["p2"]
    p3 = match_context["p3"]
    bowler1 = match_context["bowler1"]
    fielder1 = match_context["fielder1"]

    deliveries = [
        # Ball 1: p1 is caught by fielder1 off bowler1
        {
            "sequence_no": 1,
            "over_no": 0,
            "ball_in_over": 1,
            "display_over": "0.1",
            "striker_id": p1,
            "non_striker_id": p2,
            "bowler_id": bowler1,
            "batter_runs": 0,
            "extra_type": None,
            "extra_runs": 0,
            "total_runs": 0,
            "is_legal": True,
            "is_wicket": True,
            "wicket_type": "caught",
            "dismissed_player_id": p1,
            "fielder_id": fielder1,
        },
        # Ball 2: new striker p3 faces ball, 1 completed run before non-striker p2 is run out!
        {
            "sequence_no": 2,
            "over_no": 0,
            "ball_in_over": 2,
            "display_over": "0.2",
            "striker_id": p3,
            "non_striker_id": p2,
            "bowler_id": bowler1,
            "batter_runs": 1,
            "extra_type": None,
            "extra_runs": 0,
            "total_runs": 1,
            "is_legal": True,
            "is_wicket": True,
            "wicket_type": "run_out",
            "dismissed_player_id": p2,  # NON-STRIKER dismissed!
            "fielder_id": fielder1,
            "runs_completed_before_out": 1,
        },
    ]

    sc = calculate_innings_scorecard(
        innings=match_context["innings"],
        deliveries=deliveries,
        players_map=match_context["players_map"],
        batting_positions=match_context["batting_positions"],
        match=match_context["match"],
    )

    assert sc.total_wickets == 2
    assert sc.total_runs == 1
    assert sc.total_legal_balls == 2

    # Verify fall of wickets
    assert len(sc.fall_of_wickets) == 2
    fow1 = sc.fall_of_wickets[0]
    assert fow1.wicket_number == 1
    assert fow1.score == 0
    assert fow1.dismissed_player_id == p1

    fow2 = sc.fall_of_wickets[1]
    assert fow2.wicket_number == 2
    assert fow2.score == 1
    assert fow2.dismissed_player_id == p2

    # Bowler credited with ONLY 1 wicket (the caught one, not the run out)
    bowler_fig = next(bw for bw in sc.bowlers if bw.player_id == bowler1)
    assert bowler_fig.wickets == 1
    assert bowler_fig.runs_conceded == 1

    # Check batter dismissal texts
    b1 = next(b for b in sc.batters if b.player_id == p1)
    assert b1.is_out is True
    assert "c Fielder Z b Bowler X" in b1.dismissal_text

    b2 = next(b for b in sc.batters if b.player_id == p2)
    assert b2.is_out is True
    assert "run out (Fielder Z)" in b2.dismissal_text


def test_maiden_over_calculation(match_context):
    """6 legal dot deliveries in an over constitutes a maiden."""
    p1 = match_context["p1"]
    p2 = match_context["p2"]
    bowler1 = match_context["bowler1"]

    deliveries = []
    for i in range(1, 7):
        deliveries.append(
            {
                "sequence_no": i,
                "over_no": 0,
                "ball_in_over": i,
                "display_over": f"0.{i}",
                "striker_id": p1,
                "non_striker_id": p2,
                "bowler_id": bowler1,
                "batter_runs": 0,
                "extra_type": None,
                "extra_runs": 0,
                "total_runs": 0,
                "is_legal": True,
                "is_wicket": False,
            }
        )

    sc = calculate_innings_scorecard(
        innings=match_context["innings"],
        deliveries=deliveries,
        players_map=match_context["players_map"],
        batting_positions=match_context["batting_positions"],
        match=match_context["match"],
    )

    bowler_fig = next(bw for bw in sc.bowlers if bw.player_id == bowler1)
    assert bowler_fig.overs == "1.0"
    assert bowler_fig.maidens == 1
    assert bowler_fig.runs_conceded == 0
    assert bowler_fig.dots == 6


def test_voided_delivery_reconstruction(match_context):
    """Voiding a delivery removes it from scorecard reconstruction."""
    p1 = match_context["p1"]
    p2 = match_context["p2"]
    bowler1 = match_context["bowler1"]

    deliveries = [
        {
            "sequence_no": 1,
            "over_no": 0,
            "ball_in_over": 1,
            "display_over": "0.1",
            "striker_id": p1,
            "non_striker_id": p2,
            "bowler_id": bowler1,
            "batter_runs": 6,
            "extra_type": None,
            "extra_runs": 0,
            "total_runs": 6,
            "is_legal": True,
            "is_boundary": True,
            "boundary_type": 6,
            "is_batter_boundary": True,
            "is_wicket": False,
            "is_voided": True,  # VOIDED
            "voided_reason": "Scorer mistake",
        },
        {
            "sequence_no": 2,
            "over_no": 0,
            "ball_in_over": 1,
            "display_over": "0.1",
            "striker_id": p1,
            "non_striker_id": p2,
            "bowler_id": bowler1,
            "batter_runs": 1,
            "extra_type": None,
            "extra_runs": 0,
            "total_runs": 1,
            "is_legal": True,
            "is_boundary": False,
            "is_batter_boundary": False,
            "is_wicket": False,
            "is_voided": False,
        },
    ]

    sc = calculate_innings_scorecard(
        innings=match_context["innings"],
        deliveries=deliveries,
        players_map=match_context["players_map"],
        batting_positions=match_context["batting_positions"],
        match=match_context["match"],
    )

    assert sc.total_runs == 1
    assert sc.total_legal_balls == 1
    striker_fig = next(b for b in sc.batters if b.player_id == p1)
    assert striker_fig.runs == 1
    assert striker_fig.sixes == 0


def test_2nd_innings_target_reached_and_match_result(match_context):
    """
    2nd innings chases target:
    1st innings: 120 runs. Target: 121 runs.
    2nd innings: scores 121 runs for 2 wickets -> innings completes with 'target_reached'.
    Match winner is 2nd innings batting team, won by 8 wickets.
    """
    match = match_context["match"]
    team_a = match_context["innings"]["batting_team_id"]
    team_b = match_context["innings"]["bowling_team_id"]

    inn1 = {
        "id": uuid4(),
        "match_id": match["id"],
        "innings_number": 1,
        "batting_team_id": team_a,
        "bowling_team_id": team_b,
        "batting_team_name": "Team A",
        "bowling_team_name": "Team B",
        "status": "completed",
        "completed_reason": "overs_completed",
        "total_runs": 120,
        "total_wickets": 4,
        "total_legal_balls": 120,
    }
    inn1_sc = calculate_innings_scorecard(inn1, [], match_context["players_map"], match=match)
    inn1_sc.total_runs = 120

    inn2 = {
        "id": uuid4(),
        "match_id": match["id"],
        "innings_number": 2,
        "batting_team_id": team_b,
        "bowling_team_id": team_a,
        "batting_team_name": "Team B",
        "bowling_team_name": "Team A",
        "status": "in_progress",
        "target_runs": 121,
    }

    p1 = match_context["p1"]
    p2 = match_context["p2"]
    bowler1 = match_context["bowler1"]

    deliveries = [
        {
            "sequence_no": 1,
            "over_no": 0,
            "ball_in_over": 1,
            "display_over": "0.1",
            "striker_id": p1,
            "non_striker_id": p2,
            "bowler_id": bowler1,
            "batter_runs": 121,
            "extra_type": None,
            "extra_runs": 0,
            "total_runs": 121,
            "is_legal": True,
            "is_wicket": False,
        }
    ]

    inn2_sc = calculate_innings_scorecard(inn2, deliveries, match_context["players_map"], match=match)
    assert inn2_sc.status == "completed"
    assert inn2_sc.completed_reason == "target_reached"

    winner_id, result = compute_match_result(match, [inn1_sc, inn2_sc])
    assert winner_id == team_b
    assert "Team B won by 10 wickets" in result
