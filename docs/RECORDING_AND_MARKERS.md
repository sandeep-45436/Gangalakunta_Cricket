# Mobile Recording and Event Markers — Architecture & Guide (Phase 3)

## 1. Overview

Phase 3 implements reliable real-world video recording and delivery-to-video synchronization. The user records the match in the app and taps **Mark Moment** when a delivery is bowled. The resulting timestamp marker can be linked to a delivery immediately or retrospectively.

---

## 2. Recording Architecture & Data Model

### 2.1 Recording Sessions (`recording_sessions`)
- **Session Lifecycle**: `active` ➔ `paused` ➔ `completed` (or `interrupted`/`failed`).
- **Monotonic Duration**: Uses `performance.now()` monotonic timing to track elapsed milliseconds (`total_duration_ms`), avoiding wall-clock drift or timezone adjustments.
- **Media Segments**: When split recording or chunked streams are utilized, `video_segments` stores individual segment identifiers, segment indices, durations, and storage keys.

### 2.2 Event Markers (`event_markers`)
- **Monotonic Timestamps**: Stored in `elapsed_ms` (relative to session start) and `segment_offset_ms` (relative to the specific segment).
- **Delivery Linking**:
  - `status`: `'unlinked'` | `'linked'` | `'ignored'`.
  - Links to `deliveries.id` with `delivery_display` formatted e.g. `"14.2 · Player A"`.
- **Rapid-Tap Deduplication**:
  - Taps occurring within 250ms are automatically coalesced to prevent bounce errors.
  - Client-side unique `client_marker_id` ensures idempotency on retries.

---

## 3. User Experience & Mobile Workflows

1. **Starting Recording**:
   - The user opens `/matches/:id/record`.
   - The camera viewfinder requests video (`facingMode: 'environment'`) and audio permissions.
   - Tapping **Start Recording Session** initializes the monotonic timer and creates a persistent session record.
2. **Marking a Moment**:
   - The user taps the high-contrast **MARK MOMENT** button.
   - Haptic feedback (`navigator.vibrate([40, 30, 40])`) triggers on physical devices.
   - A visual toast displays the captured timestamp (e.g. `Captured at 00:14:22`).
   - The marker is written to local storage before network synchronization.
3. **Delivery Scoring & Linking**:
   - **Order A (Mark first, score second)**: The user taps Mark Moment when the bowler bowls, then enters the score in Quick Scorer. The app automatically links the pending marker to the newly created delivery.
   - **Order B (Score first, mark second)**: If score is entered first, the user selects "Link Ball" on any unlinked marker to connect it to the corresponding ball.
4. **Session Recovery**:
   - If the browser tab is accidentally reloaded or closed, session data and markers persisted in `localStorage` are restored immediately on reopening the match recording screen.

---

## 4. Hardware & Operating System Considerations

1. **Foreground Operation**:
   - Web and mobile browsers suspend active camera and media hardware when the phone is locked or another application takes foreground. Users must keep the screen unlocked and the app active during match recording.
2. **Camera Permissions**:
   - If camera or microphone access is denied, a clear notification banner guides the user to grant permissions in device settings.
3. **Storage & Upload State**:
   - The UI clearly differentiates between local capture (`upload_status: 'pending'`) and completed remote storage (`upload_status: 'uploaded'`).
