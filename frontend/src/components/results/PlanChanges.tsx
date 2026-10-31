import { headingText } from '../../lib/headingText'
import { useState, type ReactNode } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import type { ScenarioOut } from '../../api/scenarios'
import type { SeparateComparison, SeparatePlanComparison } from '../../api/types'
import { selectWorkflowScenario } from '../../api/workflow'
import { completeFiniteAverage, comparisonTotals, operationalComparisonComplete } from '../../lib/comparison'
import { fmtDecimal, fmtPctDecimal, messageOf } from '../../lib/format'
import { finiteNumber, levelClass, levelKey, minutes } from '../../lib/results'
import { utilizationBand, type UtilizationBand } from '../../lib/utilization'
import { isCurrentScenario, scenarioRows, type SelectedPlan } from './useSelectedPlan'

function money(value: number | null | undefined): string | null {
  return value === null || value === undefined || !Number.isFinite(value) ? null : `₱${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`
}

function band(rho: number | null, stable: boolean | null): UtilizationBand | null {
  if (stable === false) return 'Unstable'
  return rho === null ? null : utilizationBand(rho)
}

interface PlanRow {
  time: string
  countersNow: number | null
  countersPlan: number | null
  waitNow: number | null
  waitPlan: number | null
  levelNow: UtilizationBand | null
  levelPlan: UtilizationBand | null
  aboveTarget: boolean
}

function Level({ level }: { level: UtilizationBand | null }) {
  const { t } = useTranslation()
  return <span className={`status-badge ${levelClass(level)}`}>{t(levelKey(level))}</span>
}

function PlanTable({ rows, target }: { rows: PlanRow[]; target: number | null }) {
  const { t } = useTranslation()
  const unavailable = t('results.unavailable')
  const count = (value: number | null) => (value === null ? unavailable : String(value))
  const wait = (hours: number | null, level: UtilizationBand | null) => {
    if (level === 'Unstable') return t('results.cant_keep_up_wait')
    const value = minutes(hours)
    return value === null ? unavailable : `${fmtDecimal(value, 1)} ${t('results.min')}`
  }
  return (
    <div className="table-scroll" role="region" aria-labelledby="plan-changes-title" tabIndex={0}>
      <table>
        <thead>
          <tr><th scope="col">{t('common.time')}</th><th scope="col">{t('results.col_counters')}</th><th scope="col">{t('results.col_estimated_wait')}</th><th scope="col">{t('results.col_level')}</th></tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.time} className={row.aboveTarget ? 'row-warning' : undefined}>
              <th scope="row">
                {row.time}
                {row.aboveTarget && target !== null && <small className="plan-target-flag">{t('results.above_plan_target', { target: fmtPctDecimal(target) })}</small>}
              </th>
              <td>{count(row.countersNow)} → {count(row.countersPlan)}</td>
              <td>{wait(row.waitNow, row.levelNow)} → {wait(row.waitPlan, row.levelPlan)}</td>
              <td><Level level={row.levelNow} /> → <Level level={row.levelPlan} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
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
      <p>{t('results.suggests_wait', { now: waitText(waitNow), plan: waitText(waitPlan) })}</p>
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

function sharedRows(scenario: ScenarioOut, target: number | null): PlanRow[] {
  return scenarioRows(scenario).map((row) => {
    const rhoNow = finiteNumber(row.rho_current)
    const levelNow = band(rhoNow, row.current_stable)
    return {
      time: row.time,
      countersNow: finiteNumber(row.c_current),
      countersPlan: finiteNumber(row.c_optimal),
      waitNow: finiteNumber(row.Wq_current),
      waitPlan: finiteNumber(row.Wq_optimal),
      levelNow,
      levelPlan: band(finiteNumber(row.rho_optimal), row.optimized_stable),
      aboveTarget: target !== null && (levelNow === 'Unstable' || (rhoNow !== null && rhoNow > target)),
    }
  })
}

function separateRows(comparison: SeparateComparison, plan: SeparatePlanComparison, target: number | null): PlanRow[] {
  return comparison.current.periods.map((period) => {
    const match = plan.periods.find((item) => item.time === period.time)
    const rhoNow = finiteNumber(period.util_max)
    const rhoPlan = finiteNumber(match?.peak_util)
    return {
      time: period.time,
      countersNow: period.active_lanes === null ? null : period.active_lanes.length,
      countersPlan: finiteNumber(match?.optimal_active_lanes),
      waitNow: finiteNumber(period.wait_mean),
      waitPlan: finiteNumber(match?.wait_mean),
      levelNow: band(rhoNow, null),
      levelPlan: band(rhoPlan, null),
      aboveTarget: target !== null && rhoNow !== null && rhoNow > target,
    }
  })
}

/** "What the plan changes" (D21) and the level-1 calculated result (D31); planning file only. */
export function PlanChanges({ analysisId, plan }: { analysisId: number; plan: SelectedPlan & { scenarios?: ScenarioOut[]; separateComparison?: SeparateComparison } }) {
  const { t } = useTranslation()
  if (plan.kind === 'loading') return <p className="form-hint">{t('common.loading')}</p>
  if (plan.kind === 'error') return <div className="alert alert-error" role="alert">{t('results.plan_error')}</div>
  if (plan.kind === 'none') {
    const options = plan.separateComparison
      ? plan.separateComparison.plans.filter((item) => item.valid && !item.stale).map((item) => ({ id: item.scenario_id, name: item.name }))
      : (plan.scenarios ?? []).filter((item) => item.provenance === 'verified_snapshot' && isCurrentScenario(item) && operationalComparisonComplete(scenarioRows(item)))
        .map((item) => ({ id: Number(item.id), name: item.name }))
    return (
      <section className="card" aria-labelledby="plan-none-title">
        <h2 lang="en" id="plan-none-title" className="section-title">{headingText(t, 'results.plan_changes')}</h2>
        <p>{t(options.length > 0 ? 'results.saved_plan_available' : 'results.no_plan_selected')}</p>
        {options.length > 0 && <Switcher key={analysisId} options={options} selectedId={null} analysisId={analysisId} />}
        <Link className="button-link" to={`/analyses/${analysisId}/plans`}>{t('nav.suggested_plans')}</Link>
      </section>
    )
  }

  if (plan.kind === 'shared') {
    const { scenario, scenarios, usable, target } = plan
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
    const rows = sharedRows(scenario, target)
    const source = scenarioRows(scenario)
    const totals = comparisonTotals(source)
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
          <PlanTable rows={rows} target={target} />
          <p className="plan-cost">
            <strong>{t('results.cost_now_vs_plan')}</strong>{' '}
            {totals ? `${money(totals.current)} → ${money(totals.optimal)}` : t('results.unavailable')}
          </p>
          <p className="form-hint">{totals ? t('results.cost_basis_shared') : (scenario.roi_unavailable_reason ?? t('results.cost_unavailable_shared'))}</p>
        </Section>
      </>
    )
  }

  const { plan: chosen, comparison, usable, target } = plan
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
  const rows = separateRows(comparison, chosen, target)
  const costPlan = money(chosen.totals?.total_cost_mean)
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
        <PlanTable rows={rows} target={target} />
        <p className="plan-cost"><strong>{t('results.cost_now_vs_plan')}</strong> {t('results.unavailable')} → {costPlan ?? t('results.unavailable')}</p>
        <p className="form-hint">{t('results.cost_now_unavailable_reason', { reason: costNowReason })}</p>
      </Section>
    </>
  )
}
