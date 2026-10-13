"""
Tests for scoring service: idempotency, delivery recording, voiding,
corrections, and innings termination.
"""
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.schemas.scoring import DeliveryCreate, DeliveryUpdate, DeliveryVoidRequest, InningsStartRequest
from app.services import scoring as scoring_svc


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.select = AsyncMock(return_value=[])
    db.select_one = AsyncMock(return_value=None)
    db.insert = AsyncMock(return_value=[])
    db.insert_as_user = AsyncMock(return_value=[])
    db.update = AsyncMock(return_value=[])
    db.update_as_user = AsyncMock(return_value=[])
    return db


@pytest.mark.asyncio
async def test_idempotent_delivery_submission(mock_db):
    """Submitting the same idempotency_key returns the existing delivery without re-inserting."""
    innings_id = str(uuid4())
    match_id = str(uuid4())
    key = "mobile-req-abc-123"

    mock_db.select_one.side_effect = [
        # get_innings
        {"id": innings_id, "match_id": match_id, "status": "in_progress", "total_runs": 10, "total_wickets": 0},
        # select match
        {"id": match_id, "title": "Match 1", "format": "T20"},
        # idempotency check found existing delivery!
        {
            "id": str(uuid4()),
            "innings_id": innings_id,
            "idempotency_key": key,
            "sequence_no": 1,
            "total_runs": 4,
            "batter_runs": 4,
        },
    ]

    req = DeliveryCreate(
        striker_id=uuid4(),
        non_striker_id=uuid4(),
        bowler_id=uuid4(),
        batter_runs=4,
        idempotency_key=key,
    )

    result = await scoring_svc.record_delivery(mock_db, innings_id, req, "test-token")
    assert result["idempotency_key"] == key
    # insert_as_user should NOT have been called because existing delivery was returned
    mock_db.insert_as_user.assert_not_called()


@pytest.mark.asyncio
async def test_record_delivery_success_and_state_update(mock_db):
    """Recording a delivery inserts into deliveries and updates innings totals."""
    innings_id = str(uuid4())
    match_id = str(uuid4())
    p1 = uuid4()
    p2 = uuid4()
    bowler = uuid4()

    mock_db.select_one.side_effect = [
        # get_innings
        {
            "id": innings_id,
            "match_id": match_id,
            "status": "in_progress",
            "total_runs": 0,
            "total_wickets": 0,
            "total_legal_balls": 0,
        },
        # select match
        {"id": match_id, "overs_per_innings": 20},
        # idempotency check -> none found
        None,
    ]
    # existing deliveries -> empty
    mock_db.select.return_value = []

    inserted_delivery = {
        "id": str(uuid4()),
        "innings_id": innings_id,
        "sequence_no": 1,
        "total_runs": 1,
        "is_legal": True,
    }
    mock_db.insert_as_user.return_value = [inserted_delivery]
    mock_db.update_as_user.return_value = [{"id": innings_id}]

    req = DeliveryCreate(
        striker_id=p1,
        non_striker_id=p2,
        bowler_id=bowler,
        batter_runs=1,
    )

    res = await scoring_svc.record_delivery(mock_db, innings_id, req, "test-token")
    assert res["sequence_no"] == 1
    mock_db.insert_as_user.assert_called_once()
    mock_db.update_as_user.assert_called_once()

    # Check innings updated values: single was taken -> strikers rotated!
    call_args = mock_db.update_as_user.call_args[0]
    update_payload = call_args[2]
    assert update_payload["total_runs"] == 1
    assert update_payload["total_legal_balls"] == 1
    assert update_payload["current_striker_id"] == str(p2)
    assert update_payload["current_non_striker_id"] == str(p1)


@pytest.mark.asyncio
async def test_void_delivery_resyncs_totals(mock_db):
    """Voiding a delivery marks is_voided=True and recomputes innings totals from remaining balls."""
    delivery_id = str(uuid4())
    innings_id = str(uuid4())
    p1 = str(uuid4())
    p2 = str(uuid4())

    mock_db.select_one.side_effect = [
        # select delivery
        {
            "id": delivery_id,
            "innings_id": innings_id,
            "revision_no": 1,
            "is_voided": False,
        },
        # get_innings in resync
        {
            "id": innings_id,
            "current_striker_id": p1,
            "current_non_striker_id": p2,
        },
    ]

    mock_db.update_as_user.return_value = [{"id": delivery_id, "is_voided": True, "revision_no": 2}]
    # select remaining deliveries in resync -> delivery is now voided
    mock_db.select.return_value = [
        {"id": delivery_id, "total_runs": 6, "is_voided": True, "is_legal": True},
        {"id": str(uuid4()), "total_runs": 1, "is_voided": False, "is_legal": True},
    ]

    req = DeliveryVoidRequest(reason="Scorer hit 6 instead of 1")
    res = await scoring_svc.void_delivery(mock_db, delivery_id, req, "test-token")
    assert res["is_voided"] is True
    assert res["revision_no"] == 2

    # Verify update_as_user was called for deliveries and innings
    assert mock_db.update_as_user.call_count == 2
    innings_update = mock_db.update_as_user.call_args_list[1][0][2]
    assert innings_update["total_runs"] == 1  # 6 was voided, only 1 remains!
    assert innings_update["total_legal_balls"] == 1
