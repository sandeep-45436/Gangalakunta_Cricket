"""
Tests for Phase 4 — Automatic Clip Extraction and Player-Wise Assignment.
Validates:
  - Batter-credited four and six qualification
  - Rejection of byes, leg-byes, wides, and voided deliveries
  - Strict player ID derivation from delivery.striker_id
  - Cross-match marker validation and error handling
  - Idempotent job creation and execution
  - Highlight reprocessing with updated trim bounds and version bump
  - Safe trim window clamping against media bounds
  - Real FFmpeg clip and thumbnail extraction against synthetic media
  - Player highlight reel aggregation
"""
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.schemas.highlights import ReprocessHighlightRequest
from app.services import highlights as highlights_svc
from app.services.highlights import (
    check_delivery_qualification,
    find_usable_marker_for_delivery,
)
from app.services.video_processing import (
    calculate_trim_window,
    create_test_video,
    extract_clip_and_thumbnail,
)


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
    db.upload_storage_file = AsyncMock(return_value={"url": "https://storage.test/clip.mp4", "key": "clip.mp4"})
    db.download_storage_file = AsyncMock(return_value=b"test")
    return db


# ── Qualification Rules ───────────────────────────────────────────────────────

def test_check_delivery_qualification_four_and_six():
    # Four credited to batter
    d_four = {"is_batter_boundary": True, "boundary_type": 4, "batter_runs": 4, "is_voided": False}
    qual, ev_type = check_delivery_qualification(d_four)
    assert qual is True
    assert ev_type == "four"

    # Six credited to batter
    d_six = {"is_batter_boundary": True, "boundary_type": 6, "batter_runs": 6, "is_voided": False}
    qual, ev_type = check_delivery_qualification(d_six)
    assert qual is True
    assert ev_type == "six"


def test_check_delivery_qualification_byes_wides_rejected():
    # 4 byes (not batter boundary)
    d_byes = {"is_batter_boundary": False, "boundary_type": 4, "batter_runs": 0, "extra_type": "bye", "extra_runs": 4, "is_voided": False}
    qual, ev_type = check_delivery_qualification(d_byes)
    assert qual is False
    assert ev_type is None

    # Wide 4 (extra 4, not batter boundary)
    d_wide = {"is_batter_boundary": False, "extra_type": "wide", "extra_runs": 5, "is_voided": False}
    qual, ev_type = check_delivery_qualification(d_wide)
    assert qual is False
    assert ev_type is None

    # Overthrow boundary where not credited to batter
    d_overthrow = {"is_batter_boundary": False, "boundary_type": 4, "batter_runs": 1, "is_voided": False}
    qual, ev_type = check_delivery_qualification(d_overthrow)
    assert qual is False
    assert ev_type is None


def test_check_delivery_qualification_voided_rejected():
    d_voided = {"is_batter_boundary": True, "boundary_type": 6, "batter_runs": 6, "is_voided": True}
    qual, ev_type = check_delivery_qualification(d_voided)
    assert qual is False
    assert ev_type is None


# ── Strict Player Assignment ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_player_assignment_uses_striker_id_strictly(mock_db):
    match_id = str(uuid4())
    innings_id = str(uuid4())
    striker_id = str(uuid4())
    non_striker_id = str(uuid4())
    bowler_id = str(uuid4())
    delivery_id = str(uuid4())
    marker_id = str(uuid4())

    delivery_row = {
        "id": delivery_id,
        "match_id": match_id,
        "innings_id": innings_id,
        "striker_id": striker_id,
        "non_striker_id": non_striker_id,
        "bowler_id": bowler_id,
        "is_batter_boundary": True,
        "boundary_type": 4,
        "batter_runs": 4,
        "display_over": "4.2",
        "over_no": 4,
        "ball_in_over": 2,
        "is_voided": False,
    }

    marker_row = {
        "id": marker_id,
        "match_id": match_id,
        "elapsed_ms": 15000,
        "segment_offset_ms": 15000,
        "status": "linked",
    }

    mock_db.select_one.side_effect = lambda table, filters: {
        "deliveries": delivery_row if "id" in filters else None,
        "highlight_jobs": None,
        "event_markers": marker_row,
        "players": {"id": striker_id, "display_name": "V. Kohli"},
        "player_highlights": None,
    }.get(table)

    mock_db.insert_as_user.side_effect = lambda table, rows, token: [
        {**rows[0], "id": str(uuid4())}
    ]

    res = await highlights_svc.create_or_get_highlight_job(
        db=mock_db,
        delivery_id=delivery_id,
        token="token-abc",
        marker_id=marker_id,
    )

    # Assert that player_id in highlight is strictly derived from striker_id
    assert res["player_id"] == striker_id
    assert res["player_id"] != non_striker_id
    assert res["player_id"] != bowler_id
    assert res["event_type"] == "four"
    assert res["status"] == "pending"


