import React, { useEffect, useState, useRef, useCallback } from 'react'
import { broadcastTokens } from '../../theme'
import type { AnimationEventType, HighlightClipStatus } from '../../services/apiClient'

export interface BroadcastAnimationPayload {
  id: string
  type: AnimationEventType
  playerName: string
  batterScore?: number
  ballsFaced?: number
  foursCount?: number
  sixesCount?: number
  overDisplay?: string | null
  inningsNumber?: number
  battingTeamName?: string
  bowlerName?: string | null
  highlightStatus?: HighlightClipStatus
  highlightVideoUrl?: string | null
  highlightThumbnailUrl?: string | null
  /** If true, stays open after animation completes so user can inspect or replay */
  holdOnComplete?: boolean
}

interface BroadcastAnimationOverlayProps {
  event: BroadcastAnimationPayload | null
  onDismiss: () => void
  onWatchClip?: (videoUrl: string, title: string) => void
  reducedMotionOverride?: boolean
}

/** Hook to read both OS prefers-reduced-motion and user preference in localStorage */
export function useReducedMotion(override?: boolean): [boolean, (val: boolean) => void] {
  const [reduced, setReduced] = useState<boolean>(() => {
    if (override !== undefined) return override
    try {
      const saved = localStorage.getItem('cricket_reduced_motion')
      if (saved !== null) return saved === 'true'
      return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
    } catch {
      return false
    }
  })

  useEffect(() => {
    if (override !== undefined) {
      setReduced(override)
      return
    }
    const mq = window.matchMedia?.('(prefers-reduced-motion: reduce)')
    if (!mq) return
    const handler = (e: MediaQueryListEvent) => {
      if (localStorage.getItem('cricket_reduced_motion') === null) {
        setReduced(e.matches)
      }
    }
    mq.addEventListener?.('change', handler)
    return () => mq.removeEventListener?.('change', handler)
  }, [override])

  const updatePref = useCallback((val: boolean) => {
    setReduced(val)
    try {
      localStorage.setItem('cricket_reduced_motion', String(val))
    } catch {
      // ignore storage errors
    }
  }, [])

  return [reduced, updatePref]
}

/** Error Boundary so animation failures NEVER block score entry or video playback */
class AnimationErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props)
    this.state = { hasError: false }
  }
  static getDerivedStateFromError() {
    return { hasError: true }
  }
  override render() {
    if (this.state.hasError) return null
    return this.props.children
  }
}

const CONFETTI_COLORS = ['#fde047', '#f59e0b', '#38bdf8', '#34d399', '#f43f5e', '#a855f7']

export function BroadcastAnimationOverlay(props: BroadcastAnimationOverlayProps) {
  return (
    <AnimationErrorBoundary>
      <BroadcastAnimationOverlayInner {...props} />
    </AnimationErrorBoundary>
  )
}

