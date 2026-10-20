import { useEffect, useState, useSyncExternalStore } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { listAnalyses } from '../../api/analyses'
import { useAuth } from '../../auth/useAuth'
import { resolveLastAnalysis, storedLastAnalysis, subscribeLastAnalysis } from '../../lib/lastAnalysis'
import { Tooltip } from '../ui/Tooltip'
import { AccountMenu } from './AccountMenu'
import { navGroups, type NavIconName } from './navigation'

const iconPaths: Record<NavIconName, string> = {
  analyses: 'M6 2h9l5 5v15H6V2Zm8 1.5V8h4.5M9 12h8M9 16h8M9 20h5',
  results: 'M4 20V10m6 10V4m6 16v-8m6 8H2',
  reports: 'M7 3h7l5 5v13H7V3Zm7 0v5h5M10 13h6m-6 4h6',
  simulation: 'M3 4h7v7H3V4Zm11 9h7v7h-7v-7ZM10 7h4v6',
  calculator: 'M5 2h14v20H5V2Zm3 4h8v4H8V6Zm0 8h2m3 0h3m-8 4h2m3 0h3',
}

function NavIcon({ name }: { name: NavIconName }) {
  return (
    <svg className="nav-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path d={iconPaths[name]} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

interface SidebarProps {
  collapsed?: boolean
  onToggleCollapsed?: () => void
}

export function Sidebar({ collapsed = false, onToggleCollapsed }: SidebarProps) {
  const { t } = useTranslation()
  const { user } = useAuth()
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const analyses = useQuery({ queryKey: ['analyses'], queryFn: listAnalyses, enabled: Boolean(user) })
  const storedId = useSyncExternalStore(subscribeLastAnalysis, storedLastAnalysis)
  const lastAnalysisId = resolveLastAnalysis(analyses.data?.analyses, storedId)

  useEffect(() => setOpen(false), [location.pathname])
  useEffect(() => {
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('keydown', closeOnEscape)
    return () => document.removeEventListener('keydown', closeOnEscape)
  }, [])

  const hideLabel = collapsed ? t('nav.show_sidebar') : t('nav.hide_sidebar')

  return (
    <aside className={`sidebar${open ? ' is-open' : ''}${collapsed ? ' is-collapsed' : ''}`}>
      <div className="sidebar-header">
        <div className="sidebar-brand">Nova<b>Q</b></div>
        {onToggleCollapsed && (
          <Tooltip label={hideLabel}>
            <button
              type="button"
              className="sidebar-hide-toggle"
              aria-label={hideLabel}
              aria-expanded={!collapsed}
              aria-controls="global-navigation"
              onClick={onToggleCollapsed}
            >
              <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M9 4v16" /></svg>
            </button>
          </Tooltip>
        )}
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
          {navGroups.map((group) => (
            <div key={group.key} className="nav-section">
              <div className="nav-section-title">{t(`nav.group_${group.key}`)}</div>
              {group.items.map((item) => {
                const active = item.matches(location.pathname)
                const label = t(`nav.${item.key}`)
                return (
                  <Tooltip key={item.key} label={label} enabled={collapsed}>
                    <Link
                      to={item.target(lastAnalysisId)}
                      className={active ? 'active' : undefined}
                      aria-current={active ? 'page' : undefined}
                      aria-label={label}
                    >
                      <NavIcon name={item.icon} />
                      <span className="nav-label">{label}</span>
                    </Link>
                  </Tooltip>
                )
              })}
            </div>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="sidebar-product-note">
            <span>NovaQ v1.0 · {t('nav.capstone')}</span>
            <span>{t('nav.motto')}</span>
          </div>
          <AccountMenu compact={collapsed} />
        </div>
      </div>
    </aside>
  )
}