# ── Marker Validation & Cross-match Protection ───────────────────────────────

@pytest.mark.asyncio
async def test_marker_validation_rejects_cross_match_marker(mock_db):
    match_a = str(uuid4())
    match_b = str(uuid4())
    delivery = {"id": str(uuid4()), "match_id": match_a, "is_batter_boundary": True, "boundary_type": 4}
    marker_from_other_match = {"id": str(uuid4()), "match_id": match_b, "elapsed_ms": 10000}

    mock_db.select_one.return_value = marker_from_other_match

    with pytest.raises(HTTPException) as exc_info:
        await find_usable_marker_for_delivery(mock_db, delivery, explicit_marker_id=marker_from_other_match["id"])
    assert exc_info.value.status_code == 400
    assert "different match" in exc_info.value.detail


# ── Trim Window Clamping ─────────────────────────────────────────────────────

def test_trim_window_clamping_calculations():
    # Early marker clamped at 0.0
    w_early = calculate_trim_window(marker_sec=2.0, media_duration=30.0, config_before_sec=4.0, config_after_sec=5.0)
    assert w_early["start_sec"] == 0.0
    assert w_early["end_sec"] == 7.0
    assert w_early["duration_sec"] == 7.0

    # Late marker clamped at media_duration
    w_late = calculate_trim_window(marker_sec=28.0, media_duration=30.0, config_before_sec=4.0, config_after_sec=5.0)
    assert w_late["start_sec"] == 24.0
    assert w_late["end_sec"] == 30.0
    assert w_late["duration_sec"] == 6.0

    # Normal middle marker
    w_mid = calculate_trim_window(marker_sec=15.0, media_duration=60.0, config_before_sec=4.0, config_after_sec=5.0)
    assert w_mid["start_sec"] == 11.0
    assert w_mid["end_sec"] == 20.0
    assert w_mid["duration_sec"] == 9.0


# ── Idempotency & Reprocessing ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_or_get_highlight_job_idempotency(mock_db):
    delivery_id = str(uuid4())
    existing_job = {
        "id": str(uuid4()),
        "delivery_id": delivery_id,
        "status": "processing",
        "version": 1,
    }
    delivery_row = {
        "id": delivery_id,
        "match_id": str(uuid4()),
        "innings_id": str(uuid4()),
        "striker_id": str(uuid4()),
        "is_batter_boundary": True,
        "boundary_type": 6,
        "is_voided": False,
    }

    marker_id = str(uuid4())
    mock_db.select_one.side_effect = lambda table, filters: {
        "deliveries": delivery_row,
        "highlight_jobs": existing_job,
        "event_markers": {"id": marker_id, "match_id": delivery_row["match_id"]},
        "player_highlights": None,
    }.get(table)

    res = await highlights_svc.create_or_get_highlight_job(
        db=mock_db,
        delivery_id=delivery_id,
        token="test-token",
        marker_id=marker_id,
    )
    assert res["id"] == existing_job["id"]
    mock_db.insert_as_user.assert_not_called()



