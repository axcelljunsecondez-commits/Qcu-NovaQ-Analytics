import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from './useAuth'
import { useTranslation } from 'react-i18next'

export function RequireAuth() {
  const { user, isLoading } = useAuth()
  const location = useLocation()
  const { t } = useTranslation()

  if (isLoading) {
    return (
      <div className="empty-state">
        <div className="spinner" />
        <p>{t('common.loading')}</p>
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  return <Outlet />
}
