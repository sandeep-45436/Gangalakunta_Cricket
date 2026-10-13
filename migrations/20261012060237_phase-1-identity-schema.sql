-- =============================================================================
-- Phase 1 — Identity and Match Setup
-- =============================================================================
-- Tables: teams, players, team_players, matches, match_teams,
--         playing_xi, match_substitutes
--
-- Design decisions:
--   • Every primary key is a UUID (gen_random_uuid()).
--   • Players have a stable ID independent of team membership.
--   • Playing XI is snapshotted per (match, team) — editing a squad later
--     cannot change a historical XI.
--   • Matches snapshot participating teams so renaming a team does not alter
--     the historical match record.
--   • owner_id on teams/matches references auth.users(id); RLS restricts
--     mutations to the owner. All authenticated users may read.
--   • system.update_updated_at() is used for all updated_at triggers.
-- =============================================================================

-- ─── teams ────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.teams (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id    UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    name        TEXT        NOT NULL,
    short_name  TEXT,                           -- e.g. "IND", "AUS"
    logo_url    TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT teams_name_owner_unique UNIQUE (owner_id, name)
);

ALTER TABLE public.teams ENABLE ROW LEVEL SECURITY;

CREATE POLICY "authenticated users can read teams"
    ON public.teams FOR SELECT TO authenticated
    USING (true);

CREATE POLICY "owners can insert teams"
    ON public.teams FOR INSERT TO authenticated
    WITH CHECK (owner_id = (SELECT auth.uid()));

CREATE POLICY "owners can update teams"
    ON public.teams FOR UPDATE TO authenticated
    USING (owner_id = (SELECT auth.uid()))
    WITH CHECK (owner_id = (SELECT auth.uid()));

CREATE POLICY "owners can delete teams"
    ON public.teams FOR DELETE TO authenticated
    USING (owner_id = (SELECT auth.uid()));

GRANT SELECT ON public.teams TO authenticated;
GRANT INSERT, UPDATE, DELETE ON public.teams TO authenticated;

CREATE TRIGGER teams_updated_at
    BEFORE UPDATE ON public.teams
    FOR EACH ROW EXECUTE FUNCTION system.update_updated_at();


-- ─── players ──────────────────────────────────────────────────────────────────
-- A player has a stable identity independent of which team(s) they belong to.
-- Two players may share the same display name; their UUIDs are always distinct.
CREATE TABLE IF NOT EXISTS public.players (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id        UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name       TEXT        NOT NULL,
    display_name    TEXT,                       -- optional short/nickname
    batting_style   TEXT,                       -- e.g. "Right-hand bat"
    bowling_style   TEXT,                       -- e.g. "Right-arm fast"
    role            TEXT,                       -- Batter | Bowler | All-rounder | WK
    jersey_number   INT,
    photo_url       TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.players ENABLE ROW LEVEL SECURITY;

CREATE POLICY "authenticated users can read players"
    ON public.players FOR SELECT TO authenticated
    USING (true);

CREATE POLICY "owners can insert players"
    ON public.players FOR INSERT TO authenticated
    WITH CHECK (owner_id = (SELECT auth.uid()));

CREATE POLICY "owners can update players"
    ON public.players FOR UPDATE TO authenticated
    USING (owner_id = (SELECT auth.uid()))
    WITH CHECK (owner_id = (SELECT auth.uid()));

CREATE POLICY "owners can delete players"
    ON public.players FOR DELETE TO authenticated
    USING (owner_id = (SELECT auth.uid()));

GRANT SELECT ON public.players TO authenticated;
GRANT INSERT, UPDATE, DELETE ON public.players TO authenticated;

CREATE TRIGGER players_updated_at
    BEFORE UPDATE ON public.players
    FOR EACH ROW EXECUTE FUNCTION system.update_updated_at();


-- ─── team_players (squad membership) ─────────────────────────────────────────
-- Links a player to a team. A player can be in multiple teams over time.
-- Deleting a team_players row removes them from the squad but does NOT
-- retroactively change playing_xi records (those reference player_id directly).
CREATE TABLE IF NOT EXISTS public.team_players (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id     UUID        NOT NULL REFERENCES public.teams(id) ON DELETE CASCADE,
    player_id   UUID        NOT NULL REFERENCES public.players(id) ON DELETE CASCADE,
    is_active   BOOLEAN     NOT NULL DEFAULT true,
    joined_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT team_players_unique UNIQUE (team_id, player_id)
);

ALTER TABLE public.team_players ENABLE ROW LEVEL SECURITY;

-- Helper: is the current user the owner of a team?
-- SECURITY DEFINER + pinned search_path prevents RLS recursion.
CREATE OR REPLACE FUNCTION public.is_team_owner(p_team_id UUID)
RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.teams
        WHERE id = p_team_id
          AND owner_id = (SELECT auth.uid())
    )
$$;

