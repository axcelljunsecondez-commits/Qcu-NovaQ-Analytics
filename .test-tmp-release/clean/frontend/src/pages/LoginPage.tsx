import { useEffect, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { GoogleSignInButton } from '../auth/GoogleSignInButton'
import { apiErrorCode } from '../auth/fragmentToken'
import { useAuth } from '../auth/useAuth'

export function LoginPage() {
  const { t } = useTranslation()
  const { login, isLoading, user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [loginComplete, setLoginComplete] = useState(false)

  const from = (location.state as { from?: string } | null)?.from ?? '/analyses'

  // The query cache update can notify React after mutateAsync resolves.
  // Wait for the authenticated context before entering the protected route.
  useEffect(() => {
    if (loginComplete && user) navigate(from, { replace: true })
  }, [loginComplete, user, from, navigate])

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login(email, password)
      setLoginComplete(true)
    } catch (err) {
      setError(
        apiErrorCode(err) === 'email_not_verified'
          ? t('auth.email_not_verified')
          : t('login.error'),
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="login-page">
      <div className="card login-card">
        <h1 className="login-title">{t('login.title')}</h1>
        <form onSubmit={handleSubmit}>
          <div className="form-field">
            <label htmlFor="login-email">{t('login.email')}</label>
            <input
              id="login-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </div>
          <div className="form-field">
            <label htmlFor="login-password">{t('login.password')}</label>
            <input
              id="login-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </div>
          {error && <div className="alert alert-error">{error}</div>}
          <button type="submit" disabled={submitting || isLoading}>
            {t('login.submit')}
          </button>
        </form>
        <div className="auth-divider"><span>{t('auth.or')}</span></div>
        <GoogleSignInButton onSuccess={() => navigate(from, { replace: true })} />
        <div className="auth-links">
          <span>{t('auth.no_account')} <Link to="/register">{t('auth.register')}</Link></span>
          <Link to="/forgot-password">{t('auth.forgot')}</Link>
          <Link to="/register?mode=resend">{t('auth.resend')}</Link>
        </div>
      </div>
    </div>
  )
}
