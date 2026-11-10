import { headingText } from '../../lib/headingText'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import type { ScenarioOut } from '../../api/scenarios'
import type { AnalysisSegment, DatasetOut, EventPeriodBasis, SeparateComparison, SeparatePlanComparison } from '../../api/types'
import { completeFiniteAverage, comparisonTotals } from '../../lib/comparison'
import { basisText, separateCostBasis } from '../../lib/costBasis'
import { fmtDecimal } from '../../lib/format'
import { finiteNumber, minutes } from '../../lib/results'
import { eligibleSavedPlans, scenarioRows, type PlanState } from './useSelectedPlan'

function money(value: number | null | undefined): string | null {
  return value === null || value === undefined || !Number.isFinite(value) ? null : `₱${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`
}

interface PlanRow {
  time: string
  countersNow: number | null
  countersPlan: number | null
}

/** "Calculated result · not yet checked by simulation" (D31 level 1). No decision words. */
function CalculatedResult({ analysisId, changes, waitNow, waitPlan, costNow, costPlan, costNote, separate }: {
  analysisId: number
  changes: PlanRow[]
  waitNow: number | null
  waitPlan: number | null
  costNow: string | null
  costPlan: string | null
  costNote: string | null
  separate: boolean
}) {
  const { t } = useTranslation()
  const unavailable = t('results.unavailable')
  const waitText = (hours: number | null) => {
    const value = minutes(hours)
    return value === null ? unavailable : fmtDecimal(value, 1)
  }
  return (
    <section className="card calculated-result" aria-labelledby="calculated-result-title">
      <h2 lang="en" id="calculated-result-title" className="section-title">{headingText(t, 'results.calculated_title')}</h2>
      <p className="badge badge-warn">{t('results.calculated_label')}</p>
      <p>
        {changes.length === 0
          ? t('results.suggests_no_change')
          : t('results.suggests_changes', { changes: changes.map((row) => t('results.counter_change', { time: row.time, from: row.countersNow ?? '?', to: row.countersPlan ?? '?' })).join('; ') })}
      </p>
      {/* OD-5 / W17: separate lines pair an analytical estimate with a simulated plan, so both kinds are named. */}
      <p>{t(separate ? 'results.suggests_wait_separate' : 'results.suggests_wait', { now: waitText(waitNow), plan: waitText(waitPlan) })}</p>
      <p>{t('results.suggests_cost', { now: costNow ?? unavailable, plan: costPlan ?? unavailable })}</p>
      {costNote && <p className="form-hint">{costNote}</p>}
      {separate && <p className="form-hint">{t('results.separate_plan_basis')}</p>}
      <div className="button-row">
        <Link className="button-link" to={`/reports?analysis=${analysisId}`}>{t('results.view_plan_exports')}</Link>
        <Link className="button-link" to={`/simulation/results?analysis=${analysisId}&plan=suggested`}>{t('results.check_in_simulation')}</Link>
      </div>
    </section>
  )
}

function sharedRows(scenario: ScenarioOut): PlanRow[] {
  return scenarioRows(scenario).map((row) => ({ time: row.time, countersNow: finiteNumber(row.c_current), countersPlan: finiteNumber(row.c_optimal) }))
}

function separateRows(comparison: SeparateComparison, plan: SeparatePlanComparison): PlanRow[] {
  return comparison.current.periods.map((period) => ({
    time: period.time,
    countersNow: period.active_lanes === null ? null : period.active_lanes.length,
    countersPlan: finiteNumber(plan.periods.find((item) => item.time === period.time)?.optimal_active_lanes),
  }))
}

export function NoPlanPrompt({ analysisId, plan }: { analysisId: number; plan: PlanState }) {
  const { t } = useTranslation()
  return (
    <div className="plan-none">
      <p>{t(eligibleSavedPlans(plan).length > 0 ? 'results.saved_plan_available' : 'results.no_plan_selected')}</p>
      <Link className="button-link" to={`/analyses/${analysisId}/plans`}>{t('nav.suggested_plans')}</Link>
    </div>
  )
}

/** Calculated result for the selected plan. Suggested Plans owns plan selection. */
export function PlanChanges({ analysisId, plan, dataset, periodBasis, segments, promptShown = false }: {
  analysisId: number
  plan: PlanState
  /** The planning file, for the plan cost's day-basis label (spec §6). */
  dataset?: DatasetOut
  periodBasis?: EventPeriodBasis
  /** The Setup segments: the day-basis label needs every one to be 60 minutes (period costs are hourly rates). */
  segments?: AnalysisSegment[]
  promptShown?: boolean
}) {
  const { t } = useTranslation()
  if (plan.kind === 'loading') return <p className="form-hint">{t('common.loading')}</p>
  if (plan.kind === 'error') return <div className="alert alert-error" role="alert">{t('results.plan_error')}</div>
  if (plan.kind === 'none') return promptShown ? null : <NoPlanPrompt analysisId={analysisId} plan={plan} />

  if (plan.kind === 'shared') {
    const { scenario, usable } = plan
    if (!usable) {
      return (
        <div className="alert alert-warn" role="status">
          {t('results.plan_not_current', { name: scenario.name })}
          {scenario.evidence_reasons?.[0]?.detail && <p className="form-hint">{scenario.evidence_reasons[0].detail}</p>}
        </div>
      )
    }
    const rows = sharedRows(scenario)
    const source = scenarioRows(scenario)
    const totals = comparisonTotals(source)
    // Shared totals add the rows' costs; whether those rows cover one day is not established, so there is no day-basis label (UNKNOWN, spec §6.2).
    return (
      <CalculatedResult
        analysisId={analysisId}
        changes={rows.filter((row) => row.countersNow !== row.countersPlan)}
        waitNow={completeFiniteAverage(source.map((row) => row.Wq_current))}
        waitPlan={completeFiniteAverage(source.map((row) => row.Wq_optimal))}
        costNow={money(totals?.current)}
        costPlan={money(totals?.optimal)}
        costNote={totals ? t('results.cost_basis_shared') : (scenario.roi_unavailable_reason ?? t('results.cost_unavailable_shared'))}
        separate={false}
      />
    )
  }

  const { plan: chosen, comparison, usable } = plan
  if (!usable) {
    return (
      <div className="alert alert-warn" role="status">
        {t('results.plan_not_current', { name: chosen.name })}
        {chosen.valid_reason && <p className="form-hint">{chosen.valid_reason}</p>}
      </div>
    )
  }
  const rows = separateRows(comparison, chosen)
  const cost = money(chosen.totals?.total_cost_mean)
  const basis = cost === null ? null : separateCostBasis(periodBasis, dataset, chosen, segments)
  const costPlan = cost === null ? null : basis ? `${cost} ${basisText(t, basis)}` : cost
  const costNowReason = comparison.current.total_cost_reason
    ? t('results.cost_now_unavailable_reason', { reason: comparison.current.total_cost_reason })
    : t('results.cost_now_unavailable_separate')
  return (
    <CalculatedResult
      analysisId={analysisId}
      changes={rows.filter((row) => row.countersNow !== row.countersPlan)}
      waitNow={finiteNumber(comparison.current.wait_mean)}
      waitPlan={finiteNumber(chosen.totals?.wait_mean)}
      costNow={null}
      costPlan={costPlan}
      costNote={costNowReason}
      separate
    />
  )
}
