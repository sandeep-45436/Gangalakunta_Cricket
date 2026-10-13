import { HTMLAttributes, ReactNode } from 'react'
import { colors, radius, shadow } from '../../theme'

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode
  padding?: number
}

export function Card({ children, padding = 20, style, ...rest }: CardProps) {
  return (
    <div
      style={{
        background: colors.surface,
        borderRadius: radius.lg,
        boxShadow: shadow.card,
        border: `1px solid ${colors.border}`,
        padding,
        ...style,
      }}
      {...rest}
    >
      {children}
    </div>
  )
}
