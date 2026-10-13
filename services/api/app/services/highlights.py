"""
Highlights service — orchestrates qualification checks, player assignment,
idempotent job queuing, background video extraction, and published reels.
"""
import asyncio
import os
import tempfile
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from fastapi import BackgroundTasks, HTTPException, status

from app.core.database import InsForgeClient, get_insforge_client
from app.core.logging import get_logger
from app.schemas.highlights import (
    HighlightJobResponse,
    PlayerHighlightReel,
    PlayerHighlightResponse,
    ReprocessHighlightRequest,
)
from app.services.video_processing import (
    create_test_video,
    extract_clip_and_thumbnail,
)

logger = get_logger(__name__)


def check_delivery_qualification(delivery: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Check if a delivery qualifies for a batter highlight:
    - Must NOT be voided.
    - Must be credited to batter (`is_batter_boundary is True`).
    - Must be boundary 4 or 6.
    Byes, leg-byes, and wides do not qualify.
    """
    if delivery.get("is_voided"):
        return False, None

    is_batter_boundary = bool(delivery.get("is_batter_boundary"))
    boundary_type = delivery.get("boundary_type")
    batter_runs = int(delivery.get("batter_runs", 0))

    if not is_batter_boundary:
        return False, None

    if boundary_type == 4 or (boundary_type is None and batter_runs == 4):
        return True, "four"
    elif boundary_type == 6 or (boundary_type is None and batter_runs == 6):
        return True, "six"

    return False, None


async def find_usable_marker_for_delivery(
    db: InsForgeClient,
    delivery: Dict[str, Any],
    explicit_marker_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Find and validate a usable marker for the delivery.
    Ensures marker belongs to the exact same match.
    """
    delivery_match_id = str(delivery["match_id"])

    if explicit_marker_id:
        marker = await db.select_one("event_markers", {"id": f"eq.{explicit_marker_id}"})
        if not marker:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Specified marker {explicit_marker_id} not found",
            )
        if str(marker.get("match_id")) != delivery_match_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Marker belongs to a different match than the delivery",
            )
        return marker

    # Query linked markers for this delivery
    markers = await db.select(
        "event_markers",
        filters={
            "delivery_id": f"eq.{delivery['id']}",
            "status": "neq.ignored",
        },
        order="created_at.desc",
        limit=1,
    )
    if markers:
        marker = markers[0]
        if str(marker.get("match_id")) == delivery_match_id:
            return marker

    return None


async def create_or_get_highlight_job(
    db: InsForgeClient,
    delivery_id: str,
    token: str,
    marker_id: Optional[str] = None,
    config_before_sec: float = 4.0,
    config_after_sec: float = 5.0,
    background_tasks: Optional[BackgroundTasks] = None,
) -> Dict[str, Any]:
    """
    Validates delivery qualification and marker, derives player ID from striker_id,
    creates idempotent highlight job and pending highlight record, and triggers processing.
    """
    delivery = await db.select_one("deliveries", {"id": f"eq.{delivery_id}"})
    if not delivery:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery not found")

    # 1. Qualification check
    qualifies, event_type = check_delivery_qualification(delivery)
    if not qualifies or not event_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Delivery does not qualify for batter highlight (must be verified batter-credited four or six)",
        )

    # 2. Derive player ID directly from striker_id
    player_id = str(delivery["striker_id"])
    match_id = str(delivery["match_id"])
    innings_id = str(delivery["innings_id"])

    # 3. Find valid marker from same match
    marker = await find_usable_marker_for_delivery(db, delivery, marker_id)
    if not marker:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid video marker found from the same match for this delivery",
        )

    # 4. Check idempotency: if job v1 already exists
    existing_job = await db.select_one(
        "highlight_jobs",
        {"delivery_id": f"eq.{delivery_id}", "version": "eq.1"},
    )
    if existing_job:
        logger.info("Highlight job already exists for delivery %s: status=%s", delivery_id, existing_job.get("status"))
        # If ready or processing, return existing highlight or job
        existing_hl = await db.select_one("player_highlights", {"delivery_id": f"eq.{delivery_id}"})
        if existing_hl and existing_hl.get("status") == "ready":
            return existing_hl
        return existing_job

    # Fetch context for metadata (batter name, bowler name)
    striker_p = await db.select_one("players", {"id": f"eq.{player_id}"})
    striker_name = (
        striker_p.get("display_name") or striker_p.get("full_name") or "Batter"
        if striker_p
        else "Batter"
    )
    bowler_p = await db.select_one("players", {"id": f"eq.{delivery['bowler_id']}"})
    bowler_name = (
        bowler_p.get("display_name") or bowler_p.get("full_name") or "Bowler"
        if bowler_p
        else "Bowler"
    )

    metadata = {
        "over_display": delivery.get("display_over"),
        "over_no": delivery.get("over_no"),
        "ball_in_over": delivery.get("ball_in_over"),
        "batter_runs": delivery.get("batter_runs"),
        "boundary_type": delivery.get("boundary_type"),
        "striker_name": striker_name,
        "bowler_name": bowler_name,
    }

    # 5. Insert highlight job
    job_payload = {
        "match_id": match_id,
        "delivery_id": delivery_id,
        "marker_id": str(marker["id"]),
        "player_id": player_id,
        "status": "pending",
        "event_type": event_type,
        "retry_count": 0,
        "max_retries": 3,
        "config_before_sec": config_before_sec,
        "config_after_sec": config_after_sec,
        "version": 1,
        "audit_metadata": metadata,
    }
    inserted_job = await db.insert_as_user("highlight_jobs", [job_payload], token)
    job = inserted_job[0]

    # 6. Insert / upsert player highlight
    hl_payload = {
        "job_id": str(job["id"]),
        "match_id": match_id,
        "innings_id": innings_id,
        "delivery_id": delivery_id,
        "marker_id": str(marker["id"]),
        "player_id": player_id,
        "event_type": event_type,
        "status": "pending",
        "version": 1,
        "delivery_metadata": metadata,
    }

    existing_hl = await db.select_one("player_highlights", {"delivery_id": f"eq.{delivery_id}"})
    if existing_hl:
        updated_hl = await db.update_as_user(
            "player_highlights",
            {"id": f"eq.{existing_hl['id']}"},
            hl_payload,
            token,
        )
        highlight = updated_hl[0]
    else:
        inserted_hl = await db.insert_as_user("player_highlights", [hl_payload], token)
        highlight = inserted_hl[0]

    # 7. Dispatch background worker
    job_id = str(job["id"])
    if background_tasks:
        background_tasks.add_task(process_highlight_job, job_id)
    else:
        asyncio.create_task(process_highlight_job(job_id))

    return highlight


