import { Link, useLocation, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

const workflow = [
  ['setup', 'nav.setup'],
  ['current', 'nav.current'],
  ['optimize', 'nav.optimize'],
  ['compare', 'nav.compare'],
  ['simulate', 'nav.simulate'],
  ['decision', 'nav.decision'],
  ['reports', 'nav.reports'],
] as const

export function WorkflowNavigator() {
  const { t } = useTranslation()
  const { analysisId } = useParams()
  const location = useLocation()
  const current = location.pathname.split('/').pop()
  const index = workflow.findIndex(([path]) => path === current)
  if (!analysisId || index < 0) return null
  const previous = workflow[index - 1]
  const next = workflow[index + 1]

  return (
    <nav className="workflow-footer" aria-label={t('workflow.navigation')}>
      <div>
        <span className="workflow-position">
          {t('workflow.step', { current: index + 1, total: workflow.length })}
        </span>
        <strong>{t(workflow[index][1])}</strong>
      </div>
      <div className="workflow-footer-actions">
        {previous && (
          <Link className="btn-ghost" to={`/analyses/${analysisId}/${previous[0]}`}>
            {t('workflow.back', { step: t(previous[1]) })}
          </Link>
        )}
        {next ? (
          <Link className="btn-primary" to={`/analyses/${analysisId}/${next[0]}`}>
            {t('workflow.next', { step: t(next[1]) })}
          </Link>
        ) : (
          <Link className="btn-primary" to="/analyses">{t('workflow.finish')}</Link>
        )}
      </div>
    </nav>
  )
}
