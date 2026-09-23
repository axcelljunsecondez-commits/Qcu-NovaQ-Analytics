import { useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { resetPassword } from '../api/auth'
import { clearFragment, readFragmentToken } from '../auth/fragmentToken'

export function ResetPasswordPage() {
  const { t } = useTranslation()
  // Read without scrubbing during render: a suspended first render is discarded,
  // and scrubbing there would leave the retried render with no token.
  const [token] = useState(() => readFragmentToken())
  useEffect(() => clearFragment(), [])
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [state, setState] = useState<'form' | 'success' | 'invalid'>(token ? 'form' : 'invalid')
  const [error, setError] = useState<string | null>(null)
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (password !== confirm) { setError(t('account.password_mismatch')); return }
    if (!token) { setState('invalid'); return }
    try { await resetPassword(token, password); setState('success') } catch { setState('invalid') }
  }
  return <div className="login-page"><div className="card login-card">
    <h1 className="login-title">{t('auth.reset_title')}</h1>
    {state === 'form' && <form onSubmit={submit}>
      <div className="form-field"><label htmlFor="reset-password">{t('account.new_password')}</label><input id="reset-password" type="password" minLength={8} maxLength={128} value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="new-password" /></div>
      <div className="form-field"><label htmlFor="reset-confirm">{t('auth.confirm_password')}</label><input id="reset-confirm" type="password" minLength={8} maxLength={128} value={confirm} onChange={(e) => setConfirm(e.target.value)} required autoComplete="new-password" /></div>
      {error && <div className="alert alert-error">{error}</div>}
      <button type="submit">{t('auth.reset_password')}</button>
    </form>}
    {state === 'success' && <div className="alert alert-ok">{t('auth.reset_success')}</div>}
    {state === 'invalid' && <div className="alert alert-error">{t('auth.reset_invalid')}</div>}
    <Link to="/login">{t('auth.back_login')}</Link>
  </div></div>
}
