import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

export function HelpPage() {
  const { t } = useTranslation()

  return (
    <div className="page-stack">
      <header className="page-header">
        <p className="topbar-eyebrow">{t('help.eyebrow')}</p>
        <h1 className="page-title">{t('help.title')}</h1>
        <p className="page-caption">{t('help.subtitle')}</p>
      </header>

      <section className="card" aria-labelledby="help-preferences-title">
        <h2 id="help-preferences-title" className="card-title">{t('help.preferences_title')}</h2>
        <p>{t('help.preferences_desc')}</p>
        <Link className="button-link" to="/settings/preferences">
          {t('help.open_preferences')}
        </Link>
      </section>

      <section className="card" aria-labelledby="help-workflow-title">
        <h2 id="help-workflow-title" className="card-title">{t('help.workflow_title')}</h2>
        <p>{t('help.workflow_desc')}</p>
        <ol className="help-workflow-list">
          {['setup', 'current', 'optimize', 'compare', 'simulate', 'decision', 'reports'].map((step) => (
            <li key={step}>{t(`nav.${step}`)}</li>
          ))}
        </ol>
      </section>

      <section className="card" aria-labelledby="help-limits-title">
        <h2 id="help-limits-title" className="card-title">{t('help.limits_title')}</h2>
        <p>{t('help.limits_desc')}</p>
      </section>
    </div>
  )
}
