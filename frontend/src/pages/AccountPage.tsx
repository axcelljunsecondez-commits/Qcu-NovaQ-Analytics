import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../auth/useAuth'
import { ApiState } from '../components/ui/ApiState'

export function AccountPage() {
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
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
    </div>
  )
}
