import { InputHTMLAttributes } from 'react'
import { colors, radius } from '../../theme'

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
}

export function Input({ label, error, style, ...rest }: InputProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      {label && (
        <label style={{ fontSize: 13, fontWeight: 600, color: colors.text }}>
          {label}
        </label>
      )}
      <input
        style={{
          border: `1px solid ${error ? colors.danger : colors.border}`,
          borderRadius: radius.md,
          padding: '9px 12px',
          fontSize: 14,
          color: colors.text,
          outline: 'none',
          width: '100%',
          boxSizing: 'border-box',
          ...style,
        }}
        {...rest}
      />
      {error && (
        <span style={{ fontSize: 12, color: colors.danger }}>{error}</span>
      )}
    </div>
  )
}