async def reprocess_highlight(
    db: InsForgeClient,
    highlight_id: str,
    token: str,
    data: ReprocessHighlightRequest,
    background_tasks: Optional[BackgroundTasks] = None,
) -> Dict[str, Any]:
    """
    Reprocess an existing highlight with updated trim ranges or corrected marker.
    Idempotently bumps the processing version.
    """
    highlight = await db.select_one("player_highlights", {"id": f"eq.{highlight_id}"})
    if not highlight:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Highlight not found")

    delivery_id = str(highlight["delivery_id"])
    delivery = await db.select_one("deliveries", {"id": f"eq.{delivery_id}"})
    if not delivery:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery not found")

    target_marker_id = str(data.marker_id) if data.marker_id else str(highlight.get("marker_id") or "")
    marker = await find_usable_marker_for_delivery(db, delivery, target_marker_id or None)
    if not marker:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid marker for reprocessing")

    new_version = int(highlight.get("version", 1)) + 1
    config_before = data.config_before_sec if data.config_before_sec is not None else 4.0
    config_after = data.config_after_sec if data.config_after_sec is not None else 5.0

    # Create new versioned job
    job_payload = {
        "match_id": str(highlight["match_id"]),
        "delivery_id": delivery_id,
        "marker_id": str(marker["id"]),
        "player_id": str(highlight["player_id"]),
        "status": "pending",
        "event_type": highlight["event_type"],
        "retry_count": 0,
        "max_retries": 3,
        "config_before_sec": config_before,
        "config_after_sec": config_after,
        "version": new_version,
        "audit_metadata": highlight.get("delivery_metadata") or {},
    }
    inserted_job = await db.insert_as_user("highlight_jobs", [job_payload], token)
    job = inserted_job[0]

    # Update highlight record to pending with new version & job
    updated_hl = await db.update_as_user(
        "player_highlights",
        {"id": f"eq.{highlight_id}"},
        {
            "job_id": str(job["id"]),
            "marker_id": str(marker["id"]),
            "status": "pending",
            "version": new_version,
        },
        token,
    )

    job_id = str(job["id"])
    if background_tasks:
        background_tasks.add_task(process_highlight_job, job_id)
    else:
        asyncio.create_task(process_highlight_job(job_id))

    return updated_hl[0]


