import { useEffect, useState, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import {
  apiClient,
  type PlayerProfileResponse,
  type PlayerHighlight,
} from '../../services/apiClient'
import { AppShell } from '../../components/layout/AppShell'
import { Card } from '../../components/ui/Card'
import { Button } from '../../components/ui/Button'
import { Alert } from '../../components/ui/Alert'
import { Spinner } from '../../components/ui/Spinner'
import { MilestoneTimelineSection } from '../../components/animations/MilestoneTimelineSection'
import {
  BroadcastAnimationOverlay,
  type BroadcastAnimationPayload,
} from '../../components/animations/BroadcastAnimationOverlay'
import { colors } from '../../theme'

const PAGE_SIZE = 8

export function PlayerHighlightsPage() {
  const { playerId } = useParams<{ playerId: string }>()
  const { token } = useAuth()

  const [profile, setProfile] = useState<PlayerProfileResponse | null>(null)
  const [highlightsList, setHighlightsList] = useState<PlayerHighlight[]>([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState('')

  // Filters & Pagination
  const [filterMatchId, setFilterMatchId] = useState<string>('')
  const [filterTournament, setFilterTournament] = useState<string>('')
  const [filterEventType, setFilterEventType] = useState<string>('')
  const [offset, setOffset] = useState<number>(0)

  // Video player & Reprocessing
  const [selectedHighlight, setSelectedHighlight] = useState<PlayerHighlight | null>(null)
  const [boundaryAnim, setBoundaryAnim] = useState<BroadcastAnimationPayload | null>(null)
  const [reprocessingId, setReprocessingId] = useState<string | null>(null)
  const [trimBefore, setTrimBefore] = useState(4.0)
  const [trimAfter, setTrimAfter] = useState(5.0)
  const [reprocessMsg, setReprocessMsg] = useState('')

  const fetchProfile = useCallback(
    async (newOffset = 0, append = false) => {
      if (!token || !playerId) return
      try {
        if (append) {
          setLoadingMore(true)
        } else {
          setLoading(true)
        }
        setError('')
        const data = await apiClient.getPlayerProfile(token, playerId, {
          match_id: filterMatchId || undefined,
          tournament: filterTournament || undefined,
          event_type: filterEventType || undefined,
          limit: PAGE_SIZE,
          offset: newOffset,
        })
        setProfile(data)
        setOffset(newOffset)
        if (append) {
          setHighlightsList((prev) => [...prev, ...data.highlights])
        } else {
          setHighlightsList(data.highlights)
        }
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : String(e))
      } finally {
        setLoading(false)
        setLoadingMore(false)
      }
    },
    [token, playerId, filterMatchId, filterTournament, filterEventType],
  )

  useEffect(() => {
    void fetchProfile(0, false)
  }, [fetchProfile])

  const handleLoadMore = () => {
    if (!profile || !profile.has_more_highlights || loadingMore) return
    void fetchProfile(offset + PAGE_SIZE, true)
  }

  const handleReprocess = async (hl: PlayerHighlight) => {
    if (!token) return
    try {
      setReprocessMsg('Submitting reprocess request...')
      await apiClient.reprocessHighlight(token, hl.id, {
        config_before_sec: trimBefore,
        config_after_sec: trimAfter,
      })
      setReprocessMsg('Highlight queued for reprocessing! Refreshing...')
      setTimeout(() => {
        setReprocessingId(null)
        setReprocessMsg('')
        void fetchProfile(0, false)
      }, 2000)
    } catch (err) {
      setReprocessMsg(`Reprocessing failed: ${String(err)}`)
    }
  }

  const p = profile?.player
  const stats = profile?.career_stats
  const displayName = p?.display_name || p?.full_name || 'Player'

  return (
    <AppShell>
      <BroadcastAnimationOverlay
        event={boundaryAnim}
        onDismiss={() => setBoundaryAnim(null)}
      />

      {/* Breadcrumb */}
      <div style={{ marginBottom: 16 }}>
        <Link to="/players" style={{ color: colors.textMuted, textDecoration: 'none', fontSize: 14 }}>
          ← Back to Players Directory
        </Link>
      </div>

      {loading && !profile && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}>
          <Spinner />
        </div>
      )}

      {error && <Alert type="error">{error}</Alert>}

      {profile && p && stats && (
        <>
          {/* 1. Player Identity & Team History Header */}
          <Card
            style={{
              marginBottom: 20,
              padding: 24,
              background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
              color: '#fff',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 20 }}>
              <div style={{ display: 'flex', gap: 18, alignItems: 'center', flexWrap: 'wrap' }}>
                {/* Photo / Crest */}
                {p.photo_url ? (
                  <img
                    src={p.photo_url}
                    alt={displayName}
                    style={{ width: 76, height: 76, borderRadius: '50%', objectFit: 'cover', border: '3px solid #38bdf8' }}
                  />
                ) : (
                  <div
                    style={{
                      width: 76,
                      height: 76,
                      borderRadius: '50%',
                      background: 'linear-gradient(135deg, #16a34a, #0284c7)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: 28,
                      fontWeight: 900,
                      color: '#fff',
                      border: '3px solid rgba(255,255,255,0.25)',
                    }}
                  >
                    {displayName.slice(0, 2).toUpperCase()}
                  </div>
                )}

                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                    <h1 style={{ margin: 0, fontSize: 26, fontWeight: 900 }}>{p.full_name}</h1>
                    {p.jersey_number != null && (
                      <span
                        style={{
                          background: '#38bdf8',
                          color: '#0f172a',
                          padding: '2px 10px',
                          borderRadius: 14,
                          fontSize: 13,
                          fontWeight: 900,
                        }}
                      >
                        #{p.jersey_number}
                      </span>
                    )}
                    {p.role && (
                      <span
                        style={{
                          background: 'rgba(255,255,255,0.14)',
                          color: '#e2e8f0',
                          padding: '3px 10px',
                          borderRadius: 14,
                          fontSize: 12,
                          fontWeight: 700,
                          textTransform: 'capitalize',
                        }}
                      >
                        {p.role}
                      </span>
                    )}
                  </div>

                  <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginTop: 6, fontSize: 13, color: '#94a3b8' }}>
                    {p.display_name && <span>Known as: <strong style={{ color: '#e2e8f0' }}>{p.display_name}</strong></span>}
                    {p.batting_style && <span>🏏 Bat: <strong style={{ color: '#e2e8f0' }}>{p.batting_style}</strong></span>}
                    {p.bowling_style && <span>⚾ Bowl: <strong style={{ color: '#e2e8f0' }}>{p.bowling_style}</strong></span>}
                  </div>

                  {/* Team History */}
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginTop: 12 }}>
                    <span style={{ fontSize: 12, color: '#94a3b8', fontWeight: 600 }}>Teams:</span>
                    {profile.team_history.length === 0 ? (
                      <span style={{ fontSize: 12, color: '#64748b' }}>Unassigned</span>
                    ) : (
                      profile.team_history.map((th) => (
                        <Link
                          key={th.team_id}
                          to={`/teams/${th.team_id}`}
                          style={{
                            textDecoration: 'none',
                            background: th.is_current_squad ? 'rgba(22, 163, 74, 0.28)' : 'rgba(148, 163, 184, 0.2)',
                            border: `1px solid ${th.is_current_squad ? '#4ade80' : '#64748b'}`,
                            color: '#fff',
                            padding: '3px 10px',
                            borderRadius: 12,
                            fontSize: 12,
                            fontWeight: 700,
                          }}
                        >
                          🛡️ {th.team_name}
                          {!th.is_current_squad ? ' (Historical)' : ''}
                          {th.matches_played_for_team > 0 ? ` · ${th.matches_played_for_team}m` : ''}
                        </Link>
                      ))
                    )}
                  </div>
                </div>
              </div>

              {/* Milestone & Boundary Summary Pills */}
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <span style={{ background: '#b45309', color: '#fef9c3', padding: '5px 12px', borderRadius: 20, fontSize: 13, fontWeight: 800 }}>
                  💯 {stats.centuries} 100s
                </span>
                <span style={{ background: '#047857', color: '#d1fae5', padding: '5px 12px', borderRadius: 20, fontSize: 13, fontWeight: 800 }}>
                  ⭐ {stats.fifties} 50s
                </span>
                <span style={{ background: '#0284c7', color: '#fff', padding: '5px 12px', borderRadius: 20, fontSize: 13, fontWeight: 800 }}>
                  4️⃣ {stats.fours} Fours
                </span>
                <span style={{ background: '#7c3aed', color: '#fff', padding: '5px 12px', borderRadius: 20, fontSize: 13, fontWeight: 800 }}>
                  6️⃣ {stats.sixes} Sixes
                </span>
              </div>
            </div>
          </Card>

          {/* 2. Career Batting & Bowling Statistics Grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16, marginBottom: 24 }}>
            <Card style={{ padding: 18 }}>
              <h3 style={{ margin: '0 0 12px', fontSize: 15, color: colors.text }}>🏏 Career Batting Summary</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, textAlign: 'center' }}>
                <div style={{ background: '#f8fafc', padding: 10, borderRadius: 8 }}>
                  <div style={{ fontSize: 11, color: colors.textMuted }}>Matches</div>
                  <div style={{ fontSize: 20, fontWeight: 800 }}>{stats.matches_played}</div>
                </div>
                <div style={{ background: '#f8fafc', padding: 10, borderRadius: 8 }}>
                  <div style={{ fontSize: 11, color: colors.textMuted }}>Runs</div>
                  <div style={{ fontSize: 20, fontWeight: 800, color: colors.primary }}>{stats.total_runs}</div>
                </div>
                <div style={{ background: '#f8fafc', padding: 10, borderRadius: 8 }}>
                  <div style={{ fontSize: 11, color: colors.textMuted }}>High Score</div>
                  <div style={{ fontSize: 20, fontWeight: 800 }}>
                    {stats.highest_score}{stats.highest_score_not_out ? '*' : ''}
                  </div>
                </div>
                <div style={{ background: '#f8fafc', padding: 10, borderRadius: 8 }}>
                  <div style={{ fontSize: 11, color: colors.textMuted }}>Strike Rate</div>
                  <div style={{ fontSize: 20, fontWeight: 800 }}>{stats.batting_strike_rate.toFixed(1)}</div>
                </div>
                <div style={{ background: '#f8fafc', padding: 10, borderRadius: 8 }}>
                  <div style={{ fontSize: 11, color: colors.textMuted }}>Average</div>
                  <div style={{ fontSize: 17, fontWeight: 700 }}>{stats.batting_average.toFixed(1)}</div>
                </div>
                <div style={{ background: '#f8fafc', padding: 10, borderRadius: 8 }}>
                  <div style={{ fontSize: 11, color: colors.textMuted }}>Balls</div>
                  <div style={{ fontSize: 17, fontWeight: 700 }}>{stats.balls_faced}</div>
                </div>
                <div style={{ background: '#f8fafc', padding: 10, borderRadius: 8 }}>
                  <div style={{ fontSize: 11, color: colors.textMuted }}>50s / 100s</div>
                  <div style={{ fontSize: 17, fontWeight: 700 }}>{stats.fifties} / {stats.centuries}</div>
                </div>
                <div style={{ background: '#f8fafc', padding: 10, borderRadius: 8 }}>
                  <div style={{ fontSize: 11, color: colors.textMuted }}>4s / 6s</div>
                  <div style={{ fontSize: 17, fontWeight: 700 }}>{stats.fours} / {stats.sixes}</div>
                </div>
              </div>
            </Card>

            <Card style={{ padding: 18 }}>
              <h3 style={{ margin: '0 0 12px', fontSize: 15, color: colors.text }}>⚾ Career Bowling Summary</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12, textAlign: 'center' }}>
                <div style={{ background: '#f8fafc', padding: 10, borderRadius: 8 }}>
                  <div style={{ fontSize: 11, color: colors.textMuted }}>Innings Bowled</div>
                  <div style={{ fontSize: 20, fontWeight: 800 }}>{stats.innings_bowled}</div>
                </div>
                <div style={{ background: '#f8fafc', padding: 10, borderRadius: 8 }}>
                  <div style={{ fontSize: 11, color: colors.textMuted }}>Wickets</div>
                  <div style={{ fontSize: 20, fontWeight: 800, color: '#dc2626' }}>{stats.wickets_taken}</div>
                </div>
                <div style={{ background: '#f8fafc', padding: 10, borderRadius: 8 }}>
                  <div style={{ fontSize: 11, color: colors.textMuted }}>Best Bowling</div>
                  <div style={{ fontSize: 20, fontWeight: 800 }}>{stats.best_bowling}</div>
                </div>
                <div style={{ background: '#f8fafc', padding: 10, borderRadius: 8 }}>
                  <div style={{ fontSize: 11, color: colors.textMuted }}>Overs</div>
                  <div style={{ fontSize: 17, fontWeight: 700 }}>{stats.overs_bowled}</div>
                </div>
                <div style={{ background: '#f8fafc', padding: 10, borderRadius: 8 }}>
                  <div style={{ fontSize: 11, color: colors.textMuted }}>Economy</div>
                  <div style={{ fontSize: 17, fontWeight: 700 }}>{stats.bowling_economy.toFixed(2)}</div>
                </div>
                <div style={{ background: '#f8fafc', padding: 10, borderRadius: 8 }}>
                  <div style={{ fontSize: 11, color: colors.textMuted }}>Runs Conceded</div>
                  <div style={{ fontSize: 17, fontWeight: 700 }}>{stats.runs_conceded}</div>
                </div>
              </div>
            </Card>
          </div>

          {/* 3. Match-by-Match Batting & Bowling Log with Scorecard Links */}
          <Card style={{ marginBottom: 24, padding: 20 }}>
            <h2 style={{ margin: '0 0 6px', fontSize: 18 }}>📋 Match-by-Match Statistics & Scorecard Links</h2>
            <p style={{ margin: '0 0 14px', fontSize: 13, color: colors.textMuted }}>
              Batting and bowling figures for every match, with direct links to the original scorecard and innings
            </p>

            {profile.match_performances.length === 0 ? (
              <div style={{ padding: 24, textAlign: 'center', color: colors.textMuted, fontSize: 14 }}>
                This player has not appeared in a recorded match yet.
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ borderBottom: `2px solid ${colors.border}`, textAlign: 'left', color: colors.textMuted }}>
                      <th style={{ padding: '8px 10px' }}>Match / Series</th>
                      <th style={{ padding: '8px 10px' }}>Teams</th>
                      <th style={{ padding: '8px 10px' }}>Batting</th>
                      <th style={{ padding: '8px 10px' }}>Bowling</th>
                      <th style={{ padding: '8px 10px' }}>Clips</th>
                      <th style={{ padding: '8px 10px', textAlign: 'right' }}>Scorecard</th>
                    </tr>
                  </thead>
                  <tbody>
                    {profile.match_performances.map((mp) => (
                      <tr key={mp.match_id} style={{ borderBottom: `1px solid ${colors.border}` }}>
                        <td style={{ padding: '10px' }}>
                          <div style={{ fontWeight: 700, color: colors.text }}>{mp.match_title}</div>
                          <div style={{ fontSize: 11, color: colors.textMuted }}>
                            {mp.format}
                            {mp.tournament ? ` · 🏆 ${mp.tournament}` : ''}
                            {mp.scheduled_at ? ` · ${new Date(mp.scheduled_at).toLocaleDateString()}` : ''}
                          </div>
                        </td>
                        <td style={{ padding: '10px', fontSize: 12 }}>
                          {mp.player_team_name || 'Team'} vs {mp.opponent_team_name || 'Opponent'}
                        </td>
                        <td style={{ padding: '10px' }}>
                          {mp.batted ? (
                            <div>
                              <span style={{ fontWeight: 800, fontSize: 14 }}>
                                {mp.runs}{!mp.is_out ? '*' : ''} ({mp.balls}b)
                              </span>
                              <span style={{ fontSize: 11, color: colors.textMuted, marginLeft: 6 }}>
                                4s: {mp.fours} · 6s: {mp.sixes} · SR: {mp.strike_rate.toFixed(1)}
                              </span>
                              <div style={{ fontSize: 11, color: mp.is_out ? '#dc2626' : '#16a34a' }}>
                                {mp.dismissal_text}
                              </div>
                            </div>
                          ) : (
                            <span style={{ color: colors.textMuted, fontSize: 12 }}>Did not bat</span>
                          )}
                        </td>
                        <td style={{ padding: '10px' }}>
                          {mp.bowled ? (
                            <div>
                              <span style={{ fontWeight: 800 }}>
                                {mp.wickets}/{mp.runs_conceded}
                              </span>{' '}
                              <span style={{ fontSize: 12, color: colors.textMuted }}>
                                ({mp.overs_display} ov, Econ {mp.economy.toFixed(2)})
                              </span>
                            </div>
                          ) : (
                            <span style={{ color: colors.textMuted, fontSize: 12 }}>Did not bowl</span>
                          )}
                        </td>
                        <td style={{ padding: '10px' }}>
                          {mp.highlights_in_match > 0 ? (
                            <button
                              type="button"
                              onClick={() => setFilterMatchId(mp.match_id)}
                              style={{
                                background: colors.primaryLight,
                                color: colors.primary,
                                border: 'none',
                                padding: '3px 8px',
                                borderRadius: 6,
                                fontSize: 11,
                                fontWeight: 700,
                                cursor: 'pointer',
                              }}
                            >
                              🎬 {mp.highlights_in_match} clips
                            </button>
                          ) : (
                            <span style={{ color: colors.textMuted, fontSize: 12 }}>0</span>
                          )}
                        </td>
                        <td style={{ padding: '10px', textAlign: 'right' }}>
                          <div style={{ display: 'inline-flex', gap: 6 }}>
                            <Link
                              to={`/matches/${mp.match_id}`}
                              style={{
                                fontSize: 12,
                                fontWeight: 700,
                                color: colors.primary,
                                textDecoration: 'none',
                                padding: '4px 8px',
                                borderRadius: 6,
                                border: `1px solid ${colors.border}`,
                              }}
                            >
                              Match →
                            </Link>
                            <Link
                              to={`/matches/${mp.match_id}/score`}
                              style={{
                                fontSize: 12,
                                fontWeight: 700,
                                color: '#0284c7',
                                textDecoration: 'none',
                                padding: '4px 8px',
                                borderRadius: 6,
                                border: `1px solid ${colors.border}`,
                              }}
                            >
                              Scorecard →
                            </Link>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          {/* 4. Replayable Milestones Section */}
          <div style={{ marginBottom: 24 }}>
            <MilestoneTimelineSection
              title="🏆 Fifty & Century Milestone Cards"
              subtitle="Permanent batting milestones — replay the broadcast celebration or open the linked delivery video clip"
              milestones={profile.milestones}
              showMatchLink
            />
          </div>

          {/* 5. Filter Bar for Match-wise, Tournament-wise, and Boundary-type Highlights */}
          <Card style={{ marginBottom: 20, padding: 16 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
              <div>
                <h2 style={{ margin: 0, fontSize: 18 }}>🎬 Boundary Highlights Feed ({profile.highlights_total})</h2>
                <p style={{ margin: '2px 0 0', fontSize: 12, color: colors.textMuted }}>
                  Filter by match, tournament, or boundary type (FOUR / SIX)
                </p>
              </div>

              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                {/* Tournament Filter */}
                <select
                  value={filterTournament}
                  onChange={(e) => setFilterTournament(e.target.value)}
                  style={{ padding: '7px 10px', borderRadius: 6, border: `1px solid ${colors.border}`, fontSize: 13 }}
                >
                  <option value="">All Tournaments / Series</option>
                  {profile.available_tournaments.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>

                {/* Match Filter */}
                <select
                  value={filterMatchId}
                  onChange={(e) => setFilterMatchId(e.target.value)}
                  style={{ padding: '7px 10px', borderRadius: 6, border: `1px solid ${colors.border}`, fontSize: 13 }}
                >
                  <option value="">All Matches ({profile.available_matches.length})</option>
                  {profile.available_matches.map((m) => (
                    <option key={m.match_id} value={m.match_id}>
                      {m.title}{m.tournament ? ` (${m.tournament})` : ''}
                    </option>
                  ))}
                </select>

                {/* Event Type Filter */}
                <select
                  value={filterEventType}
                  onChange={(e) => setFilterEventType(e.target.value)}
                  style={{ padding: '7px 10px', borderRadius: 6, border: `1px solid ${colors.border}`, fontSize: 13 }}
                >
                  <option value="">All Highlights (4s, 6s & Wickets)</option>
                  <option value="four">4️⃣ Fours Only</option>
                  <option value="six">6️⃣ Sixes Only</option>
                  <option value="wicket">🎯 Wickets & Bowling Highlights</option>
                  <option value="dot">🛡️ Dot Balls & Deliveries</option>
                </select>

                {(filterMatchId || filterTournament || filterEventType) && (
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => {
                      setFilterMatchId('')
                      setFilterTournament('')
                      setFilterEventType('')
                    }}
                  >
                    Clear Filters
                  </Button>
                )}
              </div>
            </div>
          </Card>

          {/* Selected Video Player Modal / Inline Card */}
          {selectedHighlight && (
            <Card style={{ marginBottom: 24, padding: 20, background: '#0f172a', color: '#fff' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span
                    style={{
                      background:
                        selectedHighlight.event_type === 'wicket'
                          ? '#dc2626'
                          : selectedHighlight.event_type === 'four'
                          ? '#0284c7'
                          : selectedHighlight.event_type === 'six'
                          ? '#d97706'
                          : '#475569',
                      color: '#fff',
                      padding: '3px 10px',
                      borderRadius: 6,
                      fontWeight: 800,
                      fontSize: 12,
                      textTransform: 'uppercase',
                    }}
                  >
                    {selectedHighlight.event_type === 'wicket' ? 'WICKET 🎯' : selectedHighlight.event_type}
                  </span>
                  <span style={{ fontWeight: 700, fontSize: 16 }}>
                    Over {selectedHighlight.delivery_metadata?.over_display ?? '—'} vs {selectedHighlight.delivery_metadata?.bowler_name ?? 'Bowler'}
                  </span>
                </div>
                <button
                  onClick={() => setSelectedHighlight(null)}
                  style={{ background: 'transparent', border: 'none', color: '#94a3b8', fontSize: 18, cursor: 'pointer' }}
                >
                  ✕ Close
                </button>
              </div>

              <div style={{ display: 'flex', justifyContent: 'center', background: '#000', borderRadius: 8, overflow: 'hidden', minHeight: 320 }}>
                {selectedHighlight.video_url ? (
                  <video
                    controls
                    autoPlay
                    src={selectedHighlight.video_url}
                    poster={selectedHighlight.thumbnail_url ?? undefined}
                    style={{ width: '100%', maxHeight: 480, objectFit: 'contain' }}
                  />
                ) : (
                  <div style={{ padding: 60, textAlign: 'center', color: '#94a3b8' }}>
                    Video is currently processing in background...
                  </div>
                )}
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginTop: 12, fontSize: 13, color: '#94a3b8' }}>
                <div>
                  Duration: {selectedHighlight.duration_sec ? `${selectedHighlight.duration_sec}s` : '—'} · Version: v{selectedHighlight.version}
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <Link
                    to={`/matches/${selectedHighlight.match_id}/score`}
                    style={{
                      background: 'rgba(255,255,255,0.12)',
                      color: '#fff',
                      padding: '5px 10px',
                      borderRadius: 6,
                      textDecoration: 'none',
                      fontSize: 12,
                      fontWeight: 700,
                    }}
                  >
                    📋 Open Original Scorecard
                  </Link>
                  <Button
                    variant="secondary"
                    onClick={() => setReprocessingId(selectedHighlight.id)}
                    style={{ fontSize: 12, padding: '4px 10px' }}
                  >
                    ⚙ Adjust Trim & Reprocess
                  </Button>
                </div>
              </div>
            </Card>
          )}

          {/* Reprocess Trim Adjustment Dialog */}
          {reprocessingId && (
            <Card style={{ marginBottom: 20, padding: 16, border: `1px solid ${colors.primary}` }}>
              <h3 style={{ margin: '0 0 10px' }}>Adjust Clip Trim Window</h3>
              <p style={{ fontSize: 13, color: colors.textMuted, margin: '0 0 12px' }}>
                Fine-tune the time window extracted around the delivery marker.
              </p>
              <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'center', marginBottom: 12 }}>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, display: 'block', marginBottom: 4 }}>Seconds Before Marker:</label>
                  <input
                    type="number"
                    step="0.5"
                    min="0.5"
                    max="15.0"
                    value={trimBefore}
                    onChange={(e) => setTrimBefore(parseFloat(e.target.value) || 4.0)}
                    style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid #cbd5e1', width: 100 }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, display: 'block', marginBottom: 4 }}>Seconds After Marker:</label>
                  <input
                    type="number"
                    step="0.5"
                    min="0.5"
                    max="20.0"
                    value={trimAfter}
                    onChange={(e) => setTrimAfter(parseFloat(e.target.value) || 5.0)}
                    style={{ padding: '6px 10px', borderRadius: 6, border: '1px solid #cbd5e1', width: 100 }}
                  />
                </div>
                <div style={{ paddingTop: 18, display: 'flex', gap: 8 }}>
                  <Button
                    onClick={() => {
                      const hl = highlightsList.find((h) => h.id === reprocessingId)
                      if (hl) void handleReprocess(hl)
                    }}
                  >
                    Start Reprocessing
                  </Button>
                  <Button variant="secondary" onClick={() => setReprocessingId(null)}>
                    Cancel
                  </Button>
                </div>
              </div>
              {reprocessMsg && <div style={{ fontSize: 13, color: colors.primary, fontWeight: 600 }}>{reprocessMsg}</div>}
            </Card>
          )}

          {/* Highlight Cards Grid */}
          {highlightsList.length === 0 ? (
            <Card style={{ textAlign: 'center', padding: 48 }}>
              <div style={{ fontSize: 40, marginBottom: 12 }}>🎬</div>
              <h3 style={{ margin: '0 0 8px' }}>No Boundary Highlight Video Clips Found</h3>
              <p style={{ color: colors.textMuted, maxWidth: 460, margin: '0 auto' }}>
                {filterMatchId || filterTournament || filterEventType
                  ? 'No clips match your active filters. Try clearing the filters above.'
                  : 'When this player hits a batter-credited four or six and the delivery has a video marker, the background pipeline automatically extracts and assigns the clip here!'}
              </p>
            </Card>
          ) : (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16 }}>
                {highlightsList.map((hl) => {
                  const meta = hl.delivery_metadata as Record<string, unknown> | undefined
                  const matchTitle = (meta?.match_title as string) || 'Match'
                  return (
                    <Card
                      key={hl.id}
                      padding={0}
                      style={{
                        overflow: 'hidden',
                        cursor: 'pointer',
                        transition: 'transform 0.15s ease, box-shadow 0.15s ease',
                      }}
                      onClick={() => setSelectedHighlight(hl)}
                    >
                      <div style={{ position: 'relative', width: '100%', height: 160, background: '#1e293b' }}>
                        {hl.thumbnail_url ? (
                          <img
                            src={hl.thumbnail_url}
                            alt={hl.event_type}
                            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                          />
                        ) : (
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#94a3b8' }}>
                            📹 Preview Ready
                          </div>
                        )}
                        <div
                          style={{
                            position: 'absolute',
                            inset: 0,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            background: 'rgba(0,0,0,0.25)',
                          }}
                        >
                          <div
                            style={{
                              width: 44,
                              height: 44,
                              borderRadius: '50%',
                              background: 'rgba(255,255,255,0.85)',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              fontSize: 20,
                              paddingLeft: 3,
                            }}
                          >
                            ▶
                          </div>
                        </div>
                        <div
                          style={{
                            position: 'absolute',
                            top: 8,
                            left: 8,
                            background:
                              hl.event_type === 'wicket'
                                ? '#dc2626'
                                : hl.event_type === 'four'
                                ? '#0284c7'
                                : hl.event_type === 'six'
                                ? '#d97706'
                                : '#475569',
                            color: '#fff',
                            padding: '2px 8px',
                            borderRadius: 4,
                            fontWeight: 800,
                            fontSize: 11,
                            textTransform: 'uppercase',
                          }}
                        >
                          {hl.event_type === 'wicket'
                            ? 'WICKET 🎯'
                            : hl.event_type === 'four'
                            ? 'FOUR · +4'
                            : hl.event_type === 'six'
                            ? 'SIX · +6'
                            : 'DELIVERY'}
                        </div>
                        {hl.duration_sec != null && (
                          <div
                            style={{
                              position: 'absolute',
                              bottom: 8,
                              right: 8,
                              background: 'rgba(0,0,0,0.7)',
                              color: '#fff',
                              padding: '2px 6px',
                              borderRadius: 4,
                              fontSize: 11,
                              fontWeight: 600,
                            }}
                          >
                            {hl.duration_sec}s
                          </div>
                        )}
                      </div>

                      <div style={{ padding: 12 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                          <div>
                            <div style={{ fontWeight: 700, fontSize: 14 }}>
                              {hl.delivery_metadata?.shot_name
                                ? hl.delivery_metadata.shot_name
                                : `Over ${hl.delivery_metadata?.over_display ?? '—'}`}
                            </div>
                            <div style={{ fontSize: 12, color: colors.textMuted, marginTop: 2 }}>
                              Over {hl.delivery_metadata?.over_display ?? '—'} · vs {hl.delivery_metadata?.bowler_name ?? 'Bowler'}
                              {hl.delivery_metadata?.speed_kmh ? ` (${hl.delivery_metadata.speed_kmh} km/h)` : ''}
                            </div>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation()
                                setBoundaryAnim({
                                  id: `hl-player-${hl.id}-${Date.now()}`,
                                  type: hl.event_type === 'four' ? 'FOUR' : 'SIX',
                                  playerName: displayName,
                                  overDisplay: hl.delivery_metadata?.over_display,
                                  bowlerName: hl.delivery_metadata?.bowler_name,
                                  highlightStatus: hl.status === 'ready' ? 'ready' : hl.status,
                                  highlightVideoUrl: hl.video_url,
                                  highlightThumbnailUrl: hl.thumbnail_url,
                                })
                              }}
                              style={{
                                background: '#f1f5f9',
                                border: `1px solid ${colors.border}`,
                                borderRadius: 4,
                                padding: '2px 7px',
                                fontSize: 10,
                                fontWeight: 700,
                                cursor: 'pointer',
                                color: colors.text,
                              }}
                            >
                              ✨ Replay {hl.event_type === 'four' ? '4' : '6'}
                            </button>
                            <span
                              style={{
                                fontSize: 10,
                                fontWeight: 700,
                                padding: '2px 6px',
                                borderRadius: 4,
                                background: hl.status === 'ready' ? '#dcfce7' : '#fef3c7',
                                color: hl.status === 'ready' ? '#166534' : '#92400e',
                              }}
                            >
                              {hl.status.toUpperCase()}
                            </span>
                          </div>
                        </div>

                        {/* Link back to original match scorecard */}
                        <div
                          style={{
                            marginTop: 8,
                            paddingTop: 8,
                            borderTop: `1px solid ${colors.border}`,
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            fontSize: 11,
                          }}
                        >
                          <Link
                            to={`/matches/${hl.match_id}`}
                            onClick={(e) => e.stopPropagation()}
                            style={{ color: colors.primary, fontWeight: 700, textDecoration: 'none' }}
                          >
                            📋 {matchTitle} →
                          </Link>
                          <Link
                            to={`/matches/${hl.match_id}/score`}
                            onClick={(e) => e.stopPropagation()}
                            style={{ color: colors.textMuted, textDecoration: 'none' }}
                          >
                            Innings Scorecard
                          </Link>
                        </div>
                      </div>
                    </Card>
                  )
                })}
              </div>

              {/* Incremental Pagination Control */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 20 }}>
                <span style={{ fontSize: 13, color: colors.textMuted }}>
                  Showing {highlightsList.length} of {profile.highlights_total} highlights
                </span>
                {profile.has_more_highlights && (
                  <Button onClick={handleLoadMore} loading={loadingMore}>
                    Load More Highlights ({profile.highlights_total - highlightsList.length} remaining)
                  </Button>
                )}
              </div>
            </>
          )}
        </>
      )}
    </AppShell>
  )
}
