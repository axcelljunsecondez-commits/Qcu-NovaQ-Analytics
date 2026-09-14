import { useEffect, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { GoogleSignInButton } from '../auth/GoogleSignInButton'
import { apiErrorCode } from '../auth/fragmentToken'
import { useAuth } from '../auth/useAuth'

function CheckIcon() {
  return (
    <svg className="login-check" viewBox="0 0 24 24" aria-hidden="true">
      <path d="m5 12 4 4L19 6" />
    </svg>
  )
}

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
      setError(apiErrorCode(err) === 'email_not_verified' ? t('auth.email_not_verified') : t('login.error'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="login-page">
      <a className="skip-link" href="#login-form">{t('common.skip_to_content')}</a>
      <section className="login-brand" aria-labelledby="login-hero-title">
        <div className="login-brand-logo">
          <div className="logo">Nova<b>Q</b></div>
          <div className="login-brand-tagline">{t('login.brand_tagline')}</div>
        </div>

        <div className="login-hero">
          <h1 id="login-hero-title">{t('login.hero_title')}<br /><span>{t('login.hero_accent')}</span></h1>
          <h2>{t('login.hero_subtitle')}</h2>
          <p>{t('login.hero_desc')}</p>
          <ul className="login-checks">
            {['current', 'optimize', 'simulate', 'decision'].map((benefit) => (
              <li key={benefit}><CheckIcon />{t(`login.benefit_${benefit}`)}</li>
            ))}
          </ul>
          <div className="login-mini-viz" aria-label={t('login.workflow_preview')}>
            <div className="login-viz-head"><span>{t('login.workflow_preview')}</span></div>
            <div className="login-queue">
              {['observed', 'analysis', 'plan'].map((step, index) => (
                <div className="login-workflow-node" key={step}>
                  {index > 0 && <span className="login-arrow" aria-hidden="true">→</span>}
                  <span>{t(`login.workflow_${step}`)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="login-brand-foot"><span>NovaQ v1.0 · {t('nav.capstone')}</span><span>{t('nav.motto')}</span></div>
      </section>

      <main className="login-auth" id="login-form">
        <div className="login-card">
          <div className="login-mobile-logo">Nova<b>Q</b></div>
          <h2>{t('login.title')}</h2>
          <p className="sub">{t('login.subtitle')}</p>

          <GoogleSignInButton onSuccess={() => navigate(from, { replace: true })} />
          <div className="auth-divider"><span>{t('auth.or')}</span></div>

          <form onSubmit={handleSubmit}>
            <div className="form-field">
              <label htmlFor="login-email">{t('login.email')}</label>
              <input id="login-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder={t('login.email_placeholder')} required autoComplete="username" />
            </div>
            <div className="form-field">
              <label htmlFor="login-password">{t('login.password')}</label>
              <input id="login-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder={t('login.password_placeholder')} required autoComplete="current-password" />
            </div>
            <div className="login-auth-links">
              <Link to="/forgot-password" className="link">{t('auth.forgot')}</Link>
              <Link to="/verify-email" className="link">{t('auth.resend')}</Link>
            </div>
            {error && <div className="alert alert-error" role="alert">{error}</div>}
            <button type="submit" disabled={submitting || isLoading} className="button-full">{t('login.submit')}</button>
          </form>

          <div className="login-new">{t('auth.no_account')} <Link to="/register">{t('auth.register')}</Link></div>
          <div className="login-badge"><strong>{t('login.secure_title')}</strong> {t('login.secure_desc')}</div>
        </div>
      </main>
    </div>
  )
}
