import { useTranslation } from 'react-i18next'
import type { WorkflowDecision } from '../../api/workflow'

interface DecisionEndpointProps {
  decision: WorkflowDecision | null
  decisionStale: boolean
  isPending: boolean
  error: string | null
  onDerive: () => void
}

const statusClasses: Record<WorkflowDecision['status'], string> = {
  insufficient_evidence: 'badge-warn',
  revise: 'badge-bad',
  adopt: 'badge-ok',
  conditional: 'badge-warn',
}

export function DecisionEndpoint({
  decision,
  decisionStale,
  isPending,
  error,
  onDerive,
}: DecisionEndpointProps) {
  const { t } = useTranslation()
  return (
    <div className="decision-endpoint">
      <div className="topbar">
        <div>
          <div className="topbar-eyebrow">{t('decision.eyebrow')}</div>
          <h1 className="page-title">{t('decision.title')}</h1>
          <p className="page-caption">{t('decision.description')}</p>
        </div>
        <button type="button" className="btn-primary" disabled={isPending} onClick={onDerive}>
          {isPending ? t('common.loading') : t('decision.derive')}
        </button>
      </div>

      {decisionStale && <div className="alert alert-warn">{t('decision.stale')}</div>}
      {error && <div role="alert" className="alert alert-error">{error}</div>}
      {(!decision || decisionStale) && (
        <div className="card">
          <h2 className="card-title">{t('decision.no_decision')}</h2>
          <p className="form-hint">{t('decision.no_decision_help')}</p>
        </div>
      )}
      {decision && !decisionStale && (
        <div className="card decision-card">
          <span className={`badge ${statusClasses[decision.status]}`}>
            {t(`decision.status.${decision.status}`)}
          </span>
          <h2 className="decision-title">{decision.headline}</h2>
          <p className="decision-recommendation">{decision.recommendation}</p>

          <h3 className="section-title">{t('decision.evidence')}</h3>
          <ul className="decision-evidence">
            {decision.rationale.map((item) => <li key={item}>{item}</li>)}
          </ul>

          {decision.missing_evidence.length > 0 && (
            <>
              <h3 className="section-title">{t('decision.missing')}</h3>
              <ul className="decision-evidence">
                {decision.missing_evidence.map((item) => <li key={item}>{item}</li>)}
              </ul>
            </>
          )}
          <div className="alert alert-warn">{decision.provenance_warning}</div>
        </div>
      )}

    </div>
  )
}
