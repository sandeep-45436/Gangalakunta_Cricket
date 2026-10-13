"""
Recording and event markers schemas — Phase 3 video-to-delivery synchronization.
"""
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

RecordingSessionStatus = Literal[
    "active", "paused", "stopped", "completed", "failed", "interrupted"
]
UploadStatus = Literal["pending", "uploading", "uploaded", "failed", "not_required"]
ProcessingStatus = Literal["unprocessed", "processing", "completed", "failed"]
MarkerStatus = Literal["unlinked", "linked", "ignored"]


# ── Recording session models ──────────────────────────────────────────────────

class RecordingSessionCreate(BaseModel):
    match_id: Optional[UUID] = None
    session_name: str = Field("Main Camera Session", min_length=1, max_length=100)
    media_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class RecordingSessionUpdate(BaseModel):
    session_name: Optional[str] = None
    status: Optional[RecordingSessionStatus] = None
    total_duration_ms: Optional[int] = Field(None, ge=0)
    media_asset_id: Optional[str] = None
    media_url: Optional[str] = None
    upload_status: Optional[UploadStatus] = None
    processing_status: Optional[ProcessingStatus] = None
    segments_count: Optional[int] = Field(None, ge=1)
    media_metadata: Optional[Dict[str, Any]] = None


class RecordingSessionResponse(BaseModel):
    id: UUID
    match_id: UUID
    owner_id: UUID
    session_name: str
    status: RecordingSessionStatus
    started_at: datetime
    ended_at: Optional[datetime] = None
    total_duration_ms: int = 0
    media_asset_id: Optional[str] = None
    media_url: Optional[str] = None
    upload_status: UploadStatus
    processing_status: ProcessingStatus
    segments_count: int = 1
    media_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


# ── Video segment models ──────────────────────────────────────────────────────

class VideoSegmentCreate(BaseModel):
    segment_index: int = Field(..., ge=0)
    segment_name: str
    duration_ms: int = Field(0, ge=0)
    storage_key: Optional[str] = None
    storage_url: Optional[str] = None
    upload_status: UploadStatus = "pending"


class VideoSegmentResponse(BaseModel):
    id: UUID
    session_id: UUID
    match_id: UUID
    segment_index: int
    segment_name: str
    duration_ms: int
    storage_key: Optional[str] = None
    storage_url: Optional[str] = None
    upload_status: UploadStatus
    created_at: datetime
    updated_at: datetime


# ── Event marker models ───────────────────────────────────────────────────────

class EventMarkerCreate(BaseModel):
    elapsed_ms: int = Field(..., ge=0, description="Elapsed time in milliseconds from session start")
    segment_index: int = Field(0, ge=0)
    segment_offset_ms: Optional[int] = Field(None, ge=0)
    marker_label: Optional[str] = None
    delivery_id: Optional[UUID] = None
    innings_id: Optional[UUID] = None
    client_marker_id: Optional[str] = Field(None, description="Client UUID for idempotency & rapid-tap deduplication")
    audit_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_offsets(self) -> "EventMarkerCreate":
        if self.segment_offset_ms is None:
            self.segment_offset_ms = self.elapsed_ms
        return self


class EventMarkerLinkDelivery(BaseModel):
    delivery_id: UUID
    innings_id: Optional[UUID] = None
    delivery_display: Optional[str] = None


class EventMarkerUpdate(BaseModel):
    elapsed_ms: Optional[int] = Field(None, ge=0)
    segment_offset_ms: Optional[int] = Field(None, ge=0)
    marker_label: Optional[str] = None
    status: Optional[MarkerStatus] = None
    delivery_id: Optional[UUID] = None
    innings_id: Optional[UUID] = None
    delivery_display: Optional[str] = None
    audit_metadata: Optional[Dict[str, Any]] = None


class EventMarkerResponse(BaseModel):
    id: UUID
    session_id: UUID
    match_id: UUID
    segment_id: Optional[UUID] = None
    segment_index: int
    delivery_id: Optional[UUID] = None
    innings_id: Optional[UUID] = None
    marker_number: int
    elapsed_ms: int
    segment_offset_ms: int
    marker_label: str
    status: MarkerStatus
    delivery_display: Optional[str] = None
    client_marker_id: Optional[str] = None
    audit_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
