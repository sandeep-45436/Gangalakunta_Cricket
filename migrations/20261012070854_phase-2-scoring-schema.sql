-- =============================================================================
-- Phase 2 — Scoring Engine & Delivery Records
-- =============================================================================
-- Tables: innings, deliveries
--
-- Design decisions:
--   • Innings tracks the current active state of batting/bowling sides,
--     total score, wickets, balls, target, and currently active players.
--   • Deliveries table stores the canonical ball-by-ball domain events.
--   • Historical accuracy: Striker, non-striker, and bowler IDs are permanently
--     snapshotted at the time of delivery.
--   • Scorecards and stats can be calculated or reconstructed directly from
--     the canonical delivery records.
--   • Versioning & Corrections: Deliveries have revision_no, is_voided,
--     and voided_reason flags to support audited reversals and replacements.
--   • Idempotency: idempotency_key prevents duplicate delivery submissions
--     on mobile network retries.
--   • RLS: SELECT allowed for all authenticated users, mutations restricted
--     to match owners via is_match_owner(match_id).
-- =============================================================================

-- ─── innings ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.innings (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id            UUID        NOT NULL REFERENCES public.matches(id) ON DELETE CASCADE,
    innings_number      INT         NOT NULL,
    batting_team_id     UUID        NOT NULL REFERENCES public.teams(id) ON DELETE RESTRICT,
    bowling_team_id     UUID        NOT NULL REFERENCES public.teams(id) ON DELETE RESTRICT,
    current_striker_id  UUID        REFERENCES public.players(id) ON DELETE SET NULL,
    current_non_striker_id UUID     REFERENCES public.players(id) ON DELETE SET NULL,
    current_bowler_id   UUID        REFERENCES public.players(id) ON DELETE SET NULL,
    target_runs         INT,
    total_runs          INT         NOT NULL DEFAULT 0,
    total_wickets       INT         NOT NULL DEFAULT 0,
    total_legal_balls   INT         NOT NULL DEFAULT 0,
    total_wides         INT         NOT NULL DEFAULT 0,
    total_no_balls      INT         NOT NULL DEFAULT 0,
    total_byes          INT         NOT NULL DEFAULT 0,
    total_leg_byes      INT         NOT NULL DEFAULT 0,
    total_penalty_runs  INT         NOT NULL DEFAULT 0,
    status              TEXT        NOT NULL DEFAULT 'in_progress',
    completed_reason    TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT innings_match_number_unique UNIQUE (match_id, innings_number),
    CONSTRAINT innings_number_check CHECK (innings_number IN (1, 2, 3, 4)),
    CONSTRAINT innings_status_check CHECK (status IN ('not_started', 'in_progress', 'completed', 'forfeited'))
);

ALTER TABLE public.innings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "authenticated users can read innings"
    ON public.innings FOR SELECT TO authenticated
    USING (true);

CREATE POLICY "match owners can insert innings"
    ON public.innings FOR INSERT TO authenticated
    WITH CHECK (public.is_match_owner(match_id));

CREATE POLICY "match owners can update innings"
    ON public.innings FOR UPDATE TO authenticated
    USING (public.is_match_owner(match_id))
    WITH CHECK (public.is_match_owner(match_id));

CREATE POLICY "match owners can delete innings"
    ON public.innings FOR DELETE TO authenticated
    USING (public.is_match_owner(match_id));

GRANT SELECT ON public.innings TO authenticated;
GRANT INSERT, UPDATE, DELETE ON public.innings TO authenticated;

CREATE INDEX IF NOT EXISTS idx_innings_match_id
    ON public.innings(match_id);

CREATE TRIGGER innings_updated_at
    BEFORE UPDATE ON public.innings
    FOR EACH ROW EXECUTE FUNCTION system.update_updated_at();


