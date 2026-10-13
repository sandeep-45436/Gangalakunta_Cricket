import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import {
  apiClient,
  type MatchArchivePageResponse,
  type Team,
  type Player,
} from '../../services/apiClient'
import { AppShell } from '../../components/layout/AppShell'
import { Card } from '../../components/ui/Card'
import { Button } from '../../components/ui/Button'
import { Alert } from '../../components/ui/Alert'
import { Spinner } from '../../components/ui/Spinner'
import { colors } from '../../theme'

const STATUS_COLORS: Record<string, string> = {
  upcoming: '#3b82f6',
  live: colors.danger,
  completed: colors.primary,
  cancelled: colors.textMuted,
}

const PAGE_SIZE = 10

export function MatchesPage() {
  const { token } = useAuth()
  const [archivePage, setArchivePage] = useState<MatchArchivePageResponse | null>(null)
  const [teams, setTeams] = useState<Team[]>([])
  const [players, setPlayers] = useState<Player[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Phase 6.2 Match Archive Filters
  const [searchQuery, setSearchQuery] = useState('')
  const [teamAId, setTeamAId] = useState('')
  const [teamBId, setTeamBId] = useState('')
  const [playerId, setPlayerId] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [format, setFormat] = useState('')
  const [tournament, setTournament] = useState('')
  const [status, setStatus] = useState('')
  const [inningsNumber, setInningsNumber] = useState<string>('')
  const [highlightType, setHighlightType] = useState('')
  const [offset, setOffset] = useState(0)

  // Load teams and players for filter dropdowns
  useEffect(() => {
    if (!token) return
    Promise.all([
      apiClient.listTeams(token).catch(() => [] as Team[]),
      apiClient.listPlayers(token).catch(() => [] as Player[]),
    ]).then(([tList, pList]) => {
      setTeams(tList)
      setPlayers(pList)
    })
  }, [token])

  const loadArchive = useCallback(
    async (pageOffset = 0) => {
      if (!token) return
      try {
        setLoading(true)
        setError('')
        const res = await apiClient.searchMatchArchive(token, {
          q: searchQuery.trim() || undefined,
          team_id: teamAId || undefined,
          team_b_id: teamBId || undefined,
          player_id: playerId || undefined,
          date_from: dateFrom || undefined,
          date_to: dateTo || undefined,
          format: format || undefined,
          tournament: tournament || undefined,
          status: status || undefined,
          innings_number: inningsNumber ? parseInt(inningsNumber, 10) : undefined,
          highlight_type: highlightType || undefined,
          limit: PAGE_SIZE,
          offset: pageOffset,
        })
        setArchivePage(res)
        setOffset(pageOffset)
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : String(e))
      } finally {
        setLoading(false)
      }
    },
    [
      token,
      searchQuery,
      teamAId,
      teamBId,
      playerId,
      dateFrom,
      dateTo,
      format,
      tournament,
      status,
      inningsNumber,
      highlightType,
    ],
  )

  useEffect(() => {
    void loadArchive(0)
  }, [loadArchive])

  const hasActiveFilters = Boolean(
    searchQuery ||
      teamAId ||
      teamBId ||
      playerId ||
      dateFrom ||
      dateTo ||
      format ||
      tournament ||
      status ||
      inningsNumber ||
      highlightType,
  )

  const clearFilters = () => {
    setSearchQuery('')
    setTeamAId('')
    setTeamBId('')
    setPlayerId('')
    setDateFrom('')
    setDateTo('')
    setFormat('')
    setTournament('')
    setStatus('')
    setInningsNumber('')
    setHighlightType('')
  }

  return (
    <AppShell>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginBottom: 20 }}>
        <div>
          <h1 style={{ margin: 0 }}>Matches & Historical Archive</h1>
          <p style={{ margin: '4px 0 0', fontSize: 13, color: colors.textMuted }}>
            Search and filter matches by teams, player, date range, format, tournament, innings, and highlight type
          </p>
        </div>
        <Link to="/matches/new"><Button>+ New Match</Button></Link>
      </div>

      {/* Phase 6.2 Search & Multi-Facet Filter Panel */}
      <Card style={{ marginBottom: 20, padding: 16 }}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(190px, 1fr))', gap: 10 }}>
          {/* Search Input */}
          <div>
            <label style={{ display: 'block', fontSize: 11, fontWeight: 700, color: colors.textMuted, marginBottom: 4 }}>
              Search Title / Venue / Series
            </label>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="e.g. Finals, Wankhede..."
              style={{ width: '100%', padding: '7px 10px', borderRadius: 6, border: `1px solid ${colors.border}`, fontSize: 13, boxSizing: 'border-box' }}
            />
          </div>

          {/* Team A */}
          <div>
            <label style={{ display: 'block', fontSize: 11, fontWeight: 700, color: colors.textMuted, marginBottom: 4 }}>
              Team A
            </label>
            <select
              value={teamAId}
              onChange={(e) => setTeamAId(e.target.value)}
              style={{ width: '100%', padding: '7px 10px', borderRadius: 6, border: `1px solid ${colors.border}`, fontSize: 13 }}
            >
              <option value="">Any Team</option>
              {teams.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>

          {/* Team B */}
          <div>
            <label style={{ display: 'block', fontSize: 11, fontWeight: 700, color: colors.textMuted, marginBottom: 4 }}>
              Opponent (Team B)
            </label>
            <select
              value={teamBId}
              onChange={(e) => setTeamBId(e.target.value)}
              style={{ width: '100%', padding: '7px 10px', borderRadius: 6, border: `1px solid ${colors.border}`, fontSize: 13 }}
            >
              <option value="">Any Opponent</option>
              {teams.map((t) => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>

          {/* Player (disambiguates duplicate names with jersey & role) */}
          <div>
            <label style={{ display: 'block', fontSize: 11, fontWeight: 700, color: colors.textMuted, marginBottom: 4 }}>
              Player
            </label>
            <select
              value={playerId}
              onChange={(e) => setPlayerId(e.target.value)}
              style={{ width: '100%', padding: '7px 10px', borderRadius: 6, border: `1px solid ${colors.border}`, fontSize: 13 }}
            >
              <option value="">Any Player</option>
              {players.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.full_name}
                  {p.jersey_number != null ? ` (#${p.jersey_number})` : ''}
                  {p.role ? ` · ${p.role}` : ''}
                </option>
              ))}
            </select>
          </div>

          {/* Format */}
          <div>
            <label style={{ display: 'block', fontSize: 11, fontWeight: 700, color: colors.textMuted, marginBottom: 4 }}>
              Format
            </label>
            <select
              value={format}
              onChange={(e) => setFormat(e.target.value)}
              style={{ width: '100%', padding: '7px 10px', borderRadius: 6, border: `1px solid ${colors.border}`, fontSize: 13 }}
            >
              <option value="">All Formats</option>
              <option value="T20">T20</option>
              <option value="ODI">ODI</option>
              <option value="Test">Test</option>
              <option value="T10">T10</option>
              <option value="Custom">Custom</option>
            </select>
          </div>

          {/* Tournament / Series */}
          <div>
            <label style={{ display: 'block', fontSize: 11, fontWeight: 700, color: colors.textMuted, marginBottom: 4 }}>
              Tournament / Series
            </label>
            <select
              value={tournament}
              onChange={(e) => setTournament(e.target.value)}
              style={{ width: '100%', padding: '7px 10px', borderRadius: 6, border: `1px solid ${colors.border}`, fontSize: 13 }}
            >
              <option value="">All Tournaments</option>
              {(archivePage?.facets.tournaments || []).map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>

          {/* Match Status */}
          <div>
            <label style={{ display: 'block', fontSize: 11, fontWeight: 700, color: colors.textMuted, marginBottom: 4 }}>
              Status
            </label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value)}
              style={{ width: '100%', padding: '7px 10px', borderRadius: 6, border: `1px solid ${colors.border}`, fontSize: 13 }}
            >
              <option value="">All Statuses</option>
              <option value="live">Live</option>
              <option value="completed">Completed</option>
              <option value="upcoming">Upcoming</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>

          {/* Innings */}
          <div>
            <label style={{ display: 'block', fontSize: 11, fontWeight: 700, color: colors.textMuted, marginBottom: 4 }}>
              Innings
            </label>
            <select
              value={inningsNumber}
              onChange={(e) => setInningsNumber(e.target.value)}
              style={{ width: '100%', padding: '7px 10px', borderRadius: 6, border: `1px solid ${colors.border}`, fontSize: 13 }}
            >
              <option value="">Any Innings</option>
              <option value="1">1st Innings</option>
              <option value="2">2nd Innings</option>
            </select>
          </div>

          {/* Highlight / Milestone Type */}
          <div>
            <label style={{ display: 'block', fontSize: 11, fontWeight: 700, color: colors.textMuted, marginBottom: 4 }}>
              Highlight / Milestone Type
            </label>
            <select
              value={highlightType}
              onChange={(e) => setHighlightType(e.target.value)}
              style={{ width: '100%', padding: '7px 10px', borderRadius: 6, border: `1px solid ${colors.border}`, fontSize: 13 }}
            >
              <option value="">Any Highlight</option>
              <option value="four">4️⃣ Has Fours (4)</option>
              <option value="six">6️⃣ Has Sixes (6)</option>
              <option value="fifty">⭐ Has Half-Century (50)</option>
              <option value="century">💯 Has Century (100)</option>
            </select>
          </div>

          {/* Date From */}
          <div>
            <label style={{ display: 'block', fontSize: 11, fontWeight: 700, color: colors.textMuted, marginBottom: 4 }}>
              From Date
            </label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              style={{ width: '100%', padding: '6px 10px', borderRadius: 6, border: `1px solid ${colors.border}`, fontSize: 13, boxSizing: 'border-box' }}
            />
          </div>

          {/* Date To */}
          <div>
            <label style={{ display: 'block', fontSize: 11, fontWeight: 700, color: colors.textMuted, marginBottom: 4 }}>
              To Date
            </label>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              style={{ width: '100%', padding: '6px 10px', borderRadius: 6, border: `1px solid ${colors.border}`, fontSize: 13, boxSizing: 'border-box' }}
            />
          </div>
        </div>

        {hasActiveFilters && (
          <div style={{ marginTop: 12, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 12, color: colors.textMuted }}>
              Found <strong>{archivePage?.total ?? 0}</strong> matching matches
            </span>
            <Button size="sm" variant="secondary" onClick={clearFilters}>
              ✕ Reset All Filters
            </Button>
          </div>
        )}
      </Card>

      {loading && <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}><Spinner /></div>}
      {error && <Alert type="error">{error}</Alert>}

      {!loading && archivePage && archivePage.items.length === 0 && (
        <Card style={{ textAlign: 'center', padding: 48 }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>📋</div>
          <p style={{ color: colors.textMuted, marginBottom: 16 }}>
            {hasActiveFilters
              ? 'No matches match your selected archive filters.'
              : 'No matches yet. Create your first match.'}
          </p>
          {hasActiveFilters ? (
            <Button variant="secondary" onClick={clearFilters}>Clear Filters</Button>
          ) : (
            <Link to="/matches/new"><Button>Create match</Button></Link>
          )}
        </Card>
      )}

      {!loading && archivePage && archivePage.items.length > 0 && (
        <>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {archivePage.items.map((item) => {
              const match = item.match
              return (
                <Card key={match.id} style={{ padding: 18 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
                        <Link
                          to={`/matches/${match.id}`}
                          style={{ fontWeight: 800, fontSize: 17, color: colors.text, textDecoration: 'none' }}
                        >
                          {match.title}
                        </Link>
                        {item.tournament && (
                          <span
                            style={{
                              background: '#fef3c7',
                              color: '#92400e',
                              padding: '2px 8px',
                              borderRadius: 10,
                              fontSize: 11,
                              fontWeight: 700,
                            }}
                          >
                            🏆 {item.tournament}
                          </span>
                        )}
                        <span
                          style={{
                            fontSize: 11,
                            fontWeight: 700,
                            background: STATUS_COLORS[match.status] ?? '#888',
                            color: '#fff',
                            borderRadius: 10,
                            padding: '2px 8px',
                          }}
                        >
                          {match.status.toUpperCase()}
                        </span>
                      </div>

                      <div style={{ fontSize: 13, color: colors.textMuted }}>
                        {match.format}
                        {match.overs_per_innings ? ` (${match.overs_per_innings} ov)` : ''} ·{' '}
                        {match.venue ?? 'Venue TBD'} ·{' '}
                        {match.scheduled_at ? new Date(match.scheduled_at).toLocaleDateString() : new Date(match.created_at).toLocaleDateString()}
                      </div>

                      {/* Innings Score Summaries */}
                      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginTop: 10 }}>
                        {item.innings_summaries.length > 0 ? (
                          item.innings_summaries.map((inn) => (
                            <div
                              key={inn.innings_id}
                              style={{
                                background: '#f8fafc',
                                border: `1px solid ${colors.border}`,
                                borderRadius: 8,
                                padding: '6px 12px',
                                fontSize: 13,
                              }}
                            >
                              <strong>{inn.batting_team_name}:</strong>{' '}
                              <span style={{ fontWeight: 800, color: colors.primary }}>
                                {inn.total_runs}/{inn.total_wickets}
                              </span>{' '}
                              <span style={{ color: colors.textMuted, fontSize: 12 }}>({inn.overs_display} ov)</span>
                            </div>
                          ))
                        ) : (
                          <div style={{ fontSize: 13, fontWeight: 600 }}>
                            {match.teams.map((t) => t.team_name).join(' vs ')}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Right Column: Archive Badges & Actions */}
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 8 }}>
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        {item.highlights_count > 0 && (
                          <span style={{ background: '#e0f2fe', color: '#0369a1', padding: '3px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700 }}>
                            🎬 {item.highlights_count} clips ({item.fours_count}×4, {item.sixes_count}×6)
                          </span>
                        )}
                        {item.milestones_count > 0 && (
                          <span style={{ background: '#fef9c3', color: '#854d0e', padding: '3px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700 }}>
                            🏆 {item.milestones_count} milestones
                          </span>
                        )}
                      </div>

                      <div style={{ display: 'flex', gap: 8 }}>
                        <Link
                          to={`/matches/${match.id}/score`}
                          style={{
                            fontSize: 12,
                            fontWeight: 700,
                            color: colors.primary,
                            textDecoration: 'none',
                            padding: '5px 10px',
                            borderRadius: 6,
                            border: `1px solid ${colors.primary}`,
                          }}
                        >
                          ⚾ Scorecard
                        </Link>
                        <Link
                          to={`/matches/${match.id}`}
                          style={{
                            fontSize: 12,
                            fontWeight: 700,
                            color: '#fff',
                            background: colors.primary,
                            textDecoration: 'none',
                            padding: '5px 12px',
                            borderRadius: 6,
                          }}
                        >
                          Match Archive →
                        </Link>
                      </div>
                    </div>
                  </div>
                </Card>
              )
            })}
          </div>

          {/* Pagination Controls */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 20 }}>
            <span style={{ fontSize: 13, color: colors.textMuted }}>
              Showing {offset + 1}–{Math.min(offset + archivePage.items.length, archivePage.total)} of {archivePage.total} matches
            </span>
            <div style={{ display: 'flex', gap: 8 }}>
              <Button
                size="sm"
                variant="secondary"
                disabled={offset === 0}
                onClick={() => void loadArchive(Math.max(0, offset - PAGE_SIZE))}
              >
                ← Previous
              </Button>
              <Button
                size="sm"
                variant="secondary"
                disabled={!archivePage.has_more}
                onClick={() => void loadArchive(offset + PAGE_SIZE)}
              >
                Next →
              </Button>
            </div>
          </div>
        </>
      )}
    </AppShell>
  )
}