CREATE POLICY "authenticated users can read team_players"
    ON public.team_players FOR SELECT TO authenticated
    USING (true);

CREATE POLICY "team owners can insert squad members"
    ON public.team_players FOR INSERT TO authenticated
    WITH CHECK (public.is_team_owner(team_id));

CREATE POLICY "team owners can update squad members"
    ON public.team_players FOR UPDATE TO authenticated
    USING (public.is_team_owner(team_id))
    WITH CHECK (public.is_team_owner(team_id));

CREATE POLICY "team owners can delete squad members"
    ON public.team_players FOR DELETE TO authenticated
    USING (public.is_team_owner(team_id));

GRANT SELECT ON public.team_players TO authenticated;
GRANT INSERT, UPDATE, DELETE ON public.team_players TO authenticated;

CREATE INDEX IF NOT EXISTS idx_team_players_team_id
    ON public.team_players(team_id);
CREATE INDEX IF NOT EXISTS idx_team_players_player_id
    ON public.team_players(player_id);


-- ─── matches ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.matches (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id        UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title           TEXT        NOT NULL,
    format          TEXT        NOT NULL,       -- T20 | ODI | Test | T10 | Custom
    venue           TEXT,
    scheduled_at    TIMESTAMPTZ,
    status          TEXT        NOT NULL DEFAULT 'upcoming',
                                                -- upcoming | live | completed | cancelled
    overs_per_innings INT,                      -- null = Test
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT matches_status_check CHECK (
        status IN ('upcoming', 'live', 'completed', 'cancelled')
    ),
    CONSTRAINT matches_format_check CHECK (
        format IN ('T20', 'ODI', 'Test', 'T10', 'Custom')
    )
);

ALTER TABLE public.matches ENABLE ROW LEVEL SECURITY;

CREATE POLICY "authenticated users can read matches"
    ON public.matches FOR SELECT TO authenticated
    USING (true);

CREATE POLICY "owners can insert matches"
    ON public.matches FOR INSERT TO authenticated
    WITH CHECK (owner_id = (SELECT auth.uid()));

CREATE POLICY "owners can update matches"
    ON public.matches FOR UPDATE TO authenticated
    USING (owner_id = (SELECT auth.uid()))
    WITH CHECK (owner_id = (SELECT auth.uid()));

CREATE POLICY "owners can delete matches"
    ON public.matches FOR DELETE TO authenticated
    USING (owner_id = (SELECT auth.uid()));

GRANT SELECT ON public.matches TO authenticated;
GRANT INSERT, UPDATE, DELETE ON public.matches TO authenticated;

CREATE TRIGGER matches_updated_at
    BEFORE UPDATE ON public.matches
    FOR EACH ROW EXECUTE FUNCTION system.update_updated_at();


-- ─── match_teams (which two teams play in a match) ───────────────────────────
-- Snapshots the team at the time of match creation. team_name is denormalised
-- so renaming the team later does not silently change historical records.
CREATE TABLE IF NOT EXISTS public.match_teams (
    id              UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id        UUID    NOT NULL REFERENCES public.matches(id) ON DELETE CASCADE,
    team_id         UUID    NOT NULL REFERENCES public.teams(id)   ON DELETE RESTRICT,
    team_name       TEXT    NOT NULL,           -- snapshot at match creation time
    batting_order   INT     NOT NULL,           -- 1 = bat first, 2 = bat second
    CONSTRAINT match_teams_unique UNIQUE (match_id, team_id),
    CONSTRAINT match_teams_order_unique UNIQUE (match_id, batting_order),
    CONSTRAINT match_teams_order_check CHECK (batting_order IN (1, 2))
);

ALTER TABLE public.match_teams ENABLE ROW LEVEL SECURITY;

-- Helper: is the current user the owner of a match?
CREATE OR REPLACE FUNCTION public.is_match_owner(p_match_id UUID)
RETURNS BOOLEAN
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
    SELECT EXISTS (
        SELECT 1 FROM public.matches
        WHERE id = p_match_id
          AND owner_id = (SELECT auth.uid())
    )
$$;

CREATE POLICY "authenticated users can read match_teams"
    ON public.match_teams FOR SELECT TO authenticated
    USING (true);

CREATE POLICY "match owners can insert match_teams"
    ON public.match_teams FOR INSERT TO authenticated
    WITH CHECK (public.is_match_owner(match_id));

CREATE POLICY "match owners can update match_teams"
    ON public.match_teams FOR UPDATE TO authenticated
    USING (public.is_match_owner(match_id))
    WITH CHECK (public.is_match_owner(match_id));

CREATE POLICY "match owners can delete match_teams"
    ON public.match_teams FOR DELETE TO authenticated
    USING (public.is_match_owner(match_id));

GRANT SELECT ON public.match_teams TO authenticated;
GRANT INSERT, UPDATE, DELETE ON public.match_teams TO authenticated;

CREATE INDEX IF NOT EXISTS idx_match_teams_match_id
    ON public.match_teams(match_id);


