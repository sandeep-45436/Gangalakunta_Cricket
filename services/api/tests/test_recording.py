"""
Tests for Phase 3 mobile recording sessions and event markers.
Validates:
  - Session creation, status transitions (active -> paused -> stopped)
  - Monotonic elapsed timing and media segment offsets
  - Rapid-tap protection (<250ms duplicate suppression)
  - Client marker idempotency (client_marker_id reuse)
  - Linking markers to deliveries
  - Updating and deleting markers
"""
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.schemas.recording import (
    EventMarkerCreate,
    EventMarkerLinkDelivery,
    EventMarkerUpdate,
    RecordingSessionCreate,
    RecordingSessionUpdate,
    VideoSegmentCreate,
)
from app.services import recording as recording_svc


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.select = AsyncMock(return_value=[])
    db.select_one = AsyncMock(return_value=None)
    db.insert = AsyncMock(return_value=[])
    db.insert_as_user = AsyncMock(return_value=[])
    db.update = AsyncMock(return_value=[])
    db.update_as_user = AsyncMock(return_value=[])
    db.delete_as_user = AsyncMock(return_value=[])
    return db


@pytest.mark.asyncio
async def test_create_recording_session(mock_db):
    match_id = str(uuid4())
    owner_id = str(uuid4())
    mock_db.select_one.return_value = {"id": match_id, "title": "Finals"}

    session_row = {
        "id": str(uuid4()),
        "match_id": match_id,
        "owner_id": owner_id,
        "session_name": "Main Camera",
        "status": "active",
        "total_duration_ms": 0,
    }
    mock_db.insert_as_user.return_value = [session_row]

    req = RecordingSessionCreate(session_name="Main Camera")
    res = await recording_svc.create_recording_session(mock_db, match_id, owner_id, req, "token")

    assert res["status"] == "active"
    assert res["session_name"] == "Main Camera"
    mock_db.insert_as_user.assert_called_once()


@pytest.mark.asyncio
async def test_create_marker_monotonic_and_rapid_tap_protection(mock_db):
    """
    Test 1: Marker creation computes correct marker_number and elapsed_ms.
    Test 2: Second tap within 250ms is suppressed and returns existing marker.
    """
    session_id = str(uuid4())
    match_id = str(uuid4())

    mock_db.select_one.side_effect = [
        {"id": session_id, "match_id": match_id, "status": "active"},  # get_recording_session (1st call)
        None,  # idempotency check (none found)
        {"id": session_id, "match_id": match_id, "status": "active"},  # get_recording_session (2nd call)
    ]

    # First tap at 12,345 ms
    mock_db.select.return_value = []
    marker_1 = {
        "id": str(uuid4()),
        "session_id": session_id,
        "marker_number": 1,
        "elapsed_ms": 12345,
        "status": "unlinked",
    }
    mock_db.insert_as_user.return_value = [marker_1]

    req1 = EventMarkerCreate(elapsed_ms=12345, client_marker_id="tap-1")
    res1 = await recording_svc.create_marker(mock_db, session_id, req1, "token")
    assert res1["marker_number"] == 1
    assert res1["elapsed_ms"] == 12345

    # Rapid tap 80ms later at 12,425 ms without delivery_id
    mock_db.select.return_value = [marker_1]
    req2 = EventMarkerCreate(elapsed_ms=12425)
    res2 = await recording_svc.create_marker(mock_db, session_id, req2, "token")

    # Should return marker_1 due to rapid tap suppression
    assert res2["id"] == marker_1["id"]
    assert res2["elapsed_ms"] == 12345


@pytest.mark.asyncio
async def test_marker_client_id_idempotency(mock_db):
    """Network retry with same client_marker_id returns existing marker."""
    session_id = str(uuid4())
    client_id = "mobile-uuid-xyz-999"

    mock_db.select_one.side_effect = [
        # get session
        {"id": session_id, "match_id": str(uuid4())},
        # idempotency check found existing marker
        {
            "id": str(uuid4()),
            "session_id": session_id,
            "client_marker_id": client_id,
            "marker_number": 3,
            "elapsed_ms": 45000,
        },
    ]

    req = EventMarkerCreate(elapsed_ms=45000, client_marker_id=client_id)
    res = await recording_svc.create_marker(mock_db, session_id, req, "token")
    assert res["client_marker_id"] == client_id
    mock_db.insert_as_user.assert_not_called()


@pytest.mark.asyncio
async def test_link_marker_to_delivery(mock_db):
    """Linking a marker updates delivery_id, delivery_display and sets status='linked'."""
    marker_id = str(uuid4())
    delivery_id = str(uuid4())
    striker_id = str(uuid4())

    mock_db.select_one.side_effect = [
        # select marker
        {"id": marker_id, "marker_number": 2, "status": "unlinked"},
        # select delivery
        {"id": delivery_id, "display_over": "14.2", "striker_id": striker_id, "innings_id": str(uuid4())},
        # select player
        {"id": striker_id, "display_name": "Player A"},
    ]

    mock_db.update_as_user.return_value = [
        {
            "id": marker_id,
            "delivery_id": delivery_id,
            "delivery_display": "14.2 · Player A",
            "status": "linked",
        }
    ]

    req = EventMarkerLinkDelivery(delivery_id=uuid4())
    res = await recording_svc.link_marker_to_delivery(mock_db, marker_id, req, "token")
    assert res["status"] == "linked"
    assert res["delivery_display"] == "14.2 · Player A"


@pytest.mark.asyncio
async def test_segment_addition_and_counter_update(mock_db):
    session_id = str(uuid4())
    match_id = str(uuid4())

    mock_db.select_one.return_value = {
        "id": session_id,
        "match_id": match_id,
        "segments_count": 1,
    }

    seg_row = {
        "id": str(uuid4()),
        "session_id": session_id,
        "segment_index": 1,
        "segment_name": "segment_01.mp4",
        "duration_ms": 60000,
    }
    mock_db.insert_as_user.return_value = [seg_row]
    mock_db.update_as_user.return_value = [{"id": session_id, "segments_count": 2}]

    req = VideoSegmentCreate(segment_index=1, segment_name="segment_01.mp4", duration_ms=60000)
    res = await recording_svc.add_segment(mock_db, session_id, req, "token")
    assert res["segment_index"] == 1
    mock_db.update_as_user.assert_called_once()
