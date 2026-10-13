import { ReactNode } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../../features/auth/AuthContext'
import { colors } from '../../theme'

interface AppShellProps { children: ReactNode }

const navItems = [
  { to: '/dashboard', label: '🏠 Dashboard' },
  { to: '/teams', label: '👥 Teams' },
  { to: '/players', label: '🏏 Players' },
  { to: '/matches', label: '📋 Matches' },
]

export function AppShell({ children }: AppShellProps) {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()

  async function handleSignOut() {
    await signOut()
    navigate('/sign-in')
  }

  return (
    <div style={{ minHeight: '100vh', background: '#f0fdf4', fontFamily: 'system-ui, sans-serif' }}>
      {/* Top nav */}
      <nav style={{
        background: colors.primary,
        padding: '0 20px',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        height: 52,
        position: 'sticky',
        top: 0,
        zIndex: 100,
        boxShadow: '0 1px 4px rgba(0,0,0,.15)',
      }}>
        <span style={{ color: '#fff', fontWeight: 700, fontSize: 16, marginRight: 16 }}>🏏 Cricket</span>
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            style={({ isActive }) => ({
              color: isActive ? '#fff' : 'rgba(255,255,255,.75)',
              textDecoration: 'none',
              fontSize: 14,
              fontWeight: isActive ? 700 : 400,
              padding: '4px 8px',
              borderRadius: 6,
              background: isActive ? 'rgba(255,255,255,.15)' : 'transparent',
            })}
          >
            {item.label}
          </NavLink>
        ))}
        <div style={{ flex: 1 }} />
        <span style={{ color: 'rgba(255,255,255,.8)', fontSize: 13 }}>{user?.email}</span>
        <button
          onClick={() => { void handleSignOut() }}
          style={{ background: 'rgba(255,255,255,.15)', border: 'none', color: '#fff', borderRadius: 6, padding: '4px 12px', cursor: 'pointer', fontSize: 13 }}
        >
          Sign out
        </button>
      </nav>

      {/* Page content */}
      <main style={{ maxWidth: 900, margin: '0 auto', padding: '24px 16px' }}>
        {children}
      </main>
    </div>
  )
}
