import { NavLink, Navigate, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../auth/useAuth'
import { LanguageSelector } from '../components/layout/LanguageSelector'
import { ThemeToggle } from '../components/layout/ThemeToggle'
import { isSettingsSection, settingsSections, type SettingsSection } from '../components/layout/navigation'
import { AccountPage } from './AccountPage'
import { AdminPage } from './AdminPage'
import { DatasetsPage } from './DatasetsPage'
import { PreferencesSettings } from '../components/settings/PreferencesSettings'

function AppearanceSettings() {
  const { t } = useTranslation()
  return (
    <div>
      <h1 className="page-title">{t('settings.section_appearance')}</h1>
      <div className="card settings-appearance">
        <h2 className="card-title">{t('settings.theme')}</h2>
        <ThemeToggle />
        <h2 className="card-title">{t('language.label')}</h2>
        <LanguageSelector />
        <p className="form-hint">{t('settings.saved_on_device')}</p>
      </div>
    </div>
  )
}

function SectionContent({ section }: { section: SettingsSection }) {
  switch (section) {
    case 'account':
      return <AccountPage />
    case 'preferences':
      return <PreferencesSettings />
    case 'appearance':
      return <AppearanceSettings />
    case 'files':
      return <DatasetsPage />
    case 'users':
      return <AdminPage />
  }
}

// Settings composes the existing Account, Datasets and Admin pages unchanged
// (spec §7.10). Preferences are saved through B1 (/account/preferences).
// The router wraps /settings/users in RequireRole, as it wrapped /admin before.
export function SettingsPage({ section: fixedSection }: { section?: SettingsSection }) {
  const { t } = useTranslation()
  const { user } = useAuth()
  const params = useParams()
  const section = fixedSection ?? params.section
  if (!isSettingsSection(section)) return <Navigate to="/settings/account" replace />
  const visible = settingsSections.filter((item) => item !== 'users' || user?.role === 'admin')

  return (
    <div className="settings-page">
      <nav className="settings-sections" aria-label={t('settings.sections')}>
        {visible.map((item) => (
          <NavLink key={item} to={`/settings/${item}`} className={({ isActive }) => (isActive ? 'active' : undefined)}>
            {t(`settings.section_${item}`)}
          </NavLink>
        ))}
      </nav>
      <SectionContent section={section} />
    </div>
  )
}
