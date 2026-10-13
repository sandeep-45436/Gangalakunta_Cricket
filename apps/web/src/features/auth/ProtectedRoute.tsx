import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from './AuthContext'
import { Spinner } from '../../components/ui/Spinner'

/** Redirects unauthenticated users to /sign-in. Shows spinner during auth hydration. */
export function ProtectedRoute() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Spinner size={36} />
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/sign-in" replace />
  }

  return <Outlet />
}
