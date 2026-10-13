"""
Tests for scoring Pydantic schema validation rules.
"""
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.scoring import DeliveryCreate, InningsStartRequest


def test_delivery_valid_dot():
    p1, p2, b = uuid4(), uuid4(), uuid4()
    d = DeliveryCreate(
        striker_id=p1,
        non_striker_id=p2,
        bowler_id=b,
        batter_runs=0,
    )
    assert d.batter_runs == 0
    assert d.extra_type is None
    assert d.is_wicket is False


def test_delivery_same_striker_non_striker_rejected():
    p1, b = uuid4(), uuid4()
    with pytest.raises(ValidationError, match="Striker and non-striker must be different"):
        DeliveryCreate(
            striker_id=p1,
            non_striker_id=p1,
            bowler_id=b,
        )


def test_delivery_bowler_is_batter_rejected():
    p1, p2 = uuid4(), uuid4()
    with pytest.raises(ValidationError, match="Bowler cannot be currently batting"):
        DeliveryCreate(
            striker_id=p1,
            non_striker_id=p2,
            bowler_id=p1,
        )


def test_delivery_wide_with_batter_runs_rejected():
    p1, p2, b = uuid4(), uuid4(), uuid4()
    with pytest.raises(ValidationError, match="wide cannot yield batter runs"):
        DeliveryCreate(
            striker_id=p1,
            non_striker_id=p2,
            bowler_id=b,
            batter_runs=2,
            extra_type="wide",
            extra_runs=3,
        )


def test_delivery_bye_with_batter_runs_rejected():
    p1, p2, b = uuid4(), uuid4(), uuid4()
    with pytest.raises(ValidationError, match="bye cannot have batter runs"):
        DeliveryCreate(
            striker_id=p1,
            non_striker_id=p2,
            bowler_id=b,
            batter_runs=1,
            extra_type="bye",
            extra_runs=1,
        )


def test_delivery_wide_minimum_extra_run():
    p1, p2, b = uuid4(), uuid4(), uuid4()
    with pytest.raises(ValidationError, match="wide must yield at least 1 extra run"):
        DeliveryCreate(
            striker_id=p1,
            non_striker_id=p2,
            bowler_id=b,
            extra_type="wide",
            extra_runs=0,
        )


def test_delivery_bowled_striker_auto_assigned_dismissed():
    p1, p2, b = uuid4(), uuid4(), uuid4()
    d = DeliveryCreate(
        striker_id=p1,
        non_striker_id=p2,
        bowler_id=b,
        is_wicket=True,
        wicket_type="bowled",
    )
    assert d.dismissed_player_id == p1


def test_delivery_bowled_non_striker_rejected():
    p1, p2, b = uuid4(), uuid4(), uuid4()
    with pytest.raises(ValidationError, match="can only apply to striker"):
        DeliveryCreate(
            striker_id=p1,
            non_striker_id=p2,
            bowler_id=b,
            is_wicket=True,
            wicket_type="bowled",
            dismissed_player_id=p2,
        )


def test_delivery_run_out_non_striker_allowed():
    p1, p2, b, f = uuid4(), uuid4(), uuid4(), uuid4()
    d = DeliveryCreate(
        striker_id=p1,
        non_striker_id=p2,
        bowler_id=b,
        is_wicket=True,
        wicket_type="run_out",
        dismissed_player_id=p2,
        fielder_id=f,
        runs_completed_before_out=1,
    )
    assert d.dismissed_player_id == p2
    assert d.runs_completed_before_out == 1


def test_innings_start_distinct_teams_and_openers():
    t1, t2 = uuid4(), uuid4()
    p1, p2, b = uuid4(), uuid4(), uuid4()

    # Same team rejected
    with pytest.raises(ValidationError, match="must be distinct"):
        InningsStartRequest(
            innings_number=1,
            batting_team_id=t1,
            bowling_team_id=t1,
            opening_striker_id=p1,
            opening_non_striker_id=p2,
            opening_bowler_id=b,
        )

    # Same openers rejected
    with pytest.raises(ValidationError, match="distinct players"):
        InningsStartRequest(
            innings_number=1,
            batting_team_id=t1,
            bowling_team_id=t2,
            opening_striker_id=p1,
            opening_non_striker_id=p1,
            opening_bowler_id=b,
        )
