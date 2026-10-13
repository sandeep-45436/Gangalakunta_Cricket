import { useEffect, useState, FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { apiClient, type Player } from '../../services/apiClient'
import { AppShell } from '../../components/layout/AppShell'
import { Card } from '../../components/ui/Card'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Alert } from '../../components/ui/Alert'
import { Spinner } from '../../components/ui/Spinner'
import { colors } from '../../theme'

const ROLE_BADGE: Record<string, string> = {
  Batter: '#3b82f6',
  Bowler: '#f59e0b',
  'All-rounder': '#8b5cf6',
  WK: '#ec4899',
}

export function PlayersPage() {
  const { token } = useAuth()
  const [players, setPlayers] = useState<Player[]>([])
  const [filtered, setFiltered] = useState<Player[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Edit modal state
  const [editingPlayer, setEditingPlayer] = useState<Player | null>(null)
  const [editName, setEditName] = useState('')
  const [editDisplay, setEditDisplay] = useState('')
  const [editRole, setEditRole] = useState('')
  const [editJersey, setEditJersey] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!token) return
    apiClient.listPlayers(token)
      .then((p) => { setPlayers(p); setFiltered(p) })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false))
  }, [token])

  useEffect(() => {
    const q = search.toLowerCase()
    setFiltered(players.filter((p) => p.full_name.toLowerCase().includes(q) || (p.display_name ?? '').toLowerCase().includes(q)))
  }, [search, players])

  const openEdit = (p: Player) => {
    setEditingPlayer(p)
    setEditName(p.full_name)
    setEditDisplay(p.display_name ?? '')
    setEditRole(p.role ?? '')
    setEditJersey(p.jersey_number != null ? String(p.jersey_number) : '')
  }

  const handleSaveEdit = async (e: FormEvent) => {
    e.preventDefault()
    if (!token || !editingPlayer || !editName.trim()) return
    setSaving(true)
    setError('')
    try {
      const updated = await apiClient.updatePlayer(token, editingPlayer.id, {
        full_name: editName.trim(),
        display_name: editDisplay.trim() || null,
        role: editRole || null,
        jersey_number: editJersey ? parseInt(editJersey, 10) : null,
      })
      setPlayers((prev) => prev.map((p) => (p.id === updated.id ? updated : p)))
      setEditingPlayer(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (p: Player) => {
    if (!token) return
    if (!window.confirm(`Delete player "${p.full_name}"?`)) return
    try {
      await apiClient.deletePlayer(token, p.id)
      setPlayers((prev) => prev.filter((item) => item.id !== p.id))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  return (
    <AppShell>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <h1 style={{ margin: 0 }}>Players</h1>
        <Link to="/players/new"><Button>+ New player</Button></Link>
      </div>

      <Input placeholder="Search players…" value={search} onChange={(e) => setSearch(e.target.value)} style={{ marginBottom: 16 }} />

      {loading && <div style={{ display: 'flex', justifyContent: 'center', padding: 40 }}><Spinner /></div>}
      {error && <div style={{ marginBottom: 14 }}><Alert type="error">{error}</Alert></div>}

      {editingPlayer && (
        <Card style={{ marginBottom: 20, border: `1px solid ${colors.primary}` }}>
          <h3 style={{ margin: '0 0 12px', fontSize: 16 }}>Edit Player — {editingPlayer.full_name}</h3>
          <form onSubmit={(e) => { void handleSaveEdit(e) }} style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <div style={{ flex: 2, minWidth: 160 }}>
              <Input label="Full Name *" value={editName} onChange={(e) => setEditName(e.target.value)} required />
            </div>
            <div style={{ flex: 1, minWidth: 130 }}>
              <Input label="Display Name" value={editDisplay} onChange={(e) => setEditDisplay(e.target.value)} />
            </div>
            <div style={{ flex: 1, minWidth: 130 }}>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4 }}>Role</label>
              <select
                value={editRole}
                onChange={(e) => setEditRole(e.target.value)}
                style={{ width: '100%', padding: '9px 10px', borderRadius: 8, border: `1px solid ${colors.border}` }}
              >
                <option value="">Not specified</option>
                <option value="Batter">Batter</option>
                <option value="Bowler">Bowler</option>
                <option value="All-rounder">All-rounder</option>
                <option value="WK">Wicketkeeper (WK)</option>
              </select>
            </div>
            <div style={{ width: 90 }}>
              <Input label="Jersey #" type="number" value={editJersey} onChange={(e) => setEditJersey(e.target.value)} />
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <Button type="submit" loading={saving}>Save</Button>
              <Button type="button" variant="secondary" onClick={() => setEditingPlayer(null)}>Cancel</Button>
            </div>
          </form>
        </Card>
      )}

      {!loading && filtered.length === 0 && (
        <Card style={{ textAlign: 'center', padding: 48 }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>🏏</div>
          <p style={{ color: colors.textMuted, marginBottom: 16 }}>{search ? 'No players match your search.' : 'No players yet.'}</p>
          {!search && <Link to="/players/new"><Button>Create player</Button></Link>}
        </Card>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 12 }}>
        {filtered.map((player) => (
          <Card key={player.id} padding={16} style={{ cursor: 'default' }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
              <div style={{ width: 40, height: 40, borderRadius: '50%', background: colors.primaryLight, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18, fontWeight: 700, color: colors.primaryDark, flexShrink: 0 }}>
                {player.full_name[0]}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 700, fontSize: 15 }}>{player.full_name}</div>
                {player.display_name && <div style={{ fontSize: 12, color: colors.textMuted }}>{player.display_name}</div>}
                <div style={{ display: 'flex', gap: 6, marginTop: 4, flexWrap: 'wrap', alignItems: 'center' }}>
                  {player.role && (
                    <span style={{ fontSize: 11, background: ROLE_BADGE[player.role] ?? '#6b7280', color: '#fff', borderRadius: 8, padding: '1px 6px' }}>
                      {player.role}
                    </span>
                  )}
                  {player.jersey_number != null && (
                    <span style={{ fontSize: 11, color: colors.textMuted }}>#{player.jersey_number}</span>
                  )}
                </div>
                <div style={{ marginTop: 10, display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: `1px solid ${colors.border}`, paddingTop: 8 }}>
                  <Link
                    to={`/players/${player.id}/highlights`}
                    style={{
                      fontSize: 12,
                      fontWeight: 700,
                      color: colors.primary,
                      textDecoration: 'none',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 4,
                    }}
                  >
                    🎬 Highlights Reel →
                  </Link>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button
                      onClick={() => openEdit(player)}
                      style={{ background: 'none', border: 'none', fontSize: 12, color: colors.textMuted, cursor: 'pointer' }}
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => { void handleDelete(player) }}
                      style={{ background: 'none', border: 'none', fontSize: 12, color: colors.danger, cursor: 'pointer' }}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </Card>
        ))}
      </div>
    </AppShell>
  )
}
