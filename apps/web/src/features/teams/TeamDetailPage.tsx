/**
 * Team detail page — shows team info, edit/delete team, squad members,
 * quick create player into squad, add from library, and bulk import.
 */
import { useEffect, useState, FormEvent } from 'react'
import { useParams, Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { apiClient, type Team, type Player } from '../../services/apiClient'
import { AppShell } from '../../components/layout/AppShell'
import { Card } from '../../components/ui/Card'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Alert } from '../../components/ui/Alert'
import { Spinner } from '../../components/ui/Spinner'
import { colors } from '../../theme'

interface SquadEntry {
  id: string
  player_id: string
  is_active: boolean
  players: Player
}

export function TeamDetailPage() {
  const { teamId } = useParams<{ teamId: string }>()
  const navigate = useNavigate()
  const { token } = useAuth()
  const [team, setTeam] = useState<Team | null>(null)
  const [squad, setSquad] = useState<SquadEntry[]>([])
  const [allPlayers, setAllPlayers] = useState<Player[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [addSearch, setAddSearch] = useState('')
  const [addLoading, setAddLoading] = useState<string | null>(null)
  const [removeLoading, setRemoveLoading] = useState<string | null>(null)

  // Quick create player in squad
  const [newPlayerName, setNewPlayerName] = useState('')
  const [newPlayerRole, setNewPlayerRole] = useState('Batter')
  const [newPlayerJersey, setNewPlayerJersey] = useState('')
  const [creatingPlayer, setCreatingPlayer] = useState(false)

  // Bulk import
  const [importText, setImportText] = useState('')
  const [importResult, setImportResult] = useState('')
  const [importLoading, setImportLoading] = useState(false)
  const [showImport, setShowImport] = useState(false)

  // Edit / Delete team
  const [editingTeam, setEditingTeam] = useState(false)
  const [editName, setEditName] = useState('')
  const [editShortName, setEditShortName] = useState('')
  const [savingTeam, setSavingTeam] = useState(false)
  const [deletingTeam, setDeletingTeam] = useState(false)

  useEffect(() => {
    if (!token || !teamId) return
    Promise.all([
      apiClient.getTeam(token, teamId),
      apiClient.listSquad(token, teamId),
      apiClient.listPlayers(token),
    ]).then(([t, s, p]) => {
      setTeam(t)
      setEditName(t.name)
      setEditShortName(t.short_name ?? '')
      setSquad(s as unknown as SquadEntry[])
      setAllPlayers(p)
    }).catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false))
  }, [token, teamId])

  const squadIds = new Set(squad.map((s) => s.player_id))
  const filteredPlayers = allPlayers.filter(
    (p) => !squadIds.has(p.id) && p.full_name.toLowerCase().includes(addSearch.toLowerCase())
  )

  async function handleUpdateTeam(e: FormEvent) {
    e.preventDefault()
    if (!token || !teamId || !editName.trim()) return
    setSavingTeam(true)
    setError('')
    try {
      const updated = await apiClient.updateTeam(token, teamId, {
        name: editName.trim(),
        short_name: editShortName.trim() || null,
      })
      setTeam(updated)
      setEditingTeam(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setSavingTeam(false)
    }
  }

  async function handleDeleteTeam() {
    if (!token || !teamId || !team) return
    if (!window.confirm(`Delete team "${team.name}"?`)) return
    setDeletingTeam(true)
    try {
      await apiClient.deleteTeam(token, teamId)
      navigate('/teams')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setDeletingTeam(false)
    }
  }

  async function handleQuickCreatePlayer(e: FormEvent) {
    e.preventDefault()
    if (!token || !teamId || !newPlayerName.trim()) return
    setCreatingPlayer(true)
    setError('')
    try {
      const p = await apiClient.createPlayer(token, {
        full_name: newPlayerName.trim(),
        role: newPlayerRole || null,
        jersey_number: newPlayerJersey ? parseInt(newPlayerJersey, 10) : null,
      })
      await apiClient.addSquadMember(token, teamId, p.id)
      const [updatedSquad, updatedPlayers] = await Promise.all([
        apiClient.listSquad(token, teamId),
        apiClient.listPlayers(token),
      ])
      setSquad(updatedSquad as unknown as SquadEntry[])
      setAllPlayers(updatedPlayers)
      setNewPlayerName('')
      setNewPlayerJersey('')
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setCreatingPlayer(false)
    }
  }

  async function addPlayer(playerId: string) {
    if (!token || !teamId) return
    setAddLoading(playerId)
    try {
      await apiClient.addSquadMember(token, teamId, playerId)
      const updated = await apiClient.listSquad(token, teamId)
      setSquad(updated as unknown as SquadEntry[])
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setAddLoading(null)
    }
  }

  async function removePlayer(playerId: string) {
    if (!token || !teamId) return
    setRemoveLoading(playerId)
    try {
      await apiClient.removeSquadMember(token, teamId, playerId)
      setSquad((prev) => prev.filter((s) => s.player_id !== playerId))
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setRemoveLoading(null)
    }
  }

  async function handleImport(e: FormEvent) {
    e.preventDefault()
    if (!token || !teamId) return
    setImportLoading(true)
    setImportResult('')
    try {
      const lines = importText.split('\n').map((l) => l.trim()).filter(Boolean)
      const players = lines.map((line) => {
        const parts = line.split(',').map((s) => s.trim())
        return {
          full_name: parts[0],
          role: parts[1] || null,
          jersey_number: parts[2] ? parseInt(parts[2], 10) : null,
        }
      })
      const result = await apiClient.importSquad(token, teamId, players)
      setImportResult(`Created: ${result.created}, Skipped: ${result.skipped}${result.errors.length ? `, Errors: ${result.errors.join('; ')}` : ''}`)
      const [updatedSquad, updatedPlayers] = await Promise.all([
        apiClient.listSquad(token, teamId),
        apiClient.listPlayers(token),
      ])
      setSquad(updatedSquad as unknown as SquadEntry[])
      setAllPlayers(updatedPlayers)
      setImportText('')
    } catch (e) {
      setImportResult(`Error: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setImportLoading(false)
    }
  }

  if (loading) return <AppShell><div style={{ display: 'flex', justifyContent: 'center', padding: 60 }}><Spinner /></div></AppShell>

  return (
    <AppShell>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10, marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Link to="/teams" style={{ color: colors.textMuted, textDecoration: 'none', fontSize: 14 }}>← Teams</Link>
          <span style={{ color: colors.border }}>/</span>
          <h1 style={{ margin: 0, color: colors.text }}>{team?.name ?? '…'}</h1>
          {team?.short_name && <span style={{ background: colors.primaryLight, color: colors.primaryDark, padding: '2px 8px', borderRadius: 12, fontSize: 12, fontWeight: 700 }}>{team.short_name}</span>}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <Button size="sm" variant="secondary" onClick={() => setEditingTeam(!editingTeam)}>
            {editingTeam ? 'Cancel Edit' : '✎ Edit Team'}
          </Button>
          <Button size="sm" variant="danger" loading={deletingTeam} onClick={() => { void handleDeleteTeam() }}>
            Delete Team
          </Button>
        </div>
      </div>

      {error && <div style={{ marginBottom: 12 }}><Alert type="error">{error}</Alert></div>}

      {editingTeam && (
        <Card style={{ marginBottom: 20 }}>
          <form onSubmit={(e) => { void handleUpdateTeam(e) }} style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
            <div style={{ flex: 2, minWidth: 200 }}>
              <Input label="Team Name" value={editName} onChange={(e) => setEditName(e.target.value)} required />
            </div>
            <div style={{ flex: 1, minWidth: 120 }}>
              <Input label="Short Name" value={editShortName} onChange={(e) => setEditShortName(e.target.value)} maxLength={10} />
            </div>
            <Button type="submit" loading={savingTeam}>Save Changes</Button>
          </form>
        </Card>
      )}

      {/* Quick Create & Add Player to Squad */}
      <Card style={{ marginBottom: 20 }}>
        <h2 style={{ margin: '0 0 12px', fontSize: 16 }}>Quick Add New Player to Squad</h2>
        <form onSubmit={(e) => { void handleQuickCreatePlayer(e) }} style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <div style={{ flex: 2, minWidth: 180 }}>
            <Input
              label="Player Full Name *"
              placeholder="e.g. Rohit Sharma"
              value={newPlayerName}
              onChange={(e) => setNewPlayerName(e.target.value)}
              required
            />
          </div>
          <div style={{ flex: 1, minWidth: 130 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: colors.text, marginBottom: 4 }}>Role</label>
            <select
              value={newPlayerRole}
              onChange={(e) => setNewPlayerRole(e.target.value)}
              style={{ width: '100%', padding: '9px 10px', borderRadius: 8, border: `1px solid ${colors.border}`, fontSize: 14 }}
            >
              <option value="Batter">Batter</option>
              <option value="Bowler">Bowler</option>
              <option value="All-rounder">All-rounder</option>
              <option value="WK">Wicketkeeper (WK)</option>
            </select>
          </div>
          <div style={{ width: 90 }}>
            <Input
              label="Jersey #"
              type="number"
              placeholder="45"
              value={newPlayerJersey}
              onChange={(e) => setNewPlayerJersey(e.target.value)}
            />
          </div>
          <Button type="submit" loading={creatingPlayer} disabled={!newPlayerName.trim()}>
            + Create & Add
          </Button>
        </form>
      </Card>

      {/* Squad list */}
      <Card style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
          <h2 style={{ margin: 0, fontSize: 16 }}>
            Squad Roster <span style={{ background: colors.border, borderRadius: 12, padding: '2px 8px', fontSize: 13 }}>{squad.length}</span>
          </h2>
          <Button size="sm" variant="secondary" onClick={() => setShowImport(!showImport)}>
            {showImport ? 'Cancel Bulk Import' : '📋 Bulk Import Players'}
          </Button>
        </div>

        {showImport && (
          <form onSubmit={(e) => { void handleImport(e) }} style={{ marginBottom: 16, padding: 12, background: '#f9fafb', borderRadius: 8 }}>
            <p style={{ margin: '0 0 8px', fontSize: 13, color: colors.textMuted }}>
              Enter one player per line (format: <code>Full Name</code> or <code>Full Name, Role, Jersey#</code>):
            </p>
            <textarea
              value={importText}
              onChange={(e) => setImportText(e.target.value)}
              rows={6}
              placeholder={"Virat Kohli, Batter, 18\nRohit Sharma, Batter, 45\nJasprit Bumrah, Bowler, 93"}
              style={{ width: '100%', border: `1px solid ${colors.border}`, borderRadius: 6, padding: 8, fontSize: 13, boxSizing: 'border-box', resize: 'vertical' }}
            />
            {importResult && <p style={{ margin: '6px 0 0', fontSize: 13, color: colors.primary, fontWeight: 600 }}>{importResult}</p>}
            <Button type="submit" size="sm" loading={importLoading} style={{ marginTop: 8 }}>Import Players</Button>
          </form>
        )}

        {squad.length === 0 ? (
          <p style={{ color: colors.textMuted, textAlign: 'center', padding: 20 }}>No players in squad yet. Use Quick Add or Bulk Import above.</p>
        ) : (
          squad.map((entry) => (
            <div key={entry.id} style={{ display: 'flex', alignItems: 'center', padding: '8px 0', borderBottom: `1px solid ${colors.border}` }}>
              <div style={{ flex: 1 }}>
                <Link to={`/players/${entry.player_id}/highlights`} style={{ fontWeight: 600, color: colors.text, textDecoration: 'none' }}>
                  {entry.players?.full_name ?? entry.player_id}
                </Link>
                {entry.players?.role && <span style={{ marginLeft: 8, fontSize: 12, color: colors.textMuted }}>{entry.players.role}</span>}
                {entry.players?.jersey_number != null && <span style={{ marginLeft: 8, fontSize: 12, color: colors.textMuted }}>#{entry.players.jersey_number}</span>}
              </div>
              <Button
                size="sm"
                variant="danger"
                loading={removeLoading === entry.player_id}
                onClick={() => { void removePlayer(entry.player_id) }}
              >
                Remove
              </Button>
            </div>
          ))
        )}
      </Card>

      {/* Add player from existing players */}
      <Card>
        <h2 style={{ margin: '0 0 12px', fontSize: 16 }}>Add Existing Player from Library</h2>
        <Input
          placeholder="Search players…"
          value={addSearch}
          onChange={(e) => setAddSearch(e.target.value)}
          style={{ marginBottom: 12 }}
        />
        {filteredPlayers.length === 0 ? (
          <p style={{ color: colors.textMuted, fontSize: 13 }}>
            {addSearch ? 'No matching players not already in squad.' : 'All existing players are already in this squad.'}
          </p>
        ) : (
          filteredPlayers.slice(0, 20).map((p) => (
            <div key={p.id} style={{ display: 'flex', alignItems: 'center', padding: '7px 0', borderBottom: `1px solid ${colors.border}` }}>
              <span style={{ flex: 1, fontSize: 14 }}>{p.full_name} {p.role && <span style={{ color: colors.textMuted, fontSize: 12 }}>· {p.role}</span>}</span>
              <Button
                size="sm"
                loading={addLoading === p.id}
                onClick={() => { void addPlayer(p.id) }}
              >
                Add
              </Button>
            </div>
          ))
        )}
      </Card>
    </AppShell>
  )
}
