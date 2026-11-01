import { headingText } from '../../lib/headingText'
import { useState, type ReactNode } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import type { ScenarioOut } from '../../api/scenarios'
import type { AnalysisSegment, DatasetOut, EventPeriodBasis, SeparateComparison, SeparatePlanComparison } from '../../api/types'
import { selectWorkflowScenario } from '../../api/workflow'
import { completeFiniteAverage, comparisonTotals, operationalComparisonComplete } from '../../lib/comparison'
import { basisText, separateCostBasis } from '../../lib/costBasis'
import { fmtDecimal, messageOf } from '../../lib/format'
import { finiteNumber, minutes } from '../../lib/results'
import { isCurrentScenario, scenarioRows, type SelectedPlan } from './useSelectedPlan'

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
      <p>{t('results.suggests_cost', { now: costNow ?? unavailable, plan: costPlan ?? unavailable })}{costNote ? ` ${costNote}` : ''}</p>
      {separate && <p className="form-hint">{t('results.separate_plan_basis')}</p>}
      <div className="button-row">
        <Link className="button-link" to={`/reports?analysis=${analysisId}`}>{t('results.view_plan_exports')}</Link>
        <Link className="button-link" to={`/simulation/results?analysis=${analysisId}&plan=suggested`}>{t('results.check_in_simulation')}</Link>
      </div>
    </section>
  )
}

function Switcher({ options, selectedId, selectedUsable = false, analysisId }: { options: { id: number; name: string }[]; selectedId: number | null; selectedUsable?: boolean; analysisId: number }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const fallback = options.some((option) => option.id === selectedId) ? String(selectedId) : ''
  const [choice, setChoice] = useState(fallback)
  // A removed draft must not leave the native select displaying a different submitted id.
  if (choice !== '' && !options.some((option) => String(option.id) === choice)) setChoice(fallback)
  const select = useMutation({
    mutationFn: (scenarioId: number) => selectWorkflowScenario(analysisId, scenarioId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['workflow', analysisId] })
      await queryClient.invalidateQueries({ queryKey: ['separate-comparison', analysisId] })
    },
  })
  const chosen = Number(choice)
  const eligible = choice !== '' && options.some((option) => option.id === chosen)
  const selectedOption = selectedUsable && chosen === selectedId ? options.find((option) => option.id === chosen) : undefined
  return (
    <div className="plan-switcher">
      <div className="form-field">
        <label htmlFor="plan-switcher">{t('results.plan_label')}</label>
        <select id="plan-switcher" value={choice} aria-describedby={selectedOption ? 'plan-selected-status' : undefined} onChange={(event) => setChoice(event.target.value)}>
          {(selectedId === null || choice === '') && <option value="" disabled>{t('results.choose_saved_plan')}</option>}
          {options.map((option) => <option key={option.id} value={option.id}>{option.name}</option>)}
        </select>
      </div>
      <button type="button" className="btn-primary" disabled={!eligible || chosen === selectedId || select.isPending} onClick={() => select.mutate(chosen)}>
        {select.isPending ? t('common.loading') : t('results.use_for_simulation')}
      </button>
      {selectedOption && <p id="plan-selected-status" role="status" className="form-hint" style={{ flexBasis: '100%' }}>{t('compare.selected_for_simulation', { name: selectedOption.name })}</p>}
      {select.isError && <div role="alert" className="alert alert-error">{messageOf(select.error, t('errors.server'))}</div>}
    </div>
  )
}

