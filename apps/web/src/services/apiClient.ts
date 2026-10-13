/**
 * Typed HTTP client for the Cricket Highlights FastAPI backend.
 * Base URL is read from VITE_API_BASE_URL (or falls back to Vite proxy).
 */

const rawApiBase = import.meta.env.VITE_API_BASE_URL ?? ''
const isLocalhostTarget = /^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?/i.test(rawApiBase)
const isBrowserLocalhost =
  typeof window !== 'undefined' &&
  (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')

const API_BASE = isLocalhostTarget && !isBrowserLocalhost ? '' : rawApiBase

// ── Shared ────────────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: string
  service?: string
  db?: string
  storage?: string
  bucket?: string
  bucket_exists?: boolean
  provider?: string
}

// ── Teams ─────────────────────────────────────────────────────────────────────

export interface Team {
  id: string
  owner_id: string
  name: string
  short_name: string | null
  logo_url: string | null
  created_at: string
  updated_at: string
}

export interface TeamCreate {
  name: string
  short_name?: string | null
  logo_url?: string | null
}

export interface TeamUpdate {
  name?: string
  short_name?: string | null
  logo_url?: string | null
}

export interface SquadImportEntry {
  full_name: string
  display_name?: string | null
  batting_style?: string | null
  bowling_style?: string | null
  role?: string | null
  jersey_number?: number | null
}

// ── Players ───────────────────────────────────────────────────────────────────

export interface Player {
  id: string
  owner_id: string
  full_name: string
  display_name: string | null
  batting_style: string | null
  bowling_style: string | null
  role: string | null
  jersey_number: number | null
  photo_url: string | null
  created_at: string
  updated_at: string
}

export interface PlayerCreate {
  full_name: string
  display_name?: string | null
  batting_style?: string | null
  bowling_style?: string | null
  role?: string | null
  jersey_number?: number | null
  photo_url?: string | null
}

// ── Matches ───────────────────────────────────────────────────────────────────

export interface MatchTeam {
  id: string
  match_id: string
  team_id: string
  team_name: string
  batting_order: number
}

export interface Match {
  id: string
  owner_id: string
  title: string
  format: string
  tournament?: string | null
  venue: string | null
  scheduled_at: string | null
  status: string
  overs_per_innings: number | null
  created_at: string
  updated_at: string
  teams: MatchTeam[]
}

export interface MatchCreate {
  title: string
  format: string
  tournament?: string | null
  venue?: string | null
  scheduled_at?: string | null
  overs_per_innings?: number | null
  teams: Array<{ team_id: string; batting_order: number }>
}

// ── Playing XI ────────────────────────────────────────────────────────────────

export interface PlayingXIEntry {
  id: string
  match_id: string
  team_id: string
  player_id: string
  player_name: string
  batting_position: number | null
  is_captain: boolean
  is_wicketkeeper: boolean
  selected_at: string
}

export interface PlayingXISetRequest {
  team_id: string
  players: Array<{
    player_id: string
    batting_position?: number | null
    is_captain?: boolean
    is_wicketkeeper?: boolean
  }>
}

// ── HTTP helper ───────────────────────────────────────────────────────────────

function parseErrorMessage(status: number, text: string): string {
  try {
    const parsed = JSON.parse(text)
    if (typeof parsed.detail === 'string') return parsed.detail
    if (Array.isArray(parsed.detail) && parsed.detail.length > 0) {
      return parsed.detail.map((d: { msg?: string }) => d.msg || JSON.stringify(d)).join('; ')
    }
  } catch {
    // fallback to raw text
  }
  return text || `Request failed with status ${status}`
}