@pytest.mark.asyncio
async def test_reprocess_highlight_bumps_version(mock_db):
    highlight_id = str(uuid4())
    delivery_id = str(uuid4())
    marker_id = str(uuid4())

    hl_row = {
        "id": highlight_id,
        "delivery_id": delivery_id,
        "match_id": str(uuid4()),
        "player_id": str(uuid4()),
        "event_type": "four",
        "version": 1,
        "marker_id": marker_id,
    }
    deliv_row = {
        "id": delivery_id,
        "match_id": hl_row["match_id"],
    }
    marker_row = {
        "id": marker_id,
        "match_id": hl_row["match_id"],
    }

    mock_db.select_one.side_effect = lambda table, filters: {
        "player_highlights": hl_row,
        "deliveries": deliv_row,
        "event_markers": marker_row,
    }.get(table)

    mock_db.insert_as_user.return_value = [{"id": str(uuid4()), "version": 2, "status": "pending"}]
    mock_db.update_as_user.return_value = [{**hl_row, "version": 2, "status": "pending"}]

    req = ReprocessHighlightRequest(config_before_sec=5.0, config_after_sec=6.0)
    res = await highlights_svc.reprocess_highlight(
        db=mock_db,
        highlight_id=highlight_id,
        token="tok",
        data=req,
    )

    assert res["version"] == 2
    assert res["status"] == "pending"
    # Ensure insert_as_user was called with new job at version 2
    mock_db.insert_as_user.assert_called_once()
    assert mock_db.insert_as_user.call_args[0][1][0]["version"] == 2


# ── Player Reel Aggregation ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_player_highlight_reel_aggregation(mock_db):
    player_id = str(uuid4())
    match_id = str(uuid4())
    innings_id = str(uuid4())

    mock_db.select_one.return_value = {"id": player_id, "display_name": "R. Sharma"}
    mock_db.select.return_value = [
        {
            "id": str(uuid4()),
            "match_id": match_id,
            "innings_id": innings_id,
            "delivery_id": str(uuid4()),
            "player_id": player_id,
            "event_type": "six",
            "status": "ready",
            "video_url": "https://storage.test/six1.mp4",
            "thumbnail_url": "https://storage.test/six1.jpg",
            "duration_sec": 9.0,
            "delivery_metadata": {"over_display": "1.4", "batter_runs": 6},
            "version": 1,
            "created_at": "2026-10-12T10:00:00Z",
            "updated_at": "2026-10-12T10:00:00Z",
        },
        {
            "id": str(uuid4()),
            "match_id": match_id,
            "innings_id": innings_id,
            "delivery_id": str(uuid4()),
            "player_id": player_id,
            "event_type": "four",
            "status": "ready",
            "video_url": "https://storage.test/four1.mp4",
            "thumbnail_url": "https://storage.test/four1.jpg",
            "duration_sec": 8.0,
            "delivery_metadata": {"over_display": "3.1", "batter_runs": 4},
            "version": 1,
            "created_at": "2026-10-12T10:05:00Z",
            "updated_at": "2026-10-12T10:05:00Z",
        },
    ]

    reel = await highlights_svc.get_player_highlight_reel(mock_db, player_id)
    assert reel.player_name == "R. Sharma"
    assert reel.total_highlights == 2
    assert reel.fours_count == 1
    assert reel.sixes_count == 1


# ── FFmpeg Extraction Real Test with Synthetic Source ────────────────────────

def test_ffmpeg_synthetic_clip_extraction():
    with tempfile.TemporaryDirectory() as tmp_dir:
        src_path = os.path.join(tmp_dir, "test_source.mp4")
        create_test_video(src_path, duration_sec=8.0)
        assert os.path.exists(src_path)

        result = extract_clip_and_thumbnail(
            input_path=src_path,
            marker_sec=4.0,
            config_before_sec=2.0,
            config_after_sec=2.0,
            output_dir=tmp_dir,
            base_name="hl_test",
        )

        assert os.path.exists(result["clip_path"])
        assert os.path.getsize(result["clip_path"]) > 0
        assert result["thumbnail_path"] is not None
        assert os.path.exists(result["thumbnail_path"])
        assert os.path.getsize(result["thumbnail_path"]) > 0
        assert result["duration_sec"] == pytest.approx(4.0, 0.1)
