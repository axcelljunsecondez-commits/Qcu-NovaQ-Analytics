import { Link, Outlet } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../auth/useAuth'
import { ApiState } from '../ui/ApiState'
import { AppLayout } from './AppLayout'
import { LanguageSelect } from './LanguageSelect'
import { ThemeToggle } from './ThemeToggle'

/**
 * Help is public (spec 2026-10-09 §5, plan U8): a signed-in user reads it inside the app, anyone
 * else in the public frame of the Home page. The guides hold no account data.
 */
export function HelpShell() {
  const { t } = useTranslation()
  const { user, isLoading } = useAuth()
  if (isLoading) return <ApiState.Loading />
  if (user) return <AppLayout />
  return (
    <div className="home-page">
      <a className="skip-link" href="#help-main">{t('common.skip_to_content')}</a>
      <header className="home-header">
        <Link className="home-logo" to="/">Nova<b>Q</b></Link>
        <nav className="home-header-actions" aria-label={t('home.header_navigation')}>
          <LanguageSelect />
          <ThemeToggle />
          <Link className="btn-ghost home-header-link" to="/login">{t('home.sign_in')}</Link>
        </nav>
      </header>
      <main className="home-main" id="help-main" tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  )
}
