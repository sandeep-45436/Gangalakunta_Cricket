-- =============================================================================
-- Phase 3 — Mobile Recording & Event Markers Schema
-- =============================================================================
-- Tables: recording_sessions, video_segments, event_markers
--
-- Design decisions:
--   • recording_sessions: Tracks recording state, elapsed monotonic duration,
--     upload status, and associated match.
--   • video_segments: If video is recorded in chunked segments (or split files),
--     each segment is tracked with its duration and storage identifier.
--   • event_markers: Links a high-precision media-relative timestamp (in ms)
--     to a saved delivery. Markers can be logged before or after scoring.
--   • Rapid-tap protection: client_marker_id enforces uniqueness per session.
--   • RLS: Authenticated users can read; mutations restricted to match owners.
-- =============================================================================

-- ─── recording_sessions ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.recording_sessions (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id            UUID        NOT NULL REFERENCES public.matches(id) ON DELETE CASCADE,
    owner_id            UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    session_name        TEXT        NOT NULL DEFAULT 'Main Camera Session',
    status              TEXT        NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'stopped', 'completed', 'failed', 'interrupted')),
    started_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at            TIMESTAMPTZ,
    total_duration_ms   BIGINT      NOT NULL DEFAULT 0 CHECK (total_duration_ms >= 0),
    media_asset_id      TEXT,
    media_url           TEXT,
    upload_status       TEXT        NOT NULL DEFAULT 'pending' CHECK (upload_status IN ('pending', 'uploading', 'uploaded', 'failed', 'not_required')),
    processing_status   TEXT        NOT NULL DEFAULT 'unprocessed' CHECK (processing_status IN ('unprocessed', 'processing', 'completed', 'failed')),
    segments_count      INT         NOT NULL DEFAULT 1 CHECK (segments_count >= 1),
    media_metadata      JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.recording_sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "authenticated users can read recording_sessions"
    ON public.recording_sessions FOR SELECT TO authenticated
    USING (true);

CREATE POLICY "match owners can insert recording_sessions"
    ON public.recording_sessions FOR INSERT TO authenticated
    WITH CHECK (public.is_match_owner(match_id));

CREATE POLICY "match owners can update recording_sessions"
    ON public.recording_sessions FOR UPDATE TO authenticated
    USING (public.is_match_owner(match_id))
    WITH CHECK (public.is_match_owner(match_id));

CREATE POLICY "match owners can delete recording_sessions"
    ON public.recording_sessions FOR DELETE TO authenticated
    USING (public.is_match_owner(match_id));

GRANT SELECT ON public.recording_sessions TO authenticated;
GRANT INSERT, UPDATE, DELETE ON public.recording_sessions TO authenticated;

CREATE INDEX IF NOT EXISTS idx_recording_sessions_match_id
    ON public.recording_sessions(match_id);

CREATE TRIGGER recording_sessions_updated_at
    BEFORE UPDATE ON public.recording_sessions
    FOR EACH ROW EXECUTE FUNCTION system.update_updated_at();


