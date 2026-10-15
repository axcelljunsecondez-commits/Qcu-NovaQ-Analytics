import { useEffect, useRef, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { readStorage, writeStorage } from '../../lib/safeStorage'
import { AppHeader } from './AppHeader'
import { Sidebar } from './Sidebar'

export const SIDEBAR_KEY = 'novaq_sidebar'

export function AppLayout() {
  const { t } = useTranslation()
  const location = useLocation()
  const mainRef = useRef<HTMLElement>(null)
  const [collapsed, setCollapsed] = useState(() => readStorage(SIDEBAR_KEY) === 'hidden')

  useEffect(() => {
    mainRef.current?.focus({ preventScroll: true })
  }, [location.pathname])

  function toggleCollapsed() {
    const next = !collapsed
    writeStorage(SIDEBAR_KEY, next ? 'hidden' : 'shown')
    setCollapsed(next)
  }

  return (
    <div className={`app-shell${collapsed ? ' sidebar-collapsed' : ''}`}>
      <a className="skip-link" href="#main-content">{t('common.skip_to_content')}</a>
      <Sidebar collapsed={collapsed} onToggleCollapsed={toggleCollapsed} />
      <main className="app-main" id="main-content" ref={mainRef} tabIndex={-1}>
        <AppHeader />
        <Outlet />
      </main>
    </div>
  )
}
