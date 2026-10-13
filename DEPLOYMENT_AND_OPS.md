# Cricket Highlights & Archive Platform — Production Deployment & Operations Guide

## 1. Architecture & Components
- **Backend API (`services/api`)**: FastAPI service providing authenticated REST endpoints, ICC cricket scoring engine, asynchronous FFmpeg clip extraction worker, milestone event tracking, archive search, media signing, retention cleanup, and cryptographic backup export/verification.
- **Database & Storage (InsForge BaaS)**:
  - **PostgreSQL**: Stores `teams`, `players`, `team_players`, `matches`, `match_teams`, `playing_xi`, `match_substitutes`, `innings`, `deliveries`, `recording_sessions`, `recording_segments`, `video_markers`, `player_highlights`, `highlight_jobs`, `player_milestones`, and `audit_logs`.
  - **Row-Level Security (RLS)**: Enforced on every table using `owner_id = auth.uid()` (or parent match ownership).
  - **Storage Bucket (`match-media`)**: Stores raw match recording segments and extracted boundary highlight clips + thumbnails.
- **Web Application (`apps/web`)**: React + TypeScript + Vite SPA with player profiles, searchable match archive, live scoring console, video marker studio, and replayable broadcast animations.
- **Mobile Application (`apps/mobile`)**: React Native + Expo application with camera recording, live marker tagging, and Reanimated 60fps broadcast animations.

---

## 2. Production Release Checklist

### 2.1 Environment Variables
Ensure the following environment variables are configured in production (never commit secrets):

#### Backend (`services/api/.env`)
| Variable | Description | Required |
|---|---|---|
| `INSFORGE_URL` | InsForge project base URL (`https://asp6i95i.ap-southeast.insforge.app`) | Yes |
| `INSFORGE_ANON_KEY` | InsForge anonymous/public API key | Yes |
| `INSFORGE_SERVICE_KEY` | Service role key or secret used for HMAC media signing | Recommended |
| `ALLOWED_ORIGINS` | Comma-separated list of allowed frontend origins | Yes |
| `FFMPEG_PATH` | Path to `ffmpeg` binary (defaults to system `ffmpeg` or `imageio-ffmpeg`) | Optional |

#### Web Frontend (`apps/web/.env.local`)
| Variable | Description | Required |
|---|---|---|
| `VITE_API_URL` | Backend API base URL (e.g., `http://localhost:8000`) | Yes |
| `VITE_INSFORGE_URL` | InsForge base URL | Yes |
| `VITE_INSFORGE_ANON_KEY` | InsForge anonymous key | Yes |

---

### 2.2 Database Migrations & Indexes
All schema migrations are tracked in `services/api/migrations/versions/`:
1. `20260411_0001_phase1_foundation.py` — Core teams, players, matches, playing XI, innings, deliveries, and RLS policies.
2. `20261013_0002_phase5_player_milestones.py` — `player_milestones` table and unique index `idx_player_milestones_unique_valid`.
3. `20261013_0003_phase6_archive_and_ops.py` — `matches.tournament`, `matches.retention_days`, historical snapshots on `match_teams`/`playing_xi`, `audit_logs` table, and composite archive search indexes:
   - `idx_matches_owner_status_date`
   - `idx_matches_owner_format`
   - `idx_matches_owner_tournament`
   - `idx_deliveries_match_innings_seq`
   - `idx_deliveries_striker_match`
   - `idx_deliveries_bowler_match`
   - `idx_player_highlights_archive`
   - `idx_recording_sessions_owner_match`

---

## 3. Security, Authorization & Expiring Signed Media URLs

### 3.1 Server-Side Ownership Checks (IDOR Protection)
Every protected endpoint verifies `current_user.user_id` against the resource's `owner_id` on the server in addition to PostgreSQL RLS:
- Attempting to access, modify, or delete another user's `recording_sessions`, `matches`, `teams`, `players`, or media keys returns `403 Forbidden`.

### 3.2 Expiring HMAC Signed Media URLs
- **Endpoint**: `GET /api/media/sign?media_key=<key>&ttl_seconds=3600`
- Verifies that the authenticated user owns the recording segment or highlight clip associated with `media_key`.
- Issues an expiring HMAC-SHA256 signed URL (`?token=<payload>.<signature>&exp=<unix_ts>`).
- **Stream Verification Endpoint**: `GET /api/media/stream?token=<signed_token>` validates signature integrity and expiration timestamp before redirecting (`307 Temporary Redirect`) to the underlying storage object.

---

## 4. Media Retention & User-Authorized Deletion Rules

1. **User-Authorized Deletion**:
   - `DELETE /api/matches/{match_id}`: Deletes a match, its innings, deliveries, recording sessions, and cascades to dependent records.
   - `DELETE /api/recordings/{session_id}`: Deletes a specific recording session and purges its raw video segments from storage (`match-media` bucket) while recording an entry in `audit_logs`.
2. **Automated Retention Policy**:
   - `POST /api/ops/retention/apply` (`{"retention_days": 90, "dry_run": true|false}`)
   - Identifies completed recording sessions older than `retention_days` (default 90 days) and purges raw full-match source video segments to reclaim storage **while preserving extracted player boundary highlight clips (`player_highlights`) and scorecards permanently**.

---

## 5. Retry & Recovery Workflows for Missing Media or Failed Processing

- **Endpoint**: `POST /api/ops/jobs/retry?match_id=<optional_uuid>`
- Resets any `highlight_jobs` in `failed` or `retrying` state back to `pending` (`attempt_count = 0`), resets corresponding `player_highlights` records, and triggers the background FFmpeg extraction worker.
- Also recovers `recording_sessions` stuck in `failed` processing state when uploaded segments are present.

---

## 6. Monitoring, Structured Audit Logging & Health Checks

1. **Liveness Health Check**: `GET /health` returns `{"status": "ok"}`.
2. **Request Latency Header**: Every HTTP response includes `X-Process-Time-Ms` measuring server execution latency.
3. **Production Operations Diagnostics**: `GET /api/ops/diagnostics` returns database connectivity, storage connectivity, pending/processing/failed highlight job counts, ready highlight count, and audit log volume.
4. **Structured Audit Logs**: Destructive and operational actions (`match.delete`, `recording_session.delete`, `ops.retry_failed_jobs`, `ops.retention_cleanup`, `ops.backup_export`) are persisted to `public.audit_logs`.

---

## 7. Database Backup Export & Restoration Verification Procedure

1. **Export Snapshot**:
   - Call `GET /api/ops/backup/export` (or click **💾 Export & Verify DB Backup** on the Dashboard).
   - Exports all tenant records across `teams`, `players`, `team_players`, `matches`, `match_teams`, `playing_xi`, `innings`, `deliveries`, `player_highlights`, `player_milestones`, and `recording_sessions` with a canonical SHA-256 integrity digest (`checksum_sha256`).
2. **Verify Snapshot Integrity Before Restore**:
   - Call `POST /api/ops/backup/verify` with `{"checksum_sha256": "<digest>", "data": { ... }}`.
   - Recomputes the canonical SHA-256 hash and verifies row counts per table before any restoration is applied.
