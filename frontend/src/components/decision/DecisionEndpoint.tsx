/**
 * Decision Endpoint - Shows completion status and next actions.
 * This is the final screen in the NovaQ workflow.
 */
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

interface DecisionStep {
  id: string
  label: string
  completed: boolean
}

interface DecisionEndpointProps {
  steps: DecisionStep[]
  analysisId: number
}

export function DecisionEndpoint({ steps, analysisId }: DecisionEndpointProps) {
  const { t } = useTranslation()
  const completedCount = steps.filter((s) => s.completed).length
  const allComplete = completedCount === steps.length

  return (
    <div className="decision-endpoint">
      <div className="card decision-card">
        <h1 className="decision-title">{t('decision.title')}</h1>

        <div className="decision-checklist">
          {steps.map((step) => (
            <div key={step.id} className={`decision-step ${step.completed ? 'completed' : ''}`}>
              <span className="step-check">{step.completed ? '✓' : '○'}</span>
              <span className="step-label">{step.label}</span>
            </div>
          ))}
        </div>

        {allComplete && (
          <div className="decision-success">
            <p>{t('decision.all_complete')}</p>
          </div>
        )}

        <div className="decision-actions">
          <h2>{t('decision.next_actions')}</h2>
          <div className="action-grid">
            <Link to={`/analyses/${analysisId}/compare`} className="action-card">
              <span className="action-icon">📊</span>
              <span className="action-label">{t('decision.use_preferred')}</span>
            </Link>
            <Link to={`/analyses/${analysisId}/optimize`} className="action-card">
              <span className="action-icon">🔄</span>
              <span className="action-label">{t('decision.test_another')}</span>
            </Link>
            <Link to={`/analyses/${analysisId}/simulate`} className="action-card">
              <span className="action-icon">▶</span>
              <span className="action-label">{t('decision.run_simulation')}</span>
            </Link>
            <Link to="/analyses/new" className="action-card">
              <span className="action-icon">➕</span>
              <span className="action-label">{t('decision.new_analysis')}</span>
            </Link>
            <Link to="/dashboard" className="action-card">
              <span className="action-icon">🏠</span>
              <span className="action-label">{t('decision.return_dashboard')}</span>
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}

/**
 * Get completion steps for the current analysis.
 */
export function getCompletionSteps(analysis: {
  queue_setup?: { queue_structure?: string }
  datasets?: Array<{ id: number }>
  scenarios?: Array<{ id: number }>
}, t: (key: string) => string): DecisionStep[] {
  return [
    {
      id: 'setup',
      label: t('decision.step_setup'),
      completed: analysis.queue_setup?.queue_structure != null && analysis.queue_setup.queue_structure !== 'unknown',
    },
    {
      id: 'data',
      label: t('decision.step_data'),
      completed: (analysis.datasets?.length ?? 0) > 0,
    },
    {
      id: 'optimize',
      label: t('decision.step_optimize'),
      completed: (analysis.scenarios?.length ?? 0) > 0,
    },
  ]
}
