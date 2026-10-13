import { ReactNode } from 'react'
import { colors, radius } from '../../theme'

interface AlertProps {
  type: 'error' | 'success' | 'info'
  children: ReactNode
}

const styles = {
  error: { bg: colors.dangerLight, border: colors.danger, text: colors.danger },
  success: { bg: colors.primaryLight, border: colors.primary, text: colors.primaryDark },
  info: { bg: '#eff6ff', border: '#3b82f6', text: '#1d4ed8' },
}

export function Alert({ type, children }: AlertProps) {
  const s = styles[type]
  return (
    <div
      role="alert"
      style={{
        background: s.bg,
        border: `1px solid ${s.border}`,
        borderRadius: radius.md,
        padding: '10px 14px',
        fontSize: 13,
        color: s.text,
        lineHeight: 1.5,
      }}
    >
      {children}
    </div>
  )
}
