"""
Phase 5 — Unit and Service tests for Milestone Calculation, Idempotency,
Score Correction / Void Recalculation, and Highlight Clip Status Enrichment.
"""
from uuid import uuid4
import pytest

from app.services.milestones import (
    compute_innings_milestones,
    recalculate_innings_milestones,
    enrich_milestones_with_highlights,
)


def _make_delivery(
    seq: int,
    striker_id: str,
    batter_runs: int = 0,
    extra_type: str | None = None,
    extra_runs: int = 0,
    is_legal: bool = True,
    is_boundary: bool = False,
    boundary_type: int | None = None,
    is_batter_boundary: bool = False,
    is_voided: bool = False,
    delivery_id: str | None = None,
    bowler_id: str | None = None,
    display_over: str | None = None,
) -> dict:
    return {
        "id": delivery_id or str(uuid4()),
        "sequence_no": seq,
        "striker_id": striker_id,
        "non_striker_id": str(uuid4()),
        "bowler_id": bowler_id or str(uuid4()),
        "batter_runs": batter_runs,
        "extra_type": extra_type,
        "extra_runs": extra_runs,
        "total_runs": batter_runs + extra_runs,
        "is_legal": is_legal,
        "is_boundary": is_boundary,
        "boundary_type": boundary_type,
        "is_batter_boundary": is_batter_boundary,
        "is_voided": is_voided,
        "display_over": display_over or f"{(seq - 1) // 6}.{((seq - 1) % 6) + 1}",
    }


def test_fifty_and_century_thresholds_from_batter_runs():
    """Verify 50 and 100 milestones trigger strictly on cumulative batter_runs."""
    batter_a = str(uuid4())
    deliveries = []
    seq = 1
    # 12 fours = 48 runs
    for _ in range(12):
        deliveries.append(
            _make_delivery(
                seq,
                batter_a,
                batter_runs=4,
                is_boundary=True,
                boundary_type=4,
                is_batter_boundary=True,
            )
        )
        seq += 1

    # No milestone at 48
    assert compute_innings_milestones(deliveries) == []

    # Next ball: 4 runs -> crosses 50 (score = 52)
    fifty_deliv_id = str(uuid4())
    deliveries.append(
        _make_delivery(
            seq,
            batter_a,
            batter_runs=4,
            is_boundary=True,
            boundary_type=4,
            is_batter_boundary=True,
            delivery_id=fifty_deliv_id,
            display_over="2.1",
        )
    )
    seq += 1

    ms = compute_innings_milestones(deliveries)
    assert len(ms) == 1
    assert ms[0]["threshold"] == 50
    assert ms[0]["milestone_type"] == "FIFTY"
    assert ms[0]["batter_score"] == 52
    assert ms[0]["balls_faced"] == 13
    assert ms[0]["fours_count"] == 13
    assert ms[0]["delivery_id"] == fifty_deliv_id
    assert ms[0]["over_display"] == "2.1"

    # Add 7 sixes (42 runs -> 52 + 42 = 94)
    for _ in range(7):
        deliveries.append(
            _make_delivery(
                seq,
                batter_a,
                batter_runs=6,
                is_boundary=True,
                boundary_type=6,
                is_batter_boundary=True,
            )
        )
        seq += 1

    assert len(compute_innings_milestones(deliveries)) == 1

    # Hit a SIX from 94 -> 100!
    century_deliv_id = str(uuid4())
    deliveries.append(
        _make_delivery(
            seq,
            batter_a,
            batter_runs=6,
            is_boundary=True,
            boundary_type=6,
            is_batter_boundary=True,
            delivery_id=century_deliv_id,
            display_over="3.3",
        )
    )

    ms_after = compute_innings_milestones(deliveries)
    assert len(ms_after) == 2
    century = ms_after[1]
    assert century["threshold"] == 100
    assert century["milestone_type"] == "CENTURY"
    assert century["batter_score"] == 100
    assert century["balls_faced"] == 21
    assert century["fours_count"] == 13
    assert century["sixes_count"] == 8
    assert century["delivery_id"] == century_deliv_id


