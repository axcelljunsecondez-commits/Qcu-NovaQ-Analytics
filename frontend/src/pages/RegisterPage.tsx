import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { register, resendVerification } from '../api/auth'

export function RegisterPage() {
  const { t } = useTranslation()
  const [params] = useSearchParams()
  const resend = params.get('mode') === 'resend'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError(null)
    if (!resend && password !== confirm) {
      setError(t('account.password_mismatch'))
      return
    }
    setSubmitting(true)
    try {
      if (resend) await resendVerification(email)
      else await register(email, password)
      setSent(true)
    } catch {
      setError(t('auth.registration_failed'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="login-page"><div className="card login-card">
      <h1 className="login-title">{t(resend ? 'auth.resend_title' : 'auth.register_title')}</h1>
      {sent ? <div className="alert alert-ok">{t('auth.verification_sent')}</div> : (
        <form onSubmit={submit}>
          <div className="form-field"><label htmlFor="register-email">{t('login.email')}</label><input id="register-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" /></div>
          {!resend && <>
            <div className="form-field"><label htmlFor="register-password">{t('login.password')}</label><input id="register-password" type="password" minLength={8} maxLength={128} value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="new-password" /></div>
            <div className="form-field"><label htmlFor="register-confirm">{t('auth.confirm_password')}</label><input id="register-confirm" type="password" minLength={8} maxLength={128} value={confirm} onChange={(e) => setConfirm(e.target.value)} required autoComplete="new-password" /></div>
          </>}
          {error && <div className="alert alert-error">{error}</div>}
          <button type="submit" disabled={submitting}>{t(resend ? 'auth.resend' : 'auth.register')}</button>
        </form>
      )}
      <Link to="/login">{t('auth.back_login')}</Link>
    </div></div>
  )
}
