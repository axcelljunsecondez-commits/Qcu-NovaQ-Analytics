import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { forgotPassword } from '../api/auth'

export function ForgotPasswordPage() {
  const { t } = useTranslation()
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  async function submit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await forgotPassword(email)
      setSent(true)
    } catch {
      setError(t('auth.request_failed'))
    } finally {
      setSubmitting(false)
    }
  }
  return <div className="login-page"><div className="card login-card">
    <h1 className="login-title">{t('auth.forgot_title')}</h1>
    {sent ? <div className="alert alert-ok">{t('auth.reset_sent')}</div> : <form onSubmit={submit}>
      <div className="form-field"><label htmlFor="forgot-email">{t('login.email')}</label><input id="forgot-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" /></div>
      {error && <div role="alert" className="alert alert-error">{error}</div>}
      <button type="submit" disabled={submitting}>{t('auth.send_reset')}</button>
    </form>}
    <Link to="/login">{t('auth.back_login')}</Link>
  </div></div>
}
