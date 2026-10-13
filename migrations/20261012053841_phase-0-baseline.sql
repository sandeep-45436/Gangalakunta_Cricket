-- Phase 0 baseline migration
-- Marks the starting point of the Cricket Highlights schema.
-- No domain tables yet — those are added in Phases 1 and 2.
--
-- This migration confirms:
--   1. The migration workflow is connected and working.
--   2. The system.update_updated_at() trigger function is available (built-in).
--
-- Phase 1 will add: teams, players, matches, playing_xi
-- Phase 2 will add: innings, deliveries, batting_stats, bowling_stats
-- Phase 4 will add: recordings, clips, player_highlights

-- Verify the built-in trigger function exists (read-only check)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'system' AND p.proname = 'update_updated_at'
  ) THEN
    RAISE NOTICE 'system.update_updated_at not found — will use manual updated_at in triggers';
  ELSE
    RAISE NOTICE 'Phase 0 baseline migration complete — system.update_updated_at is available';
  END IF;
END
$$;
