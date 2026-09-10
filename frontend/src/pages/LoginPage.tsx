/**
 * LoginPage — Split layout matching the NovaQ reference design.
 * Left: navy gradient hero with branding, queue visualization, and checkmarks.
 * Right: auth card with Google SSO, email/password, and links.
 */
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
      {/* Left — Brand Hero */}
      <section className="login-brand">
        <div className="login-brand-logo">
          <div className="logo">Nova<b>Q</b></div>
          <div className="login-brand-tagline">An Integrated Queueing Analytics and Simulation System</div>
        </div>

        <div className="login-hero">
          <h1>Smarter Queue Decisions<br /><span>for Real Operations.</span></h1>
          <h2>Understand queues. Optimize operations.</h2>
          <p>Analyze observed data, improve staffing, simulate scenarios, compare alternatives, and produce decision-ready reports.</p>
          <div className="login-checks">
            <div><span className="login-check">✓</span>Reduce customer waiting</div>
            <div><span className="login-check">✓</span>Optimize staffing decisions</div>
            <div><span className="login-check">✓</span>Simulate real queue behavior</div>
            <div><span className="login-check">✓</span>Make evidence-based recommendations</div>
          </div>
          <div className="login-mini-viz">
            <div className="login-viz-head">
              <span>ARRIVALS → INDIVIDUAL QUEUES → CASHIERS</span>
              <span>LIVE OPERATION VIEW</span>
            </div>
            <div className="login-queue">
              <span className="login-person" />
              <span className="login-arrow">→</span>
              <div className="login-stations">
                <div className="login-station">Cashier 1</div>
                <div className="login-station">Cashier 2</div>
                <div className="login-station">Cashier 3</div>
              </div>
            </div>
          </div>
        </div>

        <div className="login-brand-foot">
          <span>NovaQ v1.0 · Capstone Prototype</span>
          <span>Real Data. Better Decisions.</span>
        </div>
      </section>

      {/* Right — Auth Card */}
      <main className="login-auth">
        <div className="login-card">
          <div className="login-mobile-logo">Nova<b>Q</b></div>
          <h2>{t('login.title')}</h2>
          <p className="sub">{t('login.subtitle', 'Sign in to continue to your queue analysis workspace.')}</p>

          <GoogleSignInButton onSuccess={() => navigate(from, { replace: true })} />

          <div className="auth-divider"><span>{t('auth.or')}</span></div>

          <form onSubmit={handleSubmit}>
            <div className="form-field">
              <label htmlFor="login-email">{t('login.email')}</label>
              <input
                id="login-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@school.edu.ph"
                required
                autoComplete="username"
              />
            </div>
            <div className="form-field">
              <label htmlFor="login-password">{t('login.password')}</label>
              <div style={{ position: 'relative' }}>
                <input
                  id="login-password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={t('login.password_placeholder', 'Enter your password')}
                  required
                  autoComplete="current-password"
                  style={{ width: '100%', paddingRight: '2.5rem' }}
                />
              </div>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', margin: '-4px 0 18px' }}>
              <Link to="/forgot-password" className="link" style={{ color: 'var(--accent)', fontSize: '12px', fontWeight: 700 }}>
                {t('auth.forgot')}
              </Link>
            </div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', margin: '-10px 0 18px' }}>
              <Link to="/verify-email" className="link" style={{ color: 'var(--accent)', fontSize: '12px', fontWeight: 700 }}>
                {t('auth.resend')}
              </Link>
            </div>
            {error && <div className="alert alert-error">{error}</div>}
            <button type="submit" disabled={submitting || isLoading} style={{ width: '100%' }}>
              {t('login.submit')}
            </button>
          </form>

          <div className="login-new">
            {t('auth.no_account')} <Link to="/register" style={{ color: 'var(--accent)', fontWeight: 700 }}>{t('auth.register')}</Link>
          </div>

          <div className="login-badge">
            <strong>Prototype behavior:</strong> Sign in continues directly to the NovaQ onboarding flow. Authentication is not connected to a production backend in this mockup.
          </div>
        </div>
      </main>
    </div>
  )
}
