import { Outlet } from 'react-router-dom'
import { useAuth } from './useAuth'
import { useTranslation } from 'react-i18next'

export function RequireRole({ role }: { role: 'admin' }) {
  const { user } = useAuth()
  const { t } = useTranslation()

  if (user?.role !== role) {
    return (
      <div className="card error-state">
        <h2>{t('errors.forbidden')}</h2>
      </div>
    )
  }

  return <Outlet />
}