def test_extras_do_not_trigger_batter_milestones():
    """Wides, byes, leg-byes, and no-ball penalty extras must NOT count toward batter milestones."""
    batter_a = str(uuid4())
    deliveries = []
    # Batter reaches 48 off 8 sixes
    for i in range(1, 9):
        deliveries.append(
            _make_delivery(i, batter_a, batter_runs=6, is_boundary=True, boundary_type=6, is_batter_boundary=True)
        )

    # Add 5 wides, 4 byes, 4 leg-byes, and 1 no-ball with 0 batter runs (14 team extra runs)
    deliveries.append(_make_delivery(9, batter_a, batter_runs=0, extra_type="wide", extra_runs=5, is_legal=False))
    deliveries.append(_make_delivery(10, batter_a, batter_runs=0, extra_type="bye", extra_runs=4, is_legal=True))
    deliveries.append(_make_delivery(11, batter_a, batter_runs=0, extra_type="leg_bye", extra_runs=4, is_legal=True))
    deliveries.append(_make_delivery(12, batter_a, batter_runs=0, extra_type="no_ball", extra_runs=1, is_legal=False))

    # Team has 62 runs, but batter still has 48 batter_runs -> 0 milestones
    assert compute_innings_milestones(deliveries) == []

    # Now batter hits 2 runs off a no-ball (batter_runs=2, extra_runs=1) -> batter reaches 50!
    nb_boundary_id = str(uuid4())
    deliveries.append(
        _make_delivery(
            13,
            batter_a,
            batter_runs=2,
            extra_type="no_ball",
            extra_runs=1,
            is_legal=False,
            delivery_id=nb_boundary_id,
        )
    )
    ms = compute_innings_milestones(deliveries)
    assert len(ms) == 1
    assert ms[0]["threshold"] == 50
    assert ms[0]["batter_score"] == 50
    assert ms[0]["delivery_id"] == nb_boundary_id


def test_voided_delivery_removes_milestone():
    """Voiding the delivery that crossed 50 must remove the milestone on recalculation."""
    batter_a = str(uuid4())
    deliveries = [
        _make_delivery(i, batter_a, batter_runs=6, is_boundary=True, boundary_type=6, is_batter_boundary=True)
        for i in range(1, 10)
    ]
    # 9 * 6 = 54 -> 50 crossed on delivery #9
    ms_initial = compute_innings_milestones(deliveries)
    assert len(ms_initial) == 1
    assert ms_initial[0]["batter_score"] == 54

    # Void delivery #9
    deliveries[-1]["is_voided"] = True
    assert compute_innings_milestones(deliveries) == []


class FakeMilestoneDB:
    """In-memory mock of InsForgeClient for testing milestone persistence, uniqueness, and invalidation."""

    def __init__(self, innings_id: str, match_id: str, player_id: str, bowler_id: str):
        self.innings_id = innings_id
        self.match_id = match_id
        self.player_id = player_id
        self.bowler_id = bowler_id
        self.deliveries: list[dict] = []
        self.milestones: list[dict] = []
        self.highlights: list[dict] = []

    async def select_one(self, table: str, filters: dict):
        if table == "innings":
            return {
                "id": self.innings_id,
                "match_id": self.match_id,
                "innings_number": 1,
                "batting_team_id": str(uuid4()),
                "bowling_team_id": str(uuid4()),
            }
        if table == "matches":
            return {"id": self.match_id, "title": "Final Match", "format": "T20"}
        if table == "teams":
            return {"name": "Warriors XI"}
        if table == "players":
            return {"id": self.player_id, "display_name": "Virat K"}
        if table == "player_highlights":
            deliv_filter = filters.get("delivery_id", "").replace("eq.", "")
            for h in self.highlights:
                if str(h["delivery_id"]) == deliv_filter:
                    return h
            return None
        return None

    async def select(self, table: str, filters: dict | None = None, order: str | None = None, limit: int | None = None):
        if table == "deliveries":
            return list(self.deliveries)
        if table == "player_milestones":
            if filters and filters.get("is_valid") == "eq.true":
                return [m for m in self.milestones if m.get("is_valid", True)]
            return list(self.milestones)
        return []

    async def insert_as_user(self, table: str, rows: list[dict], token: str):
        inserted = []
        for r in rows:
            row = {
                **r,
                "id": str(uuid4()),
                "created_at": "2026-10-13T10:00:00Z",
                "updated_at": "2026-10-13T10:00:00Z",
            }
            if table == "player_milestones":
                self.milestones.append(row)
            inserted.append(row)
        return inserted

    async def update_as_user(self, table: str, filters: dict, data: dict, token: str):
        target_id = filters.get("id", "").replace("eq.", "")
        updated = []
        if table == "player_milestones":
            for m in self.milestones:
                if str(m["id"]) == target_id:
                    m.update(data)
                    updated.append(m)
        return updated


