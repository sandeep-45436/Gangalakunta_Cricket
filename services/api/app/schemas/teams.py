"""Pydantic schemas for teams and squad membership."""
from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class TeamCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    short_name: Optional[str] = Field(None, max_length=10)
    logo_url: Optional[str] = None


class TeamUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    short_name: Optional[str] = Field(None, max_length=10)
    logo_url: Optional[str] = None


class TeamResponse(BaseModel):
    id: UUID
    owner_id: UUID
    name: str
    short_name: Optional[str]
    logo_url: Optional[str]
    created_at: datetime
    updated_at: datetime


class TeamPlayerAdd(BaseModel):
    player_id: UUID


class TeamPlayerResponse(BaseModel):
    id: UUID
    team_id: UUID
    player_id: UUID
    is_active: bool
    joined_at: datetime
    # Joined player fields (returned via PostgREST nested select)
    player: Optional[dict] = None


class SquadImportEntry(BaseModel):
    """Single row in a bulk squad import request."""
    full_name: str = Field(..., min_length=1, max_length=150)
    display_name: Optional[str] = Field(None, max_length=100)
    batting_style: Optional[str] = None
    bowling_style: Optional[str] = None
    role: Optional[str] = None
    jersey_number: Optional[int] = Field(None, ge=0, le=999)

    @field_validator("role")
    @classmethod
    def role_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        allowed = {"Batter", "Bowler", "All-rounder", "WK", None}
        if v not in allowed:
            raise ValueError(f"role must be one of {allowed - {None}}")
        return v


class SquadImportRequest(BaseModel):
    players: list[SquadImportEntry] = Field(..., min_length=1, max_length=30)

    @field_validator("players")
    @classmethod
    def no_duplicate_names(cls, players: list[SquadImportEntry]) -> list[SquadImportEntry]:
        names = [p.full_name.strip().lower() for p in players]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate player names in import request")
        return players
