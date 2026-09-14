import { Link, useLocation, useParams } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { analysisWorkflow } from '../../lib/workflow'

export function WorkflowNavigator() {
  const { t } = useTranslation()
  const { analysisId } = useParams()
  const location = useLocation()
  const current = location.pathname.split('/').pop()
  const index = analysisWorkflow.findIndex(([path]) => path === current)
  if (!analysisId || index < 0) return null
  const previous = analysisWorkflow[index - 1]
  const next = analysisWorkflow[index + 1]

  return (
    <nav className="workflow-footer" aria-label={t('workflow.navigation')}>
      <div className="workflow-summary">
        <span className="workflow-position">
          {t('workflow.step', { current: index + 1, total: analysisWorkflow.length })}
        </span>
        <strong>{t(analysisWorkflow[index][1])}</strong>
      </div>
      <ol className="workflow-stepper">
        {analysisWorkflow.map(([path, label], stepIndex) => (
          <li key={path} className={stepIndex === index ? 'active' : undefined}>
            <Link to={`/analyses/${analysisId}/${path}`} aria-current={stepIndex === index ? 'step' : undefined}>
              <span aria-hidden="true">{stepIndex + 1}</span>
              {t(label)}
            </Link>
          </li>
        ))}
      </ol>
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