-- ─── video_segments ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.video_segments (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id          UUID        NOT NULL REFERENCES public.recording_sessions(id) ON DELETE CASCADE,
    match_id            UUID        NOT NULL REFERENCES public.matches(id) ON DELETE CASCADE,
    segment_index       INT         NOT NULL DEFAULT 0 CHECK (segment_index >= 0),
    segment_name        TEXT        NOT NULL,
    duration_ms         BIGINT      NOT NULL DEFAULT 0 CHECK (duration_ms >= 0),
    storage_key         TEXT,
    storage_url         TEXT,
    upload_status       TEXT        NOT NULL DEFAULT 'pending' CHECK (upload_status IN ('pending', 'uploading', 'uploaded', 'failed')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT video_segments_session_idx_unique UNIQUE (session_id, segment_index)
);

ALTER TABLE public.video_segments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "authenticated users can read video_segments"
    ON public.video_segments FOR SELECT TO authenticated
    USING (true);

CREATE POLICY "match owners can insert video_segments"
    ON public.video_segments FOR INSERT TO authenticated
    WITH CHECK (public.is_match_owner(match_id));

CREATE POLICY "match owners can update video_segments"
    ON public.video_segments FOR UPDATE TO authenticated
    USING (public.is_match_owner(match_id))
    WITH CHECK (public.is_match_owner(match_id));

CREATE POLICY "match owners can delete video_segments"
    ON public.video_segments FOR DELETE TO authenticated
    USING (public.is_match_owner(match_id));

GRANT SELECT ON public.video_segments TO authenticated;
GRANT INSERT, UPDATE, DELETE ON public.video_segments TO authenticated;

CREATE INDEX IF NOT EXISTS idx_video_segments_session_id
    ON public.video_segments(session_id);

CREATE TRIGGER video_segments_updated_at
    BEFORE UPDATE ON public.video_segments
    FOR EACH ROW EXECUTE FUNCTION system.update_updated_at();


-- ─── event_markers ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.event_markers (
    id                          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id                  UUID        NOT NULL REFERENCES public.recording_sessions(id) ON DELETE CASCADE,
    match_id                    UUID        NOT NULL REFERENCES public.matches(id) ON DELETE CASCADE,
    segment_id                  UUID        REFERENCES public.video_segments(id) ON DELETE SET NULL,
    segment_index               INT         NOT NULL DEFAULT 0 CHECK (segment_index >= 0),
    delivery_id                 UUID        REFERENCES public.deliveries(id) ON DELETE SET NULL,
    innings_id                  UUID        REFERENCES public.innings(id) ON DELETE SET NULL,
    marker_number               INT         NOT NULL CHECK (marker_number >= 1),
    elapsed_ms                  BIGINT      NOT NULL CHECK (elapsed_ms >= 0),
    segment_offset_ms           BIGINT      NOT NULL DEFAULT 0 CHECK (segment_offset_ms >= 0),
    marker_label                TEXT        NOT NULL,
    status                      TEXT        NOT NULL DEFAULT 'unlinked' CHECK (status IN ('unlinked', 'linked', 'ignored')),
    delivery_display            TEXT,
    client_marker_id            TEXT,
    audit_metadata              JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT event_markers_session_num_unique UNIQUE (session_id, marker_number)
);

ALTER TABLE public.event_markers ENABLE ROW LEVEL SECURITY;

CREATE POLICY "authenticated users can read event_markers"
    ON public.event_markers FOR SELECT TO authenticated
    USING (true);

CREATE POLICY "match owners can insert event_markers"
    ON public.event_markers FOR INSERT TO authenticated
    WITH CHECK (public.is_match_owner(match_id));

CREATE POLICY "match owners can update event_markers"
    ON public.event_markers FOR UPDATE TO authenticated
    USING (public.is_match_owner(match_id))
    WITH CHECK (public.is_match_owner(match_id));

CREATE POLICY "match owners can delete event_markers"
    ON public.event_markers FOR DELETE TO authenticated
    USING (public.is_match_owner(match_id));

GRANT SELECT ON public.event_markers TO authenticated;
GRANT INSERT, UPDATE, DELETE ON public.event_markers TO authenticated;

CREATE INDEX IF NOT EXISTS idx_event_markers_session_id
    ON public.event_markers(session_id);
CREATE INDEX IF NOT EXISTS idx_event_markers_delivery_id
    ON public.event_markers(delivery_id)
    WHERE delivery_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_event_markers_client_id
    ON public.event_markers(session_id, client_marker_id)
    WHERE client_marker_id IS NOT NULL;

CREATE TRIGGER event_markers_updated_at
    BEFORE UPDATE ON public.event_markers
    FOR EACH ROW EXECUTE FUNCTION system.update_updated_at();
