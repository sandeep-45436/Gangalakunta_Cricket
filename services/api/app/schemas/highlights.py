"""
Pydantic schemas for Phase 4 — Highlights & Video Processing.
"""
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID
from pydantic import BaseModel, Field


HighlightStatus = Literal["pending", "processing", "ready", "retrying", "failed"]
HighlightEventType = Literal["four", "six"]


class HighlightTriggerRequest(BaseModel):
    delivery_id: UUID
    marker_id: Optional[UUID] = None
    config_before_sec: float = Field(default=4.0, ge=0.5, le=30.0, description="Seconds to clip before the marker")
    config_after_sec: float = Field(default=5.0, ge=0.5, le=30.0, description="Seconds to clip after the marker")


class ReprocessHighlightRequest(BaseModel):
    config_before_sec: Optional[float] = Field(default=None, ge=0.5, le=30.0)
    config_after_sec: Optional[float] = Field(default=None, ge=0.5, le=30.0)
    marker_id: Optional[UUID] = None


class HighlightJobResponse(BaseModel):
    id: UUID
    match_id: UUID
    delivery_id: UUID
    marker_id: Optional[UUID] = None
    player_id: UUID
    status: HighlightStatus
    event_type: HighlightEventType
    retry_count: int
    max_retries: int
    error_message: Optional[str] = None
    config_before_sec: float
    config_after_sec: float
    version: int
    audit_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class PlayerHighlightResponse(BaseModel):
    id: UUID
    job_id: Optional[UUID] = None
    match_id: UUID
    innings_id: UUID
    delivery_id: UUID
    marker_id: Optional[UUID] = None
    player_id: UUID
    event_type: HighlightEventType
    status: Literal["pending", "processing", "ready", "failed"]
    video_url: Optional[str] = None
    video_key: Optional[str] = None
    thumbnail_url: Optional[str] = None
    thumbnail_key: Optional[str] = None
    duration_sec: Optional[float] = None
    start_offset_sec: Optional[float] = None
    end_offset_sec: Optional[float] = None
    delivery_metadata: Dict[str, Any] = Field(default_factory=dict)
    version: int
    created_at: str
    updated_at: str


class PlayerHighlightReel(BaseModel):
    player_id: UUID
    player_name: str
    total_highlights: int
    fours_count: int
    sixes_count: int
    highlights: List[PlayerHighlightResponse]
