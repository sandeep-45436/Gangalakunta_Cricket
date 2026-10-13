import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import {
  apiClient,
  type Team,
  type Player,
  type Match,
  type OpsDiagnosticsResponse,
} from '../../services/apiClient'
import { AppShell } from '../../components/layout/AppShell'
import { Card } from '../../components/ui/Card'
import { Button } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/Spinner'
import { Alert } from '../../components/ui/Alert'
import { colors } from '../../theme'

export function DashboardPage() {
  const { user, token } = useAuth()
  const [teams, setTeams] = useState<Team[]>([])
  const [players, setPlayers] = useState<Player[]>([])
  const [matches, setMatches] = useState<Match[]>([])
  const [diagnostics, setDiagnostics] = useState<OpsDiagnosticsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [opsStatus, setOpsStatus] = useState('')
  const [opsBusy, setOpsBusy] = useState(false)

  useEffect(() => {
    if (!token) return
    setLoading(true)
    Promise.all([
      apiClient.listTeams(token),
      apiClient.listPlayers(token),
      apiClient.listMatches(token),
      apiClient.getOpsDiagnostics(token).catch(() => null),
    ])
      .then(([t, p, m, diag]) => {
        setTeams(t)
        setPlayers(p)
        setMatches(m)
        setDiagnostics(diag)
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : String(err)))
      .finally(() => setLoading(false))
  }, [token])

  const refreshDiagnostics = async () => {
    if (!token) return
    try {
      const diag = await apiClient.getOpsDiagnostics(token)
      setDiagnostics(diag)
    } catch {
      // ignore
    }
  }

  const handleRetryFailedJobs = async () => {
    if (!token) return
    setOpsBusy(true)
    setOpsStatus('')
    try {
      const res = await apiClient.retryFailedJobs(token)
      setOpsStatus(
        `Recovered ${res.retried_highlight_jobs} highlight job(s) & ${res.recovered_recording_sessions} recording session(s).`
      )
      await refreshDiagnostics()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setOpsBusy(false)
    }
  }

  const handleRetentionDryRun = async () => {
    if (!token) return
    setOpsBusy(true)
    setOpsStatus('')
    try {
      const res = await apiClient.applyRetentionPolicy(token, 90, true)
      setOpsStatus(
        `Retention Check (Dry Run, 90 days): ${res.expired_sessions_found} expired source video recording(s) eligible for cleanup while preserving ${res.highlights_preserved} player highlight(s).`
      )
      await refreshDiagnostics()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setOpsBusy(false)
    }
  }

  const handleBackupAndVerify = async () => {
    if (!token) return
    setOpsBusy(true)
    setOpsStatus('')
    try {
      const manifest = await apiClient.exportBackup(token)
      const verify = await apiClient.verifyBackup(token, manifest.checksum_sha256, manifest.data)
      if (verify.valid) {
        setOpsStatus(
          `Backup exported & verified! SHA-256: ${verify.computed_checksum.slice(0, 16)}… (${JSON.stringify(verify.counts)})`
        )
      } else {
        setError('Backup verification checksum mismatch.')
      }
      await refreshDiagnostics()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setOpsBusy(false)
    }
  }

  const liveMatches = matches.filter((m) => m.status === 'live')

  return (
    <AppShell>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12, marginBottom: 20 }}>
        <div>
          <h1 style={{ margin: '0 0 4px', color: colors.text }}>
            Welcome{user?.name ? `, ${user.name}` : ''}!
          </h1>
          <p style={{ margin: 0, color: colors.textMuted, fontSize: 14 }}>
            Manage your cricket teams, players, live ball-by-ball scoring, and searchable video highlight archives.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Link to="/teams/new"><Button variant="secondary" size="sm">+ Team</Button></Link>
          <Link to="/players/new"><Button variant="secondary" size="sm">+ Player</Button></Link>
          <Link to="/matches/new"><Button size="sm">+ New Match</Button></Link>
        </div>
      </div>

      {error && <div style={{ marginBottom: 16 }}><Alert type="error">{error}</Alert></div>}
      {opsStatus && <div style={{ marginBottom: 16 }}><Alert type="success">{opsStatus}</Alert></div>}

      {/* Live Stats Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 16, marginBottom: 24 }}>
        <Link to="/teams" style={{ textDecoration: 'none' }}>
          <Card style={{ cursor: 'pointer' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span style={{ fontSize: 28 }}>👥</span>
              <span style={{ fontSize: 24, fontWeight: 800, color: colors.primary }}>{loading ? '…' : teams.length}</span>
            </div>
            <div style={{ fontWeight: 700, color: colors.text, marginBottom: 2 }}>Teams</div>
            <div style={{ fontSize: 13, color: colors.textMuted }}>Manage team squads</div>
          </Card>
        </Link>

        <Link to="/players" style={{ textDecoration: 'none' }}>
          <Card style={{ cursor: 'pointer' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span style={{ fontSize: 28 }}>🏏</span>
              <span style={{ fontSize: 24, fontWeight: 800, color: colors.primary }}>{loading ? '…' : players.length}</span>
            </div>
            <div style={{ fontWeight: 700, color: colors.text, marginBottom: 2 }}>Players</div>
            <div style={{ fontSize: 13, color: colors.textMuted }}>Profiles & highlight reels</div>
          </Card>
        </Link>

        <Link to="/matches" style={{ textDecoration: 'none' }}>
          <Card style={{ cursor: 'pointer' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span style={{ fontSize: 28 }}>📋</span>
              <span style={{ fontSize: 24, fontWeight: 800, color: colors.primary }}>{loading ? '…' : matches.length}</span>
            </div>
            <div style={{ fontWeight: 700, color: colors.text, marginBottom: 2 }}>Match Archive</div>
            <div style={{ fontSize: 13, color: colors.textMuted }}>{liveMatches.length} currently live</div>
          </Card>
        </Link>

        <Link to="/matches/new" style={{ textDecoration: 'none' }}>
          <Card style={{ cursor: 'pointer', border: `1px dashed ${colors.primary}`, background: colors.primaryLight }}>
            <div style={{ fontSize: 28, marginBottom: 8 }}>➕</div>
            <div style={{ fontWeight: 700, color: colors.primaryDark, marginBottom: 2 }}>New Match</div>
            <div style={{ fontSize: 13, color: colors.primaryDark }}>Start scoring & recording</div>
          </Card>
        </Link>
      </div>

      {loading ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}><Spinner /></div>
      ) : (
        <div style={{ display: 'grid', gap: 20 }}>
          {/* Recent / Live Matches */}
          <Card>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
              <h2 style={{ margin: 0, fontSize: 17 }}>Recent Matches</h2>
              <Link to="/matches" style={{ fontSize: 13, color: colors.primary, fontWeight: 600, textDecoration: 'none' }}>
                Search full archive →
              </Link>
            </div>

            {matches.length === 0 ? (
              <div style={{ textAlign: 'center', padding: 28, color: colors.textMuted, fontSize: 14 }}>
                No matches created yet.{' '}
                {teams.length < 2 ? (
                  <>First <Link to="/teams/new" style={{ color: colors.primary, fontWeight: 600 }}>create at least 2 teams</Link>, then start a match.</>
                ) : (
                  <Link to="/matches/new" style={{ color: colors.primary, fontWeight: 600 }}>Create your first match →</Link>
                )}
              </div>
            ) : (
              <div style={{ display: 'grid', gap: 10 }}>
                {matches.slice(0, 5).map((m) => (
                  <div
                    key={m.id}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      flexWrap: 'wrap',
                      gap: 10,
                      padding: '12px 14px',
                      borderRadius: 8,
                      border: `1px solid ${colors.border}`,
                      background: '#f8fafc',
                    }}
                  >
                    <div>
                      <Link to={`/matches/${m.id}`} style={{ fontWeight: 700, color: colors.text, textDecoration: 'none', fontSize: 15 }}>
                        {m.title}
                      </Link>
                      <div style={{ fontSize: 12, color: colors.textMuted, marginTop: 2 }}>
                        {m.teams.map((t) => t.team_name).join(' vs ')} · {m.format} {m.tournament ? `· 🏆 ${m.tournament}` : ''} {m.venue ? `· ${m.venue}` : ''}
                      </div>
                    </div>

                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                      <Link
                        to={`/matches/${m.id}/score`}
                        style={{
                          background: colors.primary,
                          color: '#fff',
                          padding: '6px 12px',
                          borderRadius: 6,
                          textDecoration: 'none',
                          fontSize: 12,
                          fontWeight: 700,
                        }}
                      >
                        ⚾ Score
                      </Link>
                      <Link
                        to={`/matches/${m.id}/record`}
                        style={{
                          background: '#dc2626',
                          color: '#fff',
                          padding: '6px 12px',
                          borderRadius: 6,
                          textDecoration: 'none',
                          fontSize: 12,
                          fontWeight: 700,
                        }}
                      >
                        📹 Video
                      </Link>
                      <Link
                        to={`/matches/${m.id}`}
                        style={{
                          background: '#e2e8f0',
                          color: colors.text,
                          padding: '6px 12px',
                          borderRadius: 6,
                          textDecoration: 'none',
                          fontSize: 12,
                          fontWeight: 600,
                        }}
                      >
                        Details
                      </Link>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Phase 6: Production Operations, Media Recovery, Retention & Backup Card */}
          {diagnostics && (
            <Card style={{ background: '#f8fafc', border: `1px solid ${colors.border}` }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12, marginBottom: 12 }}>
                <div>
                  <h2 style={{ margin: 0, fontSize: 16 }}>🛡️ Production Operations, Retention & Backup Status</h2>
                  <p style={{ margin: '2px 0 0', fontSize: 12, color: colors.textMuted }}>
                    Live system health, worker queue diagnostics, media retention policy, and cryptographic backup verification
                  </p>
                </div>
                <span style={{
                  fontSize: 11,
                  fontWeight: 800,
                  padding: '3px 10px',
                  borderRadius: 999,
                  background: diagnostics.status === 'healthy' ? '#dcfce7' : '#fef3c7',
                  color: diagnostics.status === 'healthy' ? '#166534' : '#92400e',
                }}>
                  SYSTEM {diagnostics.status.toUpperCase()}
                </span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 10, marginBottom: 14 }}>
                <div style={{ background: '#fff', padding: '8px 12px', borderRadius: 6, border: `1px solid ${colors.border}` }}>
                  <div style={{ fontSize: 11, color: colors.textMuted }}>Database & Storage</div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: diagnostics.db_connected && diagnostics.storage_connected ? '#166534' : colors.danger }}>
                    {diagnostics.db_connected && diagnostics.storage_connected ? 'Connected ✓' : 'Degraded'}
                  </div>
                </div>
                <div style={{ background: '#fff', padding: '8px 12px', borderRadius: 6, border: `1px solid ${colors.border}` }}>
                  <div style={{ fontSize: 11, color: colors.textMuted }}>Ready Highlights</div>
                  <div style={{ fontSize: 15, fontWeight: 800, color: colors.primary }}>{diagnostics.total_ready_highlights}</div>
                </div>
                <div style={{ background: '#fff', padding: '8px 12px', borderRadius: 6, border: `1px solid ${colors.border}` }}>
                  <div style={{ fontSize: 11, color: colors.textMuted }}>Pending / Failed Jobs</div>
                  <div style={{ fontSize: 15, fontWeight: 800, color: diagnostics.failed_highlight_jobs > 0 ? colors.danger : colors.text }}>
                    {diagnostics.pending_highlight_jobs} / {diagnostics.failed_highlight_jobs}
                  </div>
                </div>
                <div style={{ background: '#fff', padding: '8px 12px', borderRadius: 6, border: `1px solid ${colors.border}` }}>
                  <div style={{ fontSize: 11, color: colors.textMuted }}>Recent Audit Logs</div>
                  <div style={{ fontSize: 15, fontWeight: 800, color: colors.text }}>{diagnostics.recent_audit_logs.length}</div>
                </div>
              </div>

              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <Button size="sm" variant="secondary" loading={opsBusy} onClick={() => { void handleRetryFailedJobs() }}>
                  🔧 Retry Failed Jobs
                </Button>
                <Button size="sm" variant="secondary" loading={opsBusy} onClick={() => { void handleRetentionDryRun() }}>
                  🧹 Check Media Retention (90d)
                </Button>
                <Button size="sm" variant="secondary" loading={opsBusy} onClick={() => { void handleBackupAndVerify() }}>
                  💾 Export & Verify DB Backup
                </Button>
              </div>
            </Card>
          )}
        </div>
      )}
    </AppShell>
  )
}
