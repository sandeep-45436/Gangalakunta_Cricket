/**
 * Match detail / archive dashboard page (Phase 6).
 * Shows match info, live/completed scoreline summary, full Innings Scorecards &
 * Fall of Wickets Archive, Playing XI selectors, Match Milestones timeline,
 * and Match Highlights Reel with job retry recovery.
 */
import { useEffect, useState, useCallback } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import {
  apiClient,
  type Match,
  type PlayingXIEntry,
  type PlayerHighlight,
  type MatchScorecard,
  type PlayerMilestone,
} from '../../services/apiClient'
import { AppShell } from '../../components/layout/AppShell'
import { Card } from '../../components/ui/Card'
import { Button } from '../../components/ui/Button'
import { Alert } from '../../components/ui/Alert'
import { Spinner } from '../../components/ui/Spinner'
import { PlayingXISelector } from './PlayingXISelector'
import { MilestoneTimelineSection } from '../../components/animations/MilestoneTimelineSection'
import {
  BroadcastAnimationOverlay,
  type BroadcastAnimationPayload,
} from '../../components/animations/BroadcastAnimationOverlay'
import { colors } from '../../theme'

export function MatchDetailPage() {
  const { matchId } = useParams<{ matchId: string }>()
  const navigate = useNavigate()
  const { token } = useAuth()
  const [match, setMatch] = useState<Match | null>(null)
  const [matchScorecard, setMatchScorecard] = useState<MatchScorecard | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [savedXI, setSavedXI] = useState<Record<string, PlayingXIEntry[]>>({})
  const [activeTeamTab, setActiveTeamTab] = useState(0)
  const [activeInningsTab, setActiveInningsTab] = useState(0)
  const [highlights, setHighlights] = useState<PlayerHighlight[]>([])
  const [milestones, setMilestones] = useState<PlayerMilestone[]>([])
  const [playingHighlight, setPlayingHighlight] = useState<PlayerHighlight | null>(null)
  const [boundaryAnim, setBoundaryAnim] = useState<BroadcastAnimationPayload | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [retryingJobs, setRetryingJobs] = useState(false)
  const [opsMessage, setOpsMessage] = useState('')

  const fetchHighlights = useCallback(() => {
    if (!token || !matchId) return
    apiClient.getMatchHighlights(token, matchId)
      .then((hl) => setHighlights(hl))
      .catch(() => {/* ignore */})
    apiClient.getMatchMilestones(token, matchId)
      .then((ms) => setMilestones(ms))
      .catch(() => {/* ignore */})
  }, [token, matchId])

  useEffect(() => {
    if (!token || !matchId) return
    apiClient.getMatch(token, matchId)
      .then((m) => {
        setMatch(m)
        m.teams.forEach((t) => {
          apiClient.getPlayingXI(token, matchId, t.team_id)
            .then((xi) => setSavedXI((prev) => ({ ...prev, [t.team_id]: xi })))
            .catch(() => {/* no XI yet */})
        })
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false))

    apiClient.getMatchScorecard(token, matchId)
      .then(setMatchScorecard)
      .catch(() => {/* no innings yet */})

    fetchHighlights()
  }, [token, matchId, fetchHighlights])

  // Poll highlights if any are pending/processing
  useEffect(() => {
    const hasPending = highlights.some((h) => h.status === 'pending' || h.status === 'processing')
    if (!hasPending) return
    const timer = window.setInterval(fetchHighlights, 2500)
    return () => clearInterval(timer)
  }, [highlights, fetchHighlights])

  const handleRetryFailedJobs = async () => {
    if (!token || !matchId) return
    setRetryingJobs(true)
    setOpsMessage('')
    try {
      const res = await apiClient.retryFailedJobs(token, matchId)
      setOpsMessage(
        `Recovery complete: ${res.retried_highlight_jobs} highlight job(s) & ${res.recovered_recording_sessions} recording session(s) processed.`
      )
      fetchHighlights()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setRetryingJobs(false)
    }
  }

  const handleDeleteMatch = async () => {
    if (!token || !matchId || !match) return
    if (!window.confirm(`Delete match "${match.title}" and all its scorecards/recordings?`)) return
    setDeleting(true)
    try {
      await apiClient.deleteMatch(token, matchId)
      navigate('/matches')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setDeleting(false)
    }
  }

  if (loading) return <AppShell><div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}><Spinner /></div></AppShell>
  if (error) return <AppShell><Alert type="error">{error}</Alert></AppShell>
  if (!match) return null

  const sortedTeams = [...match.teams].sort((a, b) => a.batting_order - b.batting_order)
  const [teamA, teamB] = sortedTeams

  const innA = matchScorecard?.innings.find((i) => i.batting_team_id === teamA?.team_id)
  const innB = matchScorecard?.innings.find((i) => i.batting_team_id === teamB?.team_id)

  const currentInningsScorecard = matchScorecard?.innings[activeInningsTab] ?? null

  return (
    <AppShell>
      {/* Header */}
      <div style={{ marginBottom: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <Link to="/matches" style={{ color: colors.textMuted, textDecoration: 'none', fontSize: 14 }}>← Match Archive</Link>
          <h1 style={{ margin: '6px 0 4px', color: colors.text }}>{match.title}</h1>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <span style={{ fontSize: 13, color: colors.textMuted, fontWeight: 600 }}>{match.format}</span>
            {match.overs_per_innings && <span style={{ fontSize: 13, color: colors.textMuted }}>· {match.overs_per_innings} overs</span>}
            {match.tournament && (
              <span style={{
                fontSize: 11,
                fontWeight: 700,
                background: '#fef3c7',
                color: '#92400e',
                padding: '2px 8px',
                borderRadius: 6,
              }}>
                🏆 {match.tournament}
              </span>
            )}
            {match.venue && <span style={{ fontSize: 13, color: colors.textMuted }}>· 📍 {match.venue}</span>}
            {match.scheduled_at && (
              <span style={{ fontSize: 13, color: colors.textMuted }}>
                · {new Date(match.scheduled_at).toLocaleString()}
              </span>
            )}
            <span style={{
              fontSize: 11, fontWeight: 700, borderRadius: 10, padding: '2px 8px',
              background: match.status === 'live' ? colors.danger : match.status === 'completed' ? colors.primary : '#3b82f6',
              color: '#fff',
            }}>
              {match.status.toUpperCase()}
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <Link
            to={`/matches/${matchId}/score`}
            style={{
              background: colors.primary,
              color: '#fff',
              padding: '10px 18px',
              borderRadius: 8,
              textDecoration: 'none',
              fontWeight: 700,
              fontSize: 14,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
            }}
          >
            ⚾ Live Scoring →
          </Link>

          <Link
            to={`/matches/${matchId}/record`}
            style={{
              background: '#dc2626',
              color: '#fff',
              padding: '10px 18px',
              borderRadius: 8,
              textDecoration: 'none',
              fontWeight: 700,
              fontSize: 14,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
            }}
          >
            📹 Video & Markers →
          </Link>

          <Button variant="danger" size="sm" loading={deleting} onClick={() => { void handleDeleteMatch() }}>
            Delete Match
          </Button>
        </div>
      </div>

      {opsMessage && (
        <div style={{ marginBottom: 16 }}>
          <Alert type="success">{opsMessage}</Alert>
        </div>
      )}

      {/* Scoreline */}
      <Card style={{ marginBottom: 20, textAlign: 'center', background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)', color: '#fff' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', alignItems: 'center', gap: 12 }}>
          <div>
            <div style={{ fontWeight: 700, fontSize: 17 }}>{teamA?.team_name}</div>
            {innA ? (
              <div style={{ fontSize: 24, fontWeight: 800, color: '#38bdf8', marginTop: 4 }}>
                {innA.total_runs}/{innA.total_wickets}{' '}
                <span style={{ fontSize: 13, fontWeight: 500, color: '#94a3b8' }}>({innA.overs_display} ov)</span>
              </div>
            ) : (
              <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 4 }}>Bats 1st</div>
            )}
          </div>
          <div style={{ fontSize: 16, color: '#94a3b8', fontWeight: 700 }}>VS</div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 17 }}>{teamB?.team_name}</div>
            {innB ? (
              <div style={{ fontSize: 24, fontWeight: 800, color: '#38bdf8', marginTop: 4 }}>
                {innB.total_runs}/{innB.total_wickets}{' '}
                <span style={{ fontSize: 13, fontWeight: 500, color: '#94a3b8' }}>({innB.overs_display} ov)</span>
              </div>
            ) : (
              <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 4 }}>Bats 2nd</div>
            )}
          </div>
        </div>
        {matchScorecard?.result_text && (
          <div style={{ marginTop: 12, paddingTop: 10, borderTop: '1px solid rgba(255,255,255,0.1)', fontSize: 13, color: '#10b981', fontWeight: 700 }}>
            {matchScorecard.result_text}
          </div>
        )}
      </Card>

      {/* Phase 6: Full Historical Innings Scorecards Archive */}
      {matchScorecard && matchScorecard.innings.length > 0 && (
        <Card style={{ marginBottom: 24, padding: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginBottom: 14 }}>
            <div>
              <h2 style={{ margin: 0, fontSize: 18 }}>📊 Official Match Scorecard Archive</h2>
              <p style={{ margin: '2px 0 0', fontSize: 12, color: colors.textMuted }}>
                Historical player and team names are preserved from match snapshots even if squads change later.
              </p>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              {matchScorecard.innings.map((inn, idx) => (
                <button
                  key={inn.innings_id}
                  type="button"
                  onClick={() => setActiveInningsTab(idx)}
                  style={{
                    padding: '6px 14px',
                    borderRadius: 6,
                    border: `1px solid ${activeInningsTab === idx ? colors.primary : colors.border}`,
                    background: activeInningsTab === idx ? colors.primary : '#fff',
                    color: activeInningsTab === idx ? '#fff' : colors.text,
                    fontSize: 13,
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Innings {inn.innings_number}: {inn.batting_team_name} ({inn.total_runs}/{inn.total_wickets})
                </button>
              ))}
            </div>
          </div>

          {currentInningsScorecard && (
            <div style={{ display: 'grid', gap: 18 }}>
              {/* Batting Table */}
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                  <thead>
                    <tr style={{ borderBottom: `2px solid ${colors.border}`, textAlign: 'left', color: colors.textMuted }}>
                      <th style={{ padding: '8px 6px' }}>Batter</th>
                      <th style={{ padding: '8px 6px' }}>Dismissal</th>
                      <th style={{ padding: '8px 6px' }}>R</th>
                      <th style={{ padding: '8px 6px' }}>B</th>
                      <th style={{ padding: '8px 6px' }}>4s</th>
                      <th style={{ padding: '8px 6px' }}>6s</th>
                      <th style={{ padding: '8px 6px' }}>SR</th>
                    </tr>
                  </thead>
                  <tbody>
                    {currentInningsScorecard.batters.map((b) => (
                      <tr key={b.player_id} style={{ borderBottom: `1px solid ${colors.border}` }}>
                        <td style={{ padding: '8px 6px', fontWeight: 700 }}>
                          <Link
                            to={`/players/${b.player_id}/highlights`}
                            style={{ color: colors.primary, textDecoration: 'none' }}
                          >
                            {b.player_name}
                          </Link>
                        </td>
                        <td style={{ padding: '8px 6px', fontSize: 12, color: b.is_out ? colors.danger : '#166534' }}>
                          {b.dismissal_text || (b.is_out ? (b.wicket_type || 'out') : 'not out')}
                        </td>
                        <td style={{ padding: '8px 6px', fontWeight: 800 }}>{b.runs}</td>
                        <td style={{ padding: '8px 6px' }}>{b.balls}</td>
                        <td style={{ padding: '8px 6px', color: '#059669', fontWeight: 600 }}>{b.fours}</td>
                        <td style={{ padding: '8px 6px', color: '#7c3aed', fontWeight: 600 }}>{b.sixes}</td>
                        <td style={{ padding: '8px 6px' }}>{b.strike_rate.toFixed(1)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Bowling Table */}
              {currentInningsScorecard.bowlers.length > 0 && (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                    <thead>
                      <tr style={{ borderBottom: `2px solid ${colors.border}`, textAlign: 'left', color: colors.textMuted }}>
                        <th style={{ padding: '8px 6px' }}>Bowler</th>
                        <th style={{ padding: '8px 6px' }}>O</th>
                        <th style={{ padding: '8px 6px' }}>M</th>
                        <th style={{ padding: '8px 6px' }}>R</th>
                        <th style={{ padding: '8px 6px' }}>W</th>
                        <th style={{ padding: '8px 6px' }}>Econ</th>
                      </tr>
                    </thead>
                    <tbody>
                      {currentInningsScorecard.bowlers.map((bw) => (
                        <tr key={bw.player_id} style={{ borderBottom: `1px solid ${colors.border}` }}>
                          <td style={{ padding: '8px 6px', fontWeight: 700 }}>
                            <Link
                              to={`/players/${bw.player_id}/highlights`}
                              style={{ color: colors.primary, textDecoration: 'none' }}
                            >
                              {bw.player_name}
                            </Link>
                          </td>
                          <td style={{ padding: '8px 6px' }}>{bw.overs}</td>
                          <td style={{ padding: '8px 6px' }}>{bw.maidens}</td>
                          <td style={{ padding: '8px 6px' }}>{bw.runs_conceded}</td>
                          <td style={{ padding: '8px 6px', fontWeight: 800, color: '#0284c7' }}>{bw.wickets}</td>
                          <td style={{ padding: '8px 6px' }}>{bw.economy.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {/* Fall of Wickets */}
              {currentInningsScorecard.fall_of_wickets.length > 0 && (
                <div style={{ fontSize: 12, color: colors.textMuted }}>
                  <strong>Fall of Wickets: </strong>
                  {currentInningsScorecard.fall_of_wickets
                    .map((fow) => `${fow.score}-${fow.wicket_number} (${fow.dismissed_player_name}, ${fow.overs} ov)`)
                    .join(' · ')}
                </div>
              )}
            </div>
          )}
        </Card>
      )}

      {/* Playing XI — tabbed by team */}
      <Card>
        <div style={{ display: 'flex', borderBottom: `1px solid ${colors.border}`, marginBottom: 16 }}>
          {sortedTeams.map((team, idx) => (
            <button
              key={team.team_id}
              onClick={() => setActiveTeamTab(idx)}
              style={{
                padding: '8px 16px',
                border: 'none',
                background: 'transparent',
                cursor: 'pointer',
                fontSize: 14,
                fontWeight: activeTeamTab === idx ? 700 : 400,
                color: activeTeamTab === idx ? colors.primary : colors.textMuted,
                borderBottom: activeTeamTab === idx ? `2px solid ${colors.primary}` : '2px solid transparent',
                marginBottom: -1,
              }}
            >
              {team.team_name}
              {savedXI[team.team_id]?.length === 11 && (
                <span style={{ marginLeft: 6, fontSize: 11, color: colors.primary }}>✓ XI set</span>
              )}
            </button>
          ))}
        </div>

        {token && matchId && sortedTeams[activeTeamTab] && (
          <PlayingXISelector
            matchId={matchId}
            teamId={sortedTeams[activeTeamTab].team_id}
            teamName={sortedTeams[activeTeamTab].team_name}
            token={token}
            onSaved={(xi) => {
              const tid = sortedTeams[activeTeamTab].team_id
              setSavedXI((prev) => ({ ...prev, [tid]: xi }))
            }}
          />
        )}
      </Card>

      {/* Phase 5: Match Milestones & Celebrations Timeline */}
      <MilestoneTimelineSection
        title="🏆 Match Milestones & Timeline"
        subtitle="Permanent 50 & 100 batting milestones achieved in this match — replayable with associated highlight clips"
        milestones={milestones}
        showBroadcastTester
      />

      <BroadcastAnimationOverlay
        event={boundaryAnim}
        onDismiss={() => setBoundaryAnim(null)}
      />

      {/* Match Boundary Highlights */}
      <Card style={{ marginTop: 24, padding: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 10 }}>
          <div>
            <h2 style={{ margin: 0, fontSize: 18 }}>🎬 Match Highlights Reel</h2>
            <p style={{ margin: '4px 0 0', color: colors.textMuted, fontSize: 13 }}>
              Automatically extracted batter boundary clips synchronized with scorecard deliveries
            </p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <Button
              size="sm"
              variant="secondary"
              loading={retryingJobs}
              onClick={() => { void handleRetryFailedJobs() }}
            >
              🔧 Retry Failed Jobs
            </Button>
            <Button size="sm" variant="secondary" onClick={fetchHighlights}>
              ↻ Refresh
            </Button>
            <span style={{ fontSize: 13, fontWeight: 700, color: colors.primary }}>
              {highlights.length} {highlights.length === 1 ? 'clip' : 'clips'}
            </span>
          </div>
        </div>

        {playingHighlight && (
          <div style={{ marginBottom: 20, background: '#0f172a', borderRadius: 8, padding: 16, color: '#fff' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <span style={{ fontWeight: 700 }}>
                {playingHighlight.delivery_metadata?.striker_name ?? 'Batter'} · {playingHighlight.event_type.toUpperCase()} · Over {playingHighlight.delivery_metadata?.over_display ?? '—'}
              </span>
              <button
                onClick={() => setPlayingHighlight(null)}
                style={{ background: 'transparent', border: 'none', color: '#94a3b8', cursor: 'pointer' }}
              >
                ✕ Close
              </button>
            </div>
            {playingHighlight.video_url ? (
              <video
                controls
                autoPlay
                src={playingHighlight.video_url}
                poster={playingHighlight.thumbnail_url ?? undefined}
                style={{ width: '100%', maxHeight: 400, background: '#000', borderRadius: 6 }}
              />
            ) : (
              <div style={{ padding: 40, textAlign: 'center', color: '#94a3b8' }}>
                Clip is currently processing ({playingHighlight.status})...
              </div>
            )}
          </div>
        )}

        {highlights.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 32, color: colors.textMuted, fontSize: 14 }}>
            No highlights extracted yet for this match. Open <strong>📹 Video & Markers</strong> to record or upload a match video, mark moments, and score batter fours or sixes!
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 14 }}>
            {highlights.map((hl) => (
              <div
                key={hl.id}
                onClick={() => setPlayingHighlight(hl)}
                style={{
                  border: `1px solid ${colors.border}`,
                  borderRadius: 8,
                  overflow: 'hidden',
                  cursor: 'pointer',
                  background: '#fff',
                }}
              >
                <div style={{ position: 'relative', height: 130, background: '#1e293b' }}>
                  {hl.thumbnail_url ? (
                    <img src={hl.thumbnail_url} alt={hl.event_type} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                  ) : (
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#94a3b8', fontSize: 13 }}>
                      {hl.status === 'ready' ? '▶ Play Video' : `⏳ ${hl.status.toUpperCase()}...`}
                    </div>
                  )}
                  <span style={{
                    position: 'absolute', top: 6, left: 6,
                    background: hl.event_type === 'four' ? '#10b981' : '#8b5cf6',
                    color: '#fff', fontSize: 10, fontWeight: 800, padding: '2px 6px', borderRadius: 4,
                  }}>
                    {hl.event_type.toUpperCase()}
                  </span>
                  {hl.duration_sec != null && (
                    <span style={{
                      position: 'absolute', bottom: 6, right: 6,
                      background: 'rgba(0,0,0,0.7)', color: '#fff', fontSize: 10, padding: '1px 5px', borderRadius: 4,
                    }}>
                      {hl.duration_sec}s
                    </span>
                  )}
                </div>
                <div style={{ padding: 10 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Link
                      to={`/players/${hl.player_id}/highlights`}
                      onClick={(e) => e.stopPropagation()}
                      style={{ fontWeight: 700, fontSize: 13, color: colors.text, textDecoration: 'none' }}
                    >
                      {hl.delivery_metadata?.striker_name ?? 'Batter'}
                    </Link>
                    <span style={{ fontSize: 10, fontWeight: 700, color: hl.status === 'ready' ? '#166534' : '#92400e' }}>
                      {hl.status.toUpperCase()}
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 4 }}>
                    <span style={{ fontSize: 11, color: colors.textMuted }}>
                      Over {hl.delivery_metadata?.over_display ?? '—'} vs {hl.delivery_metadata?.bowler_name ?? 'Bowler'}
                    </span>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation()
                        setBoundaryAnim({
                          id: `hl-anim-${hl.id}-${Date.now()}`,
                          type: hl.event_type === 'four' ? 'FOUR' : 'SIX',
                          playerName: hl.delivery_metadata?.striker_name || 'Batter',
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
                        padding: '2px 6px',
                        fontSize: 10,
                        fontWeight: 700,
                        cursor: 'pointer',
                        color: colors.text,
                      }}
                    >
                      ✨ Replay {hl.event_type === 'four' ? '4' : '6'}
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </AppShell>
  )
}
