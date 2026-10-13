import { useEffect, useState, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import {
  apiClient,
  type Match,
  type Innings,
  type InningsScorecard,
  type Delivery,
  type PlayingXIEntry,
  type DeliveryCreate,
  type Player,
  type PlayerMilestone,
} from '../../services/apiClient'
import { AppShell } from '../../components/layout/AppShell'
import { Card } from '../../components/ui/Card'
import { Alert } from '../../components/ui/Alert'
import { Spinner } from '../../components/ui/Spinner'
import { Button } from '../../components/ui/Button'
import {
  BroadcastAnimationOverlay,
  type BroadcastAnimationPayload,
} from '../../components/animations/BroadcastAnimationOverlay'
import { MilestoneTimelineSection } from '../../components/animations/MilestoneTimelineSection'
import { colors } from '../../theme'

interface RosterPlayer {
  player_id: string
  player_name: string
}

export function ScoringPage() {
  const { matchId } = useParams<{ matchId: string }>()
  const { token } = useAuth()

  const [match, setMatch] = useState<Match | null>(null)
  const [inningsList, setInningsList] = useState<Innings[]>([])
  const [activeInnings, setActiveInnings] = useState<Innings | null>(null)
  const [scorecard, setScorecard] = useState<InningsScorecard | null>(null)
  const [deliveries, setDeliveries] = useState<Delivery[]>([])
  const [milestones, setMilestones] = useState<PlayerMilestone[]>([])
  const [broadcastEvent, setBroadcastEvent] = useState<BroadcastAnimationPayload | null>(null)
  const [teamRosters, setTeamRosters] = useState<Record<string, RosterPlayer[]>>({})

  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [activeTab, setActiveTab] = useState<'scorer' | 'scorecard'>('scorer')

  // Detailed delivery form state
  const [batterRuns, setBatterRuns] = useState<number>(0)
  const [extraType, setExtraType] = useState<'' | 'wide' | 'no_ball' | 'bye' | 'leg_bye' | 'penalty'>('')
  const [extraRuns, setExtraRuns] = useState<number>(0)
  const [isBoundary, setIsBoundary] = useState(false)
  const [boundaryType, setBoundaryType] = useState<4 | 6>(4)
  const [isBatterBoundary, setIsBatterBoundary] = useState(true)

  // Wicket form state
  const [isWicket, setIsWicket] = useState(false)
  const [wicketType, setWicketType] = useState<string>('bowled')
  const [dismissedEnd, setDismissedEnd] = useState<'striker' | 'non_striker'>('striker')
  const [fielderId, setFielderId] = useState<string>('')
  const [runsCompletedBeforeOut, setRunsCompletedBeforeOut] = useState<number>(0)
  const [nextBatterId, setNextBatterId] = useState<string>('')

  // Bowler change modal
  const [showBowlerModal, setShowBowlerModal] = useState(false)
  const [selectedNewBowler, setSelectedNewBowler] = useState('')

  // Batter change modal
  const [changingBatterRole, setChangingBatterRole] = useState<'striker' | 'non_striker' | null>(null)
  const [selectedReplacementBatter, setSelectedReplacementBatter] = useState('')

  // Start innings modal
  const [showStartInningsModal, setShowStartInningsModal] = useState(false)
  const [startInnNum, setStartInnNum] = useState(1)
  const [openStriker, setOpenStriker] = useState('')
  const [openNonStriker, setOpenNonStriker] = useState('')
  const [openBowler, setOpenBowler] = useState('')

  const loadData = useCallback(async () => {
    if (!token || !matchId) return
    try {
      setError('')
      const [m, allPlayers] = await Promise.all([
        apiClient.getMatch(token, matchId),
        apiClient.listPlayers(token).catch(() => [] as Player[]),
      ])
      setMatch(m)

      // Build roster for each team: prefer Playing XI -> Squad -> All Players
      const rosterMap: Record<string, RosterPlayer[]> = {}
      for (const t of m.teams) {
        let entries: RosterPlayer[] = []
        try {
          const xi: PlayingXIEntry[] = await apiClient.getPlayingXI(token, matchId, t.team_id)
          if (xi.length > 0) {
            entries = xi.map((e) => ({ player_id: e.player_id, player_name: e.player_name }))
          }
        } catch {
          // ignore
        }
        if (entries.length === 0) {
          try {
            const sq = await apiClient.listSquad(token, t.team_id)
            entries = sq
              .map((r) => (r as Record<string, unknown>).players as Player)
              .filter(Boolean)
              .map((p) => ({ player_id: p.id, player_name: p.display_name || p.full_name }))
          } catch {
            // ignore
          }
        }
        if (entries.length === 0 && allPlayers.length > 0) {
          entries = allPlayers.map((p) => ({ player_id: p.id, player_name: p.display_name || p.full_name }))
        }
        rosterMap[t.team_id] = entries
      }
      setTeamRosters(rosterMap)

      // Fetch innings
      const inns = await apiClient.listMatchInnings(token, matchId)
      setInningsList(inns)

      if (inns.length > 0) {
        const cur = inns.find((i) => i.status === 'in_progress') || inns[inns.length - 1]
        setActiveInnings(cur)
        if (cur) {
          const [sc, delivs, ms] = await Promise.all([
            apiClient.getInningsScorecard(token, cur.id),
            apiClient.listDeliveries(token, cur.id),
            apiClient.getInningsMilestones(token, cur.id).catch(() => [] as PlayerMilestone[]),
          ])
          setScorecard(sc)
          setDeliveries(delivs)
          setMilestones(ms)
          // If over just completed and bowler is unset on an in-progress innings, prompt bowler selection
          if (sc.status === 'in_progress' && !sc.current_bowler && !cur.current_bowler_id) {
            setShowBowlerModal(true)
          }
        }
      } else {
        setShowStartInningsModal(true)
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [token, matchId])

  useEffect(() => {
    void loadData()
  }, [loadData])

  const sortedTeams = match ? [...match.teams].sort((a, b) => a.batting_order - b.batting_order) : []
  const battingRoster = activeInnings ? teamRosters[activeInnings.batting_team_id] || [] : []
  const bowlingRoster = activeInnings ? teamRosters[activeInnings.bowling_team_id] || [] : []

  // Remaining batters who haven't been dismissed and aren't currently at the crease
  const outBatterIds = new Set(scorecard?.fall_of_wickets.map((f) => f.dismissed_player_id) || [])
  const currentBatterIds = new Set([
    scorecard?.current_striker?.player_id || activeInnings?.current_striker_id,
    scorecard?.current_non_striker?.player_id || activeInnings?.current_non_striker_id,
  ])
  const availableBatters = battingRoster.filter(
    (p) => !outBatterIds.has(p.player_id) && !currentBatterIds.has(p.player_id)
  )

  // Auto-select first available batter when wicket is toggled on
  useEffect(() => {
    if (isWicket && !nextBatterId && availableBatters.length > 0) {
      setNextBatterId(availableBatters[0].player_id)
    }
  }, [isWicket, nextBatterId, availableBatters])

  const handleStartInnings = async () => {
    if (!token || !match || !matchId) return
    const team1 = sortedTeams.find((t) => t.batting_order === 1) || sortedTeams[0]
    const team2 = sortedTeams.find((t) => t.batting_order === 2) || sortedTeams[1]
    if (!team1 || !team2) return

    const battingTeamId = startInnNum === 1 ? team1.team_id : team2.team_id
    const bowlingTeamId = startInnNum === 1 ? team2.team_id : team1.team_id

    if (!openStriker || !openNonStriker || !openBowler) {
      setError('Please select opening striker, non-striker, and bowler.')
      return
    }
    if (openStriker === openNonStriker) {
      setError('Opening striker and non-striker must be different players.')
      return
    }

    try {
      setSubmitting(true)
      setError('')
      const inn = await apiClient.startInnings(token, matchId, {
        innings_number: startInnNum,
        batting_team_id: battingTeamId,
        bowling_team_id: bowlingTeamId,
        opening_striker_id: openStriker,
        opening_non_striker_id: openNonStriker,
        opening_bowler_id: openBowler,
      })
      setShowStartInningsModal(false)
      setActiveInnings(inn)
      await loadData()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSubmitting(false)
    }
  }

  const handleSendDelivery = async (override?: Partial<DeliveryCreate>) => {
    if (!token || !activeInnings || !scorecard) return

    const strikerId = scorecard.current_striker?.player_id || activeInnings.current_striker_id
    const nonStrikerId = scorecard.current_non_striker?.player_id || activeInnings.current_non_striker_id
    const bowlerId = scorecard.current_bowler?.player_id || activeInnings.current_bowler_id

    if (!bowlerId) {
      setShowBowlerModal(true)
      setError('Please select the bowler for this over before recording a delivery.')
      return
    }
    if (!strikerId || !nonStrikerId) {
      setError('Striker or non-striker is not set. Please select active batters.')
      return
    }

    const wicketFlag = override?.is_wicket !== undefined ? override.is_wicket : isWicket

    let dismissedPlayerId: string | undefined = undefined
    if (wicketFlag) {
      dismissedPlayerId = dismissedEnd === 'striker' ? strikerId : nonStrikerId
      if (override?.dismissed_player_id) {
        dismissedPlayerId = override.dismissed_player_id
      }
    }

    const chosenNextBatter = nextBatterId || availableBatters[0]?.player_id || null

    const payload: DeliveryCreate = {
      striker_id: strikerId,
      non_striker_id: nonStrikerId,
      bowler_id: bowlerId,
      batter_runs: override?.batter_runs !== undefined ? override.batter_runs : batterRuns,
      extra_type: override?.extra_type !== undefined ? override.extra_type : (extraType || null),
      extra_runs: override?.extra_runs !== undefined ? override.extra_runs : extraRuns,
      is_boundary: override?.is_boundary !== undefined ? override.is_boundary : isBoundary,
      boundary_type: override?.boundary_type !== undefined ? override.boundary_type : (isBoundary ? boundaryType : null),
      is_batter_boundary: override?.is_batter_boundary !== undefined ? override.is_batter_boundary : isBatterBoundary,
      is_wicket: wicketFlag,
      wicket_type: override?.wicket_type !== undefined ? override.wicket_type : (wicketFlag ? wicketType : null),
      dismissed_player_id: dismissedPlayerId,
      fielder_id: fielderId || null,
      runs_completed_before_out: runsCompletedBeforeOut,
      next_striker_id: wicketFlag && chosenNextBatter ? (dismissedEnd === 'striker' ? chosenNextBatter : strikerId) : null,
      next_non_striker_id: wicketFlag && chosenNextBatter ? (dismissedEnd === 'non_striker' ? chosenNextBatter : nonStrikerId) : null,
      idempotency_key: `client-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
    }

    // Capture striker pre-delivery stats to detect threshold crossings (50 / 100 / 150 / 200)
    const prevRuns = scorecard.current_striker?.runs ?? 0
    const prevBalls = scorecard.current_striker?.balls ?? 0
    const prevFours = scorecard.current_striker?.fours ?? 0
    const prevSixes = scorecard.current_striker?.sixes ?? 0
    const strikerName =
      scorecard.current_striker?.player_name ||
      battingRoster.find((p) => p.player_id === strikerId)?.player_name ||
      'Batter'
    const bowlerName =
      scorecard.current_bowler?.player_name ||
      bowlingRoster.find((p) => p.player_id === bowlerId)?.player_name ||
      null

    try {
      setSubmitting(true)
      setError('')
      const recorded = await apiClient.recordDelivery(token, activeInnings.id, payload)
      setBatterRuns(0)
      setExtraType('')
      setExtraRuns(0)
      setIsBoundary(false)
      setIsBatterBoundary(true)
      setIsWicket(false)
      setNextBatterId('')
      setFielderId('')
      setRunsCompletedBeforeOut(0)

      // Determine if a milestone or boundary animation should fire
      const scoredBatterRuns = payload.batter_runs ?? 0
      const newRuns = prevRuns + scoredBatterRuns
      const countsBall = payload.extra_type !== 'wide'
      const newBalls = prevBalls + (countsBall ? 1 : 0)
      const isFour = Boolean(payload.is_batter_boundary && (payload.boundary_type === 4 || scoredBatterRuns === 4))
      const isSix = Boolean(payload.is_batter_boundary && (payload.boundary_type === 6 || scoredBatterRuns === 6))
      const newFours = prevFours + (isFour ? 1 : 0)
      const newSixes = prevSixes + (isSix ? 1 : 0)

      if (prevRuns < 200 && newRuns >= 200) {
        setBroadcastEvent({
          id: `deliv-${recorded.id}-200`,
          type: 'DOUBLE_CENTURY',
          playerName: strikerName,
          batterScore: newRuns,
          ballsFaced: newBalls,
          foursCount: newFours,
          sixesCount: newSixes,
          overDisplay: recorded.display_over,
          inningsNumber: activeInnings.innings_number,
          battingTeamName: scorecard.batting_team_name,
          bowlerName,
        })
      } else if (prevRuns < 150 && newRuns >= 150) {
        setBroadcastEvent({
          id: `deliv-${recorded.id}-150`,
          type: 'ONE_FIFTY',
          playerName: strikerName,
          batterScore: newRuns,
          ballsFaced: newBalls,
          foursCount: newFours,
          sixesCount: newSixes,
          overDisplay: recorded.display_over,
          inningsNumber: activeInnings.innings_number,
          battingTeamName: scorecard.batting_team_name,
          bowlerName,
        })
      } else if (prevRuns < 100 && newRuns >= 100) {
        setBroadcastEvent({
          id: `deliv-${recorded.id}-100`,
          type: 'CENTURY',
          playerName: strikerName,
          batterScore: newRuns,
          ballsFaced: newBalls,
          foursCount: newFours,
          sixesCount: newSixes,
          overDisplay: recorded.display_over,
          inningsNumber: activeInnings.innings_number,
          battingTeamName: scorecard.batting_team_name,
          bowlerName,
        })
      } else if (prevRuns < 50 && newRuns >= 50) {
        setBroadcastEvent({
          id: `deliv-${recorded.id}-50`,
          type: 'FIFTY',
          playerName: strikerName,
          batterScore: newRuns,
          ballsFaced: newBalls,
          foursCount: newFours,
          sixesCount: newSixes,
          overDisplay: recorded.display_over,
          inningsNumber: activeInnings.innings_number,
          battingTeamName: scorecard.batting_team_name,
          bowlerName,
        })
      } else if (isSix) {
        setBroadcastEvent({
          id: `deliv-${recorded.id}-6`,
          type: 'SIX',
          playerName: strikerName,
          batterScore: newRuns,
          ballsFaced: newBalls,
          overDisplay: recorded.display_over,
          inningsNumber: activeInnings.innings_number,
          bowlerName,
        })
      } else if (isFour) {
        setBroadcastEvent({
          id: `deliv-${recorded.id}-4`,
          type: 'FOUR',
          playerName: strikerName,
          batterScore: newRuns,
          ballsFaced: newBalls,
          overDisplay: recorded.display_over,
          inningsNumber: activeInnings.innings_number,
          bowlerName,
        })
      }

      await loadData()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSubmitting(false)
    }
  }

  const handleQuickBall = (runs: number) => {
    void handleSendDelivery({
      batter_runs: runs,
      extra_type: null,
      extra_runs: 0,
      is_boundary: runs === 4 || runs === 6,
      boundary_type: runs === 4 ? 4 : runs === 6 ? 6 : null,
      is_batter_boundary: runs === 4 || runs === 6,
      is_wicket: false,
    })
  }

  const handleQuickExtra = (type: 'wide' | 'no_ball' | 'bye' | 'leg_bye') => {
    void handleSendDelivery({
      batter_runs: 0,
      extra_type: type,
      extra_runs: 1,
      is_boundary: false,
      is_batter_boundary: false,
      is_wicket: false,
    })
  }

  const handleSwapStrike = async () => {
    if (!token || !activeInnings || !scorecard) return
    const sId = scorecard.current_striker?.player_id || activeInnings.current_striker_id
    const nsId = scorecard.current_non_striker?.player_id || activeInnings.current_non_striker_id
    if (!sId || !nsId) return

    try {
      setSubmitting(true)
      await apiClient.updateInnings(token, activeInnings.id, {
        current_striker_id: nsId,
        current_non_striker_id: sId,
      })
      await loadData()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSubmitting(false)
    }
  }

  const handleBowlerChange = async () => {
    if (!token || !activeInnings || !selectedNewBowler) return
    try {
      setSubmitting(true)
      await apiClient.updateInnings(token, activeInnings.id, {
        current_bowler_id: selectedNewBowler,
      })
      setShowBowlerModal(false)
      setSelectedNewBowler('')
      await loadData()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSubmitting(false)
    }
  }

  const handleBatterChange = async () => {
    if (!token || !activeInnings || !changingBatterRole || !selectedReplacementBatter) return
    try {
      setSubmitting(true)
      await apiClient.updateInnings(
        token,
        activeInnings.id,
        changingBatterRole === 'striker'
          ? { current_striker_id: selectedReplacementBatter }
          : { current_non_striker_id: selectedReplacementBatter }
      )
      setChangingBatterRole(null)
      setSelectedReplacementBatter('')
      await loadData()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSubmitting(false)
    }
  }

  const handleVoidDeliveryById = async (deliveryId: string) => {
    if (!token) return
    const reason = window.prompt('Reason for voiding this delivery (min 3 chars):', 'Scorer correction')
    if (!reason || reason.trim().length < 3) return

    try {
      setSubmitting(true)
      await apiClient.voidDelivery(token, deliveryId, { reason: reason.trim() })
      await loadData()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSubmitting(false)
    }
  }

  const handleVoidLastBall = async () => {
    const lastActive = [...deliveries].reverse().find((d) => !d.is_voided)
    if (!lastActive) return
    await handleVoidDeliveryById(lastActive.id)
  }

  if (loading) {
    return (
      <AppShell>
        <div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}>
          <Spinner />
        </div>
      </AppShell>
    )
  }

  if (!match) return null

  const startBattingTeamId = startInnNum === 1 ? sortedTeams[0]?.team_id : sortedTeams[1]?.team_id
  const startBowlingTeamId = startInnNum === 1 ? sortedTeams[1]?.team_id : sortedTeams[0]?.team_id
  const startBattingRoster = startBattingTeamId ? teamRosters[startBattingTeamId] || [] : []
  const startBowlingRoster = startBowlingTeamId ? teamRosters[startBowlingTeamId] || [] : []

  return (
    <AppShell>
      {/* Breadcrumb & Navigation */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Link to={`/matches/${matchId}`} style={{ color: colors.textMuted, textDecoration: 'none', fontSize: 14 }}>
          ← Back to Match Details
        </Link>
        <Link
          to={`/matches/${matchId}/record`}
          style={{
            background: '#dc2626',
            color: '#fff',
            padding: '6px 14px',
            borderRadius: 6,
            textDecoration: 'none',
            fontSize: 13,
            fontWeight: 700,
          }}
        >
          📹 Open Video & Markers →
        </Link>
      </div>

      {error && (
        <div style={{ marginBottom: 16 }}>
          <Alert type="error">{error}</Alert>
        </div>
      )}

      {/* MATCH HEADER & LIVE SCOREBOARD */}
      {scorecard ? (
        <Card style={{ marginBottom: 20, background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)', color: '#fff' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
            <div>
              <div style={{ fontSize: 13, textTransform: 'uppercase', letterSpacing: 1.2, color: '#94a3b8', fontWeight: 600 }}>
                {match.title} · {scorecard.innings_number === 1 ? '1ST INNINGS' : '2ND INNINGS'} ({scorecard.batting_team_name})
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: 14, marginTop: 4 }}>
                <span style={{ fontSize: 44, fontWeight: 800, color: '#ffffff', letterSpacing: -1 }}>
                  {scorecard.total_runs}/{scorecard.total_wickets}
                </span>
                <span style={{ fontSize: 18, color: '#cbd5e1', fontWeight: 600 }}>
                  {scorecard.overs_display} overs
                </span>
                <span style={{ fontSize: 14, color: '#94a3b8' }}>
                  · Run rate {scorecard.run_rate}
                </span>
              </div>
              {scorecard.target_runs && (
                <div style={{ fontSize: 13, color: '#38bdf8', marginTop: 4, fontWeight: 600 }}>
                  Target: {scorecard.target_runs} · Needs {Math.max(0, scorecard.target_runs - scorecard.total_runs)} runs
                  {scorecard.required_run_rate ? ` · Req RR: ${scorecard.required_run_rate}` : ''}
                </div>
              )}
            </div>

            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <span
                style={{
                  background: scorecard.status === 'in_progress' ? '#ef4444' : '#10b981',
                  color: '#fff',
                  padding: '4px 10px',
                  borderRadius: 12,
                  fontSize: 12,
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  letterSpacing: 0.5,
                }}
              >
                {scorecard.status === 'in_progress' ? '● LIVE' : scorecard.status.toUpperCase()}
              </span>

              {inningsList.length === 1 && scorecard.status === 'completed' && (
                <Button
                  variant="primary"
                  onClick={() => {
                    setStartInnNum(2)
                    setOpenStriker('')
                    setOpenNonStriker('')
                    setOpenBowler('')
                    setShowStartInningsModal(true)
                  }}
                >
                  Start 2nd Innings
                </Button>
              )}
            </div>
          </div>
        </Card>
      ) : (
        <Card style={{ marginBottom: 20, textAlign: 'center', padding: 30 }}>
          <h3 style={{ margin: '0 0 10px' }}>No active innings yet</h3>
          <Button variant="primary" onClick={() => setShowStartInningsModal(true)}>
            Start 1st Innings
          </Button>
        </Card>
      )}

      {/* TABS: SCORER vs FULL SCORECARD */}
      <div style={{ display: 'flex', borderBottom: `1px solid ${colors.border}`, marginBottom: 20 }}>
        <button
          onClick={() => setActiveTab('scorer')}
          style={{
            padding: '10px 20px',
            border: 'none',
            background: 'transparent',
            cursor: 'pointer',
            fontSize: 15,
            fontWeight: activeTab === 'scorer' ? 700 : 500,
            color: activeTab === 'scorer' ? colors.primary : colors.textMuted,
            borderBottom: activeTab === 'scorer' ? `2px solid ${colors.primary}` : '2px solid transparent',
            marginBottom: -1,
          }}
        >
          Live Scoring Controls
        </button>
        <button
          onClick={() => setActiveTab('scorecard')}
          style={{
            padding: '10px 20px',
            border: 'none',
            background: 'transparent',
            cursor: 'pointer',
            fontSize: 15,
            fontWeight: activeTab === 'scorecard' ? 700 : 500,
            color: activeTab === 'scorecard' ? colors.primary : colors.textMuted,
            borderBottom: activeTab === 'scorecard' ? `2px solid ${colors.primary}` : '2px solid transparent',
            marginBottom: -1,
          }}
        >
          Full Scorecard & Ball Log
        </button>
      </div>

      {activeTab === 'scorer' && scorecard && (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr)', gap: 20 }}>
          {!scorecard.current_bowler && scorecard.status === 'in_progress' && (
            <Alert type="info">
              Over completed! Please{' '}
              <button
                onClick={() => setShowBowlerModal(true)}
                style={{ background: colors.primary, color: '#fff', border: 'none', borderRadius: 4, padding: '3px 10px', fontWeight: 700, cursor: 'pointer', marginLeft: 6 }}
              >
                Select Next Bowler
              </button>
            </Alert>
          )}

          {/* BATTERS & BOWLER CARDS */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 16 }}>
            {/* Striker Card */}
            <Card style={{ borderLeft: `4px solid ${colors.primary}`, background: '#f8fafc' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: colors.primary, letterSpacing: 0.5, textTransform: 'uppercase' }}>
                  STRIKER
                </span>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button
                    onClick={() => { void handleSwapStrike() }}
                    title="Swap Strike"
                    style={{
                      background: 'transparent',
                      border: '1px solid #cbd5e1',
                      borderRadius: 4,
                      padding: '2px 8px',
                      fontSize: 11,
                      cursor: 'pointer',
                      color: colors.textMuted,
                    }}
                  >
                    ⇄ Swap
                  </button>
                  <button
                    onClick={() => setChangingBatterRole('striker')}
                    style={{
                      background: 'transparent',
                      border: '1px solid #cbd5e1',
                      borderRadius: 4,
                      padding: '2px 8px',
                      fontSize: 11,
                      cursor: 'pointer',
                      color: colors.textMuted,
                    }}
                  >
                    Change
                  </button>
                </div>
              </div>
              <div style={{ fontSize: 18, fontWeight: 700, color: colors.text }}>
                {scorecard.current_striker?.player_name || 'Select Striker'} *
              </div>
              <div style={{ fontSize: 24, fontWeight: 800, marginTop: 4, color: colors.primary }}>
                {scorecard.current_striker?.runs || 0}{' '}
                <span style={{ fontSize: 14, fontWeight: 500, color: colors.textMuted }}>
                  ({scorecard.current_striker?.balls || 0} balls)
                </span>
              </div>
              <div style={{ fontSize: 12, color: colors.textMuted, marginTop: 4 }}>
                4s: {scorecard.current_striker?.fours || 0} · 6s: {scorecard.current_striker?.sixes || 0} · SR: {scorecard.current_striker?.strike_rate || 0}
              </div>
            </Card>

            {/* Non-Striker Card */}
            <Card style={{ borderLeft: '4px solid #94a3b8', background: '#f8fafc' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: colors.textMuted, letterSpacing: 0.5, textTransform: 'uppercase' }}>
                  NON-STRIKER
                </span>
                <button
                  onClick={() => setChangingBatterRole('non_striker')}
                  style={{
                    background: 'transparent',
                    border: '1px solid #cbd5e1',
                    borderRadius: 4,
                    padding: '2px 8px',
                    fontSize: 11,
                    cursor: 'pointer',
                    color: colors.textMuted,
                  }}
                >
                  Change
                </button>
              </div>
              <div style={{ fontSize: 18, fontWeight: 700, color: colors.text }}>
                {scorecard.current_non_striker?.player_name || 'Select Non-Striker'}
              </div>
              <div style={{ fontSize: 24, fontWeight: 800, marginTop: 4, color: colors.text }}>
                {scorecard.current_non_striker?.runs || 0}{' '}
                <span style={{ fontSize: 14, fontWeight: 500, color: colors.textMuted }}>
                  ({scorecard.current_non_striker?.balls || 0} balls)
                </span>
              </div>
              <div style={{ fontSize: 12, color: colors.textMuted, marginTop: 4 }}>
                4s: {scorecard.current_non_striker?.fours || 0} · 6s: {scorecard.current_non_striker?.sixes || 0} · SR: {scorecard.current_non_striker?.strike_rate || 0}
              </div>
            </Card>

            {/* Bowler Card */}
            <Card style={{ borderLeft: '4px solid #0284c7', background: '#f8fafc' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: '#0284c7', letterSpacing: 0.5, textTransform: 'uppercase' }}>
                  BOWLER
                </span>
                <button
                  onClick={() => setShowBowlerModal(true)}
                  style={{
                    background: !scorecard.current_bowler ? '#0284c7' : 'transparent',
                    border: '1px solid #0284c7',
                    borderRadius: 4,
                    padding: '2px 8px',
                    fontSize: 11,
                    cursor: 'pointer',
                    color: !scorecard.current_bowler ? '#fff' : '#0284c7',
                    fontWeight: 600,
                  }}
                >
                  Change Bowler
                </button>
              </div>
              <div style={{ fontSize: 18, fontWeight: 700, color: colors.text }}>
                {scorecard.current_bowler?.player_name || 'Select Bowler…'}
              </div>
              <div style={{ fontSize: 22, fontWeight: 800, marginTop: 4, color: '#0284c7' }}>
                {scorecard.current_bowler?.wickets || 0} - {scorecard.current_bowler?.runs_conceded || 0}{' '}
                <span style={{ fontSize: 14, fontWeight: 500, color: colors.textMuted }}>
                  ({scorecard.current_bowler?.overs || '0.0'} ov)
                </span>
              </div>
              <div style={{ fontSize: 12, color: colors.textMuted, marginTop: 4 }}>
                Econ: {scorecard.current_bowler?.economy || 0} · Maidens: {scorecard.current_bowler?.maidens || 0} · Dots: {scorecard.current_bowler?.dots || 0}
              </div>
            </Card>
          </div>

          {/* QUICK SHORTCUT BUTTONS */}
          <Card>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
              <h3 style={{ margin: 0, fontSize: 16 }}>Record the delivery</h3>
              {deliveries.some((d) => !d.is_voided) && (
                <button
                  onClick={() => { void handleVoidLastBall() }}
                  disabled={submitting}
                  style={{
                    background: '#fef2f2',
                    border: '1px solid #fecaca',
                    color: '#dc2626',
                    padding: '4px 10px',
                    borderRadius: 6,
                    fontSize: 12,
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  ↺ Undo Last Ball
                </button>
              )}
            </div>

            {/* Recent Balls */}
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 16, overflowX: 'auto', paddingBottom: 4 }}>
              <span style={{ fontSize: 12, color: colors.textMuted, fontWeight: 600 }}>Recent Balls:</span>
              {deliveries.slice(-8).map((d) => (
                <span
                  key={d.id}
                  title={`Over ${d.display_over}`}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    minWidth: 32,
                    height: 32,
                    padding: '0 6px',
                    borderRadius: 16,
                    fontWeight: 700,
                    fontSize: 12,
                    background: d.is_wicket
                      ? '#ef4444'
                      : d.is_boundary
                      ? '#10b981'
                      : d.is_voided
                      ? '#cbd5e1'
                      : '#e2e8f0',
                    color: d.is_wicket || d.is_boundary ? '#fff' : '#1e293b',
                    textDecoration: d.is_voided ? 'line-through' : 'none',
                  }}
                >
                  {d.is_wicket ? 'W' : d.extra_type ? (d.extra_type === 'wide' ? `${d.extra_runs}wd` : `${d.total_runs}nb`) : d.batter_runs}
                </span>
              ))}
            </div>

            {/* Quick action grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(8, 1fr)', gap: 10, marginBottom: 16 }}>
              {[0, 1, 2, 3, 4, 6].map((num) => (
                <button
                  key={num}
                  disabled={submitting || activeInnings?.status === 'completed'}
                  onClick={() => handleQuickBall(num)}
                  style={{
                    padding: '16px 0',
                    fontSize: 20,
                    fontWeight: 800,
                    borderRadius: 8,
                    border: '1px solid #cbd5e1',
                    background: num === 4 || num === 6 ? '#ecfdf5' : '#ffffff',
                    color: num === 4 || num === 6 ? '#059669' : colors.text,
                    cursor: 'pointer',
                    boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
                  }}
                >
                  {num}
                </button>
              ))}

              <button
                disabled={submitting || activeInnings?.status === 'completed'}
                onClick={() => setIsWicket(!isWicket)}
                style={{
                  padding: '16px 0',
                  fontSize: 20,
                  fontWeight: 800,
                  borderRadius: 8,
                  border: isWicket ? '2px solid #dc2626' : '1px solid #f87171',
                  background: isWicket ? '#dc2626' : '#fef2f2',
                  color: isWicket ? '#fff' : '#dc2626',
                  cursor: 'pointer',
                  boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
                }}
              >
                W
              </button>

              <button
                disabled={submitting || activeInnings?.status === 'completed'}
                onClick={() => handleQuickExtra('wide')}
                style={{
                  padding: '16px 0',
                  fontSize: 16,
                  fontWeight: 800,
                  borderRadius: 8,
                  border: '1px solid #93c5fd',
                  background: '#eff6ff',
                  color: '#2563eb',
                  cursor: 'pointer',
                  boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
                }}
              >
                1 Wd
              </button>
            </div>

            {/* Quick Extra Bar */}
            <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
              <button
                onClick={() => handleQuickExtra('no_ball')}
                disabled={submitting || activeInnings?.status === 'completed'}
                style={{ flex: 1, padding: 8, borderRadius: 6, border: '1px solid #e2e8f0', background: '#f8fafc', fontWeight: 600, fontSize: 13, cursor: 'pointer' }}
              >
                +1 No Ball
              </button>
              <button
                onClick={() => handleQuickExtra('bye')}
                disabled={submitting || activeInnings?.status === 'completed'}
                style={{ flex: 1, padding: 8, borderRadius: 6, border: '1px solid #e2e8f0', background: '#f8fafc', fontWeight: 600, fontSize: 13, cursor: 'pointer' }}
              >
                +1 Bye
              </button>
              <button
                onClick={() => handleQuickExtra('leg_bye')}
                disabled={submitting || activeInnings?.status === 'completed'}
                style={{ flex: 1, padding: 8, borderRadius: 6, border: '1px solid #e2e8f0', background: '#f8fafc', fontWeight: 600, fontSize: 13, cursor: 'pointer' }}
              >
                +1 Leg Bye
              </button>
            </div>

            {/* DETAILED DELIVERY ENTRY FORM */}
            <div style={{ marginTop: 16, padding: 16, background: isWicket ? '#fef2f2' : '#f8fafc', borderRadius: 8, border: `1px solid ${isWicket ? '#fca5a5' : '#e2e8f0'}` }}>
              <h4 style={{ margin: '0 0 12px', fontSize: 14, color: isWicket ? '#dc2626' : colors.text }}>
                {isWicket ? '⚠️ Wicket & Custom Delivery Details' : 'Custom Delivery Details'}
              </h4>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
                <div>
                  <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: colors.textMuted, marginBottom: 4 }}>
                    Runs off Bat
                  </label>
                  <select
                    value={batterRuns}
                    onChange={(e) => {
                      const r = Number(e.target.value)
                      setBatterRuns(r)
                      if (r === 4 || r === 6) {
                        setIsBoundary(true)
                        setBoundaryType(r as 4 | 6)
                        setIsBatterBoundary(true)
                      } else {
                        setIsBoundary(false)
                      }
                    }}
                    style={{ width: '100%', padding: '8px', borderRadius: 6, border: '1px solid #cbd5e1' }}
                  >
                    {[0, 1, 2, 3, 4, 5, 6].map((n) => (
                      <option key={n} value={n}>{n} runs</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: colors.textMuted, marginBottom: 4 }}>
                    Extra Type
                  </label>
                  <select
                    value={extraType}
                    onChange={(e) => {
                      // eslint-disable-next-line @typescript-eslint/no-explicit-any
                      const val = e.target.value as any
                      setExtraType(val)
                      if (val && extraRuns === 0) setExtraRuns(1)
                      if (!val) setExtraRuns(0)
                    }}
                    style={{ width: '100%', padding: '8px', borderRadius: 6, border: '1px solid #cbd5e1' }}
                  >
                    <option value="">None (Legal ball)</option>
                    <option value="wide">Wide</option>
                    <option value="no_ball">No Ball</option>
                    <option value="bye">Bye</option>
                    <option value="leg_bye">Leg Bye</option>
                    <option value="penalty">Penalty</option>
                  </select>
                </div>

                {extraType && (
                  <div>
                    <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: colors.textMuted, marginBottom: 4 }}>
                      Extra Runs
                    </label>
                    <input
                      type="number"
                      min="1"
                      value={extraRuns}
                      onChange={(e) => setExtraRuns(Math.max(1, Number(e.target.value)))}
                      style={{ width: '100%', padding: '8px', borderRadius: 6, border: '1px solid #cbd5e1' }}
                    />
                  </div>
                )}
              </div>

              {/* Boundary Options */}
              <div style={{ marginTop: 12, display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={isBoundary}
                    onChange={(e) => setIsBoundary(e.target.checked)}
                  />
                  Is Boundary
                </label>

                {isBoundary && (
                  <>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={isBatterBoundary}
                        onChange={(e) => setIsBatterBoundary(e.target.checked)}
                      />
                      Credited to batter (uncheck for overthrows/byes)
                    </label>
                    <select
                      value={boundaryType}
                      onChange={(e) => setBoundaryType(Number(e.target.value) as 4 | 6)}
                      style={{ padding: '4px 8px', borderRadius: 4, border: '1px solid #cbd5e1' }}
                    >
                      <option value={4}>Four (4)</option>
                      <option value={6}>Six (6)</option>
                    </select>
                  </>
                )}
              </div>

              {/* Wicket Section */}
              <div style={{ marginTop: 14, paddingTop: 14, borderTop: '1px solid #e2e8f0' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 14, fontWeight: 700, color: '#dc2626', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={isWicket}
                    onChange={(e) => setIsWicket(e.target.checked)}
                  />
                  Wicket on this ball
                </label>

                {isWicket && (
                  <div style={{ marginTop: 10, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12 }}>
                    <div>
                      <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: colors.textMuted, marginBottom: 4 }}>
                        Wicket Type
                      </label>
                      <select
                        value={wicketType}
                        onChange={(e) => setWicketType(e.target.value)}
                        style={{ width: '100%', padding: '8px', borderRadius: 6, border: '1px solid #cbd5e1' }}
                      >
                        <option value="bowled">Bowled</option>
                        <option value="caught">Caught</option>
                        <option value="lbw">LBW</option>
                        <option value="run_out">Run Out</option>
                        <option value="stumped">Stumped</option>
                        <option value="hit_wicket">Hit Wicket</option>
                        <option value="retired_hurt">Retired Hurt</option>
                        <option value="retired_out">Retired Out</option>
                      </select>
                    </div>

                    <div>
                      <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: colors.textMuted, marginBottom: 4 }}>
                        Dismissed Batter
                      </label>
                      <select
                        value={dismissedEnd}
                        // eslint-disable-next-line @typescript-eslint/no-explicit-any
                        onChange={(e) => setDismissedEnd(e.target.value as any)}
                        style={{ width: '100%', padding: '8px', borderRadius: 6, border: '1px solid #cbd5e1' }}
                      >
                        <option value="striker">Striker ({scorecard.current_striker?.player_name})</option>
                        <option value="non_striker">Non-Striker ({scorecard.current_non_striker?.player_name})</option>
                      </select>
                    </div>

                    {(wicketType === 'caught' || wicketType === 'run_out' || wicketType === 'stumped') && (
                      <div>
                        <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: colors.textMuted, marginBottom: 4 }}>
                          Fielder
                        </label>
                        <select
                          value={fielderId}
                          onChange={(e) => setFielderId(e.target.value)}
                          style={{ width: '100%', padding: '8px', borderRadius: 6, border: '1px solid #cbd5e1' }}
                        >
                          <option value="">Select Fielder...</option>
                          {bowlingRoster.map((p) => (
                            <option key={p.player_id} value={p.player_id}>{p.player_name}</option>
                          ))}
                        </select>
                      </div>
                    )}

                    {wicketType === 'run_out' && (
                      <div>
                        <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: colors.textMuted, marginBottom: 4 }}>
                          Completed Runs Before Out
                        </label>
                        <input
                          type="number"
                          min="0"
                          value={runsCompletedBeforeOut}
                          onChange={(e) => setRunsCompletedBeforeOut(Number(e.target.value))}
                          style={{ width: '100%', padding: '8px', borderRadius: 6, border: '1px solid #cbd5e1' }}
                        />
                      </div>
                    )}

                    {availableBatters.length > 0 && (
                      <div>
                        <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: colors.textMuted, marginBottom: 4 }}>
                          Next Batter In
                        </label>
                        <select
                          value={nextBatterId}
                          onChange={(e) => setNextBatterId(e.target.value)}
                          style={{ width: '100%', padding: '8px', borderRadius: 6, border: '1px solid #cbd5e1' }}
                        >
                          <option value="">Select Next Batter...</option>
                          {availableBatters.map((p) => (
                            <option key={p.player_id} value={p.player_id}>{p.player_name}</option>
                          ))}
                        </select>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Submit Custom Delivery */}
              <div style={{ marginTop: 16 }}>
                <Button
                  variant={isWicket ? 'danger' : 'primary'}
                  disabled={submitting || activeInnings?.status === 'completed'}
                  onClick={() => { void handleSendDelivery() }}
                >
                  {submitting ? 'Submitting...' : isWicket ? 'Record Wicket Delivery' : 'Submit Custom Delivery'}
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* FULL SCORECARD & BALL LOG TAB */}
      {activeTab === 'scorecard' && scorecard && (
        <div style={{ display: 'grid', gap: 20 }}>
          {/* Batting Scorecard */}
          <Card>
            <h3 style={{ margin: '0 0 16px', fontSize: 18 }}>{scorecard.batting_team_name} Batting</h3>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 14 }}>
                <thead>
                  <tr style={{ borderBottom: `2px solid ${colors.border}`, color: colors.textMuted, fontSize: 12 }}>
                    <th style={{ padding: '8px 12px' }}>Batter</th>
                    <th style={{ padding: '8px 12px' }}>Dismissal</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right' }}>R</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right' }}>B</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right' }}>4s</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right' }}>6s</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right' }}>SR</th>
                  </tr>
                </thead>
                <tbody>
                  {scorecard.batters.map((b) => (
                    <tr key={b.player_id} style={{ borderBottom: `1px solid ${colors.border}` }}>
                      <td style={{ padding: '10px 12px', fontWeight: 600 }}>
                        <Link to={`/players/${b.player_id}/highlights`} style={{ color: colors.text, textDecoration: 'none' }}>
                          {b.player_name}
                        </Link>{' '}
                        {b.player_id === scorecard.current_striker?.player_id ? '*' : ''}
                      </td>
                      <td style={{ padding: '10px 12px', color: b.is_out ? '#dc2626' : colors.primary }}>
                        {b.dismissal_text}
                      </td>
                      <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 700 }}>{b.runs}</td>
                      <td style={{ padding: '10px 12px', textAlign: 'right', color: colors.textMuted }}>{b.balls}</td>
                      <td style={{ padding: '10px 12px', textAlign: 'right' }}>{b.fours}</td>
                      <td style={{ padding: '10px 12px', textAlign: 'right' }}>{b.sixes}</td>
                      <td style={{ padding: '10px 12px', textAlign: 'right' }}>{b.strike_rate}</td>
                    </tr>
                  ))}
                  <tr style={{ borderBottom: `1px solid ${colors.border}`, background: '#f8fafc' }}>
                    <td style={{ padding: '10px 12px', fontWeight: 600 }}>Extras</td>
                    <td style={{ padding: '10px 12px', color: colors.textMuted }} colSpan={6}>
                      (wd {scorecard.extras.wides}, nb {scorecard.extras.no_balls}, b {scorecard.extras.byes}, lb {scorecard.extras.leg_byes}, p {scorecard.extras.penalty}) · <strong>Total {scorecard.extras.total}</strong>
                    </td>
                  </tr>
                  <tr style={{ background: '#f1f5f9', fontWeight: 700 }}>
                    <td style={{ padding: '10px 12px' }}>Total</td>
                    <td style={{ padding: '10px 12px' }}>
                      ({scorecard.total_wickets} wickets, {scorecard.overs_display} overs)
                    </td>
                    <td style={{ padding: '10px 12px', textAlign: 'right', fontSize: 16 }}>{scorecard.total_runs}</td>
                    <td style={{ padding: '10px 12px' }} colSpan={4}></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </Card>

          {/* Bowling Figures */}
          <Card>
            <h3 style={{ margin: '0 0 16px', fontSize: 18 }}>{scorecard.bowling_team_name} Bowling</h3>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 14 }}>
                <thead>
                  <tr style={{ borderBottom: `2px solid ${colors.border}`, color: colors.textMuted, fontSize: 12 }}>
                    <th style={{ padding: '8px 12px' }}>Bowler</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right' }}>O</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right' }}>M</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right' }}>R</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right' }}>W</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right' }}>Econ</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right' }}>Dots</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right' }}>Wd</th>
                    <th style={{ padding: '8px 12px', textAlign: 'right' }}>Nb</th>
                  </tr>
                </thead>
                <tbody>
                  {scorecard.bowlers.map((bw) => (
                    <tr key={bw.player_id} style={{ borderBottom: `1px solid ${colors.border}` }}>
                      <td style={{ padding: '10px 12px', fontWeight: 600 }}>{bw.player_name}</td>
                      <td style={{ padding: '10px 12px', textAlign: 'right' }}>{bw.overs}</td>
                      <td style={{ padding: '10px 12px', textAlign: 'right' }}>{bw.maidens}</td>
                      <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 700 }}>{bw.runs_conceded}</td>
                      <td style={{ padding: '10px 12px', textAlign: 'right', fontWeight: 700, color: colors.primary }}>{bw.wickets}</td>
                      <td style={{ padding: '10px 12px', textAlign: 'right' }}>{bw.economy}</td>
                      <td style={{ padding: '10px 12px', textAlign: 'right' }}>{bw.dots}</td>
                      <td style={{ padding: '10px 12px', textAlign: 'right' }}>{bw.wides}</td>
                      <td style={{ padding: '10px 12px', textAlign: 'right' }}>{bw.no_balls}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Fall of Wickets */}
          {scorecard.fall_of_wickets.length > 0 && (
            <Card>
              <h3 style={{ margin: '0 0 12px', fontSize: 16 }}>Fall of Wickets</h3>
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                {scorecard.fall_of_wickets.map((fow) => (
                  <div
                    key={fow.wicket_number}
                    style={{
                      background: '#f8fafc',
                      padding: '8px 14px',
                      borderRadius: 6,
                      border: '1px solid #e2e8f0',
                      fontSize: 13,
                    }}
                  >
                    <strong>{fow.score}/{fow.wicket_number}</strong> ({fow.dismissed_player_name}, {fow.overs} ov)
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* Ball-by-Ball Commentary & Audit Log */}
          <Card>
            <h3 style={{ margin: '0 0 12px', fontSize: 16 }}>Ball-by-Ball Delivery Log ({deliveries.length})</h3>
            {deliveries.length === 0 ? (
              <p style={{ color: colors.textMuted, fontSize: 13 }}>No deliveries recorded yet.</p>
            ) : (
              <div style={{ display: 'grid', gap: 8 }}>
                {[...deliveries].reverse().map((d) => (
                  <div
                    key={d.id}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '8px 12px',
                      borderRadius: 6,
                      background: d.is_voided ? '#f1f5f9' : '#f8fafc',
                      border: `1px solid ${colors.border}`,
                      opacity: d.is_voided ? 0.6 : 1,
                    }}
                  >
                    <div>
                      <span style={{ fontWeight: 700, fontSize: 13, marginRight: 8 }}>Over {d.display_over}</span>
                      <span style={{ fontSize: 13 }}>
                        {d.total_runs} {d.total_runs === 1 ? 'run' : 'runs'}
                        {d.extra_type ? ` (${d.extra_type})` : ''}
                        {d.is_boundary ? ` · BOUNDARY ${d.boundary_type}` : ''}
                        {d.is_wicket ? ` · WICKET (${d.wicket_type})` : ''}
                        {d.is_voided ? ` · VOIDED (${d.voided_reason})` : ''}
                      </span>
                    </div>
                    {!d.is_voided && (
                      <button
                        onClick={() => { void handleVoidDeliveryById(d.id) }}
                        style={{ background: 'none', border: 'none', color: colors.danger, fontSize: 12, cursor: 'pointer', fontWeight: 600 }}
                      >
                        Void
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      )}

      {/* START INNINGS MODAL */}
      {showStartInningsModal && match && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#fff', borderRadius: 12, padding: 24, maxWidth: 440, width: '90%', boxShadow: '0 20px 25px -5px rgba(0,0,0,0.2)' }}>
            <h3 style={{ margin: '0 0 8px' }}>Start Innings {startInnNum}</h3>
            <p style={{ margin: '0 0 16px', fontSize: 13, color: colors.textMuted }}>
              Select the opening batters and opening bowler to begin scoring.
            </p>

            {startBattingRoster.length < 2 || startBowlingRoster.length < 1 ? (
              <Alert type="info">
                Add at least 2 players to the batting team and 1 player to the bowling team on the{' '}
                <Link to={`/matches/${matchId}`} style={{ color: colors.primary, fontWeight: 700 }}>Match Details page</Link> first.
              </Alert>
            ) : (
              <div style={{ display: 'grid', gap: 12 }}>
                <div>
                  <label style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4 }}>Opening Striker</label>
                  <select
                    value={openStriker}
                    onChange={(e) => setOpenStriker(e.target.value)}
                    style={{ width: '100%', padding: 8, borderRadius: 6, border: '1px solid #cbd5e1' }}
                  >
                    <option value="">Select Opening Striker...</option>
                    {startBattingRoster.map((p) => (
                      <option key={p.player_id} value={p.player_id}>{p.player_name}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4 }}>Opening Non-Striker</label>
                  <select
                    value={openNonStriker}
                    onChange={(e) => setOpenNonStriker(e.target.value)}
                    style={{ width: '100%', padding: 8, borderRadius: 6, border: '1px solid #cbd5e1' }}
                  >
                    <option value="">Select Non-Striker...</option>
                    {startBattingRoster
                      .filter((p) => p.player_id !== openStriker)
                      .map((p) => (
                        <option key={p.player_id} value={p.player_id}>{p.player_name}</option>
                      ))}
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: 12, fontWeight: 600, marginBottom: 4 }}>Opening Bowler</label>
                  <select
                    value={openBowler}
                    onChange={(e) => setOpenBowler(e.target.value)}
                    style={{ width: '100%', padding: 8, borderRadius: 6, border: '1px solid #cbd5e1' }}
                  >
                    <option value="">Select Opening Bowler...</option>
                    {startBowlingRoster.map((p) => (
                      <option key={p.player_id} value={p.player_id}>{p.player_name}</option>
                    ))}
                  </select>
                </div>
              </div>
            )}

            <div style={{ display: 'flex', gap: 10, marginTop: 20, justifyContent: 'flex-end' }}>
              <Button variant="secondary" onClick={() => setShowStartInningsModal(false)}>Cancel</Button>
              <Button
                variant="primary"
                onClick={() => { void handleStartInnings() }}
                disabled={submitting || !openStriker || !openNonStriker || !openBowler}
              >
                {submitting ? 'Starting...' : 'Confirm & Start'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* CHANGE BOWLER MODAL */}
      {showBowlerModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#fff', borderRadius: 12, padding: 24, maxWidth: 400, width: '90%' }}>
            <h3 style={{ margin: '0 0 16px' }}>Select Bowler for Over</h3>
            <select
              value={selectedNewBowler}
              onChange={(e) => setSelectedNewBowler(e.target.value)}
              style={{ width: '100%', padding: 8, borderRadius: 6, border: '1px solid #cbd5e1', marginBottom: 16 }}
            >
              <option value="">Select Bowler from Squad...</option>
              {bowlingRoster.map((p) => (
                <option key={p.player_id} value={p.player_id}>{p.player_name}</option>
              ))}
            </select>
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <Button variant="secondary" onClick={() => setShowBowlerModal(false)}>Cancel</Button>
              <Button variant="primary" onClick={() => { void handleBowlerChange() }} disabled={!selectedNewBowler || submitting}>
                Set Bowler
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* CHANGE BATTER MODAL */}
      {changingBatterRole && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: '#fff', borderRadius: 12, padding: 24, maxWidth: 400, width: '90%' }}>
            <h3 style={{ margin: '0 0 16px' }}>
              Select {changingBatterRole === 'striker' ? 'Striker' : 'Non-Striker'}
            </h3>
            <select
              value={selectedReplacementBatter}
              onChange={(e) => setSelectedReplacementBatter(e.target.value)}
              style={{ width: '100%', padding: 8, borderRadius: 6, border: '1px solid #cbd5e1', marginBottom: 16 }}
            >
              <option value="">Select Batter from Squad...</option>
              {availableBatters.map((p) => (
                <option key={p.player_id} value={p.player_id}>{p.player_name}</option>
              ))}
            </select>
            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end' }}>
              <Button variant="secondary" onClick={() => setChangingBatterRole(null)}>Cancel</Button>
              <Button variant="primary" onClick={() => { void handleBatterChange() }} disabled={!selectedReplacementBatter || submitting}>
                Set Batter
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Phase 5: Live Broadcast Animation Overlay */}
      <BroadcastAnimationOverlay
        event={broadcastEvent}
        onDismiss={() => setBroadcastEvent(null)}
      />

      {/* Phase 5: Innings Milestones & Broadcast Replay Section */}
      {activeInnings && (
        <MilestoneTimelineSection
          title={`🏆 Innings ${activeInnings.innings_number} Milestones & Broadcast Replay`}
          subtitle="Automatic 50 and 100 celebrations from verified batter runs — plus instant broadcast animation previews"
          milestones={milestones}
          showBroadcastTester
        />
      )}
    </AppShell>
  )
}