-- ─── deliveries ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.deliveries (
    id                          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    innings_id                  UUID        NOT NULL REFERENCES public.innings(id) ON DELETE CASCADE,
    match_id                    UUID        NOT NULL REFERENCES public.matches(id) ON DELETE CASCADE,
    sequence_no                 INT         NOT NULL,
    over_no                     INT         NOT NULL, -- 0-indexed over (0 for 1st over, 1 for 2nd)
    ball_in_over                INT         NOT NULL, -- legal ball counter in over (1..6)
    display_over                TEXT        NOT NULL, -- e.g. "0.1", "14.3"
    striker_id                  UUID        NOT NULL REFERENCES public.players(id) ON DELETE RESTRICT,
    non_striker_id              UUID        NOT NULL REFERENCES public.players(id) ON DELETE RESTRICT,
    bowler_id                   UUID        NOT NULL REFERENCES public.players(id) ON DELETE RESTRICT,
    batter_runs                 INT         NOT NULL DEFAULT 0 CHECK (batter_runs >= 0),
    extra_type                  TEXT        CHECK (extra_type IN ('wide', 'no_ball', 'bye', 'leg_bye', 'penalty') OR extra_type IS NULL),
    extra_runs                  INT         NOT NULL DEFAULT 0 CHECK (extra_runs >= 0),
    total_runs                  INT         NOT NULL DEFAULT 0 CHECK (total_runs >= 0),
    is_legal                    BOOLEAN     NOT NULL DEFAULT true,
    is_boundary                 BOOLEAN     NOT NULL DEFAULT false,
    boundary_type               INT         CHECK (boundary_type IN (4, 6) OR boundary_type IS NULL),
    is_batter_boundary          BOOLEAN     NOT NULL DEFAULT false,
    is_wicket                   BOOLEAN     NOT NULL DEFAULT false,
    wicket_type                 TEXT        CHECK (wicket_type IN (
                                                'bowled', 'caught', 'lbw', 'run_out', 'stumped',
                                                'hit_wicket', 'handled_ball', 'obstructing_field',
                                                'timed_out', 'retired_hurt', 'retired_out'
                                            ) OR wicket_type IS NULL),
    dismissed_player_id         UUID        REFERENCES public.players(id) ON DELETE SET NULL,
    fielder_id                  UUID        REFERENCES public.players(id) ON DELETE SET NULL,
    fielder2_id                 UUID        REFERENCES public.players(id) ON DELETE SET NULL,
    dismissal_delivery_end      TEXT        CHECK (dismissal_delivery_end IN ('striker', 'non_striker') OR dismissal_delivery_end IS NULL),
    runs_completed_before_out   INT         NOT NULL DEFAULT 0 CHECK (runs_completed_before_out >= 0),
    next_striker_id             UUID        REFERENCES public.players(id) ON DELETE SET NULL,
    next_non_striker_id         UUID        REFERENCES public.players(id) ON DELETE SET NULL,
    revision_no                 INT         NOT NULL DEFAULT 1,
    is_voided                   BOOLEAN     NOT NULL DEFAULT false,
    voided_reason               TEXT,
    idempotency_key             TEXT,
    audit_metadata              JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT deliveries_innings_seq_unique UNIQUE (innings_id, sequence_no)
);

ALTER TABLE public.deliveries ENABLE ROW LEVEL SECURITY;

CREATE POLICY "authenticated users can read deliveries"
    ON public.deliveries FOR SELECT TO authenticated
    USING (true);

CREATE POLICY "match owners can insert deliveries"
    ON public.deliveries FOR INSERT TO authenticated
    WITH CHECK (public.is_match_owner(match_id));

CREATE POLICY "match owners can update deliveries"
    ON public.deliveries FOR UPDATE TO authenticated
    USING (public.is_match_owner(match_id))
    WITH CHECK (public.is_match_owner(match_id));

CREATE POLICY "match owners can delete deliveries"
    ON public.deliveries FOR DELETE TO authenticated
    USING (public.is_match_owner(match_id));

GRANT SELECT ON public.deliveries TO authenticated;
GRANT INSERT, UPDATE, DELETE ON public.deliveries TO authenticated;

CREATE INDEX IF NOT EXISTS idx_deliveries_innings_seq
    ON public.deliveries(innings_id, sequence_no);
CREATE INDEX IF NOT EXISTS idx_deliveries_match_id
    ON public.deliveries(match_id);
CREATE INDEX IF NOT EXISTS idx_deliveries_idempotency
    ON public.deliveries(innings_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE TRIGGER deliveries_updated_at
    BEFORE UPDATE ON public.deliveries
    FOR EACH ROW EXECUTE FUNCTION system.update_updated_at();
