import { Link, Outlet } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../auth/useAuth'
import { ApiState } from '../ui/ApiState'
import { AppLayout } from './AppLayout'
import { LanguageSelect } from './LanguageSelect'
import { ThemeToggle } from './ThemeToggle'

/**
 * Public pages (spec 2026-10-09 §5): Help (plan U8) and the guest Quick calculator (plan U9 + B2). A signed-in
 * user sees them inside the app, anyone else in the public frame of the Home page. Neither holds account data.
 */
export function PublicShell() {
  const { t } = useTranslation()
  const { user, isLoading } = useAuth()
  if (isLoading) return <ApiState.Loading />
  if (user) return <AppLayout />
  return (
    <div className="home-page">
      <a className="skip-link" href="#public-main">{t('common.skip_to_content')}</a>
      <header className="home-header">
        <Link className="home-logo" to="/">Nova<b>Q</b></Link>
        <nav className="home-header-actions" aria-label={t('home.header_navigation')}>
          <LanguageSelect />
          <ThemeToggle />
          <Link className="btn-ghost home-header-link" to="/login">{t('home.sign_in')}</Link>
        </nav>
      </header>
      <main className="home-main" id="public-main" tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  )
}
