"""
Recording and event markers service — Phase 3 video-to-delivery synchronization.
Handles session lifecycle, media segments, monotonic markers, and delivery linking.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.core.database import InsForgeClient
from app.core.logging import get_logger
from app.schemas.recording import (
    EventMarkerCreate,
    EventMarkerLinkDelivery,
    EventMarkerUpdate,
    RecordingSessionCreate,
    RecordingSessionUpdate,
    VideoSegmentCreate,
)

logger = get_logger(__name__)


async def create_recording_session(
    db: InsForgeClient,
    match_id: str,
    owner_id: str,
    data: RecordingSessionCreate,
    token: str,
) -> Dict[str, Any]:
    match = await db.select_one("matches", {"id": f"eq.{match_id}"})
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found")

    payload = {
        "match_id": match_id,
        "owner_id": owner_id,
        "session_name": data.session_name,
        "status": "active",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "total_duration_ms": 0,
        "upload_status": "pending",
        "processing_status": "unprocessed",
        "segments_count": 1,
        "media_metadata": data.media_metadata or {},
    }
    inserted = await db.insert_as_user("recording_sessions", [payload], token)
    return inserted[0]


async def get_recording_session(
    db: InsForgeClient, session_id: str, owner_id: Optional[str] = None
) -> Dict[str, Any]:
    session = await db.select_one("recording_sessions", {"id": f"eq.{session_id}"})
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recording session not found")
    if owner_id and session.get("owner_id") and str(session["owner_id"]) != str(owner_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access another user's private recording session",
        )
    return session


async def list_recording_sessions(
    db: InsForgeClient, match_id: str, owner_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    if owner_id:
        match = await db.select_one("matches", {"id": f"eq.{match_id}"})
        if match and match.get("owner_id") and str(match["owner_id"]) != str(owner_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access recordings for another user's match",
            )
    filters: Dict[str, str] = {"match_id": f"eq.{match_id}"}
    if owner_id:
        filters["owner_id"] = f"eq.{owner_id}"
    return await db.select(
        "recording_sessions",
        filters=filters,
        order="started_at.desc",
    )


async def update_recording_session(
    db: InsForgeClient,
    session_id: str,
    data: RecordingSessionUpdate,
    token: str,
    owner_id: Optional[str] = None,
) -> Dict[str, Any]:
    session = await get_recording_session(db, session_id, owner_id=owner_id)
    payload = {k: v for k, v in data.model_dump().items() if v is not None}
    if not payload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    # If status transitioned to stopped or completed, stamp ended_at
    if data.status in ("stopped", "completed") and session.get("ended_at") is None:
        payload["ended_at"] = datetime.now(timezone.utc).isoformat()

    updated = await db.update_as_user(
        "recording_sessions", {"id": f"eq.{session_id}"}, payload, token
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recording session not found")
    return updated[0]


async def delete_recording_session(
    db: InsForgeClient,
    session_id: str,
    token: str,
    owner_id: Optional[str] = None,
) -> None:
    session = await get_recording_session(db, session_id, owner_id=owner_id)
    # Delete segments and markers associated with this session
    await db.delete_as_user("event_markers", {"session_id": f"eq.{session_id}"}, token)
    await db.delete_as_user("video_segments", {"session_id": f"eq.{session_id}"}, token)
    await db.delete_as_user("recording_sessions", {"id": f"eq.{session_id}"}, token)
    # Log audit event
    if owner_id:
        try:
            await db.insert_as_user(
                "audit_logs",
                [{
                    "actor_id": owner_id,
                    "action": "recording.delete",
                    "resource_type": "recording_session",
                    "resource_id": session_id,
                    "details": {
                        "match_id": str(session.get("match_id")),
                        "session_name": session.get("session_name"),
                    },
                }],
                token,
            )
        except Exception:
            pass


async def add_segment(
    db: InsForgeClient,
    session_id: str,
    data: VideoSegmentCreate,
    token: str,
) -> Dict[str, Any]:
    session = await get_recording_session(db, session_id)
    payload = {
        "session_id": session_id,
        "match_id": str(session["match_id"]),
        "segment_index": data.segment_index,
        "segment_name": data.segment_name,
        "duration_ms": data.duration_ms,
        "storage_key": data.storage_key,
        "storage_url": data.storage_url,
        "upload_status": data.upload_status,
    }
    inserted = await db.insert_as_user("video_segments", [payload], token)

    # Increment segment count on session
    await db.update_as_user(
        "recording_sessions",
        {"id": f"eq.{session_id}"},
        {"segments_count": max(int(session.get("segments_count", 1)), data.segment_index + 1)},
        token,
    )
    return inserted[0]


async def upload_session_video(
    db: InsForgeClient,
    session_id: str,
    filename: str,
    content: bytes,
    content_type: str,
    token: str,
) -> Dict[str, Any]:
    """
    Uploads a real recorded or selected video file to InsForge Storage (`cricket-videos`),
    links it to the recording session and segment, and triggers/reprocesses any linked
    boundary highlights using the real uploaded media.
    """
    session = await get_recording_session(db, session_id)
    match_id = str(session["match_id"])

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded video file is empty",
        )

    import os
    ext = os.path.splitext(filename or "recording.webm")[1] or ".webm"
    storage_filename = f"recordings/{match_id}/{session_id}/source{ext}"

    upload_resp = await db.upload_storage_file(
        bucket="cricket-videos",
        filename=storage_filename,
        content=content,
        content_type=content_type or "video/webm",
    )

    storage_key = upload_resp.get("key")
    storage_url = upload_resp.get("url")
    if not storage_key or not storage_url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to store video file in InsForge Storage",
        )

    # Update recording session with uploaded media asset
    updated_sessions = await db.update_as_user(
        "recording_sessions",
        {"id": f"eq.{session_id}"},
        {
            "media_asset_id": storage_key,
            "media_url": storage_url,
            "upload_status": "uploaded",
        },
        token,
    )
    updated_session = updated_sessions[0] if updated_sessions else session

    # Upsert segment 0 for this session
    existing_seg = await db.select_one(
        "video_segments",
        {"session_id": f"eq.{session_id}", "segment_index": "eq.0"},
    )
    if existing_seg:
        seg_rows = await db.update_as_user(
            "video_segments",
            {"id": f"eq.{existing_seg['id']}"},
            {
                "storage_key": storage_key,
                "storage_url": storage_url,
                "upload_status": "uploaded",
            },
            token,
        )
        segment = seg_rows[0]
    else:
        seg_rows = await db.insert_as_user(
            "video_segments",
            [
                {
                    "session_id": session_id,
                    "match_id": match_id,
                    "segment_index": 0,
                    "segment_name": filename or f"session_{session_id}{ext}",
                    "duration_ms": int(updated_session.get("total_duration_ms") or 0),
                    "storage_key": storage_key,
                    "storage_url": storage_url,
                    "upload_status": "uploaded",
                }
            ],
            token,
        )
        segment = seg_rows[0]

    # Trigger or reprocess highlights for any linked boundary markers in this session
    try:
        from app.schemas.highlights import ReprocessHighlightRequest
        from app.services.highlights import (
            check_delivery_qualification,
            create_or_get_highlight_job,
            reprocess_highlight,
        )
        import asyncio

        markers = await db.select(
            "event_markers",
            filters={"session_id": f"eq.{session_id}", "status": "eq.linked"},
        )
        for m in markers:
            deliv_id = m.get("delivery_id")
            if not deliv_id:
                continue
            deliv = await db.select_one("deliveries", {"id": f"eq.{deliv_id}"})
            if not deliv:
                continue
            qualifies, _ = check_delivery_qualification(deliv)
            if not qualifies:
                continue

            existing_hl = await db.select_one("player_highlights", {"delivery_id": f"eq.{deliv_id}"})
            if existing_hl:
                asyncio.create_task(
                    reprocess_highlight(
                        db,
                        str(existing_hl["id"]),
                        token,
                        ReprocessHighlightRequest(marker_id=UUID(str(m["id"]))),
                    )
                )
            else:
                asyncio.create_task(
                    create_or_get_highlight_job(
                        db,
                        str(deliv_id),
                        token,
                        marker_id=str(m["id"]),
                    )
                )
    except Exception as hl_err:
        logger.warning("Failed to trigger highlight reprocessing after video upload: %s", hl_err)

    return updated_session


async def create_marker(
    db: InsForgeClient,
    session_id: str,
    data: EventMarkerCreate,
    token: str,
) -> Dict[str, Any]:
    session = await get_recording_session(db, session_id)
    match_id = str(session["match_id"])

    # 1. Idempotency check on client_marker_id
    if data.client_marker_id:
        existing = await db.select_one(
            "event_markers",
            {
                "session_id": f"eq.{session_id}",
                "client_marker_id": f"eq.{data.client_marker_id}",
            },
        )
        if existing:
            logger.info("Idempotent marker hit: %s", data.client_marker_id)
            return existing

    # 2. Get existing markers in session
    existing_markers = await db.select(
        "event_markers",
        filters={"session_id": f"eq.{session_id}"},
        order="marker_number.asc",
    )

    # Rapid-tap protection: check if last marker was captured within 250ms
    if existing_markers and not data.delivery_id:
        last = existing_markers[-1]
        diff_ms = abs(int(last["elapsed_ms"]) - data.elapsed_ms)
        if diff_ms < 250:
            logger.info("Rapid tap suppressed (<250ms diff), returning previous marker")
            return last

    marker_number = len(existing_markers) + 1
    marker_label = data.marker_label or f"Marker {marker_number:02d}"

    delivery_display = None
    status_str = "unlinked"

    if data.delivery_id:
        deliv = await db.select_one("deliveries", {"id": f"eq.{data.delivery_id}"})
        if deliv:
            status_str = "linked"
            striker_p = await db.select_one("players", {"id": f"eq.{deliv['striker_id']}"})
            player_name = (
                striker_p.get("display_name") or striker_p.get("full_name") or "Player"
                if striker_p
                else "Player"
            )
            delivery_display = f"{deliv['display_over']} · {player_name}"

    payload = {
        "session_id": session_id,
        "match_id": match_id,
        "segment_index": data.segment_index,
        "delivery_id": str(data.delivery_id) if data.delivery_id else None,
        "innings_id": str(data.innings_id) if data.innings_id else None,
        "marker_number": marker_number,
        "elapsed_ms": data.elapsed_ms,
        "segment_offset_ms": data.segment_offset_ms or data.elapsed_ms,
        "marker_label": marker_label,
        "status": status_str,
        "delivery_display": delivery_display,
        "client_marker_id": data.client_marker_id,
        "audit_metadata": data.audit_metadata or {},
    }

    inserted = await db.insert_as_user("event_markers", [payload], token)
    created_marker = inserted[0]

    # Automatic highlight trigger: if delivery was provided and qualifies
    if data.delivery_id and deliv and deliv.get("is_batter_boundary") and deliv.get("boundary_type") in (4, 6):
        try:
            from app.services.highlights import create_or_get_highlight_job
            import asyncio
            asyncio.create_task(create_or_get_highlight_job(db, str(data.delivery_id), token, marker_id=str(created_marker["id"])))
        except Exception as hl_err:
            logger.warning("Could not automatically trigger highlight on marker creation: %s", hl_err)

    return created_marker



async def list_markers(
    db: InsForgeClient, session_id: str
) -> List[Dict[str, Any]]:
    return await db.select(
        "event_markers",
        filters={"session_id": f"eq.{session_id}"},
        order="marker_number.asc",
    )


async def link_marker_to_delivery(
    db: InsForgeClient,
    marker_id: str,
    data: EventMarkerLinkDelivery,
    token: str,
) -> Dict[str, Any]:
    marker = await db.select_one("event_markers", {"id": f"eq.{marker_id}"})
    if not marker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Marker not found")

    deliv = await db.select_one("deliveries", {"id": f"eq.{data.delivery_id}"})
    if not deliv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery not found")

    striker_p = await db.select_one("players", {"id": f"eq.{deliv['striker_id']}"})
    player_name = (
        striker_p.get("display_name") or striker_p.get("full_name") or "Player"
        if striker_p
        else "Player"
    )
    delivery_display = data.delivery_display or f"{deliv['display_over']} · {player_name}"

    updated = await db.update_as_user(
        "event_markers",
        {"id": f"eq.{marker_id}"},
        {
            "delivery_id": str(data.delivery_id),
            "innings_id": str(data.innings_id or deliv.get("innings_id")),
            "delivery_display": delivery_display,
            "status": "linked",
        },
        token,
    )

    # Automatic highlight trigger: if delivery qualifies for batter boundary 4/6
    if deliv.get("is_batter_boundary") and deliv.get("boundary_type") in (4, 6):
        try:
            from app.services.highlights import create_or_get_highlight_job
            import asyncio
            asyncio.create_task(create_or_get_highlight_job(db, str(data.delivery_id), token, marker_id=str(marker_id)))
        except Exception as hl_err:
            logger.warning("Could not automatically trigger highlight on marker link: %s", hl_err)

    return updated[0]



async def update_marker(
    db: InsForgeClient,
    marker_id: str,
    data: EventMarkerUpdate,
    token: str,
) -> Dict[str, Any]:
    marker = await db.select_one("event_markers", {"id": f"eq.{marker_id}"})
    if not marker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Marker not found")

    payload = {k: str(v) if isinstance(v, UUID) else v for k, v in data.model_dump().items() if v is not None}
    if not payload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    updated = await db.update_as_user("event_markers", {"id": f"eq.{marker_id}"}, payload, token)
    return updated[0]


async def delete_marker(
    db: InsForgeClient,
    marker_id: str,
    token: str,
) -> None:
    marker = await db.select_one("event_markers", {"id": f"eq.{marker_id}"})
    if not marker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Marker not found")
    await db.delete_as_user("event_markers", {"id": f"eq.{marker_id}"}, token)
