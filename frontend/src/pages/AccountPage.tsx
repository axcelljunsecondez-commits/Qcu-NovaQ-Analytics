import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQueryClient } from '@tanstack/react-query'
import { changePassword, forgotPassword, linkGoogle } from '../api/auth'
import { useAuth } from '../auth/useAuth'
import { GoogleSignInButton } from '../auth/GoogleSignInButton'
import { ApiState } from '../components/ui/ApiState'

export function AccountPage() {
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [resetSent, setResetSent] = useState(false)
  const [googleLinked, setGoogleLinked] = useState(false)

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  async function handlePasswordChange(event: FormEvent) {
    event.preventDefault()
    setError(null)
    setSuccess(false)
    if (newPassword !== confirmPassword) {
      setError(t('account.password_mismatch'))
      return
    }
    setSubmitting(true)
    try {
      await changePassword(currentPassword, newPassword)
      setSuccess(true)
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (err) {
      const status = (err as { response?: { status?: number } }).response?.status
      setError(
        status === 401
          ? t('account.wrong_current_password')
          : t('account.password_change_failed'),
      )
    } finally {
      setSubmitting(false)
    }
  }

  if (!user) return <ApiState.Loading />

  return (
    <div>
      <h1 className="page-title">{t('account.title')}</h1>

      <div className="card">
        <div className="form-field">
          <label>{t('account.email')}</label>
          <p className="page-caption">{user.email}</p>
        </div>
        <div className="form-field">
          <label>{t('auth.email_status')}</label>
          <span className={`badge ${user.email_verified ? 'badge-ok' : 'badge-warn'}`}>
            {t(user.email_verified ? 'auth.verified' : 'auth.unverified')}
          </span>
        </div>
        <div className="form-field">
          <label>{t('auth.login_methods')}</label>
          <p className="page-caption">{(user.auth_methods ?? (user.has_password === false ? [] : ['password'])).join(', ') || '—'}</p>
        </div>
        <div className="form-field">
          <label>{t('account.role')}</label>
          <span className={`badge ${user.role === 'admin' ? 'badge-ok' : 'badge-neutral'}`}>
            {user.role}
          </span>
        </div>
        <div className="form-field">
          <label>{t('account.created')}</label>
          <p className="page-caption">
            {new Intl.DateTimeFormat(undefined, { dateStyle: 'long' }).format(
              new Date(user.created_at),
            )}
          </p>
        </div>
        <button type="button" className="btn-ghost" onClick={handleLogout}>
          {t('account.logout')}
        </button>
      </div>

      {user.has_password === false ? <div className="card">
        <h2 className="page-title">{t('auth.set_password')}</h2>
        <p className="page-caption">{t('auth.set_password_help')}</p>
        {resetSent && <div role="status" className="alert alert-ok">{t('auth.reset_sent')}</div>}
        <button type="button" onClick={() => void forgotPassword(user.email).then(() => setResetSent(true))}>
          {t('auth.send_reset')}
        </button>
      </div> : <div className="card">
        <h2 className="page-title">{t('account.change_password')}</h2>
        <form onSubmit={handlePasswordChange}>
          <div className="form-field">
            <label htmlFor="account-current-password">{t('account.current_password')}</label>
            <input
              id="account-current-password"
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </div>
          <div className="form-field">
            <label htmlFor="account-new-password">{t('account.new_password')}</label>
            <input
              id="account-new-password"
              type="password"
              minLength={8}
              maxLength={128}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
              autoComplete="new-password"
            />
          </div>
          <div className="form-field">
            <label htmlFor="account-confirm-password">{t('account.confirm_password')}</label>
            <input
              id="account-confirm-password"
              type="password"
              minLength={8}
              maxLength={128}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              autoComplete="new-password"
            />
          </div>
          {error && <div role="alert" className="alert alert-error">{error}</div>}
          {success && <div role="status" className="alert alert-ok">{t('account.password_changed')}</div>}
          <button type="submit" disabled={submitting}>
            {t('account.change_password')}
          </button>
        </form>
      </div>}

      {!user.auth_methods?.includes('google') && <div className="card">
        <h2 className="page-title">{t('auth.link_google')}</h2>
        <p className="page-caption">{t('auth.link_google_help')}</p>
        {googleLinked && <div role="status" className="alert alert-ok">{t('auth.google_linked')}</div>}
        <GoogleSignInButton onCredential={async (credential) => {
          const response = await linkGoogle(credential)
          queryClient.setQueryData(['me'], response.user)
          setGoogleLinked(true)
        }} />
      </div>}
    </div>
  )
}
