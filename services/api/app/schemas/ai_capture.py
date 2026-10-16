"""
Pydantic schemas for AI Continuous Live Capture, Delivery Detection & LangGraph agents.
"""
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


class AICaptureStreamRequest(BaseModel):
    session_id: UUID
    match_id: UUID
    innings_id: Optional[UUID] = None
    delivery_id: Optional[UUID] = None
    current_timestamp_ms: int = Field(ge=0, description="Current monotonic elapsed or video playback time in ms")
    frame_base64: Optional[str] = Field(default=None, description="Optional base64 JPEG snapshot for Gemini vision")
    video_url: Optional[str] = None
    striker_id: Optional[UUID] = None
    striker_name: Optional[str] = None
    bowler_id: Optional[UUID] = None
    bowler_name: Optional[str] = None
    fielder_id: Optional[UUID] = None
    fielder_name: Optional[str] = None
    
    # Scorer admin inputs (when admin records ball or auto-suggested)
    admin_runs: Optional[int] = None
    admin_extra_type: Optional[str] = None
    admin_is_wicket: Optional[bool] = None
    admin_wicket_type: Optional[str] = None


class AttributedPlayerItem(BaseModel):
    player_id: str
    player_name: str
    role: str
    event_type: str
    title: str
    description: str
    metrics: Dict[str, Any] = Field(default_factory=dict)


class AICaptureResponse(BaseModel):
    session_id: str
    match_id: str
    delivery_detected: bool
    delivery_phase: str
    window_start_ms: int
    window_impact_ms: int
    window_end_ms: int
    bowler_speed_kmh: Optional[float] = None
    event_type: str
    shot_name: str
    shot_quality: str
    runs_estimate: int
    wicket_type: Optional[str] = None
    gemini_summary: str
    gemini_confidence: float
    score_reconciled: bool
    marker_id: Optional[str] = None
    highlight_job_id: Optional[str] = None
    attributed_players: List[AttributedPlayerItem] = Field(default_factory=list)
    status_message: str
    logs: List[str] = Field(default_factory=list)