function Section({ children, note }: { children: ReactNode; note?: string }) {
  const { t } = useTranslation()
  return (
    <section className="card" aria-labelledby="plan-changes-title">
      <h2 lang="en" id="plan-changes-title" className="section-title">{headingText(t, 'results.plan_changes')}</h2>
      <p className="form-hint">{note ?? t('results.plans_use_planning_file')}</p>
      {children}
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

type PlanState = SelectedPlan & { scenarios?: ScenarioOut[]; separateComparison?: SeparateComparison }

/** The "no plan selected" prompt (D21): the saved plans that can be chosen and the way to Suggested Plans. */
export function NoPlanPrompt({ analysisId, plan }: { analysisId: number; plan: PlanState }) {
  const { t } = useTranslation()
  const options = plan.separateComparison
    ? plan.separateComparison.plans.filter((item) => item.valid && !item.stale).map((item) => ({ id: item.scenario_id, name: item.name }))
    : (plan.scenarios ?? []).filter((item) => item.provenance === 'verified_snapshot' && isCurrentScenario(item) && operationalComparisonComplete(scenarioRows(item)))
      .map((item) => ({ id: Number(item.id), name: item.name }))
  return (
    <div className="plan-none">
      <p>{t(options.length > 0 ? 'results.saved_plan_available' : 'results.no_plan_selected')}</p>
      {options.length > 0 && <Switcher key={analysisId} options={options} selectedId={null} analysisId={analysisId} />}
      <Link className="button-link" to={`/analyses/${analysisId}/plans`}>{t('nav.suggested_plans')}</Link>
    </div>
  )
}

/**
 * The selected plan's Switcher, calculated result (D31) and cost line; planning file only. Its
 * per-period counters, waits and levels are drawn in the Results chart tabs (spec 2026-10-29 §5.4).
 * `promptShown`: the no-plan prompt is already shown under the wait chart, so it is not repeated here.
 */
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
  if (plan.kind === 'none') {
    if (promptShown) return null
    return (
      <section className="card" aria-labelledby="plan-none-title">
        <h2 lang="en" id="plan-none-title" className="section-title">{headingText(t, 'results.plan_changes')}</h2>
        <NoPlanPrompt analysisId={analysisId} plan={plan} />
      </section>
    )
  }

  if (plan.kind === 'shared') {
    const { scenario, scenarios, usable } = plan
    const options = scenarios
      .filter((item) => item.provenance === 'verified_snapshot' && isCurrentScenario(item) && operationalComparisonComplete(scenarioRows(item)))
      .map((item) => ({ id: Number(item.id), name: item.name }))
    if (!options.some((option) => option.id === Number(scenario.id))) options.unshift({ id: Number(scenario.id), name: scenario.name })
    if (!usable) {
      return (
        <Section>
          <Switcher key={`${analysisId}-${scenario.id}`} options={options} selectedId={Number(scenario.id)} selectedUsable={usable} analysisId={analysisId} />
          <div className="alert alert-warn" role="status">
            {t('results.plan_not_current', { name: scenario.name })}
            {scenario.evidence_reasons?.[0]?.detail && <p className="form-hint">{scenario.evidence_reasons[0].detail}</p>}
          </div>
        </Section>
      )
    }
    const rows = sharedRows(scenario)
    const source = scenarioRows(scenario)
    const totals = comparisonTotals(source)
    // Shared totals add the rows' costs; whether those rows cover one day is not established, so there is no day-basis label (UNKNOWN, spec §6.2).
    return (
      <>
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
        <Section>
          <Switcher key={`${analysisId}-${scenario.id}`} options={options} selectedId={Number(scenario.id)} selectedUsable={usable} analysisId={analysisId} />
          <p className="plan-cost">
            <strong>{t('results.cost_now_vs_plan')}</strong>{' '}
            {totals ? `${money(totals.current)} → ${money(totals.optimal)}` : t('results.unavailable')}
          </p>
          <p className="form-hint">{totals ? t('results.cost_basis_shared') : (scenario.roi_unavailable_reason ?? t('results.cost_unavailable_shared'))}</p>
        </Section>
      </>
    )
  }

  const { plan: chosen, comparison, usable } = plan
  const options = comparison.plans.filter((item) => item.valid && !item.stale).map((item) => ({ id: item.scenario_id, name: item.name }))
  if (!options.some((option) => option.id === chosen.scenario_id)) options.unshift({ id: chosen.scenario_id, name: chosen.name })
  if (!usable) {
    return (
      <Section>
        <Switcher key={`${analysisId}-${chosen.scenario_id}`} options={options} selectedId={chosen.scenario_id} selectedUsable={usable} analysisId={analysisId} />
        <div className="alert alert-warn" role="status">{t('results.plan_not_current', { name: chosen.name })}{chosen.valid_reason && <p className="form-hint">{chosen.valid_reason}</p>}</div>
      </Section>
    )
  }
  const rows = separateRows(comparison, chosen)
  const cost = money(chosen.totals?.total_cost_mean)
  const basis = cost === null ? null : separateCostBasis(periodBasis, dataset, chosen, segments)
  const costPlan = cost === null ? null : basis ? `${cost} ${basisText(t, basis)}` : cost
  const costNowReason = comparison.current.total_cost_reason ?? t('results.cost_now_unavailable_separate')
  return (
    <>
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
      <Section>
        <Switcher key={`${analysisId}-${chosen.scenario_id}`} options={options} selectedId={chosen.scenario_id} selectedUsable={usable} analysisId={analysisId} />
        <p className="plan-cost" data-testid="plan-cost"><strong>{t('results.cost_now_vs_plan')}</strong> {t('results.unavailable')} → {costPlan ?? t('results.unavailable')}</p>
        <p className="form-hint">{t('results.cost_now_unavailable_reason', { reason: costNowReason })}</p>
      </Section>
    </>
  )
}