function BroadcastAnimationOverlayInner({
  event,
  onDismiss,
  onWatchClip,
  reducedMotionOverride,
}: BroadcastAnimationOverlayProps) {
  const [reducedMotion] = useReducedMotion(reducedMotionOverride)
  const [replayCount, setReplayCount] = useState(0)
  const [displayScore, setDisplayScore] = useState(0)
  const [playingInlineClip, setPlayingInlineClip] = useState(false)
  const timerRef = useRef<number | null>(null)
  const rafRef = useRef<number | null>(null)

  const isMilestone =
    event?.type === 'FIFTY' ||
    event?.type === 'CENTURY' ||
    event?.type === 'ONE_FIFTY' ||
    event?.type === 'DOUBLE_CENTURY'

  const isCenturyOrHigher =
    event?.type === 'CENTURY' ||
    event?.type === 'ONE_FIFTY' ||
    event?.type === 'DOUBLE_CENTURY'

  // Reset inline clip state when event changes
  useEffect(() => {
    setPlayingInlineClip(false)
  }, [event?.id])

  // Count-up animation & auto-dismiss lifecycle
  useEffect(() => {
    if (!event) return

    const targetScore = event.batterScore ?? (event.type === 'FOUR' ? 4 : event.type === 'SIX' ? 6 : 50)

    if (reducedMotion || !isMilestone) {
      setDisplayScore(targetScore)
    } else {
      // Smooth count-up from max(0, targetScore - 25) to targetScore over 900ms
      const startScore = Math.max(0, targetScore - 35)
      const durationMs = 950
      const startTime = performance.now()
      setDisplayScore(startScore)

      const step = (now: number) => {
        const progress = Math.min(1, (now - startTime) / durationMs)
        // Ease-out cubic
        const eased = 1 - Math.pow(1 - progress, 3)
        setDisplayScore(Math.round(startScore + (targetScore - startScore) * eased))
        if (progress < 1) {
          rafRef.current = requestAnimationFrame(step)
        }
      }
      rafRef.current = requestAnimationFrame(step)
    }

    // Auto-dismiss timer unless holdOnComplete or playingInlineClip is active
    if (!event.holdOnComplete && !playingInlineClip) {
      const duration = reducedMotion
        ? broadcastTokens.durations.reducedMotion
        : broadcastTokens.durations[event.type] || 3000

      timerRef.current = window.setTimeout(() => {
        onDismiss()
      }, duration)
    }

    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
      if (rafRef.current) cancelAnimationFrame(rafRef.current)
    }
  }, [event, replayCount, reducedMotion, isMilestone, playingInlineClip, onDismiss])

  // Pause/reset cleanly if tab/app is backgrounded
  useEffect(() => {
    if (!event) return
    const handleVisibility = () => {
      if (document.visibilityState === 'hidden' && timerRef.current) {
        clearTimeout(timerRef.current)
      }
    }
    document.addEventListener('visibilitychange', handleVisibility)
    return () => document.removeEventListener('visibilitychange', handleVisibility)
  }, [event])

  if (!event) return null

  const palette = broadcastTokens.palettes[event.type] || broadcastTokens.palettes.FOUR
  const clipStatus: HighlightClipStatus = event.highlightStatus || 'unavailable'
  const hasReadyClip = clipStatus === 'ready' && Boolean(event.highlightVideoUrl)

  const handleReplayFromBeginning = (e: React.MouseEvent) => {
    e.stopPropagation()
    setPlayingInlineClip(false)
    setReplayCount((c) => c + 1)
  }

  const handleOpenClip = (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!hasReadyClip || !event.highlightVideoUrl) return
    if (onWatchClip) {
      onWatchClip(event.highlightVideoUrl, `${event.playerName} · ${palette.title}`)
    } else {
      setPlayingInlineClip(true)
    }
  }

  return (
    <div
      key={`${event.id}-${replayCount}`}
      role="status"
      aria-live="polite"
      aria-label={`${palette.title} by ${event.playerName}${event.batterScore != null ? `, score ${event.batterScore}` : ''}`}
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        pointerEvents: 'none', // Never block scorecard or delivery buttons underneath!
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: isMilestone ? 'center' : 'flex-start',
        paddingTop: isMilestone ? 0 : 76,
        paddingLeft: 16,
        paddingRight: 16,
      }}
    >
      {/* Keyframes injected once */}
      <style>{`
        @keyframes broadcastImpactIn {
          0% { opacity: 0; transform: scale(0.78) translateY(24px); }
          55% { opacity: 1; transform: scale(1.03) translateY(-3px); }
          100% { opacity: 1; transform: scale(1) translateY(0); }
        }
        @keyframes broadcastSixRise {
          0% { opacity: 0; transform: translateY(42px) scale(0.65); }
          60% { opacity: 1; transform: translateY(-8px) scale(1.08); }
          100% { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes broadcastLightSweep {
          0% { transform: translateX(-120%) skewX(-22deg); }
          100% { transform: translateX(240%) skewX(-22deg); }
        }
        @keyframes broadcastBoundaryFlash {
          0% { opacity: 0.75; }
          100% { opacity: 0; }
        }
        @keyframes broadcastConfettiFall {
          0% { opacity: 1; transform: translateY(-20px) rotate(0deg); }
          100% { opacity: 0; transform: translateY(220px) rotate(320deg); }
        }
      `}</style>

      {/* Subtle screen edge flash for FOUR and SIX (disabled in reduced motion) */}
      {!reducedMotion && (event.type === 'FOUR' || event.type === 'SIX') && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            pointerEvents: 'none',
            boxShadow: `inset 0 0 65px ${palette.glow}`,
            animation: 'broadcastBoundaryFlash 0.75s ease-out forwards',
          }}
        />
      )}

      {/* Controlled Confetti for CENTURY / 150 / 200 (capped at 24 particles, disabled in reduced motion) */}
      {!reducedMotion && isCenturyOrHigher && (
        <div
          aria-hidden="true"
          style={{
            position: 'fixed',
            top: '15%',
            left: '50%',
            width: 520,
            maxWidth: '95vw',
            height: 260,
            transform: 'translateX(-50%)',
            pointerEvents: 'none',
            overflow: 'hidden',
          }}
        >
          {Array.from({ length: broadcastTokens.maxConfettiParticles }).map((_, idx) => {
            const leftPct = (idx * 100) / broadcastTokens.maxConfettiParticles
            const delay = (idx % 6) * 0.12
            const color = CONFETTI_COLORS[idx % CONFETTI_COLORS.length]
            return (
              <span
                key={idx}
                style={{
                  position: 'absolute',
                  top: 0,
                  left: `${leftPct}%`,
                  width: idx % 2 === 0 ? 8 : 6,
                  height: idx % 2 === 0 ? 14 : 8,
                  borderRadius: 2,
                  background: color,
                  animation: `broadcastConfettiFall 2.2s cubic-bezier(0.2, 0.8, 0.4, 1) ${delay}s forwards`,
                }}
              />
            )
          })}
        </div>
      )}

      {/* Main Broadcast Banner / Milestone Card */}
      <div
        style={{
          pointerEvents: 'auto', // Interactive buttons inside card work immediately
          position: 'relative',
          overflow: 'hidden',
          width: '100%',
          maxWidth: isMilestone ? 520 : 440,
          borderRadius: isMilestone ? 18 : 14,
          background: palette.gradient,
          border: `2px solid ${palette.secondary}`,
          boxShadow: `0 20px 45px -10px rgba(0,0,0,0.65), 0 0 32px ${palette.glow}`,
          color: '#ffffff',
          padding: isMilestone ? '22px 24px' : '14px 20px',
          animation: reducedMotion
            ? 'none'
            : event.type === 'SIX'
              ? 'broadcastSixRise 0.48s cubic-bezier(0.22, 1, 0.36, 1) forwards'
              : 'broadcastImpactIn 0.36s cubic-bezier(0.22, 1, 0.36, 1) forwards',
        }}
      >
        {/* Light Sweep Effect for SIX, FIFTY, CENTURY */}
        {!reducedMotion && event.type !== 'FOUR' && (
          <div
            aria-hidden="true"
            style={{
              position: 'absolute',
              top: 0,
              bottom: 0,
              left: 0,
              width: '45%',
              background:
                'linear-gradient(90deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.28) 50%, rgba(255,255,255,0) 100%)',
              animation: 'broadcastLightSweep 1.25s ease-in-out 0.15s forwards',
              pointerEvents: 'none',
            }}
          />
        )}

        {/* Top Row: Badge + Title + Dismiss */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 14 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            {/* Impact Number Emblem */}
            <div
              style={{
                minWidth: isMilestone ? 68 : 52,
                height: isMilestone ? 68 : 52,
                borderRadius: isMilestone ? 16 : 12,
                background: 'rgba(0, 0, 0, 0.35)',
                border: `2px solid ${palette.secondary}`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: isMilestone ? 30 : 26,
                fontWeight: 900,
                color: palette.secondary,
                boxShadow: `0 0 18px ${palette.glow}`,
                letterSpacing: -1,
              }}
            >
              {palette.badge}
            </div>

            <div>
              <div
                style={{
                  fontSize: 11,
                  fontWeight: 800,
                  letterSpacing: 1.6,
                  textTransform: 'uppercase',
                  color: palette.accentText,
                  opacity: 0.9,
                }}
              >
                {palette.subtitle}
                {event.inningsNumber ? ` · INNINGS ${event.inningsNumber}` : ''}
                {event.overDisplay ? ` · OVER ${event.overDisplay}` : ''}
              </div>

              <div
                style={{
                  fontSize: isMilestone ? 26 : 22,
                  fontWeight: 900,
                  letterSpacing: 0.5,
                  lineHeight: 1.15,
                  marginTop: 2,
                }}
              >
                {palette.title}
              </div>

              <div style={{ fontSize: isMilestone ? 18 : 15, fontWeight: 700, marginTop: 2, color: '#fff' }}>
                🏏 {event.playerName}
                {event.batterScore != null && (
                  <span style={{ marginLeft: 8, color: palette.secondary, fontWeight: 900 }}>
                    {displayScore}*
                    {event.ballsFaced != null ? (
                      <span style={{ fontSize: 13, fontWeight: 600, color: palette.accentText }}>
                        {' '}
                        ({event.ballsFaced}b)
                      </span>
                    ) : null}
                  </span>
                )}
              </div>
            </div>
          </div>

          <button
            type="button"
            onClick={onDismiss}
            aria-label="Dismiss animation"
            style={{
              background: 'rgba(0,0,0,0.3)',
              border: '1px solid rgba(255,255,255,0.25)',
              color: '#fff',
              borderRadius: 8,
              padding: '6px 10px',
              fontSize: 12,
              fontWeight: 700,
              cursor: 'pointer',
              alignSelf: 'flex-start',
            }}
          >
            ✕
          </button>
        </div>

        {/* Milestone Stats & Replay Controls (for 50 / 100 / 150 / 200 or held replays) */}
        {(isMilestone || event.holdOnComplete) && (
          <div
            style={{
              marginTop: 14,
              paddingTop: 12,
              borderTop: '1px solid rgba(255,255,255,0.18)',
              display: 'flex',
              flexDirection: 'column',
              gap: 10,
            }}
          >
            {/* Stat Pills */}
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', fontSize: 12, fontWeight: 700 }}>
              {event.battingTeamName && (
                <span style={{ background: 'rgba(0,0,0,0.28)', padding: '4px 10px', borderRadius: 6 }}>
                  🛡️ {event.battingTeamName}
                </span>
              )}
              {event.foursCount != null && (
                <span style={{ background: 'rgba(0,0,0,0.28)', padding: '4px 10px', borderRadius: 6 }}>
                  4s: {event.foursCount}
                </span>
              )}
              {event.sixesCount != null && (
                <span style={{ background: 'rgba(0,0,0,0.28)', padding: '4px 10px', borderRadius: 6 }}>
                  6s: {event.sixesCount}
                </span>
              )}
              {event.ballsFaced && event.ballsFaced > 0 && event.batterScore != null ? (
                <span style={{ background: 'rgba(0,0,0,0.28)', padding: '4px 10px', borderRadius: 6 }}>
                  SR: {((event.batterScore / event.ballsFaced) * 100).toFixed(1)}
                </span>
              ) : null}
              {event.bowlerName && (
                <span style={{ background: 'rgba(0,0,0,0.28)', padding: '4px 10px', borderRadius: 6 }}>
                  vs {event.bowlerName}
                </span>
              )}
            </div>

            {/* Inline Video Player when user clicks Replay Highlight Clip */}
            {playingInlineClip && event.highlightVideoUrl && (
              <div style={{ background: '#000', borderRadius: 10, overflow: 'hidden', marginTop: 4 }}>
                <video
                  controls
                  autoPlay
                  src={event.highlightVideoUrl}
                  poster={event.highlightThumbnailUrl ?? undefined}
                  style={{ width: '100%', maxHeight: 260, display: 'block' }}
                />
              </div>
            )}

            {/* Action Buttons: Replay Animation + Highlight Clip or Explicit Clip Status */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                <button
                  type="button"
                  onClick={handleReplayFromBeginning}
                  style={{
                    background: 'rgba(255,255,255,0.18)',
                    border: '1px solid rgba(255,255,255,0.35)',
                    color: '#fff',
                    padding: '6px 12px',
                    borderRadius: 8,
                    fontSize: 12,
                    fontWeight: 800,
                    cursor: 'pointer',
                  }}
                >
                  ↻ Replay Animation
                </button>

                {hasReadyClip ? (
                  <button
                    type="button"
                    onClick={handleOpenClip}
                    style={{
                      background: palette.secondary,
                      border: 'none',
                      color: '#0f172a',
                      padding: '6px 14px',
                      borderRadius: 8,
                      fontSize: 12,
                      fontWeight: 900,
                      cursor: 'pointer',
                    }}
                  >
                    🎬 Replay Highlight Clip
                  </button>
                ) : (
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      color: palette.accentText,
                      background: 'rgba(0,0,0,0.28)',
                      padding: '5px 10px',
                      borderRadius: 6,
                    }}
                  >
                    {clipStatus === 'processing' || clipStatus === 'pending'
                      ? '⏳ Highlight clip processing in background...'
                      : clipStatus === 'failed'
                        ? '⚠️ Highlight clip processing failed'
                        : '📹 No video clip linked to this delivery'}
                  </span>
                )}
              </div>

              {reducedMotion && (
                <span style={{ fontSize: 10, color: palette.accentText, opacity: 0.85 }}>
                  Reduced Motion Active
                </span>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
