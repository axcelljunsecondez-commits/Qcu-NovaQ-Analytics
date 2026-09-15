import { useEffect, useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../auth/useAuth'
import { LanguageSelector } from './LanguageSelector'
import { ThemeToggle } from './ThemeToggle'

type IconName = 'dashboard' | 'analyses' | 'datasets' | 'calculator' | 'help' | 'account' | 'admin'

interface NavItem {
  key: string
  to: string
  icon: IconName
  adminOnly?: boolean
  end?: boolean
  matchSearch?: string
}

interface NavSection {
  title: string
  items: NavItem[]
}

const navSections: NavSection[] = [
  { title: 'nav.section_overview', items: [{ key: 'dashboard', to: '/dashboard', icon: 'dashboard' }] },
  {
    title: 'nav.section_operation',
    items: [
      { key: 'analyses', to: '/analyses', icon: 'analyses', end: true },
      { key: 'shared_analyses', to: '/analyses?structure=shared_queue', icon: 'analyses', matchSearch: 'structure=shared_queue' },
      { key: 'separate_analyses', to: '/analyses?structure=separate_queues', icon: 'analyses', matchSearch: 'structure=separate_queues' },
      { key: 'datasets', to: '/datasets', icon: 'datasets' },
    ],
  },
  { title: 'nav.section_decision', items: [{ key: 'advanced_analysis', to: '/analysis', icon: 'calculator' }] },
  {
    title: 'nav.section_account',
    items: [
      { key: 'help', to: '/help', icon: 'help' },
      { key: 'account', to: '/account', icon: 'account' },
      { key: 'admin', to: '/admin', icon: 'admin', adminOnly: true },
    ],
  },
]

const iconPaths: Record<IconName, string> = {
  dashboard: 'M3 13h8V3H3v10Zm10 8h8V11h-8v10ZM3 21h8v-6H3v6Zm10-12h8V3h-8v6Z',
  analyses: 'M6 2h9l5 5v15H6V2Zm8 1.5V8h4.5M9 12h8M9 16h8M9 20h5',
  datasets: 'M4 6c0-2 3.6-3 8-3s8 1 8 3-3.6 3-8 3-8-1-8-3Zm0 0v6c0 2 3.6 3 8 3s8-1 8-3V6m-16 6v6c0 2 3.6 3 8 3s8-1 8-3v-6',
  calculator: 'M5 2h14v20H5V2Zm3 4h8v4H8V6Zm0 8h2m3 0h3m-8 4h2m3 0h3',
  help: 'M9.5 9a2.5 2.5 0 1 1 3.4 2.3c-.9.4-1.4 1-1.4 2.2M12 18h.01M22 12A10 10 0 1 1 2 12a10 10 0 0 1 20 0Z',
  account: 'M20 21a8 8 0 0 0-16 0m8-10a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z',
  admin: 'M12 3 4 6v6c0 5 3.4 8 8 9 4.6-1 8-4 8-9V6l-8-3Zm0 5v8m-4-4h8',
}

function NavIcon({ name }: { name: IconName }) {
  return (
    <svg className="nav-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d={iconPaths[name]} fill={name === 'dashboard' ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export function Sidebar() {
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [open, setOpen] = useState(false)

  useEffect(() => setOpen(false), [location.pathname])
  useEffect(() => {
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', closeOnEscape)
    return () => document.removeEventListener('keydown', closeOnEscape)
  }, [])

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <aside className={`sidebar${open ? ' is-open' : ''}`}>
      <div className="sidebar-header">
        <div className="sidebar-brand">Nova<b>Q</b></div>
        <button
          type="button"
          className="sidebar-menu-toggle"
          aria-expanded={open}
          aria-controls="global-navigation"
          aria-label={t('nav.toggle_menu')}
          onClick={() => setOpen((value) => !value)}
        >
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" /></svg>
        </button>
      </div>
      <div className="sidebar-drawer" id="global-navigation">
        <nav className="sidebar-nav" aria-label={t('nav.global_navigation')}>
          {navSections.map((section) => (
            <div key={section.title} className="nav-section">
              <div className="nav-section-title">{t(section.title)}</div>
              {section.items.map((item) => {
                if (item.adminOnly && user?.role !== 'admin') return null
                if (item.matchSearch !== undefined) {
                  const active = location.pathname === '/analyses' && location.search.includes(item.matchSearch)
                  return (
                    <NavLink key={item.key} to={item.to} className={active ? 'active' : undefined}>
                      <NavIcon name={item.icon} />
                      <span>{t(`nav.${item.key}`)}</span>
                    </NavLink>
                  )
                }
                return (
                  <NavLink key={item.key} to={item.to} end={item.end} className={({ isActive }) => (isActive ? 'active' : undefined)}>
                    <NavIcon name={item.icon} />
                    <span>{t(`nav.${item.key}`)}</span>
                  </NavLink>
                )
              })}
            </div>
          ))}
        </nav>
        <div className="sidebar-footer">
          <LanguageSelector />
          <ThemeToggle />
          <div className="sidebar-product-note">
            <span>NovaQ v1.0 · {t('nav.capstone')}</span>
            <span>{t('nav.motto')}</span>
          </div>
          {user && <div className="sidebar-user">{user.email}</div>}
          <button type="button" className="btn-ghost sidebar-logout" onClick={handleLogout}>{t('nav.logout')}</button>
        </div>
      </div>
    </aside>
  )
}
