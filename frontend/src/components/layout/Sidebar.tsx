import { NavLink, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../auth/useAuth'
import { LanguageSelector } from './LanguageSelector'
import { ThemeToggle } from './ThemeToggle'

interface NavItem {
  key: string
  to: string
  adminOnly?: boolean
}

const navItems: NavItem[] = [
  { key: 'dashboard', to: '/dashboard' },
  { key: 'datasets', to: '/datasets' },
  { key: 'analysis', to: '/analysis' },
  { key: 'optimize', to: '/optimize' },
  { key: 'simulate', to: '/simulate' },
  { key: 'compare', to: '/compare' },
  { key: 'reports', to: '/reports' },
  { key: 'account', to: '/account' },
  { key: 'admin', to: '/admin', adminOnly: true },
]

export function Sidebar() {
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">NovaQ</div>
      <nav className="sidebar-nav">
        {navItems.map((item) => {
          if (item.adminOnly && user?.role !== 'admin') {
            return null
          }
          return (
            <NavLink
              key={item.key}
              to={item.to}
              className={({ isActive }) => (isActive ? 'active' : undefined)}
            >
              {t(`nav.${item.key}`)}
            </NavLink>
          )
        })}
      </nav>
      <LanguageSelector />
      <ThemeToggle />
      <div className="sidebar-footer">
        <button type="button" className="btn-ghost" onClick={handleLogout}>
          {t('nav.logout')}
        </button>
      </div>
    </aside>
  )
}
