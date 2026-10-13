/** Design tokens — consistent across all Phase 1–5 screens and broadcast animations. */
export const colors = {
  primary: '#16a34a',       // green-600
  primaryDark: '#15803d',   // green-700
  primaryLight: '#dcfce7',  // green-100
  danger: '#dc2626',        // red-600
  dangerLight: '#fee2e2',
  warning: '#d97706',       // amber-600
  surface: '#ffffff',
  background: '#f0fdf4',    // green-50
  border: '#e5e7eb',        // gray-200
  text: '#111827',          // gray-900
  textMuted: '#6b7280',     // gray-500
  textOnPrimary: '#ffffff',
}

export const radius = { sm: 6, md: 8, lg: 12, xl: 16 }

export const shadow = {
  card: '0 1px 3px 0 rgba(0,0,0,.1), 0 1px 2px -1px rgba(0,0,0,.1)',
  broadcast: '0 20px 45px -10px rgba(0,0,0,0.55), 0 0 30px rgba(255,255,255,0.12)',
}

/** Phase 5 — Sports-Broadcast Animation Tokens */
export const broadcastTokens = {
  durations: {
    FOUR: 1800,           // Short boundary flash so repeated 4s never annoy scorers
    SIX: 2400,            // Dramatic gold/purple rising impact
    FIFTY: 4500,          // Player milestone card with count-up
    CENTURY: 6000,        // Cinematic gold reveal + controlled confetti
    ONE_FIFTY: 5500,
    DOUBLE_CENTURY: 6500,
    reducedMotion: 1800,  // Accessible static reveal duration
  },
  maxConfettiParticles: 24, // Capped to prevent frame drops on mobile/low-end Android devices
  palettes: {
    FOUR: {
      badge: '4',
      title: 'FOUR · +4',
      subtitle: 'BOUNDARY',
      primary: '#0284c7',
      secondary: '#38bdf8',
      glow: 'rgba(56, 189, 248, 0.45)',
      gradient: 'linear-gradient(135deg, #082f49 0%, #0369a1 55%, #0ea5e9 100%)',
      accentText: '#e0f2fe',
    },
    SIX: {
      badge: '6',
      title: 'SIX · +6',
      subtitle: 'MAXIMUM',
      primary: '#d97706',
      secondary: '#fbbf24',
      glow: 'rgba(251, 191, 36, 0.55)',
      gradient: 'linear-gradient(135deg, #3b0764 0%, #6d28d9 45%, #d97706 100%)',
      accentText: '#fef3c7',
    },
    FIFTY: {
      badge: '50',
      title: 'HALF-CENTURY',
      subtitle: 'MILESTONE ACHIEVED',
      primary: '#059669',
      secondary: '#34d399',
      glow: 'rgba(52, 211, 153, 0.5)',
      gradient: 'linear-gradient(135deg, #064e3b 0%, #047857 50%, #0d9488 100%)',
      accentText: '#d1fae5',
    },
    CENTURY: {
      badge: '100',
      title: 'CENTURY',
      subtitle: 'MAGNIFICENT HUNDRED',
      primary: '#b45309',
      secondary: '#fde047',
      glow: 'rgba(250, 204, 21, 0.65)',
      gradient: 'linear-gradient(135deg, #451a03 0%, #92400e 45%, #eab308 100%)',
      accentText: '#fef9c3',
    },
    ONE_FIFTY: {
      badge: '150',
      title: '150 RUNS',
      subtitle: 'MARATHON INNINGS',
      primary: '#7c3aed',
      secondary: '#c4b5fd',
      glow: 'rgba(167, 139, 250, 0.55)',
      gradient: 'linear-gradient(135deg, #2e1065 0%, #5b21b6 50%, #9333ea 100%)',
      accentText: '#ede9fe',
    },
    DOUBLE_CENTURY: {
      badge: '200',
      title: 'DOUBLE CENTURY',
      subtitle: 'HISTORIC LANDMARK',
      primary: '#b91c1c',
      secondary: '#fde047',
      glow: 'rgba(250, 204, 21, 0.7)',
      gradient: 'linear-gradient(135deg, #450a0a 0%, #991b1b 45%, #ca8a04 100%)',
      accentText: '#fef08a',
    },
  },
}
