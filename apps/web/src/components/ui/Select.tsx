import { SelectHTMLAttributes } from 'react'
import { colors, radius } from '../../theme'

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
  error?: string
  options: Array<{ value: string; label: string }>
}

export function Select({ label, error, options, style, ...rest }: SelectProps) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      {label && (
        <label style={{ fontSize: 13, fontWeight: 600, color: colors.text }}>
          {label}
        </label>
      )}
      <select
        style={{
          border: `1px solid ${error ? colors.danger : colors.border}`,
          borderRadius: radius.md,
          padding: '9px 12px',
          fontSize: 14,
          color: colors.text,
          background: '#fff',
          width: '100%',
          boxSizing: 'border-box',
          ...style,
        }}
        {...rest}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      {error && <span style={{ fontSize: 12, color: colors.danger }}>{error}</span>}
    </div>
  )
}