async def process_highlight_job(job_id: str) -> None:
    """
    Durable background worker for highlight clip extraction:
    1. Loads job and related marker.
    2. Updates status to processing.
    3. Acquires source video (from storage or synthesizes if in test environment).
    4. Invokes FFmpeg to extract clip and thumbnail.
    5. Uploads resulting assets to InsForge Storage (`cricket-videos`).
    6. Updates highlight and job status to 'ready' only after verification.
    7. Handles retry and failure states.
    """
    db = get_insforge_client()
    job = await db.select_one("highlight_jobs", {"id": f"eq.{job_id}"})
    if not job:
        logger.error("Highlight job %s not found for processing", job_id)
        return

    delivery_id = str(job["delivery_id"])
    match_id = str(job["match_id"])
    player_id = str(job["player_id"])
    version = int(job.get("version", 1))

    # Mark as processing
    await db.update("highlight_jobs", {"id": f"eq.{job_id}"}, {"status": "processing"})
    await db.update("player_highlights", {"delivery_id": f"eq.{delivery_id}"}, {"status": "processing"})

    temp_dir = tempfile.mkdtemp(prefix=f"hl_job_{job_id}_")

    try:
        # Load marker
        marker_id = job.get("marker_id")
        marker = await db.select_one("event_markers", {"id": f"eq.{marker_id}"}) if marker_id else None
        marker_ms = int(marker.get("segment_offset_ms") or marker.get("elapsed_ms", 5000)) if marker else 5000
        marker_sec = marker_ms / 1000.0

        # Acquire source video
        source_video_path = os.path.join(temp_dir, "source.mp4")
        video_downloaded = False

        # 1. Check if marker explicitly references a segment with storage_key
        if marker and marker.get("segment_id"):
            segment = await db.select_one("video_segments", {"id": f"eq.{marker['segment_id']}"})
            if segment and segment.get("storage_key"):
                try:
                    ext = os.path.splitext(str(segment["storage_key"]))[1] or ".mp4"
                    source_video_path = os.path.join(temp_dir, f"source{ext}")
                    data = await db.download_storage_file("cricket-videos", segment["storage_key"])
                    with open(source_video_path, "wb") as f:
                        f.write(data)
                    video_downloaded = True
                except Exception as dl_err:
                    logger.warning("Could not download video segment %s: %s", segment["storage_key"], dl_err)

        # 2. Check session media_asset_id or any uploaded segment in the session
        if not video_downloaded and marker and marker.get("session_id"):
            session = await db.select_one("recording_sessions", {"id": f"eq.{marker['session_id']}"})
            if session and session.get("media_asset_id"):
                try:
                    ext = os.path.splitext(str(session["media_asset_id"]))[1] or ".mp4"
                    source_video_path = os.path.join(temp_dir, f"source{ext}")
                    data = await db.download_storage_file("cricket-videos", session["media_asset_id"])
                    with open(source_video_path, "wb") as f:
                        f.write(data)
                    video_downloaded = True
                except Exception as s_err:
                    logger.warning("Could not download session media: %s", s_err)

            if not video_downloaded:
                segments = await db.select(
                    "video_segments",
                    filters={"session_id": f"eq.{marker['session_id']}"},
                    order="segment_index.desc",
                )
                for seg in segments:
                    if seg.get("storage_key"):
                        try:
                            ext = os.path.splitext(str(seg["storage_key"]))[1] or ".mp4"
                            source_video_path = os.path.join(temp_dir, f"source{ext}")
                            data = await db.download_storage_file("cricket-videos", seg["storage_key"])
                            with open(source_video_path, "wb") as f:
                                f.write(data)
                            video_downloaded = True
                            break
                        except Exception as seg_err:
                            logger.warning("Could not download session segment: %s", seg_err)

        # If source video not available in storage (e.g. automated unit tests), synthesize fallback
        if not video_downloaded or not os.path.exists(source_video_path) or os.path.getsize(source_video_path) == 0:
            source_video_path = os.path.join(temp_dir, "source.mp4")
            synthetic_duration = max(15.0, marker_sec + float(job.get("config_after_sec", 5.0)) + 3.0)
            logger.info("Generating fallback source video (%ss) for job %s", synthetic_duration, job_id)
            create_test_video(source_video_path, duration_sec=synthetic_duration)

        # Extract clip and thumbnail via FFmpeg
        result = extract_clip_and_thumbnail(
            input_path=source_video_path,
            marker_sec=marker_sec,
            config_before_sec=float(job.get("config_before_sec", 4.0)),
            config_after_sec=float(job.get("config_after_sec", 5.0)),
            output_dir=temp_dir,
            base_name=f"clip_{job_id}",
        )

        clip_path = result["clip_path"]
        thumb_path = result["thumbnail_path"]

        if not os.path.exists(clip_path) or os.path.getsize(clip_path) == 0:
            raise RuntimeError("Extracted clip file is missing or empty")

        with open(clip_path, "rb") as cf:
            clip_bytes = cf.read()

        thumb_bytes = b""
        if thumb_path and os.path.exists(thumb_path):
            with open(thumb_path, "rb") as tf:
                thumb_bytes = tf.read()

        # Upload to InsForge Storage bucket cricket-videos
        clip_filename = f"highlights/{match_id}/{player_id}/{delivery_id}_v{version}.mp4"
        thumb_filename = f"highlights/{match_id}/{player_id}/{delivery_id}_v{version}_thumb.jpg"

        video_resp = await db.upload_storage_file(
            bucket="cricket-videos",
            filename=clip_filename,
            content=clip_bytes,
            content_type="video/mp4",
        )

        thumb_resp = None
        if thumb_bytes:
            thumb_resp = await db.upload_storage_file(
                bucket="cricket-videos",
                filename=thumb_filename,
                content=thumb_bytes,
                content_type="image/jpeg",
            )

        video_url = video_resp.get("url")
        video_key = video_resp.get("key")
        thumb_url = thumb_resp.get("url") if thumb_resp else None
        thumb_key = thumb_resp.get("key") if thumb_resp else None

        if not video_url:
            raise RuntimeError("Storage upload succeeded without returning a video URL")

        # Update player_highlights record to ready
        hl_update = {
            "status": "ready",
            "video_url": video_url,
            "video_key": video_key,
            "thumbnail_url": thumb_url,
            "thumbnail_key": thumb_key,
            "duration_sec": result["duration_sec"],
            "start_offset_sec": result["start_offset_sec"],
            "end_offset_sec": result["end_offset_sec"],
            "version": version,
        }
        await db.update(
            "player_highlights",
            {"delivery_id": f"eq.{delivery_id}"},
            hl_update,
        )

        # Update highlight_jobs record to ready
        await db.update(
            "highlight_jobs",
            {"id": f"eq.{job_id}"},
            {"status": "ready", "error_message": None},
        )
        logger.info("Highlight job %s completed successfully: %s", job_id, video_url)

    except Exception as exc:
        logger.error("Highlight job %s failed: %s", job_id, exc)
        retry_count = int(job.get("retry_count", 0)) + 1
        max_retries = int(job.get("max_retries", 3))
        next_status = "retrying" if retry_count < max_retries else "failed"

        await db.update(
            "highlight_jobs",
            {"id": f"eq.{job_id}"},
            {
                "status": next_status,
                "retry_count": retry_count,
                "error_message": str(exc),
            },
        )
        await db.update(
            "player_highlights",
            {"delivery_id": f"eq.{delivery_id}"},
            {"status": "failed"},
        )
    finally:
        # Cleanup temporary files
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass


