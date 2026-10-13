import { ButtonHTMLAttributes, ReactNode } from 'react'
import { colors, radius } from '../../theme'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  children: ReactNode
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled,
  children,
  style,
  ...rest
}: ButtonProps) {
  const bg: Record<string, string> = {
    primary: colors.primary,
    secondary: colors.border,
    danger: colors.danger,
    ghost: 'transparent',
  }
  const fg: Record<string, string> = {
    primary: '#fff',
    secondary: colors.text,
    danger: '#fff',
    ghost: colors.text,
  }
  const pad: Record<string, string> = {
    sm: '6px 12px',
    md: '10px 18px',
    lg: '12px 24px',
  }
  const fontSize: Record<string, number> = { sm: 13, md: 14, lg: 16 }

  return (
    <button
      disabled={disabled || loading}
      style={{
        background: bg[variant],
        color: fg[variant],
        border: variant === 'secondary' ? `1px solid ${colors.border}` : 'none',
        borderRadius: radius.md,
        padding: pad[size],
        fontSize: fontSize[size],
        fontWeight: 600,
        cursor: disabled || loading ? 'not-allowed' : 'pointer',
        opacity: disabled || loading ? 0.65 : 1,
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        transition: 'opacity 150ms',
        ...style,
      }}
      {...rest}
    >
      {loading ? '...' : children}
    </button>
  )
}
