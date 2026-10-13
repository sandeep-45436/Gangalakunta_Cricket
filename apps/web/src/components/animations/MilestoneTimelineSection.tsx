import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Card } from '../ui/Card'
import { Button } from '../ui/Button'
import { broadcastTokens, colors } from '../../theme'
import type { PlayerMilestone } from '../../services/apiClient'
import {
  BroadcastAnimationOverlay,
  useReducedMotion,
  type BroadcastAnimationPayload,
} from './BroadcastAnimationOverlay'

interface MilestoneTimelineSectionProps {
  title?: string
  subtitle?: string
  milestones: PlayerMilestone[]
  showMatchLink?: boolean
  showBroadcastTester?: boolean
}

export function MilestoneTimelineSection({
  title = '🏆 Batting Milestones & Celebrations',
  subtitle = 'Verified 50s and 100s calculated from canonical batter runs — replayable anytime',
  milestones,
  showMatchLink = false,
  showBroadcastTester = false,
}: MilestoneTimelineSectionProps) {
  const [activeAnim, setActiveAnim] = useState<BroadcastAnimationPayload | null>(null)
  const [inlineClip, setInlineClip] = useState<{ url: string; title: string } | null>(null)
  const [reducedMotion, setReducedMotion] = useReducedMotion()

  const triggerMilestoneReplay = (m: PlayerMilestone) => {
    setActiveAnim({
      id: `milestone-${m.id}-${Date.now()}`,
      type: m.milestone_type,
      playerName: m.metadata?.player_name || 'Batter',
      batterScore: m.batter_score,
      ballsFaced: m.balls_faced,
      foursCount: m.fours_count,
      sixesCount: m.sixes_count,
      overDisplay: m.over_display,
      inningsNumber: m.metadata?.innings_number,
      battingTeamName: m.metadata?.batting_team_name,
      bowlerName: m.metadata?.bowler_name,
      highlightStatus: m.highlight_status,
      highlightVideoUrl: m.highlight_video_url,
      highlightThumbnailUrl: m.highlight_thumbnail_url,
      holdOnComplete: true,
    })
  }

  return (
    <Card style={{ marginTop: 24, padding: 20 }}>
      <BroadcastAnimationOverlay
        event={activeAnim}
        onDismiss={() => setActiveAnim(null)}
        onWatchClip={(url, clipTitle) => {
          setActiveAnim(null)
          setInlineClip({ url, title: clipTitle })
        }}
        reducedMotionOverride={reducedMotion}
      />

      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          flexWrap: 'wrap',
          gap: 12,
          marginBottom: 16,
        }}
      >
        <div>
          <h2 style={{ margin: 0, fontSize: 18 }}>{title}</h2>
          <p style={{ margin: '4px 0 0', color: colors.textMuted, fontSize: 13 }}>{subtitle}</p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <label
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              fontSize: 12,
              fontWeight: 600,
              color: colors.textMuted,
              cursor: 'pointer',
              background: '#f8fafc',
              padding: '5px 10px',
              borderRadius: 6,
              border: `1px solid ${colors.border}`,
            }}
          >
            <input
              type="checkbox"
              checked={reducedMotion}
              onChange={(e) => setReducedMotion(e.target.checked)}
            />
            Reduced Motion
          </label>

          {showBroadcastTester && (
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              <Button
                size="sm"
                variant="secondary"
                onClick={() =>
                  setActiveAnim({
                    id: `preview-4-${Date.now()}`,
                    type: 'FOUR',
                    playerName: 'Striker',
                    batterScore: 28,
                    ballsFaced: 19,
                    overDisplay: '4.2',
                    inningsNumber: 1,
                  })
                }
              >
                ▶ 4
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() =>
                  setActiveAnim({
                    id: `preview-6-${Date.now()}`,
                    type: 'SIX',
                    playerName: 'Striker',
                    batterScore: 34,
                    ballsFaced: 20,
                    overDisplay: '4.3',
                    inningsNumber: 1,
                  })
                }
              >
                ▶ 6
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() =>
                  setActiveAnim({
                    id: `preview-50-${Date.now()}`,
                    type: 'FIFTY',
                    playerName: 'Striker',
                    batterScore: 52,
                    ballsFaced: 31,
                    foursCount: 6,
                    sixesCount: 2,
                    overDisplay: '9.4',
                    inningsNumber: 1,
                    highlightStatus: 'unavailable',
                    holdOnComplete: true,
                  })
                }
              >
                ▶ 50
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() =>
                  setActiveAnim({
                    id: `preview-100-${Date.now()}`,
                    type: 'CENTURY',
                    playerName: 'Striker',
                    batterScore: 102,
                    ballsFaced: 58,
                    foursCount: 10,
                    sixesCount: 5,
                    overDisplay: '17.1',
                    inningsNumber: 1,
                    highlightStatus: 'unavailable',
                    holdOnComplete: true,
                  })
                }
              >
                ▶ 100
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Inline Video Modal when user clicks Watch Clip from Milestone Card */}
      {inlineClip && (
        <div
          style={{
            marginBottom: 18,
            padding: 16,
            borderRadius: 10,
            background: '#0f172a',
            color: '#fff',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <span style={{ fontWeight: 700 }}>{inlineClip.title}</span>
            <button
              type="button"
              onClick={() => setInlineClip(null)}
              style={{
                background: 'transparent',
                border: 'none',
                color: '#94a3b8',
                cursor: 'pointer',
                fontSize: 15,
              }}
            >
              ✕ Close
            </button>
          </div>
          <video
            controls
            autoPlay
            src={inlineClip.url}
            style={{ width: '100%', maxHeight: 380, background: '#000', borderRadius: 8 }}
          />
        </div>
      )}

      {milestones.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 28, color: colors.textMuted, fontSize: 14 }}>
          No 50 or 100 batting milestones recorded yet. When a batter's cumulative score crosses{' '}
          <strong>50</strong> or <strong>100</strong> runs, a permanent replayable milestone is created automatically!
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
            gap: 14,
          }}
        >
          {milestones.map((m) => {
            const palette = broadcastTokens.palettes[m.milestone_type] || broadcastTokens.palettes.FIFTY
            const playerName = m.metadata?.player_name || 'Batter'
            const hasClip = m.highlight_status === 'ready' && Boolean(m.highlight_video_url)

            return (
              <div
                key={m.id}
                style={{
                  borderRadius: 12,
                  background: palette.gradient,
                  color: '#fff',
                  padding: 16,
                  border: `1.5px solid ${palette.secondary}`,
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  gap: 12,
                  boxShadow: '0 4px 12px rgba(0,0,0,0.12)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div
                      style={{
                        width: 48,
                        height: 48,
                        borderRadius: 12,
                        background: 'rgba(0,0,0,0.35)',
                        border: `2px solid ${palette.secondary}`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: 20,
                        fontWeight: 900,
                        color: palette.secondary,
                      }}
                    >
                      {m.threshold}
                    </div>
                    <div>
                      <div
                        style={{
                          fontSize: 10,
                          fontWeight: 800,
                          letterSpacing: 1.2,
                          textTransform: 'uppercase',
                          color: palette.accentText,
                        }}
                      >
                        {palette.title}
                        {m.metadata?.innings_number ? ` · Innings ${m.metadata.innings_number}` : ''}
                        {m.over_display ? ` · Ov ${m.over_display}` : ''}
                      </div>
                      <div style={{ fontSize: 17, fontWeight: 800, marginTop: 2 }}>
                        {playerName}{' '}
                        <span style={{ color: palette.secondary }}>
                          {m.batter_score}* ({m.balls_faced}b)
                        </span>
                      </div>
                      <div style={{ fontSize: 12, color: palette.accentText, marginTop: 2 }}>
                        4s: {m.fours_count} · 6s: {m.sixes_count}
                        {m.metadata?.batting_team_name ? ` · ${m.metadata.batting_team_name}` : ''}
                      </div>
                    </div>
                  </div>
                </div>

                {showMatchLink && m.metadata?.match_title && (
                  <div style={{ fontSize: 12, color: palette.accentText }}>
                    Match:{' '}
                    <Link
                      to={`/matches/${m.match_id}`}
                      style={{ color: '#fff', fontWeight: 700, textDecoration: 'underline' }}
                    >
                      {m.metadata.match_title}
                    </Link>
                  </div>
                )}

                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    flexWrap: 'wrap',
                    gap: 8,
                    paddingTop: 10,
                    borderTop: '1px solid rgba(255,255,255,0.18)',
                  }}
                >
                  <button
                    type="button"
                    onClick={() => triggerMilestoneReplay(m)}
                    style={{
                      background: 'rgba(255,255,255,0.2)',
                      border: '1px solid rgba(255,255,255,0.4)',
                      color: '#fff',
                      padding: '6px 12px',
                      borderRadius: 8,
                      fontSize: 12,
                      fontWeight: 800,
                      cursor: 'pointer',
                    }}
                  >
                    ✨ Replay Animation
                  </button>

                  {hasClip && m.highlight_video_url ? (
                    <button
                      type="button"
                      onClick={() =>
                        setInlineClip({
                          url: m.highlight_video_url!,
                          title: `${playerName} · ${palette.title} (${m.batter_score}* off ${m.balls_faced}b)`,
                        })
                      }
                      style={{
                        background: palette.secondary,
                        border: 'none',
                        color: '#0f172a',
                        padding: '6px 12px',
                        borderRadius: 8,
                        fontSize: 12,
                        fontWeight: 900,
                        cursor: 'pointer',
                      }}
                    >
                      🎬 Watch Highlight Clip
                    </button>
                  ) : (
                    <span
                      style={{
                        fontSize: 11,
                        color: palette.accentText,
                        background: 'rgba(0,0,0,0.28)',
                        padding: '4px 8px',
                        borderRadius: 6,
                      }}
                    >
                      {m.highlight_status === 'processing' || m.highlight_status === 'pending'
                        ? '⏳ Clip processing...'
                        : m.highlight_status === 'failed'
                          ? '⚠️ Clip failed'
                          : '📹 No video clip linked'}
                    </span>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </Card>
  )
}
