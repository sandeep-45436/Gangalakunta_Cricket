import { FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { apiClient } from '../../services/apiClient'
import { AppShell } from '../../components/layout/AppShell'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { Select } from '../../components/ui/Select'
import { Button } from '../../components/ui/Button'
import { Alert } from '../../components/ui/Alert'
import { colors } from '../../theme'

const ROLES = [
  { value: '', label: 'Not specified' },
  { value: 'Batter', label: 'Batter' },
  { value: 'Bowler', label: 'Bowler' },
  { value: 'All-rounder', label: 'All-rounder' },
  { value: 'WK', label: 'Wicketkeeper (WK)' },
]

export function CreatePlayerPage() {
  const { token } = useAuth()
  const navigate = useNavigate()
  const [fullName, setFullName] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [role, setRole] = useState('')
  const [jerseyNumber, setJerseyNumber] = useState('')
  const [battingStyle, setBattingStyle] = useState('')
  const [bowlingStyle, setBowlingStyle] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!token) return
    setError('')
    setLoading(true)
    try {
      await apiClient.createPlayer(token, {
        full_name: fullName.trim(),
        display_name: displayName.trim() || null,
        role: role || null,
        jersey_number: jerseyNumber ? parseInt(jerseyNumber, 10) : null,
        batting_style: battingStyle.trim() || null,
        bowling_style: bowlingStyle.trim() || null,
      })
      navigate('/players')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create player')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AppShell>
      <h1 style={{ margin: '0 0 20px', color: colors.text }}>New player</h1>
      <Card style={{ maxWidth: 520 }}>
        {error && <div style={{ marginBottom: 14 }}><Alert type="error">{error}</Alert></div>}
        <form onSubmit={(e) => { void handleSubmit(e) }} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Input label="Full name *" value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="e.g. Virat Kohli" required />
          <Input label="Display / nickname" value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="e.g. Virat" />
          <Select label="Role" value={role} onChange={(e) => setRole(e.target.value)} options={ROLES} />
          <Input label="Jersey number" type="number" value={jerseyNumber} onChange={(e) => setJerseyNumber(e.target.value)} placeholder="e.g. 18" min={0} max={999} />
          <Input label="Batting style" value={battingStyle} onChange={(e) => setBattingStyle(e.target.value)} placeholder="e.g. Right-hand bat" />
          <Input label="Bowling style" value={bowlingStyle} onChange={(e) => setBowlingStyle(e.target.value)} placeholder="e.g. Right-arm fast" />
          <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
            <Button type="submit" loading={loading} disabled={!fullName.trim()}>Create player</Button>
            <Button type="button" variant="secondary" onClick={() => navigate('/players')}>Cancel</Button>
          </div>
        </form>
      </Card>
    </AppShell>
  )
}
