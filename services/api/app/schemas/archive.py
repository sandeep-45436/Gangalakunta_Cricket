"""
Pydantic schemas for Phase 6 — Player Profiles, Historical Match Archive,
Signed Media Access, Audit Logging, Backup/Restore & Operational Diagnostics.
"""
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID
from pydantic import BaseModel, Field

from app.schemas.highlights import PlayerHighlightResponse
from app.schemas.milestones import MilestoneResponse
from app.schemas.players import PlayerResponse
from app.schemas.matches import MatchResponse


class PlayerTeamHistoryEntry(BaseModel):
    team_id: UUID
    team_name: str
    short_name: Optional[str] = None
    is_current_squad: bool = True
    matches_played_for_team: int = 0


class PlayerCareerStats(BaseModel):
    # Batting
    matches_played: int = 0
    innings_batted: int = 0
    not_outs: int = 0
    total_runs: int = 0
    highest_score: int = 0
    highest_score_not_out: bool = False
    batting_average: float = 0.0
    balls_faced: int = 0
    batting_strike_rate: float = 0.0
    fours: int = 0
    sixes: int = 0
    fifties: int = 0
    centuries: int = 0
    # Bowling
    innings_bowled: int = 0
    balls_bowled: int = 0
    overs_bowled: str = "0.0"
    maidens: int = 0
    runs_conceded: int = 0
    wickets_taken: int = 0
    best_bowling: str = "0/0"
    bowling_economy: float = 0.0
    bowling_average: float = 0.0


class PlayerMatchPerformance(BaseModel):
    match_id: UUID
    match_title: str
    tournament: Optional[str] = None
    format: str
    venue: Optional[str] = None
    scheduled_at: Optional[str] = None
    match_status: str
    player_team_name: Optional[str] = None
    opponent_team_name: Optional[str] = None
    # Batting in match
    batted: bool = False
    innings_id: Optional[UUID] = None
    innings_number: Optional[int] = None
    runs: int = 0
    balls: int = 0
    fours: int = 0
    sixes: int = 0
    strike_rate: float = 0.0
    is_out: bool = False
    dismissal_text: str = "did not bat"
    # Bowling in match
    bowled: bool = False
    bowling_innings_id: Optional[UUID] = None
    overs_display: str = "0.0"
    maidens: int = 0
    runs_conceded: int = 0
    wickets: int = 0
    economy: float = 0.0
    highlights_in_match: int = 0


class PlayerMatchFacet(BaseModel):
    match_id: UUID
    title: str
    tournament: Optional[str] = None


class PlayerProfileResponse(BaseModel):
    player: PlayerResponse
    team_history: List[PlayerTeamHistoryEntry] = Field(default_factory=list)
    career_stats: PlayerCareerStats
    match_performances: List[PlayerMatchPerformance] = Field(default_factory=list)
    milestones: List[MilestoneResponse] = Field(default_factory=list)
    highlights: List[PlayerHighlightResponse] = Field(default_factory=list)
    highlights_total: int = 0
    highlights_limit: int = 12
    highlights_offset: int = 0
    has_more_highlights: bool = False
    available_tournaments: List[str] = Field(default_factory=list)
    available_matches: List[PlayerMatchFacet] = Field(default_factory=list)


class ArchivedInningsSummary(BaseModel):
    innings_id: UUID
    innings_number: int
    batting_team_id: UUID
    batting_team_name: str
    total_runs: int
    total_wickets: int
    overs_display: str
    status: str


class ArchivedMatchItem(BaseModel):
    match: MatchResponse
    tournament: Optional[str] = None
    innings_summaries: List[ArchivedInningsSummary] = Field(default_factory=list)
    result_text: Optional[str] = None
    highlights_count: int = 0
    fours_count: int = 0
    sixes_count: int = 0
    milestones_count: int = 0


class MatchArchiveFacets(BaseModel):
    tournaments: List[str] = Field(default_factory=list)
    formats: List[str] = Field(default_factory=list)


class MatchArchivePageResponse(BaseModel):
    items: List[ArchivedMatchItem]
    total: int
    limit: int
    offset: int
    has_more: bool
    facets: MatchArchiveFacets


class SignedMediaUrlResponse(BaseModel):
    key: str
    signed_url: str
    expires_at: int
    signature: str


class AuditLogEntry(BaseModel):
    id: UUID
    actor_id: UUID
    action: str
    resource_type: str
    resource_id: Optional[UUID] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: str


class OpsDiagnosticsResponse(BaseModel):
    status: Literal["healthy", "degraded"]
    service_version: str
    db_connected: bool
    storage_connected: bool
    failed_highlight_jobs: int
    pending_highlight_jobs: int
    interrupted_recordings: int
    total_archived_matches: int
    total_ready_highlights: int
    retention_policy_default_days: int
    recent_audit_logs: List[AuditLogEntry] = Field(default_factory=list)


class RetryJobsResult(BaseModel):
    retried_highlight_jobs: int
    recovered_recording_sessions: int
    details: List[str] = Field(default_factory=list)


class RetentionCleanupRequest(BaseModel):
    retention_days: int = Field(default=90, ge=1, le=3650)
    dry_run: bool = Field(default=False)


class RetentionCleanupResponse(BaseModel):
    retention_days: int
    dry_run: bool
    expired_sessions_found: int
    raw_videos_purged: int
    highlights_preserved: int


class BackupManifestResponse(BaseModel):
    exported_at: str
    owner_id: str
    counts: Dict[str, int]
    checksum_sha256: str
    data: Dict[str, Any]


class BackupVerifyRequest(BaseModel):
    checksum_sha256: str
    data: Dict[str, Any]


class BackupVerifyResponse(BaseModel):
    valid: bool
    computed_checksum: str
    counts: Dict[str, int]
    message: str
