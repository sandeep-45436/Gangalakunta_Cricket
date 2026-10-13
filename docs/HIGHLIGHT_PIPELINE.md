# Phase 4 — Automatic Clip Extraction & Player-Wise Assignment

This document details the video processing architecture, event qualification rules, worker lifecycle, and storage model for the Cricket Highlights platform.

---

## 1. Pipeline Overview

When a ball is recorded and scored, the highlight pipeline connects the real-world video recording to canonical delivery events without blocking the live scoring HTTP requests.

```
       Delivery Saved / Marker Linked
                     │
                     ▼
       ┌───────────────────────────┐
       │ Qualification Check       │
       │ • Batter-credited 4 or 6? │
       │ • Valid same-match marker?│
       └─────────────┬─────────────┘
                     │ Yes
                     ▼
       ┌───────────────────────────┐
       │ Player Assignment         │
       │ player_id = striker_id    │
       │ (Canonical event identity)│
       └─────────────┬─────────────┘
                     │
                     ▼
       ┌───────────────────────────┐
       │ Idempotent Job Queue      │
       │ Status: pending           │
       └─────────────┬─────────────┘
                     │ Background Worker
                     ▼
       ┌───────────────────────────┐
       │ FFmpeg Trimming           │
       │ • Clamped window bounds   │
       │ • H.264 MP4 extract       │
       │ • JPEG Thumbnail preview  │
       └─────────────┬─────────────┘
                     │
                     ▼
       ┌───────────────────────────┐
       │ InsForge Storage Upload   │
       │ Bucket: cricket-videos    │
       │ URLs & keys verified      │
       └─────────────┬─────────────┘
                     │
                     ▼
       ┌───────────────────────────┐
       │ Publish Highlight (ready) │
       │ Player Reel & Match Reel  │
       └───────────────────────────┘
```

---

## 2. Event Qualification Rules

Highlight extraction is strictly gated to verified batter achievements:

| Event Type | `is_batter_boundary` | `boundary_type` | Qualifies? | Notes |
| :--- | :---: | :---: | :---: | :--- |
| **Batter Four** | `true` | `4` | ✅ **Yes** | 4 runs credited to striker's scorecard figure |
| **Batter Six** | `true` | `6` | ✅ **Yes** | 6 runs credited to striker's scorecard figure |
| **Byes Four** | `false` | `4` | ❌ **No** | Contributes to team extras, not to striker |
| **Leg-byes Four**| `false` | `4` | ❌ **No** | Contributes to team extras, not to striker |
| **Wide + Four** | `false` | `None` | ❌ **No** | Illegal delivery; contributes to bowler runs conceded & team extras |
| **Overthrow (not batter)** | `false` | `4` | ❌ **No** | Batter runs credited only for completed physical runs |
| **Voided Ball** | `true` | `4` or `6` | ❌ **No** | Delivery was voided/canceled during scorecard correction |

---

## 3. Strict Player Identity Derivation

Highlights are assigned to players using the **canonical delivery record**:
- `player_id` is assigned directly from `delivery.striker_id`.
- The system never relies on typed player names or client-side form text.
- Even if a player changes display names or leaves a squad, all historical highlights retain referential integrity linked to the player UUID.

---

## 4. Processing Lifecycle & States

Every highlight job transitions through explicit lifecycle states:

```
[ pending ] ──► [ processing ] ──► [ ready ] (Output verified & URLs saved)
                       │
                       ▼ (failure)
                [ retrying ] ──(retries >= 3)──► [ failed ]
```

- **pending**: Job created with unique constraint on `(delivery_id, version)`.
- **processing**: Worker acquires media and invokes FFmpeg.
- **ready**: MP4 video clip and JPEG preview thumbnail uploaded and verified in InsForge Storage (`cricket-videos`).
- **retrying / failed**: If media download, trim, or upload fails, error diagnostic messages are logged. Retries are attempted up to `max_retries` (default: 3).

---

## 5. Time Window Clamping & Trim Defaults

Default trim window:
- **Before Marker**: `4.0` seconds
- **After Marker**: `5.0` seconds

### Clamping Logic
- Window start is clamped to `max(0.0, marker_timestamp - config_before_sec)`.
- Window end is clamped to `min(media_duration, marker_timestamp + config_after_sec)` when media duration is known.
- Clip duration is guaranteed to be $\ge 0.5$ seconds.

### Reprocessing Support
Authorized users and operators can fine-tune the trim window using the reprocessing API or UI:
```http
POST /api/highlights/{highlight_id}/reprocess
Content-Type: application/json

{
  "config_before_sec": 5.5,
  "config_after_sec": 6.0
}
```
Reprocessing increments `version` (e.g. `v1` $\to$ `v2`), resets status to `pending`, and replaces the clip without creating duplicate scorecard entries.

---

## 6. API Endpoints

### 1. Trigger Highlight Extraction
`POST /api/highlights/trigger`
- Headers: `Authorization: Bearer <user_token>`
- Body:
```json
{
  "delivery_id": "848bb250-93cb-4f99-a3c3-6b744d010c28",
  "marker_id": "c13876ab-84a1-432d-8e65-3511eb44d930",
  "config_before_sec": 4.0,
  "config_after_sec": 5.0
}
```

### 2. Reprocess Highlight
`POST /api/highlights/{highlight_id}/reprocess`
- Headers: `Authorization: Bearer <user_token>`
- Body:
```json
{
  "config_before_sec": 4.5,
  "config_after_sec": 6.5
}
```

### 3. Get Player Highlight Reel
`GET /api/players/{player_id}/highlights`
- Response:
```json
{
  "player_id": "848bb250-93cb-4f99-a3c3-6b744d010c28",
  "player_name": "V. Kohli",
  "total_highlights": 12,
  "fours_count": 8,
  "sixes_count": 4,
  "highlights": [
    {
      "id": "e43b1778-95ef-4cb3-bc59-7bf1c37b2d56",
      "match_id": "...",
      "event_type": "six",
      "status": "ready",
      "video_url": "https://asp6i95i.ap-southeast.insforge.app/api/storage/buckets/cricket-videos/objects/highlights/...",
      "thumbnail_url": "https://asp6i95i.ap-southeast.insforge.app/api/storage/buckets/cricket-videos/objects/highlights/...",
      "duration_sec": 9.0,
      "delivery_metadata": {
        "over_display": "14.3",
        "batter_runs": 6,
        "bowler_name": "P. Cummins"
      }
    }
  ]
}
```

### 4. Get Match Highlights
`GET /api/matches/{match_id}/highlights`
- Returns all published highlights for the match.

### 5. Check Job Status
`GET /api/highlights/jobs/{job_id}`
- Operator-visible status, retry counts, configuration, and error diagnostics.

---

## 7. Verification

All tests run cleanly with zero regressions:
```bash
# Backend pytest suite (130 passing tests)
cd services/api
.\.venv\Scripts\pytest.exe -v

# Frontend test & build
cd apps/web
npm run test
npm run build
```
