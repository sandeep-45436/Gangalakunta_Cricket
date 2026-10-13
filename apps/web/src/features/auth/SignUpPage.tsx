/**
 * Sign-up page — handles full registration flow:
 * 1. Sign up form
 * 2. 6-digit code verification (requireEmailVerification=true, verifyEmailMethod="code")
 */
import { FormEvent, useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from './AuthContext'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { Button } from '../../components/ui/Button'
import { Alert } from '../../components/ui/Alert'
import { colors } from '../../theme'

type Step = 'register' | 'verify'

export function SignUpPage() {
  const { signUp, verifyEmail, resendVerification, signInWithOAuth } = useAuth()
  const navigate = useNavigate()
  const [step, setStep] = useState<Step>('register')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [otp, setOtp] = useState('')
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleRegister(e: FormEvent) {
    e.preventDefault()
    setError('')
    if (password.length < 6) { setError('Password must be at least 6 characters'); return }
    setLoading(true)
    try {
      const { requiresVerification } = await signUp(email, password, name)
      if (requiresVerification) {
        setStep('verify')
        setInfo('A 6-digit code was sent to your email.')
      } else {
        navigate('/dashboard')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign up failed')
    } finally {
      setLoading(false)
    }
  }

  async function handleVerify(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await verifyEmail(email, otp)
      navigate('/dashboard')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Verification failed')
    } finally {
      setLoading(false)
    }
  }

  async function handleResend() {
    setError('')
    setInfo('')
    try {
      await resendVerification(email)
      setInfo('A new code was sent to your email.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to resend')
    }
  }

  return (
    <div style={{ minHeight: '100vh', background: '#f0fdf4', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <Card style={{ width: '100%', maxWidth: 400 }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div style={{ fontSize: 32, marginBottom: 4 }}>🏏</div>
          <h1 style={{ margin: 0, fontSize: 22, color: colors.text }}>
            {step === 'register' ? 'Create account' : 'Verify your email'}
          </h1>
          {step === 'verify' && (
            <p style={{ margin: '6px 0 0', fontSize: 13, color: colors.textMuted }}>
              Enter the 6-digit code sent to <strong>{email}</strong>
            </p>
          )}
        </div>

        {error && <Alert type="error">{error}</Alert>}
        {info && <Alert type="success">{info}</Alert>}

        {step === 'register' ? (
          <>
            <form onSubmit={(e) => { void handleRegister(e) }} style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
              <Input label="Name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Your name" autoComplete="name" />
              <Input label="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" autoComplete="email" required />
              <Input label="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Min 6 characters" autoComplete="new-password" required />
              <Button type="submit" loading={loading} style={{ width: '100%', justifyContent: 'center', marginTop: 4 }}>
                Create account
              </Button>
            </form>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8, margin: '18px 0' }}>
              <hr style={{ flex: 1, border: 'none', borderTop: `1px solid ${colors.border}` }} />
              <span style={{ fontSize: 12, color: colors.textMuted }}>or</span>
              <hr style={{ flex: 1, border: 'none', borderTop: `1px solid ${colors.border}` }} />
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              <Button variant="secondary" style={{ flex: 1, justifyContent: 'center' }} onClick={() => { void signInWithOAuth('google') }}>Google</Button>
              <Button variant="secondary" style={{ flex: 1, justifyContent: 'center' }} onClick={() => { void signInWithOAuth('github') }}>GitHub</Button>
            </div>
            <p style={{ textAlign: 'center', marginTop: 18, fontSize: 13, color: colors.textMuted }}>
              Have an account? <Link to="/sign-in" style={{ color: colors.primary, fontWeight: 600 }}>Sign in</Link>
            </p>
          </>
        ) : (
          <form onSubmit={(e) => { void handleVerify(e) }} style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
            <Input
              label="Verification code"
              value={otp}
              onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))}
              placeholder="123456"
              inputMode="numeric"
              maxLength={6}
              autoFocus
              required
            />
            <Button type="submit" loading={loading} disabled={otp.length !== 6} style={{ width: '100%', justifyContent: 'center' }}>
              Verify email
            </Button>
            <button
              type="button"
              onClick={() => { void handleResend() }}
              style={{ background: 'none', border: 'none', color: colors.primary, fontSize: 13, cursor: 'pointer', textDecoration: 'underline' }}
            >
              Resend code
            </button>
          </form>
        )}
      </Card>
    </div>
  )
}
