import { colors } from '../../theme'

export function Spinner({ size = 24 }: { size?: number }) {
  return (
    <div
      role="status"
      aria-label="Loading"
      style={{
        width: size,
        height: size,
        border: `3px solid ${colors.primaryLight}`,
        borderTop: `3px solid ${colors.primary}`,
        borderRadius: '50%',
        animation: 'spin 0.7s linear infinite',
      }}
    >
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </div>
  )
}
