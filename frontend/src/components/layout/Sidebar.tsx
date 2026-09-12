/**
 * Sidebar navigation for NovaQ frontend.
 * Groups navigation items by section: OVERVIEW, OPERATION, DECISION SUPPORT, OUTPUT.
 * Matches the reference design with gradient background, nav icons, and footer.
 */
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../auth/useAuth'
import { LanguageSelector } from './LanguageSelector'
import { ThemeToggle } from './ThemeToggle'

interface NavSection {
  title: string
  items: NavItem[]
}

interface NavItem {
  key: string
  to: string
  icon: string
  adminOnly?: boolean
  end?: boolean
}

const navSections: NavSection[] = [
  {
    title: 'nav.section_overview',
    items: [
      { key: 'dashboard', to: '/dashboard', icon: '\u2302' },
    ],
  },
  {
    title: 'nav.section_operation',
    items: [
      { key: 'analyses', to: '/analyses', icon: '\u2699', end: true },
      { key: 'datasets', to: '/datasets', icon: '\u21E7' },
    ],
  },
  {
    title: 'nav.section_decision',
    items: [
      { key: 'advanced_analysis', to: '/analysis', icon: '\u2197' },
    ],
  },
  {
    title: 'nav.section_account',
    items: [
      { key: 'account', to: '/account', icon: '\u2699' },
      { key: 'admin', to: '/admin', icon: '\u2699', adminOnly: true },
    ],
  },
]

export function Sidebar() {
  const { t } = useTranslation()
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const analysisId = location.pathname.match(/^\/analyses\/(\d+)(?:\/|$)/)?.[1]
  const sections: NavSection[] = analysisId
    ? [
        ...navSections.slice(0, 2),
        {
          title: 'nav.section_workflow',
          items: [
            { key: 'setup', to: `/analyses/${analysisId}/setup`, icon: '1' },
            { key: 'current', to: `/analyses/${analysisId}/current`, icon: '2' },
            { key: 'optimize', to: `/analyses/${analysisId}/optimize`, icon: '3' },
            { key: 'compare', to: `/analyses/${analysisId}/compare`, icon: '4' },
            { key: 'simulate', to: `/analyses/${analysisId}/simulate`, icon: '5' },
            { key: 'decision', to: `/analyses/${analysisId}/decision`, icon: '6' },
            { key: 'reports', to: `/analyses/${analysisId}/reports`, icon: '7' },
          ],
        },
        ...navSections.slice(2),
      ]
    : navSections

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        Nova<b>Q</b>
      </div>
      <nav className="sidebar-nav">
        {sections.map((section) => (
          <div key={section.title} className="nav-section">
            <div className="nav-section-title">{t(section.title)}</div>
            {section.items.map((item) => {
              if (item.adminOnly && user?.role !== 'admin') {
                return null
              }
              return (
                <NavLink
                  key={item.key}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) => (isActive ? 'active' : undefined)}
                >
                  <span className="nav-icon">{item.icon}</span>
                  {t(`nav.${item.key}`)}
                </NavLink>
              )
            })}
          </div>
        ))}
      </nav>
      <div className="sidebar-footer">
        <LanguageSelector />
        <ThemeToggle />
        <div style={{ marginTop: '14px', borderTop: '1px solid #1d466c', paddingTop: '14px', fontSize: '10px', lineHeight: '1.6', color: '#8ea8c3' }}>
          NovaQ v1.0<br />
          Capstone Project<br /><br />
          Real Data.<br />
          Better Decisions.
        </div>
        {user && (
          <div style={{ marginTop: '8px', fontSize: '10px', color: '#8ea8c3' }}>
            {user.email}
          </div>
        )}
        <button type="button" className="btn-ghost" onClick={handleLogout} style={{ marginTop: '8px', fontSize: '10px' }}>
          {t('nav.logout')}
        </button>
      </div>
    </aside>
  )
}
