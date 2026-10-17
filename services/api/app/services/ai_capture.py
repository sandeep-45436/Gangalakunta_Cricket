"""
Service orchestrating AI Continuous Live Capture, LangGraph Multi-Agent execution,
automatic marker creation, and direct player reel attribution.
"""
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import BackgroundTasks

from app.ai.agents import CricketCaptureState, get_cricket_capture_graph
from app.core.database import InsForgeClient
from app.schemas.ai_capture import AICaptureResponse, AICaptureStreamRequest
from app.services import highlights as highlights_svc
from app.services import recording as recording_svc

logger = logging.getLogger(__name__)


async def run_ai_capture_pipeline(
    db: InsForgeClient,
    req: AICaptureStreamRequest,
    token: str,
    background_tasks: Optional[BackgroundTasks] = None,
) -> AICaptureResponse:
    """
    Executes the 4-agent LangGraph workflow for continuous delivery analysis:
    1. DeliverySegmenterAgent -> delivery window & speed
    2. CricketEventRecognizerAgent -> Gemini Multimodal Vision analysis
    3. ScoreCaptureFusionAgent -> Reconciles with live scorer input & clip offsets
    4. PlayerReelPublisherAgent -> Direct attribution to Striker, Bowler, Fielder records
    """
    # 1. Resolve player display names if IDs were supplied without names
    striker_name = req.striker_name
    if req.striker_id and not striker_name:
        p = await db.select_one("players", {"id": f"eq.{req.striker_id}"})
        if p:
            striker_name = p.get("display_name") or p.get("full_name")

    bowler_name = req.bowler_name
    if req.bowler_id and not bowler_name:
        p = await db.select_one("players", {"id": f"eq.{req.bowler_id}"})
        if p:
            bowler_name = p.get("display_name") or p.get("full_name")

    fielder_name = req.fielder_name
    if req.fielder_id and not fielder_name:
        p = await db.select_one("players", {"id": f"eq.{req.fielder_id}"})
        if p:
            fielder_name = p.get("display_name") or p.get("full_name")

    # 2. Build initial state for LangGraph
    initial_state: CricketCaptureState = {
        "session_id": str(req.session_id),
        "match_id": str(req.match_id),
        "innings_id": str(req.innings_id) if req.innings_id else None,
        "delivery_id": str(req.delivery_id) if req.delivery_id else None,
        "striker_id": str(req.striker_id) if req.striker_id else None,
        "striker_name": striker_name,
        "bowler_id": str(req.bowler_id) if req.bowler_id else None,
        "bowler_name": bowler_name,
        "fielder_id": str(req.fielder_id) if req.fielder_id else None,
        "fielder_name": fielder_name,
        "current_timestamp_ms": req.current_timestamp_ms,
        "video_url": req.video_url,
        "frame_base64": req.frame_base64,
        "admin_runs": req.admin_runs,
        "admin_extra_type": req.admin_extra_type,
        "admin_is_wicket": req.admin_is_wicket,
        "admin_wicket_type": req.admin_wicket_type,
        "logs": [],
    }

    # 3. Invoke LangGraph multi-agent graph
    graph = get_cricket_capture_graph()
    final_state: CricketCaptureState = await graph.ainvoke(initial_state)

    marker_id = final_state.get("marker_id")
    highlight_job_id = None

    # 4. If delivery was detected or score updated, auto-create event marker in InsForge DB
    try:
        from app.schemas.recording import EventMarkerCreate

        marker_time_ms = final_state.get("window_impact_ms", req.current_timestamp_ms)
        client_marker_id = f"ai-marker-{req.session_id}-{marker_time_ms}"

        marker_payload = EventMarkerCreate(
            elapsed_ms=marker_time_ms,
            segment_index=0,
            segment_offset_ms=marker_time_ms,
            client_marker_id=client_marker_id,
        )

        marker_rec = await recording_svc.create_marker(
            db=db,
            session_id=str(req.session_id),
            data=marker_payload,
            token=token,
        )
        marker_id = str(marker_rec.get("id"))

        # Link marker if delivery_id is present
        if req.delivery_id:
            from app.schemas.recording import EventMarkerLinkDelivery
            await recording_svc.link_marker_to_delivery(
                db=db,
                marker_id=marker_id,
                data=EventMarkerLinkDelivery(delivery_id=req.delivery_id),
                token=token,
            )

        final_state["marker_id"] = marker_id
        final_state["marker_created"] = True
    except Exception as m_err:
        logger.warning("Could not auto-create marker for session %s: %s", req.session_id, m_err)

    # 5. Automatically trigger highlight clip extraction if delivery qualifies (4, 6, or wicket)
    event_type = final_state.get("event_type")
    if req.delivery_id and event_type in ("four", "six", "wicket"):
        try:
            hl_res = await highlights_svc.create_or_get_highlight_job(
                db=db,
                delivery_id=str(req.delivery_id),
                token=token,
                marker_id=marker_id,
                config_before_sec=final_state.get("config_before_sec", 4.0),
                config_after_sec=final_state.get("config_after_sec", 5.0),
                background_tasks=background_tasks,
            )
            highlight_job_id = str(hl_res.get("id"))
            final_state["highlight_job_id"] = highlight_job_id
        except Exception as hl_err:
            logger.warning("Highlight auto-trigger note: %s", hl_err)

    attributed = final_state.get("attributed_records", [])

    return AICaptureResponse(
        session_id=str(req.session_id),
        match_id=str(req.match_id),
        delivery_detected=final_state.get("delivery_detected", True),
        delivery_phase=final_state.get("delivery_phase", "completed"),
        window_start_ms=final_state.get("window_start_ms", 0),
        window_impact_ms=final_state.get("window_impact_ms", req.current_timestamp_ms),
        window_end_ms=final_state.get("window_end_ms", req.current_timestamp_ms + 4000),
        bowler_speed_kmh=final_state.get("bowler_speed_kmh"),
        event_type=event_type or "delivery",
        shot_name=final_state.get("shot_name", "Cricket Delivery"),
        shot_quality=final_state.get("shot_quality", "good"),
        runs_estimate=final_state.get("runs_estimate", 0),
        wicket_type=final_state.get("wicket_type"),
        gemini_summary=final_state.get("gemini_summary", "Analyzed via LangGraph multi-agent workflow"),
        gemini_confidence=final_state.get("gemini_confidence", 0.95),
        score_reconciled=final_state.get("score_reconciled", True),
        marker_id=marker_id,
        highlight_job_id=highlight_job_id,
        attributed_players=attributed,
        status_message=final_state.get("status_message", "AI capture processed successfully"),
        logs=final_state.get("logs", []),
    )
