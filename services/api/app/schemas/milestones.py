"""
Pydantic schemas for Phase 5 — Score Animations & Replayable Milestones.
"""
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID
from pydantic import BaseModel, Field

MilestoneType = Literal["FIFTY", "CENTURY", "ONE_FIFTY", "DOUBLE_CENTURY"]
AnimationEventType = Literal["FOUR", "SIX", "FIFTY", "CENTURY", "ONE_FIFTY", "DOUBLE_CENTURY"]
HighlightClipStatus = Literal["ready", "processing", "pending", "failed", "unavailable"]

MILESTONE_THRESHOLDS: Dict[int, MilestoneType] = {
    50: "FIFTY",
    100: "CENTURY",
    150: "ONE_FIFTY",
    200: "DOUBLE_CENTURY",
}


class MilestoneResponse(BaseModel):
    id: UUID
    match_id: UUID
    innings_id: UUID
    player_id: UUID
    delivery_id: UUID
    threshold: int = Field(..., description="Milestone threshold crossed (50, 100, 150, 200)")
    milestone_type: MilestoneType
    batter_score: int = Field(..., description="Batter's cumulative score at the delivery")
    balls_faced: int = 0
    fours_count: int = 0
    sixes_count: int = 0
    over_display: Optional[str] = None
    is_valid: bool = True
    invalidated_reason: Optional[str] = None
    animation_version: int = 1
    metadata: Dict[str, Any] = Field(default_factory=dict)
    # Associated video highlight clip availability
    highlight_id: Optional[UUID] = None
    highlight_status: HighlightClipStatus = "unavailable"
    highlight_video_url: Optional[str] = None
    highlight_thumbnail_url: Optional[str] = None
    created_at: str
    updated_at: str


class PlayerMilestoneSummary(BaseModel):
    player_id: UUID
    player_name: str
    total_milestones: int
    fifties_count: int
    centuries_count: int
    one_fifties_count: int = 0
    double_centuries_count: int = 0
    milestones: List[MilestoneResponse]