async function request<T>(
  path: string,
  options?: RequestInit & { token?: string },
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (options?.token) {
    headers['Authorization'] = `Bearer ${options.token}`
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { ...headers, ...options?.headers },
  })
  if (!response.ok) {
    if (response.status === 401) {
      window.dispatchEvent(new CustomEvent('cricket:unauthorized'))
    }
    const text = await response.text()
    throw new Error(parseErrorMessage(response.status, text))
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

// ── apiClient ─────────────────────────────────────────────────────────────────

export const apiClient = {
  // health
  health: () => request<HealthResponse>('/health'),
  healthDb: () => request<HealthResponse>('/health/db'),
  healthStorage: () => request<HealthResponse>('/health/storage'),
  me: (token: string) =>
    request<{ user_id: string; email: string; role: string }>('/api/me', { token }),

  // teams
  createTeam: (token: string, body: TeamCreate) =>
    request<Team>('/api/teams', { method: 'POST', body: JSON.stringify(body), token }),
  listTeams: (token: string) =>
    request<Team[]>('/api/teams', { token }),
  getTeam: (token: string, id: string) =>
    request<Team>(`/api/teams/${id}`, { token }),
  updateTeam: (token: string, id: string, body: TeamUpdate) =>
    request<Team>(`/api/teams/${id}`, { method: 'PATCH', body: JSON.stringify(body), token }),
  deleteTeam: (token: string, id: string) =>
    request<void>(`/api/teams/${id}`, { method: 'DELETE', token }),

  // squad
  listSquad: (token: string, teamId: string) =>
    request<Array<{ id: string; player_id: string; is_active: boolean; players: Player }>>(
      `/api/teams/${teamId}/squad`,
      { token },
    ),
  addSquadMember: (token: string, teamId: string, playerId: string) =>
    request<unknown>(`/api/teams/${teamId}/squad`, {
      method: 'POST',
      body: JSON.stringify({ player_id: playerId }),
      token,
    }),
  removeSquadMember: (token: string, teamId: string, playerId: string) =>
    request<void>(`/api/teams/${teamId}/squad/${playerId}`, { method: 'DELETE', token }),
  importSquad: (token: string, teamId: string, players: SquadImportEntry[]) =>
    request<{ created: number; skipped: number; errors: string[] }>(
      `/api/teams/${teamId}/squad/import`,
      { method: 'POST', body: JSON.stringify({ players }), token },
    ),

  // players
  createPlayer: (token: string, body: PlayerCreate) =>
    request<Player>('/api/players', { method: 'POST', body: JSON.stringify(body), token }),
  listPlayers: (token: string, search?: string) =>
    request<Player[]>(`/api/players${search ? `?search=${encodeURIComponent(search)}` : ''}`, { token }),
  getPlayer: (token: string, id: string) =>
    request<Player>(`/api/players/${id}`, { token }),
  updatePlayer: (token: string, id: string, body: Partial<PlayerCreate>) =>
    request<Player>(`/api/players/${id}`, { method: 'PATCH', body: JSON.stringify(body), token }),
  deletePlayer: (token: string, id: string) =>
    request<void>(`/api/players/${id}`, { method: 'DELETE', token }),

  // matches
  createMatch: (token: string, body: MatchCreate) =>
    request<Match>('/api/matches', { method: 'POST', body: JSON.stringify(body), token }),
  listMatches: (token: string) =>
    request<Match[]>('/api/matches', { token }),
  getMatch: (token: string, id: string) =>
    request<Match>(`/api/matches/${id}`, { token }),
  updateMatch: (token: string, id: string, body: Partial<{ title: string; venue: string | null; status: string; overs_per_innings: number | null }>) =>
    request<Match>(`/api/matches/${id}`, { method: 'PATCH', body: JSON.stringify(body), token }),
  deleteMatch: (token: string, id: string) =>
    request<void>(`/api/matches/${id}`, { method: 'DELETE', token }),

  // playing XI
  setPlayingXI: (token: string, matchId: string, body: PlayingXISetRequest) =>
    request<PlayingXIEntry[]>(`/api/matches/${matchId}/playing-xi`, {
      method: 'PUT',
      body: JSON.stringify(body),
      token,
    }),
  getPlayingXI: (token: string, matchId: string, teamId: string) =>
    request<PlayingXIEntry[]>(`/api/matches/${matchId}/playing-xi/${teamId}`, { token }),

  // scoring & innings
  startInnings: (token: string, matchId: string, body: InningsStartRequest) =>
    request<Innings>(`/api/matches/${matchId}/innings`, {
      method: 'POST',
      body: JSON.stringify(body),
      token,
    }),
  listMatchInnings: (token: string, matchId: string) =>
    request<Innings[]>(`/api/matches/${matchId}/innings`, { token }),
  getInnings: (token: string, inningsId: string) =>
    request<Innings>(`/api/innings/${inningsId}`, { token }),
  updateInnings: (token: string, inningsId: string, body: InningsUpdateRequest) =>
    request<Innings>(`/api/innings/${inningsId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
      token,
    }),
  getInningsScorecard: (token: string, inningsId: string) =>
    request<InningsScorecard>(`/api/innings/${inningsId}/scorecard`, { token }),
  getMatchScorecard: (token: string, matchId: string) =>
    request<MatchScorecard>(`/api/matches/${matchId}/scorecard`, { token }),
  listDeliveries: (token: string, inningsId: string) =>
    request<Delivery[]>(`/api/innings/${inningsId}/deliveries`, { token }),
  recordDelivery: (token: string, inningsId: string, body: DeliveryCreate) =>
    request<Delivery>(`/api/innings/${inningsId}/deliveries`, {
      method: 'POST',
      body: JSON.stringify(body),
      token,
    }),
  voidDelivery: (token: string, deliveryId: string, body: DeliveryVoidRequest) =>
    request<Delivery>(`/api/deliveries/${deliveryId}/void`, {
      method: 'POST',
      body: JSON.stringify(body),
      token,
    }),
  updateDelivery: (token: string, deliveryId: string, body: DeliveryUpdate) =>
    request<Delivery>(`/api/deliveries/${deliveryId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
      token,
    }),

  // recording sessions & event markers
  createRecordingSession: (token: string, matchId: string, body: RecordingSessionCreate) =>
    request<RecordingSession>(`/api/matches/${matchId}/recordings`, {
      method: 'POST',
      body: JSON.stringify(body),
      token,
    }),
  listRecordingSessions: (token: string, matchId: string) =>
    request<RecordingSession[]>(`/api/matches/${matchId}/recordings`, { token }),
  getRecordingSession: (token: string, sessionId: string) =>
    request<RecordingSession>(`/api/recordings/${sessionId}`, { token }),
  updateRecordingSession: (token: string, sessionId: string, body: RecordingSessionUpdate) =>
    request<RecordingSession>(`/api/recordings/${sessionId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
      token,
    }),
  uploadSessionVideo: async (token: string, sessionId: string, file: Blob | File, filename = 'recording.webm'): Promise<RecordingSession> => {
    const formData = new FormData()
    formData.append('file', file, filename)
    const response = await fetch(`${API_BASE}/api/recordings/${sessionId}/upload`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
      },
      body: formData,
    })
    if (!response.ok) {
      if (response.status === 401) {
        window.dispatchEvent(new CustomEvent('cricket:unauthorized'))
      }
      const text = await response.text()
      throw new Error(parseErrorMessage(response.status, text))
    }
    return response.json() as Promise<RecordingSession>
  },
  addVideoSegment: (token: string, sessionId: string, body: VideoSegmentCreate) =>
    request<VideoSegment>(`/api/recordings/${sessionId}/segments`, {
      method: 'POST',
      body: JSON.stringify(body),
      token,
    }),
  createMarker: (token: string, sessionId: string, body: EventMarkerCreate) =>
    request<EventMarker>(`/api/recordings/${sessionId}/markers`, {
      method: 'POST',
      body: JSON.stringify(body),
      token,
    }),
  listMarkers: (token: string, sessionId: string) =>
    request<EventMarker[]>(`/api/recordings/${sessionId}/markers`, { token }),
  linkMarker: (token: string, markerId: string, body: EventMarkerLinkDelivery) =>
    request<EventMarker>(`/api/markers/${markerId}/link`, {
      method: 'POST',
      body: JSON.stringify(body),
      token,
    }),
  updateMarker: (token: string, markerId: string, body: EventMarkerUpdate) =>
    request<EventMarker>(`/api/markers/${markerId}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
      token,
    }),
  deleteMarker: (token: string, markerId: string) =>
    request<void>(`/api/markers/${markerId}`, { method: 'DELETE', token }),

  // highlights
  triggerHighlight: (token: string, body: HighlightTriggerRequest) =>
    request<PlayerHighlight>('/api/highlights/trigger', {
      method: 'POST',
      body: JSON.stringify(body),
      token,
    }),
  reprocessHighlight: (token: string, highlightId: string, body: ReprocessHighlightRequest) =>
    request<PlayerHighlight>(`/api/highlights/${highlightId}/reprocess`, {
      method: 'POST',
      body: JSON.stringify(body),
      token,
    }),
  getHighlightJob: (token: string, jobId: string) =>
    request<HighlightJob>(`/api/highlights/jobs/${jobId}`, { token }),
  getPlayerHighlights: (token: string, playerId: string) =>
    request<PlayerHighlightReel>(`/api/players/${playerId}/highlights`, { token }),
  getMatchHighlights: (token: string, matchId: string) =>
    request<PlayerHighlight[]>(`/api/matches/${matchId}/highlights`, { token }),

  // milestones & celebrations (Phase 5)
  getMatchMilestones: (token: string, matchId: string) =>
    request<PlayerMilestone[]>(`/api/matches/${matchId}/milestones`, { token }),
  getInningsMilestones: (token: string, inningsId: string) =>
    request<PlayerMilestone[]>(`/api/innings/${inningsId}/milestones`, { token }),
  recalculateInningsMilestones: (token: string, inningsId: string) =>
    request<PlayerMilestone[]>(`/api/innings/${inningsId}/milestones/recalculate`, {
      method: 'POST',
      token,
    }),
  getPlayerMilestones: (token: string, playerId: string) =>
    request<PlayerMilestoneSummary>(`/api/players/${playerId}/milestones`, { token }),
  getMilestone: (token: string, milestoneId: string) =>
    request<PlayerMilestone>(`/api/milestones/${milestoneId}`, { token }),

  // Phase 6: Player Profiles, Historical Match Archive & Operations
  deleteRecordingSession: (token: string, sessionId: string) =>
    request<void>(`/api/recordings/${sessionId}`, { method: 'DELETE', token }),
  getPlayerProfile: (
    token: string,
    playerId: string,
    params?: {
      match_id?: string
      tournament?: string
      event_type?: string
      limit?: number
      offset?: number
    },
  ) => {
    const qs = new URLSearchParams()
    if (params?.match_id) qs.set('match_id', params.match_id)
    if (params?.tournament) qs.set('tournament', params.tournament)
    if (params?.event_type) qs.set('event_type', params.event_type)
    if (params?.limit != null) qs.set('limit', String(params.limit))
    if (params?.offset != null) qs.set('offset', String(params.offset))
    const queryStr = qs.toString()
    return request<PlayerProfileResponse>(
      `/api/players/${playerId}/profile${queryStr ? `?${queryStr}` : ''}`,
      { token },
    )
  },
  searchMatchArchive: (
    token: string,
    params?: {
      q?: string
      team_id?: string
      team_b_id?: string
      player_id?: string
      date_from?: string
      date_to?: string
      format?: string
      tournament?: string
      status?: string
      innings_number?: number
      highlight_type?: string
      limit?: number
      offset?: number
    },
  ) => {
    const qs = new URLSearchParams()
    if (params?.q) qs.set('q', params.q)
    if (params?.team_id) qs.set('team_id', params.team_id)
    if (params?.team_b_id) qs.set('team_b_id', params.team_b_id)
    if (params?.player_id) qs.set('player_id', params.player_id)
    if (params?.date_from) qs.set('date_from', params.date_from)
    if (params?.date_to) qs.set('date_to', params.date_to)
    if (params?.format) qs.set('format', params.format)
    if (params?.tournament) qs.set('tournament', params.tournament)
    if (params?.status) qs.set('status', params.status)
    if (params?.innings_number != null) qs.set('innings_number', String(params.innings_number))
    if (params?.highlight_type) qs.set('highlight_type', params.highlight_type)
    if (params?.limit != null) qs.set('limit', String(params.limit))
    if (params?.offset != null) qs.set('offset', String(params.offset))
    const queryStr = qs.toString()
    return request<MatchArchivePageResponse>(
      `/api/archive/matches${queryStr ? `?${queryStr}` : ''}`,
      { token },
    )
  },
  getSignedMediaUrl: (token: string, key: string) =>
    request<{ key: string; signed_url: string; expires_at: number; signature: string }>(
      `/api/media/sign?key=${encodeURIComponent(key)}`,
      { token },
    ),
  getOpsDiagnostics: (token: string) =>
    request<OpsDiagnosticsResponse>('/api/ops/diagnostics', { token }),
  retryFailedJobs: (token: string, matchId?: string) =>
    request<{ retried_highlight_jobs: number; recovered_recording_sessions: number; details: string[] }>(
      `/api/ops/jobs/retry-failed${matchId ? `?match_id=${encodeURIComponent(matchId)}` : ''}`,
      { method: 'POST', token },
    ),
  applyRetentionPolicy: (token: string, retentionDays = 90, dryRun = false) =>
    request<{
      retention_days: number
      dry_run: boolean
      expired_sessions_found: number
      raw_videos_purged: number
      highlights_preserved: number
    }>('/api/ops/retention/apply', {
      method: 'POST',
      body: JSON.stringify({ retention_days: retentionDays, dry_run: dryRun }),
      token,
    }),
  exportBackup: (token: string) =>
    request<BackupManifestResponse>('/api/ops/backup/export', { token }),
  verifyBackup: (token: string, checksum_sha256: string, data: Record<string, unknown>) =>
    request<{ valid: boolean; computed_checksum: string; counts: Record<string, number>; message: string }>(
      '/api/ops/backup/verify',
      { method: 'POST', body: JSON.stringify({ checksum_sha256, data }), token },
    ),
}

