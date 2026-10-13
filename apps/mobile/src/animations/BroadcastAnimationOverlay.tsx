/**
 * Phase 5 — React Native Reanimated Sports-Broadcast Animation Overlay.
 * Non-blocking (`pointerEvents="box-none"`), accessible, reduced-motion aware,
 * and resilient to app backgrounding and mid-animation interruption.
 */
import React, { useEffect, useState, useCallback } from 'react'
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  AppState,
  type AppStateStatus,
} from 'react-native'
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withSpring,
  withTiming,
  withSequence,
  cancelAnimation,
  useReducedMotion,
  Easing,
} from 'react-native-reanimated'
import {
  mobileBroadcastTokens,
  type AnimationEventType,
  type HighlightClipStatus,
} from './tokens'

export interface MobileBroadcastEvent {
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
  holdOnComplete?: boolean
}

interface Props {
  event: MobileBroadcastEvent | null
  onDismiss: () => void
  onOpenHighlightClip?: (videoUrl: string) => void
}

export function BroadcastAnimationOverlay({
  event,
  onDismiss,
  onOpenHighlightClip,
}: Props) {
  const systemReducedMotion = useReducedMotion()
  const [replayVersion, setReplayVersion] = useState(0)
  const [displayScore, setDisplayScore] = useState(0)

  // Shared values running on the UI thread
  const opacity = useSharedValue(0)
  const scale = useSharedValue(0.82)
  const translateY = useSharedValue(28)
  const sweepX = useSharedValue(-220)
  const flashOpacity = useSharedValue(0)

  const startAnimation = useCallback(() => {
    if (!event) return

    // Cancel any previous animations before starting or replaying
    cancelAnimation(opacity)
    cancelAnimation(scale)
    cancelAnimation(translateY)
    cancelAnimation(sweepX)
    cancelAnimation(flashOpacity)

    const targetScore = event.batterScore ?? (event.type === 'FOUR' ? 4 : event.type === 'SIX' ? 6 : 50)
    setDisplayScore(targetScore)

    if (systemReducedMotion) {
      opacity.value = withTiming(1, { duration: 150 })
      scale.value = 1
      translateY.value = 0
      flashOpacity.value = 0
      return
    }

    opacity.value = withTiming(1, { duration: 220 })

    if (event.type === 'SIX') {
      // Dramatic rising number and bounce
      translateY.value = 46
      scale.value = 0.68
      translateY.value = withSpring(0, { damping: 12, stiffness: 140 })
      scale.value = withSequence(
        withTiming(1.08, { duration: 260, easing: Easing.out(Easing.cubic) }),
        withSpring(1, { damping: 14, stiffness: 160 }),
      )
      sweepX.value = -220
      sweepX.value = withTiming(420, { duration: 950, easing: Easing.inOut(Easing.quad) })
      flashOpacity.value = withSequence(
        withTiming(0.55, { duration: 140 }),
        withTiming(0, { duration: 480 }),
      )
    } else if (event.type === 'FOUR') {
      // Fast blue impact
      translateY.value = 18
      scale.value = 0.85
      translateY.value = withTiming(0, { duration: 220 })
      scale.value = withSpring(1, { damping: 15, stiffness: 200 })
      flashOpacity.value = withSequence(
        withTiming(0.45, { duration: 110 }),
        withTiming(0, { duration: 360 }),
      )
    } else {
      // FIFTY / CENTURY / 150 / 200 milestone celebration
      translateY.value = 24
      scale.value = 0.8
      translateY.value = withSpring(0, { damping: 14, stiffness: 130 })
      scale.value = withSequence(
        withTiming(1.05, { duration: 300 }),
        withSpring(1, { damping: 14, stiffness: 150 }),
      )
      sweepX.value = -240
      sweepX.value = withTiming(460, { duration: 1100, easing: Easing.inOut(Easing.quad) })
    }
  }, [event, systemReducedMotion, opacity, scale, translateY, sweepX, flashOpacity])

  useEffect(() => {
    if (!event) return
    startAnimation()

    if (event.holdOnComplete) return
    const duration = systemReducedMotion
      ? mobileBroadcastTokens.durations.reducedMotion
      : mobileBroadcastTokens.durations[event.type] || 3000

    const timer = setTimeout(() => {
      onDismiss()
    }, duration)

    return () => clearTimeout(timer)
  }, [event, replayVersion, systemReducedMotion, startAnimation, onDismiss])

  // Handle AppState backgrounding cleanly
  useEffect(() => {
    const subscription = AppState.addEventListener('change', (nextState: AppStateStatus) => {
      if (nextState !== 'active') {
        cancelAnimation(opacity)
        cancelAnimation(scale)
        cancelAnimation(translateY)
        cancelAnimation(sweepX)
        cancelAnimation(flashOpacity)
      }
    })
    return () => subscription.remove()
  }, [opacity, scale, translateY, sweepX, flashOpacity])

  const cardAnimatedStyle = useAnimatedStyle(() => ({
    opacity: opacity.value,
    transform: [{ translateY: translateY.value }, { scale: scale.value }],
  }))

  const sweepAnimatedStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: sweepX.value }, { skewX: '-20deg' }],
  }))

  if (!event) return null

  const palette = mobileBroadcastTokens.palettes[event.type]
  const isMilestone =
    event.type === 'FIFTY' ||
    event.type === 'CENTURY' ||
    event.type === 'ONE_FIFTY' ||
    event.type === 'DOUBLE_CENTURY'
  const clipStatus = event.highlightStatus || 'unavailable'
  const hasReadyClip = clipStatus === 'ready' && Boolean(event.highlightVideoUrl)

  return (
    <View
      pointerEvents="box-none"
      style={styles.overlayContainer}
      accessible
      accessibilityRole="alert"
      accessibilityLiveRegion="polite"
      accessibilityLabel={`${palette.title} by ${event.playerName}, score ${displayScore}`}
    >
      <Animated.View
        style={[
          styles.card,
          { backgroundColor: palette.background, borderColor: palette.border },
          cardAnimatedStyle,
        ]}
      >
        {!systemReducedMotion && event.type !== 'FOUR' && (
          <Animated.View pointerEvents="none" style={[styles.lightSweep, sweepAnimatedStyle]} />
        )}

        <View style={styles.headerRow}>
          <View style={[styles.badgeBox, { borderColor: palette.border }]}>
            <Text style={[styles.badgeText, { color: palette.border }]}>{palette.badge}</Text>
          </View>

          <View style={styles.titleBlock}>
            <Text style={[styles.subtitle, { color: palette.accent }]}>
              {palette.subtitle}
              {event.inningsNumber ? ` · INN ${event.inningsNumber}` : ''}
              {event.overDisplay ? ` · OV ${event.overDisplay}` : ''}
            </Text>
            <Text style={styles.title}>{palette.title}</Text>
            <Text style={styles.playerLine}>
              {event.playerName}{' '}
              {event.batterScore != null ? (
                <Text style={{ color: palette.border, fontWeight: '900' }}>
                  {displayScore}* ({event.ballsFaced ?? 0}b)
                </Text>
              ) : null}
            </Text>
          </View>

          <TouchableOpacity
            onPress={onDismiss}
            accessibilityRole="button"
            accessibilityLabel="Dismiss celebration"
            style={styles.closeBtn}
          >
            <Text style={styles.closeBtnText}>✕</Text>
          </TouchableOpacity>
        </View>

        {isMilestone && (
          <View style={styles.actionsRow}>
            <TouchableOpacity
              onPress={() => setReplayVersion((v) => v + 1)}
              accessibilityRole="button"
              accessibilityLabel="Replay milestone animation from beginning"
              style={styles.replayBtn}
            >
              <Text style={styles.replayBtnText}>↻ Replay Animation</Text>
            </TouchableOpacity>

            {hasReadyClip && event.highlightVideoUrl ? (
              <TouchableOpacity
                onPress={() => onOpenHighlightClip?.(event.highlightVideoUrl!)}
                accessibilityRole="button"
                accessibilityLabel="Watch associated highlight video clip"
                style={[styles.clipBtn, { backgroundColor: palette.border }]}
              >
                <Text style={styles.clipBtnText}>🎬 Replay Clip</Text>
              </TouchableOpacity>
            ) : (
              <View style={styles.statusPill}>
                <Text style={[styles.statusPillText, { color: palette.accent }]}>
                  {clipStatus === 'processing' || clipStatus === 'pending'
                    ? '⏳ Clip processing...'
                    : clipStatus === 'failed'
                      ? '⚠️ Clip extraction failed'
                      : '📹 No video clip linked'}
                </Text>
              </View>
            )}
          </View>
        )}
      </Animated.View>
    </View>
  )
}

