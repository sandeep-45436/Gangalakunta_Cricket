"""Phase 5 — Player Milestones table and uniqueness constraints.

Revision ID: 0002_phase5_milestones
Revises: 0001_baseline
Create Date: 2026-10-13
"""
from typing import Sequence, Union

revision: str = "0002_phase5_milestones"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UPGRADE_SQL = """
CREATE TABLE IF NOT EXISTS public.player_milestones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id UUID NOT NULL REFERENCES public.matches(id) ON DELETE CASCADE,
    innings_id UUID NOT NULL REFERENCES public.innings(id) ON DELETE CASCADE,
    player_id UUID NOT NULL REFERENCES public.players(id) ON DELETE CASCADE,
    delivery_id UUID NOT NULL REFERENCES public.deliveries(id) ON DELETE CASCADE,
    threshold INTEGER NOT NULL CHECK (threshold IN (50, 100, 150, 200)),
    milestone_type TEXT NOT NULL CHECK (milestone_type IN ('FIFTY', 'CENTURY', 'ONE_FIFTY', 'DOUBLE_CENTURY')),
    batter_score INTEGER NOT NULL CHECK (batter_score >= threshold),
    balls_faced INTEGER NOT NULL DEFAULT 0,
    fours_count INTEGER NOT NULL DEFAULT 0,
    sixes_count INTEGER NOT NULL DEFAULT 0,
    over_display TEXT,
    is_valid BOOLEAN NOT NULL DEFAULT true,
    invalidated_reason TEXT,
    animation_version INTEGER NOT NULL DEFAULT 1,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_player_milestones_unique_valid
    ON public.player_milestones (player_id, innings_id, threshold)
    WHERE is_valid = true;
"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS public.player_milestones;
"""


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
