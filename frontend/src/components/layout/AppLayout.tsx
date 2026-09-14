import { useEffect, useRef } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { Sidebar } from './Sidebar'

export function AppLayout() {
  const { t } = useTranslation()
  const location = useLocation()
  const mainRef = useRef<HTMLElement>(null)

  useEffect(() => {
    mainRef.current?.focus({ preventScroll: true })
  }, [location.pathname])

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">{t('common.skip_to_content')}</a>
      <Sidebar />
      <main className="app-main" id="main-content" ref={mainRef} tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  )
}
