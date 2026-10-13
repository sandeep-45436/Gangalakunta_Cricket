import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { apiClient, type Team } from '../../services/apiClient'
import { AppShell } from '../../components/layout/AppShell'
import { Card } from '../../components/ui/Card'
import { Button } from '../../components/ui/Button'
import { Alert } from '../../components/ui/Alert'
import { Spinner } from '../../components/ui/Spinner'
import { colors } from '../../theme'

export function TeamsPage() {
  const { token } = useAuth()
  const [teams, setTeams] = useState<Team[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!token) return
    apiClient.listTeams(token)
      .then(setTeams)
      .catch((e: unknown) => setError(String(e)))
      .finally(() => setLoading(false))
  }, [token])

  return (
    <AppShell>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
        <h1 style={{ margin: 0, color: colors.text }}>Teams</h1>
        <Link to="/teams/new"><Button>+ New team</Button></Link>
      </div>

      {loading && <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}><Spinner /></div>}
      {error && <Alert type="error">{error}</Alert>}

      {!loading && teams.length === 0 && (
        <Card style={{ textAlign: 'center', padding: 48 }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>👥</div>
          <p style={{ color: colors.textMuted, marginBottom: 16 }}>No teams yet. Create your first team to get started.</p>
          <Link to="/teams/new"><Button>Create team</Button></Link>
        </Card>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {teams.map((team) => (
          <Link key={team.id} to={`/teams/${team.id}`} style={{ textDecoration: 'none' }}>
            <Card style={{ display: 'flex', alignItems: 'center', gap: 16, cursor: 'pointer' }}>
              <div style={{ width: 44, height: 44, borderRadius: '50%', background: colors.primaryLight, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20, flexShrink: 0 }}>
                {team.short_name?.[0] ?? team.name[0]}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 700, color: colors.text }}>{team.name}</div>
                {team.short_name && <div style={{ fontSize: 13, color: colors.textMuted }}>{team.short_name}</div>}
              </div>
              <span style={{ color: colors.textMuted, fontSize: 18 }}>›</span>
            </Card>
          </Link>
        ))}
      </div>
    </AppShell>
  )
}
