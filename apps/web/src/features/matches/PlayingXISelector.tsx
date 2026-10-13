/**
 * PlayingXISelector — select 11 distinct players for one team.
 * Includes "Select First 11" shortcut and "Quick Fill 11 Squad Players" helper
 * so users don't have to manually create 11 players one by one if their squad is smaller.
 */
import { useState, useEffect } from 'react'
import { apiClient, type Player, type PlayingXIEntry } from '../../services/apiClient'
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Alert } from '../../components/ui/Alert'
import { Spinner } from '../../components/ui/Spinner'
import { colors } from '../../theme'

interface XIDraft {
  player_id: string
  player_name: string
  batting_position: number | null
  is_captain: boolean
  is_wicketkeeper: boolean
}

interface Props {
  matchId: string
  teamId: string
  teamName: string
  token: string
  onSaved: (xi: PlayingXIEntry[]) => void
}

export function PlayingXISelector({ matchId, teamId, teamName, token, onSaved }: Props) {
  const [squad, setSquad] = useState<Player[]>([])
  const [draft, setDraft] = useState<XIDraft[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [fillingSquad, setFillingSquad] = useState(false)
  const [error, setError] = useState('')
  const [successMsg, setSuccessMsg] = useState('')

  const loadSquadAndXI = () => {
    setLoading(true)
    Promise.all([
      apiClient.listSquad(token, teamId),
      apiClient.getPlayingXI(token, matchId, teamId).catch(() => [] as PlayingXIEntry[]),
    ])
      .then(([rows, xi]) => {
        const players = rows.map((r) => (r as Record<string, unknown>).players as Player).filter(Boolean)
        setSquad(players)
        if (xi.length > 0) {
          setDraft(
            xi.map((e, i) => ({
              player_id: e.player_id,
              player_name: e.player_name,
              batting_position: e.batting_position ?? i + 1,
              is_captain: e.is_captain,
              is_wicketkeeper: e.is_wicketkeeper,
            }))
          )
        }
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    loadSquadAndXI()
  }, [token, matchId, teamId])

  const selectedIds = new Set(draft.map((d) => d.player_id))

  function toggle(player: Player) {
    setSuccessMsg('')
    if (selectedIds.has(player.id)) {
      setDraft((prev) => prev.filter((d) => d.player_id !== player.id))
    } else {
      if (draft.length >= 11) {
        setError('XI already has 11 players — remove one first')
        return
      }
      setDraft((prev) => [
        ...prev,
        {
          player_id: player.id,
          player_name: player.display_name ?? player.full_name,
          batting_position: prev.length + 1,
          is_captain: prev.length === 0,
          is_wicketkeeper: prev.length === 1,
        },
      ])
      setError('')
    }
  }

  function handleSelectFirst11() {
    const first11 = squad.slice(0, 11).map((p, idx) => ({
      player_id: p.id,
      player_name: p.display_name ?? p.full_name,
      batting_position: idx + 1,
      is_captain: idx === 0,
      is_wicketkeeper: idx === 1,
    }))
    setDraft(first11)
    setError('')
    setSuccessMsg('')
  }

  async function handleAutoFillSquadTo11() {
    setFillingSquad(true)
    setError('')
    try {
      const needed = Math.max(0, 11 - squad.length)
      if (needed > 0) {
        const entries = Array.from({ length: needed }, (_, i) => ({
          full_name: `${teamName} Player ${squad.length + i + 1}`,
          role: i < 5 ? 'Batter' : i === 5 ? 'WK' : i < 8 ? 'All-rounder' : 'Bowler',
          jersey_number: squad.length + i + 1,
        }))
        await apiClient.importSquad(token, teamId, entries)
      }
      const rows = await apiClient.listSquad(token, teamId)
      const players = rows.map((r) => (r as Record<string, unknown>).players as Player).filter(Boolean)
      setSquad(players)
      const first11 = players.slice(0, 11).map((p, idx) => ({
        player_id: p.id,
        player_name: p.display_name ?? p.full_name,
        batting_position: idx + 1,
        is_captain: idx === 0,
        is_wicketkeeper: idx === 1,
      }))
      setDraft(first11)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setFillingSquad(false)
    }
  }

  function toggleCaptain(player_id: string) {
    setDraft((prev) =>
      prev.map((d) => ({
        ...d,
        is_captain: d.player_id === player_id ? !d.is_captain : false,
      }))
    )
  }

  function toggleKeeper(player_id: string) {
    setDraft((prev) =>
      prev.map((d) => ({
        ...d,
        is_wicketkeeper: d.player_id === player_id ? !d.is_wicketkeeper : false,
      }))
    )
  }

  async function handleSave() {
    if (draft.length !== 11) {
      setError('Select 11 players to save the official Playing XI')
      return
    }
    setSaving(true)
    setError('')
    setSuccessMsg('')
    try {
      const result = await apiClient.setPlayingXI(token, matchId, {
        team_id: teamId,
        players: draft.map((d, idx) => ({
          player_id: d.player_id,
          batting_position: idx + 1,
          is_captain: d.is_captain,
          is_wicketkeeper: d.is_wicketkeeper,
        })),
      })
      setSuccessMsg(`Saved Playing XI for ${teamName}!`)
      onSaved(result)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setSaving(false)
    }
  }

  const filteredSquad = squad.filter((p) => p.full_name.toLowerCase().includes(search.toLowerCase()))

  if (loading) return <div style={{ display: 'flex', justifyContent: 'center', padding: 20 }}><Spinner /></div>

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
        <h3 style={{ margin: 0, fontSize: 15 }}>
          {teamName} — Playing XI
          <span
            style={{
              marginLeft: 8,
              fontSize: 13,
              color: draft.length === 11 ? colors.primary : colors.warning,
              fontWeight: 700,
            }}
          >
            {draft.length}/11
          </span>
        </h3>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {squad.length < 11 ? (
            <Button size="sm" variant="secondary" loading={fillingSquad} onClick={() => { void handleAutoFillSquadTo11() }}>
              + Auto-Fill Squad to 11 Players
            </Button>
          ) : (
            draft.length < 11 && (
              <Button size="sm" variant="secondary" onClick={handleSelectFirst11}>
                Select First 11
              </Button>
            )
          )}
          <Button size="sm" onClick={() => { void handleSave() }} loading={saving} disabled={draft.length !== 11}>
            Save XI
          </Button>
        </div>
      </div>

      {error && <div style={{ marginBottom: 10 }}><Alert type="error">{error}</Alert></div>}
      {successMsg && <div style={{ marginBottom: 10 }}><Alert type="success">{successMsg}</Alert></div>}

      {/* Selected players */}
      {draft.length > 0 && (
        <div style={{ marginBottom: 12, padding: 12, background: colors.primaryLight, borderRadius: 8 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: colors.primaryDark, marginBottom: 6 }}>SELECTED ({draft.length}/11)</div>
          {draft.map((d, i) => (
            <div key={d.player_id} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '4px 0', fontSize: 13 }}>
              <span style={{ color: colors.textMuted, width: 20 }}>{i + 1}.</span>
              <span style={{ flex: 1 }}>{d.player_name}</span>
              <button
                onClick={() => toggleCaptain(d.player_id)}
                title="Captain"
                style={{
                  background: d.is_captain ? colors.primary : 'transparent',
                  border: `1px solid ${colors.primary}`,
                  color: d.is_captain ? '#fff' : colors.primary,
                  borderRadius: 4,
                  padding: '1px 5px',
                  cursor: 'pointer',
                  fontSize: 11,
                }}
              >
                C
              </button>
              <button
                onClick={() => toggleKeeper(d.player_id)}
                title="Wicketkeeper"
                style={{
                  background: d.is_wicketkeeper ? '#ec4899' : 'transparent',
                  border: '1px solid #ec4899',
                  color: d.is_wicketkeeper ? '#fff' : '#ec4899',
                  borderRadius: 4,
                  padding: '1px 5px',
                  cursor: 'pointer',
                  fontSize: 11,
                }}
              >
                WK
              </button>
              <button
                onClick={() => {
                  const found = squad.find((p) => p.id === d.player_id)
                  if (found) toggle(found)
                  else setDraft((prev) => prev.filter((item) => item.player_id !== d.player_id))
                }}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: colors.danger, fontSize: 14, padding: '1px 4px' }}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Squad picker */}
      <Input placeholder="Search squad…" value={search} onChange={(e) => setSearch(e.target.value)} style={{ marginBottom: 8 }} />

      {squad.length === 0 ? (
        <p style={{ color: colors.textMuted, fontSize: 13 }}>
          No squad members found. Click <strong>+ Auto-Fill Squad to 11 Players</strong> above or add players on the Team page.
        </p>
      ) : (
        filteredSquad.map((player) => {
          const selected = selectedIds.has(player.id)
          return (
            <div
              key={player.id}
              onClick={() => toggle(player)}
              style={{
                display: 'flex',
                alignItems: 'center',
                padding: '8px 10px',
                borderRadius: 6,
                marginBottom: 4,
                cursor: 'pointer',
                background: selected ? colors.primaryLight : '#f9fafb',
                border: `1px solid ${selected ? colors.primary : colors.border}`,
              }}
            >
              <span style={{ flex: 1, fontSize: 14, fontWeight: selected ? 600 : 400 }}>
                {player.full_name}
                {player.role && <span style={{ marginLeft: 6, fontSize: 12, color: colors.textMuted }}>{player.role}</span>}
              </span>
              {selected && <span style={{ color: colors.primary, fontWeight: 700 }}>✓</span>}
            </div>
          )
        })
      )}
    </div>
  )
}
