"""
Unit tests for Pydantic schemas — validate all business rules
enforced at the schema layer without any DB or HTTP calls.
"""
import pytest
from uuid import uuid4
from pydantic import ValidationError

from app.schemas.teams import TeamCreate, TeamUpdate, SquadImportRequest, SquadImportEntry
from app.schemas.players import PlayerCreate, PlayerUpdate
from app.schemas.matches import (
    MatchCreate, MatchUpdate,
    PlayingXISetRequest, PlayingXIEntry,
    SubstituteAdd,
    MatchTeamInput,
)


# ── TeamCreate ─────────────────────────────────────────────────────────────────

class TestTeamCreate:
    def test_valid(self):
        t = TeamCreate(name="Mumbai Indians", short_name="MI")
        assert t.name == "Mumbai Indians"
        assert t.short_name == "MI"

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            TeamCreate(name="")

    def test_short_name_too_long_rejected(self):
        with pytest.raises(ValidationError):
            TeamCreate(name="Team", short_name="X" * 11)

    def test_optional_fields_default_none(self):
        t = TeamCreate(name="Team A")
        assert t.short_name is None
        assert t.logo_url is None


# ── PlayerCreate ───────────────────────────────────────────────────────────────

class TestPlayerCreate:
    def test_valid_minimal(self):
        p = PlayerCreate(full_name="Virat Kohli")
        assert p.full_name == "Virat Kohli"
        assert p.role is None

    def test_valid_with_role(self):
        p = PlayerCreate(full_name="Kohli", role="Batter")
        assert p.role == "Batter"

    def test_invalid_role_rejected(self):
        with pytest.raises(ValidationError):
            PlayerCreate(full_name="X", role="Fielder")

    def test_all_valid_roles(self):
        for role in ("Batter", "Bowler", "All-rounder", "WK"):
            p = PlayerCreate(full_name="Player", role=role)
            assert p.role == role

    def test_jersey_number_bounds(self):
        PlayerCreate(full_name="P", jersey_number=0)
        PlayerCreate(full_name="P", jersey_number=999)
        with pytest.raises(ValidationError):
            PlayerCreate(full_name="P", jersey_number=-1)
        with pytest.raises(ValidationError):
            PlayerCreate(full_name="P", jersey_number=1000)

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            PlayerCreate(full_name="")


# ── SquadImportRequest ─────────────────────────────────────────────────────────

class TestSquadImportRequest:
    def test_valid(self):
        req = SquadImportRequest(players=[
            SquadImportEntry(full_name="Player A"),
            SquadImportEntry(full_name="Player B"),
        ])
        assert len(req.players) == 2

    def test_duplicate_names_rejected(self):
        with pytest.raises(ValidationError, match="Duplicate player names"):
            SquadImportRequest(players=[
                SquadImportEntry(full_name="Player A"),
                SquadImportEntry(full_name="Player A"),   # exact duplicate
            ])

    def test_empty_list_rejected(self):
        with pytest.raises(ValidationError):
            SquadImportRequest(players=[])


# ── MatchCreate ────────────────────────────────────────────────────────────────

def _make_teams(id1=None, id2=None, order1=1, order2=2):
    return [
        MatchTeamInput(team_id=id1 or uuid4(), batting_order=order1),
        MatchTeamInput(team_id=id2 or uuid4(), batting_order=order2),
    ]


class TestMatchCreate:
    def test_valid_t20(self):
        m = MatchCreate(title="Finals", format="T20", teams=_make_teams())
        assert m.format == "T20"

    def test_invalid_format_rejected(self):
        with pytest.raises(ValidationError):
            MatchCreate(title="X", format="IPL", teams=_make_teams())

    def test_same_team_twice_rejected(self):
        same_id = uuid4()
        with pytest.raises(ValidationError, match="same team twice"):
            MatchCreate(title="X", format="T20", teams=_make_teams(id1=same_id, id2=same_id))

    def test_duplicate_batting_order_rejected(self):
        with pytest.raises(ValidationError, match="distinct batting_order"):
            MatchCreate(title="X", format="T20", teams=_make_teams(order1=1, order2=1))

    def test_wrong_team_count_rejected(self):
        with pytest.raises(ValidationError):
            MatchCreate(title="X", format="T20", teams=[MatchTeamInput(team_id=uuid4(), batting_order=1)])

    def test_all_valid_formats(self):
        for fmt in ("T20", "ODI", "Test", "T10", "Custom"):
            m = MatchCreate(title="M", format=fmt, teams=_make_teams())
            assert m.format == fmt


