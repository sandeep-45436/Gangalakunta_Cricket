# Cricket Scoring Engine — Rules, Specifications & Limitations (Phase 2)

## 1. Overview

The Cricket Scoring Engine is a deterministic domain engine designed to produce trustworthy, immutable delivery logs and reproducible scorecards. It models ball-by-ball deliveries as persisted domain events, maintains live state (current striker, non-striker, bowler, runs, wickets, overs), and guarantees that every individual player and team statistic can be mathematically reconstructed from canonical records.

---

## 2. Canonical Delivery Record Architecture

Every delivery is stored in the `deliveries` table as an immutable domain event with audit capabilities:

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Unique delivery primary key. |
| `innings_id` | UUID | Reference to active innings. |
| `match_id` | UUID | Reference to parent match. |
| `sequence_no` | INT | Sequential ordering within the innings (1, 2, 3, ...). |
| `over_no` | INT | 0-indexed over number (e.g. 0 for 1st over, 14 for 15th over). |
| `ball_in_over` | INT | Legal ball count in current over (1 to 6). |
| `display_over` | TEXT | Human-readable over/ball string (e.g. `"14.3"` or `"0.2 (wd)"`). |
| `striker_id` | UUID | Batter facing the delivery (snapshotted at delivery time). |
| `non_striker_id` | UUID | Batter at the non-striker's end (snapshotted at delivery time). |
| `bowler_id` | UUID | Bowler bowling the delivery (snapshotted at delivery time). |
| `batter_runs` | INT | Runs scored off the bat credited to the batter. |
| `extra_type` | TEXT | `wide`, `no_ball`, `bye`, `leg_bye`, `penalty`, or `NULL`. |
| `extra_runs` | INT | Extra runs credited to team / charged under relevant rules. |
| `total_runs` | INT | `batter_runs + extra_runs`. |
| `is_legal` | BOOLEAN | `True` for legal balls; `False` for wides and no-balls. |
| `is_boundary` | BOOLEAN | Whether delivery resulted in a boundary. |
| `boundary_type` | INT | `4` or `6`. |
| `is_batter_boundary` | BOOLEAN | `True` if boundary is credited to batter; `False` for overthrows / extras boundaries. |
| `is_wicket` | BOOLEAN | Whether a dismissal occurred on this delivery. |
| `wicket_type` | TEXT | Dismissal category (see Section 4). |
| `dismissed_player_id` | UUID | Player dismissed (striker or non-striker). |
| `fielder_id` | UUID | Fielder credited with catch / stumping / run-out. |
| `fielder2_id` | UUID | Second fielder involved in combo run-out. |
| `dismissal_delivery_end`| TEXT | `striker` or `non_striker` (end of run-out). |
| `runs_completed_before_out`| INT | Runs completed before run-out occurred. |
| `next_striker_id` | UUID | Batter taking strike on the next delivery. |
| `next_non_striker_id` | UUID | Batter taking non-striker end on the next delivery. |
| `revision_no` | INT | Incremented upon audited correction. |
| `is_voided` | BOOLEAN | Reversal flag (`True` excludes ball from scorecard). |
| `voided_reason` | TEXT | Reason for voiding delivery. |
| `idempotency_key` | TEXT | Client key preventing duplicate submission on retries. |
| `audit_metadata` | JSONB | Audit trail (timestamp, device, operator). |

---

## 3. Supported Cricket Rules & Logic

### 3.1 Legality, Extras, and Stat Attribution

1. **Dots & Normal Runs off the Bat**:
   - `is_legal = True`
   - Legal ball counter increments (`+1`).
   - Runs off bat credited to batter (`batter_runs`).
   - Bowler charged with `batter_runs`.
   - Striker balls faced increments (`+1`).
   - Strike rotates if `batter_runs` is odd (1, 3, 5).

2. **Wides**:
   - `is_legal = False` (does not increment legal over ball counter).
   - `batter_runs = 0` (a wide cannot yield runs off the bat).
   - `extra_runs >= 1` (1 penalty + any running/boundary extras).
   - Bowler charged with all wide runs.
   - Striker balls faced does **not** increment.
   - Strike rotates only if physical running runs (`extra_runs - 1`) is odd.

3. **No-Balls**:
   - `is_legal = False` (does not increment legal over ball counter).
   - `extra_runs >= 1` (penalty 1 + any extra runs).
   - Batter may score runs off the bat (`batter_runs > 0`).
   - Striker balls faced increments (`+1`).
   - Bowler charged with `extra_runs + batter_runs`.
   - Strike rotates if `batter_runs` + running extras is odd.

