"""
Scoring schemas — Phase 2 ball-by-ball delivery records, innings, and scorecards.
"""
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

ExtraType = Literal["wide", "no_ball", "bye", "leg_bye", "penalty"]
WicketType = Literal[
    "bowled",
    "caught",
    "lbw",
    "run_out",
    "stumped",
    "hit_wicket",
    "handled_ball",
    "obstructing_field",
    "timed_out",
    "retired_hurt",
    "retired_out",
]
InningsStatus = Literal["not_started", "in_progress", "completed", "forfeited"]


# ── Innings creation and status ──────────────────────────────────────────────

class InningsStartRequest(BaseModel):
    innings_number: int = Field(..., ge=1, le=4)
    batting_team_id: UUID
    bowling_team_id: UUID
    opening_striker_id: UUID
    opening_non_striker_id: UUID
    opening_bowler_id: UUID
    target_runs: Optional[int] = Field(None, ge=1)

    @model_validator(mode="after")
    def check_distinct_openers(self) -> "InningsStartRequest":
        if self.batting_team_id == self.bowling_team_id:
            raise ValueError("Batting team and bowling team must be distinct")
        if self.opening_striker_id == self.opening_non_striker_id:
            raise ValueError("Opening striker and non-striker must be distinct players")
        return self


class InningsUpdateRequest(BaseModel):
    current_striker_id: Optional[UUID] = None
    current_non_striker_id: Optional[UUID] = None
    current_bowler_id: Optional[UUID] = None
    status: Optional[InningsStatus] = None
    completed_reason: Optional[str] = None


# ── Delivery creation and update ─────────────────────────────────────────────

class DeliveryCreate(BaseModel):
    striker_id: UUID
    non_striker_id: UUID
    bowler_id: UUID
    batter_runs: int = Field(0, ge=0)
    extra_type: Optional[ExtraType] = None
    extra_runs: int = Field(0, ge=0)
    is_boundary: bool = False
    boundary_type: Optional[Literal[4, 6]] = None
    is_batter_boundary: bool = False
    is_wicket: bool = False
    wicket_type: Optional[WicketType] = None
    dismissed_player_id: Optional[UUID] = None
    fielder_id: Optional[UUID] = None
    fielder2_id: Optional[UUID] = None
    dismissal_delivery_end: Optional[Literal["striker", "non_striker"]] = None
    runs_completed_before_out: int = Field(0, ge=0)
    next_striker_id: Optional[UUID] = None
    next_non_striker_id: Optional[UUID] = None
    idempotency_key: Optional[str] = None
    audit_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_cricket_rules(self) -> "DeliveryCreate":
        # 1. Striker and non-striker cannot be the same player
        if self.striker_id == self.non_striker_id:
            raise ValueError("Striker and non-striker must be different players")

        # 2. Bowler cannot be striker or non-striker
        if self.bowler_id in (self.striker_id, self.non_striker_id):
            raise ValueError("Bowler cannot be currently batting as striker or non-striker")

        # 3. Wides cannot have batter runs
        if self.extra_type == "wide" and self.batter_runs > 0:
            raise ValueError("A wide cannot yield batter runs off the bat")

        # 4. Wides must have at least 1 extra run
        if self.extra_type == "wide" and self.extra_runs < 1:
            raise ValueError("A wide must yield at least 1 extra run (the penalty)")

        # 5. No-ball must have at least 1 extra run
        if self.extra_type == "no_ball" and self.extra_runs < 1:
            raise ValueError("A no-ball must yield at least 1 extra run (the penalty)")

        # 6. Byes and leg-byes cannot have batter runs
        if self.extra_type in ("bye", "leg_bye") and self.batter_runs > 0:
            raise ValueError(f"A {self.extra_type} cannot have batter runs")

        # 7. Boundary consistency
        if self.is_boundary:
            if not self.boundary_type:
                self.boundary_type = 6 if self.batter_runs == 6 else 4
            if self.is_batter_boundary and self.extra_type in ("bye", "leg_bye", "wide"):
                raise ValueError("Extras boundary cannot be credited as batter boundary")

        # 8. Wicket validation
        if self.is_wicket:
            if not self.wicket_type:
                raise ValueError("wicket_type is required when is_wicket is true")
            if not self.dismissed_player_id:
                # Default to striker for standard dismissals
                if self.wicket_type in ("bowled", "caught", "lbw", "stumped", "hit_wicket"):
                    self.dismissed_player_id = self.striker_id
                else:
                    raise ValueError(f"dismissed_player_id is required for {self.wicket_type}")
            if self.dismissed_player_id not in (self.striker_id, self.non_striker_id):
                raise ValueError("Dismissed player must be either current striker or non-striker")
            if self.wicket_type in ("bowled", "caught", "lbw", "stumped", "hit_wicket"):
                if self.dismissed_player_id != self.striker_id:
                    raise ValueError(f"{self.wicket_type} dismissal can only apply to striker")
            if self.wicket_type in ("caught", "stumped") and not self.fielder_id:
                # In amateur/informal games catcher may not always be logged, but field is available
                pass
        else:
            if self.wicket_type or self.dismissed_player_id:
                raise ValueError("Wicket fields cannot be set when is_wicket is false")

        return self


