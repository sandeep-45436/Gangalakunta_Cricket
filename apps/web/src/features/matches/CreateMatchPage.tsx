import { FormEvent, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { apiClient, type Team } from '../../services/apiClient'
import { AppShell } from '../../components/layout/AppShell'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Button } from '../../components/ui/Button'
import { Alert } from '../../components/ui/Alert'
import { Spinner } from '../../components/ui/Spinner'
import { colors } from '../../theme'

const FORMAT_OPTIONS = [
  { value: 'T20', label: 'T20' },
  { value: 'ODI', label: 'ODI (50 overs)' },
  { value: 'T10', label: 'T10' },
  { value: 'Test', label: 'Test' },
  { value: 'Custom', label: 'Custom' },
]

export function CreateMatchPage() {
  const { token } = useAuth()
  const navigate = useNavigate()
  const [teams, setTeams] = useState<Team[]>([])
  const [loadingTeams, setLoadingTeams] = useState(true)
  const [title, setTitle] = useState('')
  const [tournament, setTournament] = useState('')
  const [format, setFormat] = useState('T20')
  const [venue, setVenue] = useState('')
  const [scheduledAt, setScheduledAt] = useState('')
  const [overs, setOvers] = useState('20')
  const [team1Id, setTeam1Id] = useState('')
  const [team2Id, setTeam2Id] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!token) return
    apiClient.listTeams(token)
      .then((t) => { setTeams(t); if (t.length >= 1) setTeam1Id(t[0].id); if (t.length >= 2) setTeam2Id(t[1].id) })
      .catch((e: unknown) => setError(String(e)))
      .finally(() => setLoadingTeams(false))
  }, [token])

  const teamOptions = [{ value: '', label: 'Select a team…' }, ...teams.map((t) => ({ value: t.id, label: t.name }))]

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!token) return
    if (!team1Id || !team2Id) { setError('Select both teams'); return }
    if (team1Id === team2Id) { setError('A match cannot have the same team twice'); return }
    setError('')
    setLoading(true)
    try {
      const match = await apiClient.createMatch(token, {
        title: title.trim(),
        tournament: tournament.trim() || null,
        format,
        venue: venue.trim() || null,
        scheduled_at: scheduledAt || null,
        overs_per_innings: format !== 'Test' && overs ? parseInt(overs, 10) : null,
        teams: [
          { team_id: team1Id, batting_order: 1 },
          { team_id: team2Id, batting_order: 2 },
        ],
      })
      navigate(`/matches/${match.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create match')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AppShell>
      <h1 style={{ margin: '0 0 20px', color: colors.text }}>New match</h1>
      {loadingTeams ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}><Spinner /></div>
      ) : teams.length < 2 ? (
        <Alert type="info">You need at least 2 teams to create a match. <a href="/teams/new" style={{ color: colors.primary }}>Create teams first →</a></Alert>
      ) : (
        <Card style={{ maxWidth: 560 }}>
          {error && <div style={{ marginBottom: 14 }}><Alert type="error">{error}</Alert></div>}
          <form onSubmit={(e) => { void handleSubmit(e) }} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <Input label="Match title *" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Mumbai vs Chennai — Finals" required />
            <Input label="Tournament / Series" value={tournament} onChange={(e) => setTournament(e.target.value)} placeholder="e.g. Premier Club League 2026" />
            <Select label="Format *" value={format} onChange={(e) => { setFormat(e.target.value); if (e.target.value === 'T20') setOvers('20'); else if (e.target.value === 'ODI') setOvers('50'); else if (e.target.value === 'T10') setOvers('10') }} options={FORMAT_OPTIONS} />
            {format !== 'Test' && <Input label="Overs per innings" type="number" value={overs} onChange={(e) => setOvers(e.target.value)} min={1} max={100} />}
            <Input label="Venue" value={venue} onChange={(e) => setVenue(e.target.value)} placeholder="e.g. Wankhede Stadium" />
            <Input label="Scheduled date" type="datetime-local" value={scheduledAt} onChange={(e) => setScheduledAt(e.target.value)} />

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <Select label="Team 1 (bats first) *" value={team1Id} onChange={(e) => setTeam1Id(e.target.value)} options={teamOptions} />
              <Select label="Team 2 (bats second) *" value={team2Id} onChange={(e) => setTeam2Id(e.target.value)} options={teamOptions} />
            </div>

            <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
              <Button type="submit" loading={loading} disabled={!title.trim() || !team1Id || !team2Id}>Create match</Button>
              <Button type="button" variant="secondary" onClick={() => navigate('/matches')}>Cancel</Button>
            </div>
          </form>
        </Card>
      )}
    </AppShell>
  )
}
