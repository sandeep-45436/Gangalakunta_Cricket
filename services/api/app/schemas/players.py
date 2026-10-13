"""Pydantic schemas for player profiles."""
from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


VALID_ROLES = {"Batter", "Bowler", "All-rounder", "WK"}


class PlayerCreate(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=150)
    display_name: Optional[str] = Field(None, max_length=100)
    batting_style: Optional[str] = None
    bowling_style: Optional[str] = None
    role: Optional[str] = None
    jersey_number: Optional[int] = Field(None, ge=0, le=999)
    photo_url: Optional[str] = None

    @field_validator("role")
    @classmethod
    def role_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_ROLES:
            raise ValueError(f"role must be one of {VALID_ROLES}")
        return v


class PlayerUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=150)
    display_name: Optional[str] = Field(None, max_length=100)
    batting_style: Optional[str] = None
    bowling_style: Optional[str] = None
    role: Optional[str] = None
    jersey_number: Optional[int] = Field(None, ge=0, le=999)
    photo_url: Optional[str] = None

    @field_validator("role")
    @classmethod
    def role_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_ROLES:
            raise ValueError(f"role must be one of {VALID_ROLES}")
        return v


class PlayerResponse(BaseModel):
    id: UUID
    owner_id: UUID
    full_name: str
    display_name: Optional[str]
    batting_style: Optional[str]
    bowling_style: Optional[str]
    role: Optional[str]
    jersey_number: Optional[int]
    photo_url: Optional[str]
    created_at: datetime
    updated_at: datetime
