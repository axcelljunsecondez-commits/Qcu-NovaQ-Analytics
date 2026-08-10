import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { changePassword } from '../api/auth'
import { useAuth } from '../auth/useAuth'
import { ApiState } from '../components/ui/ApiState'

export function AccountPage() {
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [submitting, setSubmitting] = useState(false)

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

      <div className="card">
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
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              autoComplete="new-password"
            />
          </div>
          {error && <div className="alert alert-error">{error}</div>}
          {success && <div className="alert alert-ok">{t('account.password_changed')}</div>}
          <button type="submit" disabled={submitting}>
            {t('account.change_password')}
          </button>
        </form>
      </div>
    </div>
  )
}