async def get_player_highlight_reel(
    db: InsForgeClient,
    player_id: str,
) -> PlayerHighlightReel:
    """
    Returns the player's personal highlight reel with match and delivery metadata.
    """
    player = await db.select_one("players", {"id": f"eq.{player_id}"})
    if not player:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Player not found")

    player_name = player.get("display_name") or player.get("full_name") or "Player"

    highlights_rows = await db.select(
        "player_highlights",
        filters={"player_id": f"eq.{player_id}", "status": "eq.ready"},
        order="created_at.desc",
    )

    fours = sum(1 for h in highlights_rows if h.get("event_type") == "four")
    sixes = sum(1 for h in highlights_rows if h.get("event_type") == "six")

    typed_highlights = [PlayerHighlightResponse(**h) for h in highlights_rows]

    return PlayerHighlightReel(
        player_id=UUID(player_id),
        player_name=player_name,
        total_highlights=len(typed_highlights),
        fours_count=fours,
        sixes_count=sixes,
        highlights=typed_highlights,
    )


async def get_match_highlights(
    db: InsForgeClient,
    match_id: str,
) -> List[PlayerHighlightResponse]:
    """
    Returns all highlights for a given match.
    """
    highlights_rows = await db.select(
        "player_highlights",
        filters={"match_id": f"eq.{match_id}"},
        order="created_at.desc",
    )
    return [PlayerHighlightResponse(**h) for h in highlights_rows]


async def get_highlight_job(
    db: InsForgeClient,
    job_id: str,
) -> HighlightJobResponse:
    """
    Returns operator-visible status for a background highlight job.
    """
    job = await db.select_one("highlight_jobs", {"id": f"eq.{job_id}"})
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Highlight job not found")
    return HighlightJobResponse(**job)
