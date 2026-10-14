import { useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ThemeToggle } from './ThemeToggle'
import { breadcrumbKeys } from './navigation'

export function AppHeader() {
  const { t } = useTranslation()
  const location = useLocation()
  const crumbs = breadcrumbKeys(location.pathname)

  return (
    <header className="app-header">
      {crumbs.length > 0 ? (
        <nav aria-label={t('nav.breadcrumb')} className="app-breadcrumb">
          <ol>
            {crumbs.map((key, index) => (
              <li key={key} aria-current={index === crumbs.length - 1 ? 'page' : undefined}>{t(key)}</li>
            ))}
          </ol>
        </nav>
      ) : <span />}
      <ThemeToggle />
    </header>
  )
}
