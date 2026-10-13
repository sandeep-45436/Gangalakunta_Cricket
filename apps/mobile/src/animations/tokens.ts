/**
 * Phase 5 — React Native Reanimated Design Tokens for Sports-Broadcast Animations.
 * Shared across Android & iOS screens (Scoring, Match Timeline, Player Profile).
 */
export type AnimationEventType =
  | 'FOUR'
  | 'SIX'
  | 'FIFTY'
  | 'CENTURY'
  | 'ONE_FIFTY'
  | 'DOUBLE_CENTURY'

export type HighlightClipStatus =
  | 'ready'
  | 'processing'
  | 'pending'
  | 'failed'
  | 'unavailable'

export const mobileBroadcastTokens = {
  spacing: {
    xs: 4,
    sm: 8,
    md: 14,
    lg: 20,
    xl: 26,
  },
  radius: {
    sm: 8,
    md: 14,
    lg: 20,
  },
  durations: {
    FOUR: 1800,
    SIX: 2400,
    FIFTY: 4500,
    CENTURY: 6000,
    ONE_FIFTY: 5500,
    DOUBLE_CENTURY: 6500,
    reducedMotion: 1800,
  },
  maxConfettiParticles: 18, // Capped for smooth 60fps UI-thread rendering on Android devices
  palettes: {
    FOUR: {
      badge: '4',
      title: 'FOUR · +4',
      subtitle: 'BOUNDARY IMPACT',
      background: '#0369a1',
      border: '#38bdf8',
      accent: '#e0f2fe',
    },
    SIX: {
      badge: '6',
      title: 'SIX · +6',
      subtitle: 'MAXIMUM',
      background: '#4c1d95',
      border: '#fbbf24',
      accent: '#fef3c7',
    },
    FIFTY: {
      badge: '50',
      title: 'HALF-CENTURY',
      subtitle: 'MILESTONE ACHIEVED',
      background: '#065f46',
      border: '#34d399',
      accent: '#d1fae5',
    },
    CENTURY: {
      badge: '100',
      title: 'CENTURY',
      subtitle: 'MAGNIFICENT HUNDRED',
      background: '#78350f',
      border: '#fde047',
      accent: '#fef9c3',
    },
    ONE_FIFTY: {
      badge: '150',
      title: '150 RUNS',
      subtitle: 'MARATHON INNINGS',
      background: '#4c1d95',
      border: '#c4b5fd',
      accent: '#ede9fe',
    },
    DOUBLE_CENTURY: {
      badge: '200',
      title: 'DOUBLE CENTURY',
      subtitle: 'HISTORIC LANDMARK',
      background: '#7f1d1d',
      border: '#fde047',
      accent: '#fef08a',
    },
  },
}
