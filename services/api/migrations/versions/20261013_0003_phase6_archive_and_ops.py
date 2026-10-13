"""Phase 6 — Historical Archive Indexes, Snapshot Columns, Audit Logs & Retention.

Revision ID: 0003_phase6_archive_and_ops
Revises: 0002_phase5_milestones
Create Date: 2026-10-13
"""
from typing import Sequence, Union

revision: str = "0003_phase6_archive_and_ops"
down_revision: Union[str, None] = "0002_phase5_milestones"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UPGRADE_SQL = """
ALTER TABLE public.matches ADD COLUMN IF NOT EXISTS tournament TEXT;
ALTER TABLE public.matches ADD COLUMN IF NOT EXISTS retention_days INTEGER NOT NULL DEFAULT 90;
ALTER TABLE public.match_teams ADD COLUMN IF NOT EXISTS team_name_snapshot TEXT;
ALTER TABLE public.playing_xi ADD COLUMN IF NOT EXISTS player_name_snapshot TEXT;
ALTER TABLE public.playing_xi ADD COLUMN IF NOT EXISTS role_snapshot TEXT;
ALTER TABLE public.playing_xi ADD COLUMN IF NOT EXISTS jersey_snapshot INTEGER;

CREATE TABLE IF NOT EXISTS public.audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id UUID NOT NULL,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id UUID,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_actor_created ON public.audit_logs (actor_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_matches_owner_status_date ON public.matches (owner_id, status, scheduled_at DESC, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_matches_owner_format ON public.matches (owner_id, format);
CREATE INDEX IF NOT EXISTS idx_matches_owner_tournament ON public.matches (owner_id, tournament);
CREATE INDEX IF NOT EXISTS idx_deliveries_match_innings_seq ON public.deliveries (match_id, innings_id, sequence_no);
CREATE INDEX IF NOT EXISTS idx_deliveries_striker_match ON public.deliveries (striker_id, match_id);
CREATE INDEX IF NOT EXISTS idx_deliveries_bowler_match ON public.deliveries (bowler_id, match_id);
CREATE INDEX IF NOT EXISTS idx_player_highlights_archive ON public.player_highlights (player_id, match_id, event_type, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_recording_sessions_owner_match ON public.recording_sessions (owner_id, match_id);
"""

DOWNGRADE_SQL = """
DROP TABLE IF EXISTS public.audit_logs;
"""


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
