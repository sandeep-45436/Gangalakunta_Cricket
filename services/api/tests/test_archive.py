"""
Phase 6 — Automated Unit & Integration tests for:
1. Player Profile & Career/Match-by-Match Batting & Bowling Aggregation + Highlight Pagination
2. Match Archive Search & Filtering (Team A/B, Duplicate Player Names by UUID, Date Range, Format, Tournament, Highlight/Milestone Type)
3. Historical Match Identity Preservation when squads/names change after a match
4. Cross-User Authorization Enforcement (IDOR prevention on recordings & media signing)
5. Expiring HMAC Signed Media Tokens (creation, verification, expiry & tamper rejection)
6. Database Backup Export & Cryptographic Restoration Verification + Job Recovery & Retention Policy
"""
from uuid import UUID, uuid4
import pytest
from fastapi import HTTPException

from app.schemas.recording import RecordingSessionUpdate
from app.services.archive import (
    apply_retention_policy,
    create_signed_media_token,
    export_owner_backup,
    generate_signed_media_url,
    get_player_profile,
    retry_failed_jobs_and_sessions,
    search_match_archive,
    verify_backup_manifest,
    verify_signed_media_token,
)
from app.services.recording import (
    delete_recording_session,
    get_recording_session,
    update_recording_session,
)
from app.services.scoring import get_scorecard