@pytest.mark.asyncio
async def test_recalculate_milestones_idempotency_and_invalidation():
    """
    Verify:
    1. Crossing 50 creates exactly one valid milestone.
    2. Retrying / calling recalculate again does NOT create a duplicate milestone.
    3. Voiding the milestone delivery marks the milestone is_valid=False.
    4. Scoring a new delivery that crosses 50 creates a new valid milestone while keeping the old invalidated one.
    5. Highlight clip status is accurately attached ('unavailable' vs 'ready').
    """
    innings_id = str(uuid4())
    match_id = str(uuid4())
    player_id = str(uuid4())
    bowler_id = str(uuid4())
    db = FakeMilestoneDB(innings_id, match_id, player_id, bowler_id)

    # 8 sixes = 48 runs
    for i in range(1, 9):
        db.deliveries.append(
            _make_delivery(i, player_id, batter_runs=6, is_boundary=True, boundary_type=6, is_batter_boundary=True, bowler_id=bowler_id)
        )

    # 9th ball: FOUR -> 52 runs
    d9 = _make_delivery(9, player_id, batter_runs=4, is_boundary=True, boundary_type=4, is_batter_boundary=True, bowler_id=bowler_id)
    db.deliveries.append(d9)

    active = await recalculate_innings_milestones(db, innings_id, "test-token")
    assert len(active) == 1
    assert active[0]["threshold"] == 50
    assert active[0]["batter_score"] == 52
    assert active[0]["is_valid"] is True
    assert active[0]["highlight_status"] == "unavailable"

    # Call recalculate again (retry simulation) -> still only 1 milestone in DB
    active_retry = await recalculate_innings_milestones(db, innings_id, "test-token")
    assert len(active_retry) == 1
    assert len(db.milestones) == 1

    # Void 9th ball -> milestone must be invalidated
    d9["is_voided"] = True
    active_after_void = await recalculate_innings_milestones(db, innings_id, "test-token")
    assert len(active_after_void) == 0
    assert len(db.milestones) == 1
    assert db.milestones[0]["is_valid"] is False
    assert db.milestones[0]["invalidated_reason"] is not None

    # 10th ball: SIX -> 54 runs (with a ready highlight clip!)
    d10 = _make_delivery(10, player_id, batter_runs=6, is_boundary=True, boundary_type=6, is_batter_boundary=True, bowler_id=bowler_id)
    db.deliveries.append(d10)
    db.highlights.append({
        "id": str(uuid4()),
        "delivery_id": d10["id"],
        "status": "ready",
        "video_url": "https://cdn.example.com/fifty-clip.mp4",
        "thumbnail_url": "https://cdn.example.com/fifty-thumb.jpg",
    })

    active_reachieved = await recalculate_innings_milestones(db, innings_id, "test-token")
    assert len(active_reachieved) == 1
    assert active_reachieved[0]["delivery_id"] == d10["id"]
    assert active_reachieved[0]["batter_score"] == 54
    assert active_reachieved[0]["is_valid"] is True
    assert active_reachieved[0]["highlight_status"] == "ready"
    assert active_reachieved[0]["highlight_video_url"] == "https://cdn.example.com/fifty-clip.mp4"