-- ─── playing_xi ───────────────────────────────────────────────────────────────
-- The 11 players confirmed to start for a given team in a specific match.
-- Snapshotted at selection time — editing the squad later must NOT modify this.
-- Uniqueness is enforced at (match_id, team_id, player_id).
CREATE TABLE IF NOT EXISTS public.playing_xi (
    id              UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id        UUID    NOT NULL REFERENCES public.matches(id) ON DELETE CASCADE,
    team_id         UUID    NOT NULL REFERENCES public.teams(id)   ON DELETE RESTRICT,
    player_id       UUID    NOT NULL REFERENCES public.players(id) ON DELETE RESTRICT,
    -- Snapshot fields — protect historical accuracy
    player_name     TEXT    NOT NULL,           -- snapshot of player name at selection
    batting_position INT,                       -- 1–11, nullable until confirmed
    is_captain      BOOLEAN NOT NULL DEFAULT false,
    is_wicketkeeper BOOLEAN NOT NULL DEFAULT false,
    selected_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT playing_xi_unique UNIQUE (match_id, team_id, player_id),
    CONSTRAINT playing_xi_batting_position_range CHECK (
        batting_position IS NULL OR (batting_position >= 1 AND batting_position <= 11)
    )
);

ALTER TABLE public.playing_xi ENABLE ROW LEVEL SECURITY;

CREATE POLICY "authenticated users can read playing_xi"
    ON public.playing_xi FOR SELECT TO authenticated
    USING (true);

CREATE POLICY "match owners can insert playing_xi"
    ON public.playing_xi FOR INSERT TO authenticated
    WITH CHECK (public.is_match_owner(match_id));

CREATE POLICY "match owners can update playing_xi"
    ON public.playing_xi FOR UPDATE TO authenticated
    USING (public.is_match_owner(match_id))
    WITH CHECK (public.is_match_owner(match_id));

CREATE POLICY "match owners can delete playing_xi"
    ON public.playing_xi FOR DELETE TO authenticated
    USING (public.is_match_owner(match_id));

GRANT SELECT ON public.playing_xi TO authenticated;
GRANT INSERT, UPDATE, DELETE ON public.playing_xi TO authenticated;

CREATE INDEX IF NOT EXISTS idx_playing_xi_match_id
    ON public.playing_xi(match_id);
CREATE INDEX IF NOT EXISTS idx_playing_xi_match_team
    ON public.playing_xi(match_id, team_id);
CREATE INDEX IF NOT EXISTS idx_playing_xi_player_id
    ON public.playing_xi(player_id);


-- ─── match_substitutes ────────────────────────────────────────────────────────
-- Declared substitutes and impact players for a match/team.
-- Not part of the starting XI but recorded for regulatory compliance.
CREATE TABLE IF NOT EXISTS public.match_substitutes (
    id              UUID    PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id        UUID    NOT NULL REFERENCES public.matches(id) ON DELETE CASCADE,
    team_id         UUID    NOT NULL REFERENCES public.teams(id)   ON DELETE RESTRICT,
    player_id       UUID    NOT NULL REFERENCES public.players(id) ON DELETE RESTRICT,
    player_name     TEXT    NOT NULL,           -- snapshot
    substitute_type TEXT    NOT NULL DEFAULT 'substitute',
                                                -- substitute | impact | concussion
    declared_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT match_substitutes_unique UNIQUE (match_id, team_id, player_id),
    CONSTRAINT match_substitutes_type_check CHECK (
        substitute_type IN ('substitute', 'impact', 'concussion')
    )
);

ALTER TABLE public.match_substitutes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "authenticated users can read match_substitutes"
    ON public.match_substitutes FOR SELECT TO authenticated
    USING (true);

CREATE POLICY "match owners can insert match_substitutes"
    ON public.match_substitutes FOR INSERT TO authenticated
    WITH CHECK (public.is_match_owner(match_id));

CREATE POLICY "match owners can update match_substitutes"
    ON public.match_substitutes FOR UPDATE TO authenticated
    USING (public.is_match_owner(match_id))
    WITH CHECK (public.is_match_owner(match_id));

CREATE POLICY "match owners can delete match_substitutes"
    ON public.match_substitutes FOR DELETE TO authenticated
    USING (public.is_match_owner(match_id));

GRANT SELECT ON public.match_substitutes TO authenticated;
GRANT INSERT, UPDATE, DELETE ON public.match_substitutes TO authenticated;

CREATE INDEX IF NOT EXISTS idx_match_substitutes_match_id
    ON public.match_substitutes(match_id);


-- =============================================================================
-- Database-level constraint: a match must have exactly 2 teams.
-- Enforced at the application layer (FastAPI) — PostgreSQL cannot enforce
-- a "count = 2" as a table constraint, so we rely on the service layer +
-- the unique constraint on (match_id, batting_order IN (1,2)).
-- =============================================================================
