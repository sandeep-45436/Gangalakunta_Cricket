-- =============================================================================
-- Phase 4 — Video Processing, Automatic Highlights & Player Assignment Schema
-- =============================================================================
-- Tables: highlight_jobs, player_highlights
--
-- Design decisions:
--   • highlight_jobs: Durable queue/tracking for asynchronous clip extraction.
--     Maintains retry count, error diagnostics, configurable trim bounds,
--     and explicit state machine: pending -> processing -> ready (or retrying / failed).
--   • player_highlights: Published highlight reel entries.
--     Player identity strictly inherited from delivery.striker_id (not typed name).
--     Stores verified video_url, video_key, thumbnail_url, thumbnail_key,
--     duration, offset window, and delivery metadata (over, ball, score, bowler).
--   • Idempotency: highlight_jobs enforces unique (delivery_id, version).
--     player_highlights enforces unique (delivery_id) for the canonical highlight.
--   • Reprocessing: Bumps the version number and re-executes with updated trim.
-- =============================================================================

-- ─── highlight_jobs ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.highlight_jobs (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id            UUID        NOT NULL REFERENCES public.matches(id) ON DELETE CASCADE,
    delivery_id         UUID        NOT NULL REFERENCES public.deliveries(id) ON DELETE CASCADE,
    marker_id           UUID        REFERENCES public.event_markers(id) ON DELETE SET NULL,
    player_id           UUID        NOT NULL REFERENCES public.players(id) ON DELETE CASCADE,
    status              TEXT        NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'ready', 'retrying', 'failed')),
    event_type          TEXT        NOT NULL CHECK (event_type IN ('four', 'six')),
    retry_count         INT         NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
    max_retries         INT         NOT NULL DEFAULT 3 CHECK (max_retries >= 0),
    error_message       TEXT,
    config_before_sec   NUMERIC(6, 2) NOT NULL DEFAULT 4.00 CHECK (config_before_sec >= 0),
    config_after_sec    NUMERIC(6, 2) NOT NULL DEFAULT 5.00 CHECK (config_after_sec >= 0),
    version             INT         NOT NULL DEFAULT 1 CHECK (version >= 1),
    audit_metadata      JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT highlight_jobs_delivery_version_unique UNIQUE (delivery_id, version)
);

ALTER TABLE public.highlight_jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "authenticated users can read highlight_jobs"
    ON public.highlight_jobs FOR SELECT TO authenticated
    USING (true);

CREATE POLICY "match owners can insert highlight_jobs"
    ON public.highlight_jobs FOR INSERT TO authenticated
    WITH CHECK (public.is_match_owner(match_id));

CREATE POLICY "match owners can update highlight_jobs"
    ON public.highlight_jobs FOR UPDATE TO authenticated
    USING (public.is_match_owner(match_id))
    WITH CHECK (public.is_match_owner(match_id));

CREATE POLICY "match owners can delete highlight_jobs"
    ON public.highlight_jobs FOR DELETE TO authenticated
    USING (public.is_match_owner(match_id));

GRANT SELECT ON public.highlight_jobs TO authenticated;
GRANT INSERT, UPDATE, DELETE ON public.highlight_jobs TO authenticated;

CREATE INDEX IF NOT EXISTS idx_highlight_jobs_match_id
    ON public.highlight_jobs(match_id);
CREATE INDEX IF NOT EXISTS idx_highlight_jobs_delivery_id
    ON public.highlight_jobs(delivery_id);
CREATE INDEX IF NOT EXISTS idx_highlight_jobs_player_id
    ON public.highlight_jobs(player_id);
CREATE INDEX IF NOT EXISTS idx_highlight_jobs_status
    ON public.highlight_jobs(status);

CREATE TRIGGER highlight_jobs_updated_at
    BEFORE UPDATE ON public.highlight_jobs
    FOR EACH ROW EXECUTE FUNCTION system.update_updated_at();


-- ─── player_highlights ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.player_highlights (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id              UUID        REFERENCES public.highlight_jobs(id) ON DELETE SET NULL,
    match_id            UUID        NOT NULL REFERENCES public.matches(id) ON DELETE CASCADE,
    innings_id          UUID        NOT NULL REFERENCES public.innings(id) ON DELETE CASCADE,
    delivery_id         UUID        NOT NULL REFERENCES public.deliveries(id) ON DELETE CASCADE,
    marker_id           UUID        REFERENCES public.event_markers(id) ON DELETE SET NULL,
    player_id           UUID        NOT NULL REFERENCES public.players(id) ON DELETE CASCADE,
    event_type          TEXT        NOT NULL CHECK (event_type IN ('four', 'six')),
    status              TEXT        NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'ready', 'failed')),
    video_url           TEXT,
    video_key           TEXT,
    thumbnail_url       TEXT,
    thumbnail_key       TEXT,
    duration_sec        NUMERIC(6, 2) CHECK (duration_sec IS NULL OR duration_sec >= 0),
    start_offset_sec    NUMERIC(8, 2) CHECK (start_offset_sec IS NULL OR start_offset_sec >= 0),
    end_offset_sec      NUMERIC(8, 2) CHECK (end_offset_sec IS NULL OR end_offset_sec >= 0),
    delivery_metadata   JSONB       NOT NULL DEFAULT '{}'::jsonb,
    version             INT         NOT NULL DEFAULT 1 CHECK (version >= 1),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT player_highlights_delivery_unique UNIQUE (delivery_id)
);

ALTER TABLE public.player_highlights ENABLE ROW LEVEL SECURITY;

CREATE POLICY "authenticated users can read player_highlights"
    ON public.player_highlights FOR SELECT TO authenticated
    USING (true);

CREATE POLICY "match owners can insert player_highlights"
    ON public.player_highlights FOR INSERT TO authenticated
    WITH CHECK (public.is_match_owner(match_id));

CREATE POLICY "match owners can update player_highlights"
    ON public.player_highlights FOR UPDATE TO authenticated
    USING (public.is_match_owner(match_id))
    WITH CHECK (public.is_match_owner(match_id));

CREATE POLICY "match owners can delete player_highlights"
    ON public.player_highlights FOR DELETE TO authenticated
    USING (public.is_match_owner(match_id));

GRANT SELECT ON public.player_highlights TO authenticated;
GRANT INSERT, UPDATE, DELETE ON public.player_highlights TO authenticated;

CREATE INDEX IF NOT EXISTS idx_player_highlights_match_id
    ON public.player_highlights(match_id);
CREATE INDEX IF NOT EXISTS idx_player_highlights_player_id
    ON public.player_highlights(player_id);
CREATE INDEX IF NOT EXISTS idx_player_highlights_delivery_id
    ON public.player_highlights(delivery_id);
CREATE INDEX IF NOT EXISTS idx_player_highlights_status
    ON public.player_highlights(status);

CREATE TRIGGER player_highlights_updated_at
    BEFORE UPDATE ON public.player_highlights
    FOR EACH ROW EXECUTE FUNCTION system.update_updated_at();