class DeliveryUpdate(BaseModel):
    batter_runs: Optional[int] = Field(None, ge=0)
    extra_type: Optional[Optional[ExtraType]] = None
    extra_runs: Optional[int] = Field(None, ge=0)
    is_boundary: Optional[bool] = None
    boundary_type: Optional[Literal[4, 6]] = None
    is_batter_boundary: Optional[bool] = None
    is_wicket: Optional[bool] = None
    wicket_type: Optional[WicketType] = None
    dismissed_player_id: Optional[UUID] = None
    fielder_id: Optional[UUID] = None
    correction_reason: Optional[str] = None


class DeliveryVoidRequest(BaseModel):
    reason: str = Field(..., min_length=3)


# ── Scorecard and figure models ──────────────────────────────────────────────

class BatterScorecardFigure(BaseModel):
    player_id: UUID
    player_name: str
    runs: int = 0
    balls: int = 0
    fours: int = 0
    sixes: int = 0
    strike_rate: float = 0.0
    is_out: bool = False
    dismissal_text: str = "not out"
    wicket_type: Optional[str] = None
    bowler_name: Optional[str] = None
    fielder_name: Optional[str] = None
    batting_position: Optional[int] = None


class BowlerScorecardFigure(BaseModel):
    player_id: UUID
    player_name: str
    overs: str = "0.0"
    legal_balls: int = 0
    maidens: int = 0
    runs_conceded: int = 0
    wickets: int = 0
    economy: float = 0.0
    dots: int = 0
    wides: int = 0
    no_balls: int = 0


class ExtrasBreakdown(BaseModel):
    total: int = 0
    wides: int = 0
    no_balls: int = 0
    byes: int = 0
    leg_byes: int = 0
    penalty: int = 0


class FallOfWicketFigure(BaseModel):
    wicket_number: int
    score: int
    overs: str
    dismissed_player_id: UUID
    dismissed_player_name: str


class PartnershipFigure(BaseModel):
    batter1_id: UUID
    batter1_name: str
    batter2_id: UUID
    batter2_name: str
    runs: int = 0
    balls: int = 0


class InningsScorecard(BaseModel):
    innings_id: UUID
    match_id: UUID
    innings_number: int
    batting_team_id: UUID
    batting_team_name: str
    bowling_team_id: UUID
    bowling_team_name: str
    status: InningsStatus
    completed_reason: Optional[str] = None
    total_runs: int = 0
    total_wickets: int = 0
    total_legal_balls: int = 0
    overs_display: str = "0.0"
    run_rate: float = 0.0
    target_runs: Optional[int] = None
    required_run_rate: Optional[float] = None
    current_striker: Optional[BatterScorecardFigure] = None
    current_non_striker: Optional[BatterScorecardFigure] = None
    current_bowler: Optional[BowlerScorecardFigure] = None
    batters: List[BatterScorecardFigure] = []
    bowlers: List[BowlerScorecardFigure] = []
    extras: ExtrasBreakdown = ExtrasBreakdown()
    fall_of_wickets: List[FallOfWicketFigure] = []
    partnerships: List[PartnershipFigure] = []
    current_partnership: Optional[PartnershipFigure] = None


class MatchScorecard(BaseModel):
    match_id: UUID
    title: str
    format: str
    status: str
    overs_per_innings: Optional[int] = None
    winner_team_id: Optional[UUID] = None
    result_text: Optional[str] = None
    innings: List[InningsScorecard] = []