class FakePhase6DB:
    """In-memory relational mock of InsForge DB for Phase 6 tests."""

    def __init__(self, owner_a: UUID, owner_b: UUID):
        self.owner_a = str(owner_a)
        self.owner_b = str(owner_b)
        self.teams: list[dict] = []
        self.players: list[dict] = []
        self.team_players: list[dict] = []
        self.matches: list[dict] = []
        self.match_teams: list[dict] = []
        self.playing_xi: list[dict] = []
        self.innings: list[dict] = []
        self.deliveries: list[dict] = []
        self.recording_sessions: list[dict] = []
        self.video_segments: list[dict] = []
        self.event_markers: list[dict] = []
        self.player_highlights: list[dict] = []
        self.highlight_jobs: list[dict] = []
        self.player_milestones: list[dict] = []
        self.audit_logs: list[dict] = []

    def get_public_url(self, key: str) -> str:
        return f"https://cdn.example.com/{key}"

    def _table_list(self, table: str) -> list[dict]:
        return getattr(self, table, [])

    def _matches_filters(self, row: dict, filters: dict | None) -> bool:
        if not filters:
            return True
        for col, expr in filters.items():
            val = row.get(col)
            if expr.startswith("eq."):
                target = expr[3:]
                if target == "true":
                    if val is not True:
                        return False
                elif target == "false":
                    if val is not False:
                        return False
                else:
                    if str(val) != target:
                        return False
            elif expr.startswith("in.(") and expr.endswith(")"):
                inner = expr[4:-1]
                items = [x.strip() for x in inner.split(",") if x.strip()]
                if str(val) not in items:
                    return False
        return True

    async def select(
        self,
        table: str,
        *,
        columns: str = "*",
        filters: dict | None = None,
        order: str | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        rows = [dict(r) for r in self._table_list(table) if self._matches_filters(r, filters)]
        if limit is not None:
            rows = rows[:limit]
        return rows

    async def select_one(
        self,
        table: str,
        filters: dict | None = None,
        *,
        columns: str = "*",
    ) -> dict | None:
        rows = await self.select(table, columns=columns, filters=filters, limit=1)
        return rows[0] if rows else None

    async def insert_as_user(self, table: str, rows: list[dict], token: str) -> list[dict]:
        target = self._table_list(table)
        inserted = []
        for r in rows:
            item = {
                "id": str(uuid4()),
                "created_at": "2026-10-13T10:00:00Z",
                "updated_at": "2026-10-13T10:00:00Z",
                **r,
            }
            target.append(item)
            inserted.append(item)
        return inserted

    async def update_as_user(self, table: str, filters: dict, data: dict, token: str) -> list[dict]:
        target = self._table_list(table)
        updated = []
        for r in target:
            if self._matches_filters(r, filters):
                r.update(data)
                updated.append(dict(r))
        return updated

    async def delete_as_user(self, table: str, filters: dict, token: str) -> list[dict]:
        target = self._table_list(table)
        keep = []
        deleted = []
        for r in target:
            if self._matches_filters(r, filters):
                deleted.append(dict(r))
            else:
                keep.append(r)
        setattr(self, table, keep)
        return deleted


def _seed_phase6_archive(db: FakePhase6DB):
    """Seed two teams, two players with the same display_name ('Rohit Sharma'), a completed match, deliveries, highlights, and milestones."""
    owner_a = db.owner_a
    team1_id = str(uuid4())
    team2_id = str(uuid4())
    db.teams.extend([
        {"id": team1_id, "owner_id": owner_a, "name": "Mumbai Lions", "short_name": "MUM"},
        {"id": team2_id, "owner_id": owner_a, "name": "Chennai Kings", "short_name": "CHE"},
    ])

    # Two players with identical display_name to verify disambiguation by UUID
    rohit_1 = str(uuid4())
    rohit_2 = str(uuid4())
    bowler_1 = str(uuid4())
    db.players.extend([
        {
            "id": rohit_1,
            "owner_id": owner_a,
            "display_name": "Rohit Sharma",
            "role": "batter",
            "batting_hand": "right",
            "jersey_number": 45,
            "avatar_url": None,
            "created_at": "2026-01-01T00:00:00Z",
        },
        {
            "id": rohit_2,
            "owner_id": owner_a,
            "display_name": "Rohit Sharma",
            "role": "bowler",
            "batting_hand": "left",
            "jersey_number": 99,
            "avatar_url": None,
            "created_at": "2026-01-01T00:00:00Z",
        },
        {
            "id": bowler_1,
            "owner_id": owner_a,
            "display_name": "Jasprit Bumrah",
            "role": "bowler",
            "batting_hand": "right",
            "jersey_number": 93,
            "avatar_url": None,
            "created_at": "2026-01-01T00:00:00Z",
        },
    ])

    # Team history for rohit_1 (active on Mumbai Lions, historical on Chennai Kings)
    db.team_players.extend([
        {
            "id": str(uuid4()),
            "team_id": team1_id,
            "player_id": rohit_1,
            "is_active": True,
        },
        {
            "id": str(uuid4()),
            "team_id": team2_id,
            "player_id": rohit_1,
            "is_active": False,
        },
    ])

    match_id = str(uuid4())
    db.matches.append({
        "id": match_id,
        "owner_id": owner_a,
        "title": "Finals Showdown",
        "format": "T20",
        "custom_overs": None,
        "overs_per_innings": 20,
        "tournament": "Premier Trophy 2026",
        "venue": "Wankhede Stadium",
        "scheduled_at": "2026-05-15T14:00:00Z",
        "status": "completed",
        "created_at": "2026-05-15T14:00:00Z",
        "updated_at": "2026-05-15T18:00:00Z",
    })

    # Snapshot team names at match time
    db.match_teams.extend([
        {"id": str(uuid4()), "match_id": match_id, "team_id": team1_id, "team_name": "Mumbai Lions (2026)", "batting_order": 1},
        {"id": str(uuid4()), "match_id": match_id, "team_id": team2_id, "team_name": "Chennai Kings (2026)", "batting_order": 2},
    ])

    # Snapshot playing_xi names at match time
    db.playing_xi.extend([
        {"id": str(uuid4()), "match_id": match_id, "team_id": team1_id, "player_id": rohit_1, "player_name": "Rohit Sharma (Capt)", "batting_position": 1},
        {"id": str(uuid4()), "match_id": match_id, "team_id": team2_id, "player_id": bowler_1, "player_name": "Jasprit Bumrah", "batting_position": 1},
    ])

    innings_id = str(uuid4())
    db.innings.append({
        "id": innings_id,
        "match_id": match_id,
        "innings_number": 1,
        "batting_team_id": team1_id,
        "bowling_team_id": team2_id,
        "overs_limit": 20,
        "status": "completed",
        "total_runs": 54,
        "total_wickets": 0,
        "total_legal_balls": 9,
        "total_wides": 0,
        "total_no_balls": 0,
        "total_byes": 0,
        "total_leg_byes": 0,
        "total_penalty_runs": 0,
    })

    # 9 sixes by rohit_1 against bowler_1 = 54 runs
    for seq in range(1, 10):
        deliv_id = str(uuid4())
        db.deliveries.append({
            "id": deliv_id,
            "innings_id": innings_id,
            "match_id": match_id,
            "sequence_no": seq,
            "over_no": (seq - 1) // 6,
            "ball_in_over": ((seq - 1) % 6) + 1,
            "display_over": f"{(seq - 1) // 6}.{((seq - 1) % 6) + 1}",
            "striker_id": rohit_1,
            "non_striker_id": rohit_2,
            "bowler_id": bowler_1,
            "batter_runs": 6,
            "extra_type": None,
            "extra_runs": 0,
            "total_runs": 6,
            "is_legal": True,
            "is_boundary": True,
            "boundary_type": 6,
            "is_batter_boundary": True,
            "is_wicket": False,
            "wicket_type": None,
            "dismissed_player_id": None,
            "fielder_id": None,
            "is_voided": False,
            "created_at": "2026-05-15T15:00:00Z",
        })
        if seq in (1, 9):
            db.player_highlights.append({
                "id": str(uuid4()),
                "owner_id": owner_a,
                "player_id": rohit_1,
                "match_id": match_id,
                "innings_id": innings_id,
                "delivery_id": deliv_id,
                "marker_id": None,
                "session_id": None,
                "event_type": "six",
                "status": "ready",
                "duration_sec": 9.0,
                "video_key": f"highlights/{match_id}/{deliv_id}.mp4",
                "video_url": f"https://cdn.example.com/{deliv_id}.mp4",
                "thumbnail_key": None,
                "thumbnail_url": None,
                "delivery_metadata": {"over_display": "0.1", "striker_name": "Rohit Sharma"},
                "version": 1,
                "created_at": f"2026-05-15T15:0{seq}:00Z",
                "updated_at": f"2026-05-15T15:0{seq}:00Z",
            })
        if seq == 9:
            db.player_milestones.append({
                "id": str(uuid4()),
                "owner_id": owner_a,
                "player_id": rohit_1,
                "match_id": match_id,
                "innings_id": innings_id,
                "delivery_id": deliv_id,
                "milestone_type": "FIFTY",
                "threshold": 50,
                "batter_score": 54,
                "balls_faced": 9,
                "fours_count": 0,
                "sixes_count": 9,
                "over_display": "1.3",
                "animation_version": 1,
                "is_valid": True,
                "invalidated_reason": None,
                "metadata": {"player_name": "Rohit Sharma"},
                "created_at": "2026-05-15T15:09:00Z",
                "updated_at": "2026-05-15T15:09:00Z",
            })

    return {
        "team1_id": team1_id,
        "team2_id": team2_id,
        "rohit_1": rohit_1,
        "rohit_2": rohit_2,
        "bowler_1": bowler_1,
        "match_id": match_id,
        "innings_id": innings_id,
    }


@pytest.mark.asyncio
async def test_player_profile_aggregation_filters_and_pagination():
    """Verify player profile returns team history, batting/bowling stats, tournament filters, and paginated highlights."""
    owner_a = uuid4()
    owner_b = uuid4()
    db = FakePhase6DB(owner_a, owner_b)
    ids = _seed_phase6_archive(db)

    profile = await get_player_profile(
        db=db,
        player_id=ids["rohit_1"],
        owner_id=str(owner_a),
        tournament="Premier Trophy 2026",
        limit=1,
        offset=0,
    )

    assert profile["player"]["display_name"] == "Rohit Sharma"
    assert len(profile["team_history"]) == 2
    assert profile["career_stats"]["innings_batted"] == 1
    assert profile["career_stats"]["total_runs"] == 54
    assert profile["career_stats"]["sixes"] == 9
    assert profile["career_stats"]["fifties"] == 1
    assert profile["career_stats"]["highest_score"] == 54
    assert len(profile["match_performances"]) == 1
    assert profile["match_performances"][0]["tournament"] == "Premier Trophy 2026"
    assert profile["match_performances"][0]["runs"] == 54
    # Pagination check: 2 total highlights, limit=1 -> has_more_highlights=True
    assert profile["highlights_total"] == 2
    assert len(profile["highlights"]) == 1
    assert profile["has_more_highlights"] is True
    assert len(profile["milestones"]) == 1
    assert profile["milestones"][0]["milestone_type"] == "FIFTY"


@pytest.mark.asyncio
async def test_match_archive_filters_and_duplicate_player_disambiguation():
    """Verify match archive filters by Team A/B, specific player UUID (disambiguating duplicate names), tournament, date, and highlight type."""
    owner_a = uuid4()
    owner_b = uuid4()
    db = FakePhase6DB(owner_a, owner_b)
    ids = _seed_phase6_archive(db)

    # Filter by rohit_1 UUID + tournament + highlight_type='fifty'
    page1 = await search_match_archive(
        db=db,
        owner_id=str(owner_a),
        player_id=ids["rohit_1"],
        tournament="Premier",
        highlight_type="fifty",
        date_from="2026-05-01",
        date_to="2026-05-31",
        limit=10,
        offset=0,
    )
    assert page1["total"] == 1
    assert str(page1["items"][0]["match"]["id"]) == ids["match_id"]
    assert page1["items"][0]["milestones_count"] == 1
    assert page1["items"][0]["highlights_count"] == 2

    # Filter by century -> should return 0 matches
    page_century = await search_match_archive(
        db=db,
        owner_id=str(owner_a),
        highlight_type="century",
    )
    assert page_century["total"] == 0


@pytest.mark.asyncio
async def test_historical_identity_preserved_when_squad_or_names_change():
    """
    Verify that renaming a player in `players` or a team in `teams` after a match
    does NOT corrupt historical match scorecards because `playing_xi.player_name`
    and `match_teams.team_name` snapshots take precedence.
    """
    owner_a = uuid4()
    owner_b = uuid4()
    db = FakePhase6DB(owner_a, owner_b)
    ids = _seed_phase6_archive(db)

    # Mutate live team name and live player name in master tables
    db.teams[0]["name"] = "Renamed Franchise 2029"
    db.players[0]["display_name"] = "Renamed Player 2029"

    scorecard = await get_scorecard(db, ids["innings_id"])
    # Historical snapshot names must still be returned!
    assert scorecard.batting_team_name == "Mumbai Lions (2026)"
    assert scorecard.batters[0].player_name == "Rohit Sharma (Capt)"


@pytest.mark.asyncio
async def test_cross_user_recording_and_media_authorization_denial():
    """
    Security test: User B cannot access, update, delete, or sign media URLs for
    User A's private recording sessions by changing an ID in the request.
    """
    owner_a = uuid4()
    owner_b = uuid4()
    db = FakePhase6DB(owner_a, owner_b)
    ids = _seed_phase6_archive(db)

    session_id = str(uuid4())
    db.recording_sessions.append({
        "id": session_id,
        "match_id": ids["match_id"],
        "owner_id": str(owner_a),
        "session_name": "Session 1",
        "status": "completed",
        "upload_status": "uploaded",
        "processing_status": "completed",
        "media_asset_id": "recordings/session-1.webm",
        "started_at": "2026-05-15T14:00:00Z",
    })

    # User B tries to GET User A's recording session -> 403 Forbidden
    with pytest.raises(HTTPException) as exc_get:
        await get_recording_session(db, session_id, owner_id=str(owner_b))
    assert exc_get.value.status_code == 403

    # User B tries to PATCH User A's recording session -> 403 Forbidden
    with pytest.raises(HTTPException) as exc_patch:
        await update_recording_session(
            db, session_id, RecordingSessionUpdate(status="failed"), "tok-b", owner_id=str(owner_b)
        )
    assert exc_patch.value.status_code == 403

    # User B tries to DELETE User A's recording session -> 403 Forbidden
    with pytest.raises(HTTPException) as exc_del:
        await delete_recording_session(db, session_id, "tok-b", owner_id=str(owner_b))
    assert exc_del.value.status_code == 403

    # User B tries to sign User A's highlight video_key -> 403 Forbidden
    video_key = db.player_highlights[0]["video_key"]
    with pytest.raises(HTTPException) as exc_sign:
        await generate_signed_media_url(db, key=video_key, owner_id=str(owner_b))
    assert exc_sign.value.status_code == 403

    # User A CAN sign their own highlight video_key -> succeeds
    signed = await generate_signed_media_url(db, key=video_key, owner_id=str(owner_a))
    assert signed["key"] == video_key
    assert "sig=" in signed["signed_url"]


def test_expiring_hmac_signed_media_tokens():
    """Verify HMAC media token signature validation, expiry enforcement, and tamper rejection."""
    owner_id = str(uuid4())
    media_key = "highlights/match-1/clip-1.mp4"
    expires_at, signature = create_signed_media_token(media_key, owner_id, expires_in=300)

    assert verify_signed_media_token(media_key, owner_id, expires_at, signature) is True

    # Expired timestamp must return False
    assert verify_signed_media_token(media_key, owner_id, expires_at - 10000, signature) is False

    # Tampered signature must return False
    assert verify_signed_media_token(media_key, owner_id, expires_at, signature + "tampered") is False


@pytest.mark.asyncio
async def test_backup_export_and_restoration_verification_and_job_recovery():
    """Verify backup export SHA-256 manifest, restoration verification, tamper detection, and session recovery."""
    owner_a = uuid4()
    owner_b = uuid4()
    db = FakePhase6DB(owner_a, owner_b)
    ids = _seed_phase6_archive(db)

    # Add an interrupted recording session to test recovery
    session_id = str(uuid4())
    db.recording_sessions.append({
        "id": session_id,
        "match_id": ids["match_id"],
        "owner_id": str(owner_a),
        "session_name": "Interrupted Cam",
        "status": "interrupted",
        "processing_status": "failed",
        "media_asset_id": "recordings/cam1.webm",
        "created_at": "2025-01-01T00:00:00Z",
    })

    retry_res = await retry_failed_jobs_and_sessions(db, str(owner_a), "tok-a", ids["match_id"])
    assert retry_res["recovered_recording_sessions"] == 1
    assert db.recording_sessions[0]["status"] == "completed"

    # Export backup manifest
    manifest = await export_owner_backup(db, str(owner_a), "tok-a")
    assert manifest["counts"]["matches"] == 1
    assert manifest["counts"]["deliveries"] == 9
    assert len(manifest["checksum_sha256"]) == 64

    # Verify untampered backup manifest -> valid=True
    verify_ok = verify_backup_manifest(manifest["checksum_sha256"], manifest["data"])
    assert verify_ok["valid"] is True
    assert verify_ok["counts"]["deliveries"] == 9

    # Tamper with backup data -> valid=False
    tampered_data = dict(manifest["data"])
    tampered_data["matches"] = []
    verify_bad = verify_backup_manifest(manifest["checksum_sha256"], tampered_data)
    assert verify_bad["valid"] is False

    # Retention policy check: expired session (created 2025-01-01) is detected while highlights are preserved
    retention_res = await apply_retention_policy(
        db, str(owner_a), "tok-a", retention_days=90, dry_run=True
    )
    assert retention_res["dry_run"] is True
    assert retention_res["expired_sessions_found"] == 1
    assert retention_res["highlights_preserved"] == 2


@pytest.mark.asyncio
async def test_player_and_team_deletion_safeguard_preserves_completed_match_history():
    """
    Spec 2.3 Safeguard: Player and team deletions must not silently destroy completed-match history.
    Attempting to delete a player or team with completed match/delivery records raises 409 Conflict.
    """
    from app.services.players import delete_player
    from app.services.teams import delete_team

    owner_a = uuid4()
    owner_b = uuid4()
    db = FakePhase6DB(owner_a, owner_b)
    ids = _seed_phase6_archive(db)

    with pytest.raises(HTTPException) as exc_player:
        await delete_player(db, ids["rohit_1"], "tok-a")
    assert exc_player.value.status_code == 409

    with pytest.raises(HTTPException) as exc_team:
        await delete_team(db, ids["team1_id"], "tok-a")
    assert exc_team.value.status_code == 409

