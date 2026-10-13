"""Pydantic schemas for matches, match teams, playing XI and substitutes."""
from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator


VALID_FORMATS = {"T20", "ODI", "Test", "T10", "Custom"}
VALID_STATUSES = {"upcoming", "live", "completed", "cancelled"}
VALID_SUB_TYPES = {"substitute", "impact", "concussion"}


# ── Match ──────────────────────────────────────────────────────────────────────

class MatchTeamInput(BaseModel):
    """One team entry inside a CreateMatch request."""
    team_id: UUID
    batting_order: int = Field(..., ge=1, le=2)


class MatchCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    format: str
    tournament: Optional[str] = Field(None, max_length=200)
    venue: Optional[str] = Field(None, max_length=200)
    scheduled_at: Optional[datetime] = None
    overs_per_innings: Optional[int] = Field(None, ge=1, le=100)
    teams: list[MatchTeamInput] = Field(..., min_length=2, max_length=2)

    @field_validator("format")
    @classmethod
    def format_must_be_valid(cls, v: str) -> str:
        if v not in VALID_FORMATS:
            raise ValueError(f"format must be one of {VALID_FORMATS}")
        return v

    @model_validator(mode="after")
    def teams_must_have_distinct_orders(self) -> "MatchCreate":
        orders = [t.batting_order for t in self.teams]
        if len(set(orders)) != 2:
            raise ValueError("The two teams must have distinct batting_order values (1 and 2)")
        team_ids = [t.team_id for t in self.teams]
        if len(set(team_ids)) != 2:
            raise ValueError("A match cannot have the same team twice")
        return self


class MatchUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    tournament: Optional[str] = Field(None, max_length=200)
    venue: Optional[str] = Field(None, max_length=200)
    scheduled_at: Optional[datetime] = None
    status: Optional[str] = None
    overs_per_innings: Optional[int] = Field(None, ge=1, le=100)

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_STATUSES:
            raise ValueError(f"status must be one of {VALID_STATUSES}")
        return v


class MatchTeamResponse(BaseModel):
    id: UUID
    match_id: UUID
    team_id: UUID
    team_name: str
    batting_order: int


class MatchResponse(BaseModel):
    id: UUID
    owner_id: UUID
    title: str
    format: str
    tournament: Optional[str] = None
    venue: Optional[str]
    scheduled_at: Optional[datetime]
    status: str
    overs_per_innings: Optional[int]
    created_at: datetime
    updated_at: datetime
    teams: list[MatchTeamResponse] = []


# ── Playing XI ────────────────────────────────────────────────────────────────

class PlayingXIEntry(BaseModel):
    player_id: UUID
    batting_position: Optional[int] = Field(None, ge=1, le=11)
    is_captain: bool = False
    is_wicketkeeper: bool = False


class PlayingXISetRequest(BaseModel):
    """Set (replace) the full Playing XI for one team in a match."""
    team_id: UUID
    players: list[PlayingXIEntry] = Field(..., min_length=11, max_length=11)

    @field_validator("players")
    @classmethod
    def no_duplicate_players(cls, players: list[PlayingXIEntry]) -> list[PlayingXIEntry]:
        ids = [str(p.player_id) for p in players]
        if len(ids) != len(set(ids)):
            raise ValueError("A player cannot appear twice in the same Playing XI")
        return players

    @model_validator(mode="after")
    def at_most_one_captain_and_keeper(self) -> "PlayingXISetRequest":
        captains = sum(1 for p in self.players if p.is_captain)
        keepers = sum(1 for p in self.players if p.is_wicketkeeper)
        if captains > 1:
            raise ValueError("A team can have at most one captain")
        if keepers > 1:
            raise ValueError("A team can have at most one wicketkeeper")
        return self


class PlayingXIEntryResponse(BaseModel):
    id: UUID
    match_id: UUID
    team_id: UUID
    player_id: UUID
    player_name: str
    batting_position: Optional[int]
    is_captain: bool
    is_wicketkeeper: bool
    selected_at: datetime


# ── Substitutes ───────────────────────────────────────────────────────────────

class SubstituteAdd(BaseModel):
    team_id: UUID
    player_id: UUID
    substitute_type: str = "substitute"

    @field_validator("substitute_type")
    @classmethod
    def type_must_be_valid(cls, v: str) -> str:
        if v not in VALID_SUB_TYPES:
            raise ValueError(f"substitute_type must be one of {VALID_SUB_TYPES}")
        return v


class SubstituteResponse(BaseModel):
    id: UUID
    match_id: UUID
    team_id: UUID
    player_id: UUID
    player_name: str
    substitute_type: str
    declared_at: datetime