4. **Byes & Leg-Byes**:
   - `is_legal = True` (legal delivery).
   - `batter_runs = 0`.
   - `extra_runs` added to team extras.
   - Bowler charged runs = **0** (neither byes nor leg-byes count against bowler).
   - Striker balls faced increments (`+1`).
   - Strike rotates if `extra_runs` is odd.
   - If boundary (4 byes / 4 leg byes): `is_boundary = True`, but `is_batter_boundary = False`.

5. **Penalties**:
   - Awarded to team total (`total_penalty_runs`). Not charged to bowler.

---

## 4. Wickets & Dismissal Handling

### 4.1 Bowler-Credited Wickets
- `bowled`, `caught`, `lbw`, `stumped`, `hit_wicket`.
- Dismissed player is always the `striker_id`.
- Bowler is credited with `+1` wicket.

### 4.2 Non-Bowler-Credited Wickets
- `run_out`: Can dismiss either the **striker** or the **non-striker**.
  - Bowler is **not** credited with the wicket.
  - Completed runs prior to run-out (`runs_completed_before_out`) are credited to team and batter/extras.
- `retired_hurt`, `retired_out`: Batter leaves; bowler not credited.
- `handled_ball`, `obstructing_field`, `timed_out`: Law infractions; bowler not credited.

### 4.3 Strike on Wickets
- Under MCC Law 18.11 / ICC Standard Playing Conditions (from October 2022), the incoming batter takes strike, unless dismissal was a run-out where the non-striker was out and batters had crossed.
- Delivery input permits specifying `next_striker_id` and `next_non_striker_id`. If omitted, the engine assigns the incoming batter to replace the dismissed batter.

---

## 5. Over Completion & Strike Rotation

1. An over consists of **6 legal deliveries** (`is_legal = True`).
2. When the 6th legal delivery is completed:
   - Batters swap physical ends for the new over.
   - Bowler must change (bowler cannot bowl consecutive overs).
3. Compound rotation on ball 6:
   - If 1 run is scored on the 6th ball: runners swap ends during the run, and then swap ends again at over completion. The net effect is that the striker who scored the single remains on strike for the next over.
   - If 0 runs (dot) or 2 runs are scored on the 6th ball: runners swap ends at over completion, placing the non-striker on strike.

---

## 6. Innings & Match Termination

1. **Innings 1 Termination**:
   - All Out: 10 wickets fall in an 11-player squad (`completed_reason = 'all_out'`).
   - Overs limit reached: `total_legal_balls == overs_per_innings * 6` (`completed_reason = 'overs_completed'`).
   - Declaration / forfeit.
2. **Target Calculation**:
   - Innings 2 target = `Innings 1 total_runs + 1`.
3. **Innings 2 & Match Termination**:
   - If Innings 2 `total_runs >= target`: Innings terminates immediately (`completed_reason = 'target_reached'`), Match marked `completed`, batting team wins by `(10 - wickets)` wickets.
   - If Innings 2 completes (all out or overs limit):
     - If `total_runs == target - 1`: Match Tied.
     - If `total_runs < target - 1`: Bowling team wins by `(target - 1 - total_runs)` runs.

---

## 7. Reversals, Voiding, and Idempotency

1. **Idempotency**:
   - Network retries from mobile scoring devices supply an `idempotency_key`.
   - If a delivery with the same `(innings_id, idempotency_key)` is already logged, the server returns the existing delivery without double-counting.
2. **Delivery Voiding (Undo)**:
   - When a delivery is voided, `is_voided` is set to `True` with a recorded `voided_reason`.
   - The engine deterministically recalculates all innings totals and dependent player figures using the remaining valid deliveries in sequence order.
3. **Delivery Correction (Edit)**:
   - Edits increment `revision_no`, update audit metadata, and trigger deterministic recalculation of innings state.

---

## 8. Explicit Limitations & Out-of-Scope Playing Conditions

1. **Free Hit State**:
   - Tracking foot-fault no-balls triggering a free hit on the immediate subsequent delivery is currently managed as a field annotation rather than strict validation preventing bowled dismissals on free hits.
2. **Duckworth-Lewis-Stern (DLS) Calculations**:
   - Rain interruptions or adjusted targets in curtailed matches require manual target updates via `PATCH /api/innings/{id}`.
3. **Timed-Out Timer**:
   - Auto-expiring countdown timers for incoming batters (2 minutes / 3 minutes) are not enforced server-side.
4. **Declared Batting in Multi-day / 4-Innings Matches**:
   - Schema supports up to 4 innings (`innings_number IN (1, 2, 3, 4)`), but match victory logic in Phase 2 defaults to 2-innings limited overs formats (T20, ODI, T10).
