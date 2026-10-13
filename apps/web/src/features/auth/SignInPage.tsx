import { FormEvent, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from './AuthContext'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { Button } from '../../components/ui/Button'
import { Alert } from '../../components/ui/Alert'
import { colors } from '../../theme'

export function SignInPage() {
  const { signIn, signInWithOAuth } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await signIn(email, password)
      navigate('/dashboard')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign in failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', background: '#f0fdf4', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <Card style={{ width: '100%', maxWidth: 400 }}>
        <div style={{ textAlign: 'center', marginBottom: 20 }}>
          <div style={{ fontSize: 32, marginBottom: 4 }}>🏏</div>
          <h1 style={{ margin: 0, fontSize: 22, color: colors.text }}>Cricket Highlights</h1>
          <p style={{ margin: '4px 0 0', color: colors.textMuted, fontSize: 14 }}>Sign in to your account</p>
        </div>

        {error && <Alert type="error">{error}</Alert>}

        <form onSubmit={(e) => { void handleSubmit(e) }} style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <Input
            label="Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            autoComplete="email"
            required
          />
          <Input
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            autoComplete="current-password"
            required
          />
          <Button type="submit" loading={loading} style={{ width: '100%', justifyContent: 'center', marginTop: 4 }}>
            Sign in
          </Button>
        </form>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '18px 0' }}>
          <hr style={{ flex: 1, border: 'none', borderTop: `1px solid ${colors.border}` }} />
          <span style={{ fontSize: 12, color: colors.textMuted }}>or continue with</span>
          <hr style={{ flex: 1, border: 'none', borderTop: `1px solid ${colors.border}` }} />
        </div>

        <div style={{ display: 'flex', gap: 10 }}>
          <Button variant="secondary" style={{ flex: 1, justifyContent: 'center' }} onClick={() => { void signInWithOAuth('google') }}>
            Google
          </Button>
          <Button variant="secondary" style={{ flex: 1, justifyContent: 'center' }} onClick={() => { void signInWithOAuth('github') }}>
            GitHub
          </Button>
        </div>

        <p style={{ textAlign: 'center', marginTop: 18, fontSize: 13, color: colors.textMuted }}>
          No account?{' '}
          <Link to="/sign-up" style={{ color: colors.primary, fontWeight: 600 }}>Sign up</Link>
        </p>
      </Card>

    </div>
  )
}