// ── Highlights Models ────────────────────────────────────────────────────────

export interface HighlightTriggerRequest {
  delivery_id: string
  marker_id?: string | null
  config_before_sec?: number
  config_after_sec?: number
}

export interface ReprocessHighlightRequest {
  config_before_sec?: number
  config_after_sec?: number
  marker_id?: string | null
}

export interface HighlightJob {
  id: string
  match_id: string
  delivery_id: string
  marker_id?: string | null
  player_id: string
  status: 'pending' | 'processing' | 'ready' | 'retrying' | 'failed'
  event_type: 'four' | 'six'
  retry_count: number
  max_retries: number
  error_message?: string | null
  config_before_sec: number
  config_after_sec: number
  version: number
  audit_metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface PlayerHighlight {
  id: string
  job_id?: string | null
  match_id: string
  innings_id: string
  delivery_id: string
  marker_id?: string | null
  player_id: string
  event_type: 'four' | 'six'
  status: 'pending' | 'processing' | 'ready' | 'failed'
  video_url?: string | null
  video_key?: string | null
  thumbnail_url?: string | null
  thumbnail_key?: string | null
  duration_sec?: number | null
  start_offset_sec?: number | null
  end_offset_sec?: number | null
  delivery_metadata: {
    over_display?: string
    over_no?: number
    ball_in_over?: number
    batter_runs?: number
    boundary_type?: number
    striker_name?: string
    bowler_name?: string
  }
  version: number
  created_at: string
  updated_at: string
}

export interface PlayerHighlightReel {
  player_id: string
  player_name: string
  total_highlights: number
  fours_count: number
  sixes_count: number
  highlights: PlayerHighlight[]
}

// ── Recording Models ──────────────────────────────────────────────────────────


export interface RecordingSession {
  id: string
  match_id: string
  owner_id: string
  session_name: string
  status: 'active' | 'paused' | 'stopped' | 'completed' | 'failed' | 'interrupted'
  started_at: string
  ended_at: string | null
  total_duration_ms: number
  media_asset_id: string | null
  media_url: string | null
  upload_status: 'pending' | 'uploading' | 'uploaded' | 'failed' | 'not_required'
  processing_status: 'unprocessed' | 'processing' | 'completed' | 'failed'
  segments_count: number
  media_metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface RecordingSessionCreate {
  session_name?: string
  media_metadata?: Record<string, unknown>
}

export interface RecordingSessionUpdate {
  session_name?: string
  status?: 'active' | 'paused' | 'stopped' | 'completed' | 'failed' | 'interrupted'
  total_duration_ms?: number
  media_asset_id?: string
  media_url?: string
  upload_status?: 'pending' | 'uploading' | 'uploaded' | 'failed' | 'not_required'
  processing_status?: 'unprocessed' | 'processing' | 'completed' | 'failed'
  segments_count?: number
  media_metadata?: Record<string, unknown>
}

export interface VideoSegment {
  id: string
  session_id: string
  match_id: string
  segment_index: number
  segment_name: string
  duration_ms: number
  storage_key: string | null
  storage_url: string | null
  upload_status: 'pending' | 'uploading' | 'uploaded' | 'failed'
  created_at: string
  updated_at: string
}

export interface VideoSegmentCreate {
  segment_index: number
  segment_name: string
  duration_ms?: number
  storage_key?: string | null
  storage_url?: string | null
  upload_status?: 'pending' | 'uploading' | 'uploaded' | 'failed'
}

export interface EventMarker {
  id: string
  session_id: string
  match_id: string
  segment_id: string | null
  segment_index: number
  delivery_id: string | null
  innings_id: string | null
  marker_number: number
  elapsed_ms: number
  segment_offset_ms: number
  marker_label: string
  status: 'unlinked' | 'linked' | 'ignored'
  delivery_display: string | null
  client_marker_id: string | null
  audit_metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface EventMarkerCreate {
  elapsed_ms: number
  segment_index?: number
  segment_offset_ms?: number
  marker_label?: string
  delivery_id?: string | null
  innings_id?: string | null
  client_marker_id?: string | null
  audit_metadata?: Record<string, unknown>
}

export interface EventMarkerLinkDelivery {
  delivery_id: string
  innings_id?: string | null
  delivery_display?: string | null
}

export interface EventMarkerUpdate {
  elapsed_ms?: number
  segment_offset_ms?: number
  marker_label?: string
  status?: 'unlinked' | 'linked' | 'ignored'
  delivery_id?: string | null
  innings_id?: string | null
  delivery_display?: string | null
  audit_metadata?: Record<string, unknown>
}

// ── Scoring Models ────────────────────────────────────────────────────────────

export interface Innings {
  id: string
  match_id: string
  innings_number: number
  batting_team_id: string
  bowling_team_id: string
  current_striker_id: string | null
  current_non_striker_id: string | null
  current_bowler_id: string | null
  target_runs: number | null
  total_runs: number
  total_wickets: number
  total_legal_balls: number
  total_wides: number
  total_no_balls: number
  total_byes: number
  total_leg_byes: number
  total_penalty_runs: number
  status: 'not_started' | 'in_progress' | 'completed' | 'forfeited'
  completed_reason: string | null
  created_at: string
  updated_at: string
}

export interface InningsStartRequest {
  innings_number: number
  batting_team_id: string
  bowling_team_id: string
  opening_striker_id: string
  opening_non_striker_id: string
  opening_bowler_id: string
  target_runs?: number | null
}

export interface InningsUpdateRequest {
  current_striker_id?: string | null
  current_non_striker_id?: string | null
  current_bowler_id?: string | null
  status?: string | null
  completed_reason?: string | null
}

export interface Delivery {
  id: string
  innings_id: string
  match_id: string
  sequence_no: number
  over_no: number
  ball_in_over: number
  display_over: string
  striker_id: string
  non_striker_id: string
  bowler_id: string
  batter_runs: number
  extra_type: 'wide' | 'no_ball' | 'bye' | 'leg_bye' | 'penalty' | null
  extra_runs: number
  total_runs: number
  is_legal: boolean
  is_boundary: boolean
  boundary_type: number | null
  is_batter_boundary: boolean
  is_wicket: boolean
  wicket_type: string | null
  dismissed_player_id: string | null
  fielder_id: string | null
  fielder2_id: string | null
  dismissal_delivery_end: string | null
  runs_completed_before_out: number
  next_striker_id: string | null
  next_non_striker_id: string | null
  revision_no: number
  is_voided: boolean
  voided_reason: string | null
  idempotency_key: string | null
  audit_metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface DeliveryCreate {
  striker_id: string
  non_striker_id: string
  bowler_id: string
  batter_runs?: number
  extra_type?: 'wide' | 'no_ball' | 'bye' | 'leg_bye' | 'penalty' | null
  extra_runs?: number
  is_boundary?: boolean
  boundary_type?: 4 | 6 | null
  is_batter_boundary?: boolean
  is_wicket?: boolean
  wicket_type?: string | null
  dismissed_player_id?: string | null
  fielder_id?: string | null
  fielder2_id?: string | null
  dismissal_delivery_end?: 'striker' | 'non_striker' | null
  runs_completed_before_out?: number
  next_striker_id?: string | null
  next_non_striker_id?: string | null
  idempotency_key?: string | null
  audit_metadata?: Record<string, unknown>
}

export interface DeliveryUpdate {
  batter_runs?: number
  extra_type?: 'wide' | 'no_ball' | 'bye' | 'leg_bye' | 'penalty' | null
  extra_runs?: number
  is_boundary?: boolean
  boundary_type?: 4 | 6 | null
  is_batter_boundary?: boolean
  is_wicket?: boolean
  wicket_type?: string | null
  dismissed_player_id?: string | null
  fielder_id?: string | null
  correction_reason?: string
}

export interface DeliveryVoidRequest {
  reason: string
}

export interface BatterScorecardFigure {
  player_id: string
  player_name: string
  runs: number
  balls: number
  fours: number
  sixes: number
  strike_rate: number
  is_out: boolean
  dismissal_text: string
  wicket_type: string | null
  bowler_name: string | null
  fielder_name: string | null
  batting_position: number | null
}

export interface BowlerScorecardFigure {
  player_id: string
  player_name: string
  overs: string
  legal_balls: number
  maidens: number
  runs_conceded: number
  wickets: number
  economy: number
  dots: number
  wides: number
  no_balls: number
}

export interface ExtrasBreakdown {
  total: number
  wides: number
  no_balls: number
  byes: number
  leg_byes: number
  penalty: number
}

export interface FallOfWicketFigure {
  wicket_number: number
  score: number
  overs: string
  dismissed_player_id: string
  dismissed_player_name: string
}

export interface PartnershipFigure {
  batter1_id: string
  batter1_name: string
  batter2_id: string
  batter2_name: string
  runs: number
  balls: number
}

export interface InningsScorecard {
  innings_id: string
  match_id: string
  innings_number: number
  batting_team_id: string
  batting_team_name: string
  bowling_team_id: string
  bowling_team_name: string
  status: 'not_started' | 'in_progress' | 'completed' | 'forfeited'
  completed_reason: string | null
  total_runs: number
  total_wickets: number
  total_legal_balls: number
  overs_display: string
  run_rate: number
  target_runs: number | null
  required_run_rate: number | null
  current_striker: BatterScorecardFigure | null
  current_non_striker: BatterScorecardFigure | null
  current_bowler: BowlerScorecardFigure | null
  batters: BatterScorecardFigure[]
  bowlers: BowlerScorecardFigure[]
  extras: ExtrasBreakdown
  fall_of_wickets: FallOfWicketFigure[]
  partnerships: PartnershipFigure[]
  current_partnership: PartnershipFigure | null
}

export interface MatchScorecard {
  match_id: string
  title: string
  format: string
  status: string
  overs_per_innings: number | null
  winner_team_id: string | null
  result_text: string | null
  innings: InningsScorecard[]
}

// ── Phase 5: Milestones & Broadcast Animations ──────────────────────────────

export type MilestoneType = 'FIFTY' | 'CENTURY' | 'ONE_FIFTY' | 'DOUBLE_CENTURY'
export type AnimationEventType = 'FOUR' | 'SIX' | MilestoneType
export type HighlightClipStatus = 'ready' | 'processing' | 'pending' | 'failed' | 'unavailable'

export interface PlayerMilestone {
  id: string
  match_id: string
  innings_id: string
  player_id: string
  delivery_id: string
  threshold: number
  milestone_type: MilestoneType
  batter_score: number
  balls_faced: number
  fours_count: number
  sixes_count: number
  over_display: string | null
  is_valid: boolean
  invalidated_reason: string | null
  animation_version: number
  metadata: {
    match_title?: string
    format?: string
    innings_number?: number
    batting_team_name?: string
    bowling_team_name?: string
    player_name?: string
    bowler_name?: string | null
    boundary_type?: number | null
    strike_rate?: number
  }
  highlight_id: string | null
  highlight_status: HighlightClipStatus
  highlight_video_url: string | null
  highlight_thumbnail_url: string | null
  created_at: string
  updated_at: string
}

export interface PlayerMilestoneSummary {
  player_id: string
  player_name: string
  total_milestones: number
  fifties_count: number
  centuries_count: number
  one_fifties_count: number
  double_centuries_count: number
  milestones: PlayerMilestone[]
}

// ── Phase 6: Player Profiles, Historical Match Archive & Operations ──────────

export interface PlayerTeamHistoryEntry {
  team_id: string
  team_name: string
  short_name: string | null
  is_current_squad: boolean
  matches_played_for_team: number
}

export interface PlayerCareerStats {
  matches_played: number
  innings_batted: number
  not_outs: number
  total_runs: number
  highest_score: number
  highest_score_not_out: boolean
  batting_average: number
  balls_faced: number
  batting_strike_rate: number
  fours: number
  sixes: number
  fifties: number
  centuries: number
  innings_bowled: number
  balls_bowled: number
  overs_bowled: string
  maidens: number
  runs_conceded: number
  wickets_taken: number
  best_bowling: string
  bowling_economy: number
  bowling_average: number
}

export interface PlayerMatchPerformance {
  match_id: string
  match_title: string
  tournament: string | null
  format: string
  venue: string | null
  scheduled_at: string | null
  match_status: string
  player_team_name: string | null
  opponent_team_name: string | null
  batted: boolean
  innings_id: string | null
  innings_number: number | null
  runs: number
  balls: number
  fours: number
  sixes: number
  strike_rate: number
  is_out: boolean
  dismissal_text: string
  bowled: boolean
  bowling_innings_id: string | null
  overs_display: string
  maidens: number
  runs_conceded: number
  wickets: number
  economy: number
  highlights_in_match: number
}

export interface PlayerProfileResponse {
  player: Player
  team_history: PlayerTeamHistoryEntry[]
  career_stats: PlayerCareerStats
  match_performances: PlayerMatchPerformance[]
  milestones: PlayerMilestone[]
  highlights: PlayerHighlight[]
  highlights_total: number
  highlights_limit: number
  highlights_offset: number
  has_more_highlights: boolean
  available_tournaments: string[]
  available_matches: Array<{ match_id: string; title: string; tournament: string | null }>
}

export interface ArchivedInningsSummary {
  innings_id: string
  innings_number: number
  batting_team_id: string
  batting_team_name: string
  total_runs: number
  total_wickets: number
  overs_display: string
  status: string
}

export interface ArchivedMatchItem {
  match: Match
  tournament: string | null
  innings_summaries: ArchivedInningsSummary[]
  result_text: string | null
  highlights_count: number
  fours_count: number
  sixes_count: number
  milestones_count: number
}

export interface MatchArchivePageResponse {
  items: ArchivedMatchItem[]
  total: number
  limit: number
  offset: number
  has_more: boolean
  facets: {
    tournaments: string[]
    formats: string[]
  }
}

export interface AuditLogEntry {
  id: string
  actor_id: string
  action: string
  resource_type: string
  resource_id: string | null
  details: Record<string, unknown>
  created_at: string
}

export interface OpsDiagnosticsResponse {
  status: 'healthy' | 'degraded'
  service_version: string
  db_connected: boolean
  storage_connected: boolean
  failed_highlight_jobs: number
  pending_highlight_jobs: number
  interrupted_recordings: number
  total_archived_matches: number
  total_ready_highlights: number
  retention_policy_default_days: number
  recent_audit_logs: AuditLogEntry[]
}

export interface BackupManifestResponse {
  exported_at: string
  owner_id: string
  counts: Record<string, number>
  checksum_sha256: string
  data: Record<string, unknown>
}


