import { FormEvent, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { apiClient } from '../../services/apiClient'
import { AppShell } from '../../components/layout/AppShell'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { Button } from '../../components/ui/Button'
import { Alert } from '../../components/ui/Alert'
import { colors } from '../../theme'

export function CreateTeamPage() {
  const { token } = useAuth()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [shortName, setShortName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!token) return
    setError('')
    setLoading(true)
    try {
      const team = await apiClient.createTeam(token, {
        name: name.trim(),
        short_name: shortName.trim() || null,
      })
      navigate(`/teams/${team.id}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create team')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AppShell>
      <h1 style={{ margin: '0 0 20px', color: colors.text }}>New team</h1>
      <Card style={{ maxWidth: 480 }}>
        {error && <div style={{ marginBottom: 14 }}><Alert type="error">{error}</Alert></div>}
        <form onSubmit={(e) => { void handleSubmit(e) }} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Input label="Team name *" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Mumbai Indians" required />
          <Input label="Short name" value={shortName} onChange={(e) => setShortName(e.target.value)} placeholder="e.g. MI (max 10 chars)" maxLength={10} />
          <div style={{ display: 'flex', gap: 10, marginTop: 4 }}>
            <Button type="submit" loading={loading} disabled={!name.trim()}>Create team</Button>
            <Button type="button" variant="secondary" onClick={() => navigate('/teams')}>Cancel</Button>
          </div>
        </form>
      </Card>
    </AppShell>
  )
}
