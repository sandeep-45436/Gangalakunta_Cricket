"""Baseline — Phase 0 empty migration checkpoint.

Subsequent phases will add domain tables (teams, players, matches, deliveries, clips).

Revision ID: 0001_baseline
Revises:
Create Date: 2026-10-12
"""
from typing import Sequence, Union

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Phase 0 — no tables yet. This marks the starting migration point.
    pass


def downgrade() -> None:
    pass
