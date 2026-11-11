import { useRef, useState } from 'react'
import { Outlet } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { readStorage, writeStorage } from '../../lib/safeStorage'
import { AppHeader } from './AppHeader'
import { usePageContent } from '../../lib/useContentEntrance'
import { Sidebar } from './Sidebar'

export const SIDEBAR_KEY = 'novaq_sidebar'

export function AppLayout() {
  const { t } = useTranslation()
  const mainRef = useRef<HTMLElement>(null)
  const contentRef = usePageContent<HTMLDivElement>(mainRef)
  const [collapsed, setCollapsed] = useState(() => readStorage(SIDEBAR_KEY) === 'hidden')

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
        <div className="route-content" ref={contentRef}><Outlet /></div>
      </main>
    </div>
  )
}