# ── PlayingXISetRequest ────────────────────────────────────────────────────────

def _xi_players(n: int, *, duplicate_id=None):
    from uuid import uuid4
    players = []
    for i in range(n):
        pid = duplicate_id if (duplicate_id and i == n - 1) else uuid4()
        players.append(PlayingXIEntry(player_id=pid, batting_position=i + 1))
    return players


class TestPlayingXISetRequest:
    def test_valid_11_players(self):
        req = PlayingXISetRequest(team_id=uuid4(), players=_xi_players(11))
        assert len(req.players) == 11

    def test_fewer_than_11_rejected(self):
        with pytest.raises(ValidationError):
            PlayingXISetRequest(team_id=uuid4(), players=_xi_players(10))

    def test_more_than_11_rejected(self):
        with pytest.raises(ValidationError):
            PlayingXISetRequest(team_id=uuid4(), players=_xi_players(12))

    def test_duplicate_player_rejected(self):
        shared_id = uuid4()
        players = _xi_players(10) + [PlayingXIEntry(player_id=shared_id, batting_position=11)]
        # Manually add the shared_id at position 0 to create a duplicate
        players[0] = PlayingXIEntry(player_id=shared_id, batting_position=1)
        with pytest.raises(ValidationError, match="player cannot appear twice"):
            PlayingXISetRequest(team_id=uuid4(), players=players)

    def test_at_most_one_captain(self):
        players = _xi_players(11)
        players[0] = PlayingXIEntry(player_id=players[0].player_id, is_captain=True)
        players[1] = PlayingXIEntry(player_id=players[1].player_id, is_captain=True)
        with pytest.raises(ValidationError, match="at most one captain"):
            PlayingXISetRequest(team_id=uuid4(), players=players)

    def test_at_most_one_keeper(self):
        players = _xi_players(11)
        players[0] = PlayingXIEntry(player_id=players[0].player_id, is_wicketkeeper=True)
        players[1] = PlayingXIEntry(player_id=players[1].player_id, is_wicketkeeper=True)
        with pytest.raises(ValidationError, match="at most one wicketkeeper"):
            PlayingXISetRequest(team_id=uuid4(), players=players)

    def test_batting_position_bounds(self):
        # batting_position=0 should be rejected at PlayingXIEntry level (ge=1)
        with pytest.raises(ValidationError):
            PlayingXIEntry(player_id=uuid4(), batting_position=0)
        # batting_position=12 should be rejected (le=11)
        with pytest.raises(ValidationError):
            PlayingXIEntry(player_id=uuid4(), batting_position=12)
        # valid bounds
        PlayingXIEntry(player_id=uuid4(), batting_position=1)
        PlayingXIEntry(player_id=uuid4(), batting_position=11)


# ── SubstituteAdd ─────────────────────────────────────────────────────────────

class TestSubstituteAdd:
    def test_valid_substitute_types(self):
        for st in ("substitute", "impact", "concussion"):
            s = SubstituteAdd(team_id=uuid4(), player_id=uuid4(), substitute_type=st)
            assert s.substitute_type == st

    def test_invalid_type_rejected(self):
        with pytest.raises(ValidationError):
            SubstituteAdd(team_id=uuid4(), player_id=uuid4(), substitute_type="twelfth_man")


# ── MatchUpdate ───────────────────────────────────────────────────────────────

class TestMatchUpdate:
    def test_valid_status_values(self):
        for st in ("upcoming", "live", "completed", "cancelled"):
            u = MatchUpdate(status=st)
            assert u.status == st

    def test_invalid_status_rejected(self):
        with pytest.raises(ValidationError):
            MatchUpdate(status="in_progress")