const styles = StyleSheet.create({
  overlayContainer: {
    ...StyleSheet.absoluteFillObject,
    justifyContent: 'flex-start',
    alignItems: 'center',
    paddingTop: 64,
    paddingHorizontal: 16,
    zIndex: 999,
  },
  card: {
    width: '100%',
    maxWidth: 460,
    borderRadius: mobileBroadcastTokens.radius.lg,
    borderWidth: 2,
    padding: mobileBroadcastTokens.spacing.lg,
    overflow: 'hidden',
    elevation: 10,
  },
  lightSweep: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    width: 110,
    backgroundColor: 'rgba(255,255,255,0.2)',
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  badgeBox: {
    width: 56,
    height: 56,
    borderRadius: 14,
    borderWidth: 2,
    backgroundColor: 'rgba(0,0,0,0.35)',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  badgeText: {
    fontSize: 24,
    fontWeight: '900',
  },
  titleBlock: {
    flex: 1,
  },
  subtitle: {
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 1.2,
  },
  title: {
    fontSize: 22,
    fontWeight: '900',
    color: '#ffffff',
  },
  playerLine: {
    fontSize: 15,
    fontWeight: '700',
    color: '#ffffff',
    marginTop: 2,
  },
  closeBtn: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    backgroundColor: 'rgba(0,0,0,0.3)',
  },
  closeBtnText: {
    color: '#ffffff',
    fontWeight: '700',
  },
  actionsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 14,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255,255,255,0.18)',
  },
  replayBtn: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
    backgroundColor: 'rgba(255,255,255,0.18)',
  },
  replayBtnText: {
    color: '#ffffff',
    fontSize: 12,
    fontWeight: '800',
  },
  clipBtn: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
  },
  clipBtnText: {
    color: '#0f172a',
    fontSize: 12,
    fontWeight: '900',
  },
  statusPill: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 6,
    backgroundColor: 'rgba(0,0,0,0.28)',
  },
  statusPillText: {
    fontSize: 11,
    fontWeight: '600',
  },
})
