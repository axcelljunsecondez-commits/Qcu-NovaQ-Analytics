import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams, Link } from 'react-router-dom'
import { listScenarios, type ScenarioOut } from '../api/scenarios'
import type { OptimizationOut, SeparateComparison } from '../api/types'
import {
  completeFiniteAverage,
  comparisonTotals,
  operationalComparisonComplete,
} from '../lib/comparison'
import {
  UtilizationCompareBars,
  ServerCompareBars,
  WaitTimeLines,
  CostWaterfall,
  ScenarioCompareBars,
} from '../components/charts/Charts'
import { NovaQInsights } from '../components/insights/NovaQInsights'
import { generateOptimizationInsights } from '../lib/insights'
import { ApiState } from '../components/ui/ApiState'
import { MetricCard } from '../components/ui/MetricCard'
import { getWorkflow, selectWorkflowScenario, getSeparateComparison } from '../api/workflow'
import { getAnalysis } from '../api/analyses'

function formatCount(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  return String(Math.round(value))
}

function SeparateComparisonView({ analysisId }: { analysisId: number }) {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const comparison = useQuery({
    queryKey: ['separate-comparison', analysisId],
    queryFn: () => getSeparateComparison(analysisId),
  })
  const [choice, setChoice] = useState('')
  const selection = useMutation({
    mutationFn: (scenarioId: number) => selectWorkflowScenario(analysisId, scenarioId),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['separate-comparison', analysisId] })
      await queryClient.invalidateQueries({ queryKey: ['workflow', analysisId] })
    },
  })
  if (comparison.isLoading) return <ApiState.Loading />
  if (comparison.isError || !comparison.data) return <ApiState.ErrorState />
  const data: SeparateComparison = comparison.data
  const validPlans = data.plans.filter((plan) => plan.valid && !plan.stale)
  const chosen = validPlans.find((plan) => String(plan.scenario_id) === choice) ?? null
  const selectedPlan = data.plans.find((plan) => plan.scenario_id === data.selected_scenario_id) ?? null
  const currentLanePeriods = data.current.periods.every((p) => p.active_lanes !== null)
    ? data.current.periods.reduce((sum, p) => sum + (p.active_lanes?.length ?? 0), 0)
    : null
  return (
    <div>
      <div className="topbar">
        <div>
          <div className="topbar-eyebrow">{t('compare.eyebrow')}</div>
          <h1 className="page-title">{t('compare.sep_title')}</h1>
          <p className="page-caption">
            {t('compare.sep_current')}
            {data.plans.map((plan) => ` vs ${plan.name}`).join('')}
          </p>
        </div>
      </div>
      {data.plans.length === 0 && (
        <div className="card" style={{ marginTop: '12px', padding: '18px' }}>
          <p style={{ margin: 0 }}>{t('compare.sep_no_plans')}</p>
          <p className="page-caption" style={{ marginTop: '4px' }}>{t('compare.sep_no_plans_hint')}</p>
        </div>
      )}
      {data.plans.length > 0 && (
        <>
          <div className="card" style={{ marginTop: '12px', padding: '18px' }}>
            <div className="table-scroll" role="region" aria-label={t('compare.sep_title')} tabIndex={0}>
              <table>
                <thead>
                  <tr>
                    <th scope="col">{t('common.time')}</th>
                    <th scope="col">{t('compare.sep_current')}</th>
                    {data.plans.map((plan) => (
                      <th scope="col" key={plan.scenario_id}>
                        {plan.name}
                        {plan.stale && <span className="badge badge-warn" style={{ marginLeft: '6px' }}>{t('compare.sep_stale')}</span>}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <th scope="row">{t('compare.sep_row_target')}</th>
                    <td>—</td>
                    {data.plans.map((plan) => (
                      <td key={plan.scenario_id}>{plan.target === null ? '—' : formatPercent(plan.target)}</td>
                    ))}
                  </tr>
                  <tr>
                    <th scope="row">{t('compare.sep_row_method')}</th>
                    <td>{t('compare.sep_current')}</td>
                    {data.plans.map((plan) => (
                      <td key={plan.scenario_id}>{plan.evaluation_method === 'DES_REPLICATIONS' ? t('optimize.sep_method') : (plan.evaluation_method ?? '—')}</td>
                    ))}
                  </tr>
                  <tr>
                    <th scope="row">{t('compare.sep_row_replications')}</th>
                    <td>—</td>
                    {data.plans.map((plan) => (
                      <td key={plan.scenario_id}>{plan.replications ?? '—'}</td>
                    ))}
                  </tr>
                  <tr>
                    <th scope="row">{t('compare.sep_row_lane_periods')}</th>
                    <td>{formatCount(currentLanePeriods)}</td>
                    {data.plans.map((plan) => (
                      <td key={plan.scenario_id}>{formatCount(plan.totals?.lane_periods ?? null)}</td>
                    ))}
                  </tr>
                  <tr>
                    <th scope="row">{t('compare.sep_row_wait')}</th>
                    <td>{formatMetric(data.current.wait_mean, 60)}</td>
                    {data.plans.map((plan) => (
                      <td key={plan.scenario_id}>{formatMetric(plan.totals?.wait_mean ?? null, 60)}</td>
                    ))}
                  </tr>
                  <tr>
                    <th scope="row">{t('compare.sep_row_peak')}</th>
                    <td>{formatPercent(data.current.util_max)}</td>
                    {data.plans.map((plan) => (
                      <td key={plan.scenario_id}>{formatPercent(plan.totals?.peak_util ?? null)}</td>
                    ))}
                  </tr>
                  <tr>
                    <th scope="row">{t('compare.sep_row_waiting_cost')}</th>
                    <td>{formatMetric(data.current.waiting_cost)}</td>
                    {data.plans.map((plan) => (
                      <td key={plan.scenario_id}>{formatMetric(plan.totals?.waiting_cost_mean ?? null)}</td>
                    ))}
                  </tr>
                  <tr>
                    <th scope="row">{t('compare.sep_row_total_cost')}</th>
                    <td title={data.current.total_cost_reason ?? ''}>N/A</td>
                    {data.plans.map((plan) => (
                      <td key={plan.scenario_id}>{formatMetric(plan.totals?.total_cost_mean ?? null)}</td>
                    ))}
                  </tr>
                  <tr>
                    <th scope="row">{t('compare.sep_row_complete')}</th>
                    <td>—</td>
                    {data.plans.map((plan) => (
                      <td key={plan.scenario_id}>
                        {plan.valid ? '✓' : '—'}
                        {!plan.valid && plan.valid_reason && (
                          <small style={{ display: 'block', color: 'var(--text-secondary)' }}>{plan.valid_reason}</small>
                        )}
                      </td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
            <p className="page-caption" style={{ marginTop: '8px' }}>{t('compare.sep_basis_note')}</p>
          </div>

          <section className="card" style={{ marginTop: '12px', padding: '18px' }} aria-labelledby="sep-staffing-title">
            <h2 id="sep-staffing-title" className="section-title">{t('compare.sep_staffing_schedule')}</h2>
            <div className="table-scroll" role="region" aria-labelledby="sep-staffing-title" tabIndex={0}>
              <table>
                <thead>
                  <tr>
                    <th scope="col">{t('common.time')}</th>
                    <th scope="col">{t('compare.sep_current')}</th>
                    {data.plans.map((plan) => (
                      <th scope="col" key={plan.scenario_id}>{plan.name}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {data.current.periods.map((period) => (
                    <tr key={period.time}>
                      <th scope="row">{period.time}</th>
                      <td>
                        {period.active_lanes === null ? '—' : period.active_lanes.length}
                        {period.active_lanes !== null && (
                          <small style={{ display: 'block', color: 'var(--text-secondary)' }}>
                            {period.active_lanes.join(', ')}
                          </small>
                        )}
                      </td>
                      {data.plans.map((plan) => {
                        const match = plan.periods.find((p) => p.time === period.time)
                        return (
                          <td key={plan.scenario_id}>
                            {match?.optimal_active_lanes ?? '—'}
                            {match?.adjustment !== null && match?.adjustment !== undefined && (
                              <small style={{ display: 'block', color: 'var(--text-secondary)' }}>
                                {match.adjustment === 0 ? t('optimize.sep_keep') : String(match.adjustment)}
                              </small>
                            )}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {data.plans.filter((plan) => plan.valid).map((plan) => (
              <details key={plan.scenario_id} style={{ marginTop: '8px' }}>
                <summary style={{ fontSize: '14px', fontWeight: 700, cursor: 'pointer' }}>
                  {t('compare.sep_candidate_detail')} · {plan.name}
                </summary>
                <table style={{ marginTop: '6px' }}>
                  <thead>
                    <tr>
                      <th scope="col">{t('common.time')}</th>
                      <th scope="col">{t('optimize.sep_col_lanes')}</th>
                      <th scope="col">{t('optimize.sep_col_peak')}</th>
                      <th scope="col">{t('optimize.sep_col_mean_cost')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {plan.periods.map((detail) => (
                      <tr key={detail.time}>
                        <th scope="row">{detail.time}</th>
                        <td>{detail.optimal_active_lanes ?? '—'}</td>
                        <td>{formatPercent(detail.peak_util)}</td>
                        <td>
                          {formatMetric(detail.total_cost_mean)}
                          {detail.total_cost_ci !== null && detail.total_cost_ci[0] !== null && detail.total_cost_ci[1] !== null && (
                            <small style={{ display: 'block', color: 'var(--text-secondary)' }}>
                              {formatMetric(detail.total_cost_ci[0])}–{formatMetric(detail.total_cost_ci[1])}
                            </small>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>
            ))}
          </section>

          <div className="card" style={{ marginTop: '12px', padding: '18px' }}>
            <h3 className="section-title">{t('compare.select_for_simulation')}</h3>
            <p className="page-caption">{t('compare.sep_select_prompt')}</p>
            <div role="radiogroup" aria-label={t('compare.select_for_simulation')} style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '8px' }}>
              {data.plans.map((plan) => {
                const selectable = plan.valid && !plan.stale
                return (
                  <label key={plan.scenario_id} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px' }}>
                    <input
                      type="radio"
                      name="separate-plan-choice"
                      disabled={!selectable}
                      checked={choice === String(plan.scenario_id)}
                      onChange={() => setChoice(String(plan.scenario_id))}
                    />
                    {plan.name}
                    {plan.stale && <span className="badge badge-warn" style={{ marginLeft: '6px' }}>{t('compare.sep_stale')}</span>}
                  </label>
                )
              })}
            </div>
            <button
              type="button"
              className="btn-primary"
              disabled={chosen === null || selection.isPending}
              onClick={() => chosen && selection.mutate(chosen.scenario_id)}
              style={{ marginTop: '10px' }}
            >
              {selection.isPending ? t('common.loading') : t('compare.select_for_simulation')}
            </button>
            {selectedPlan !== null && (
              <div className={`alert ${selectedPlan.valid && !selectedPlan.stale ? 'alert-ok' : 'alert-warn'}`} style={{ marginTop: '10px' }}>
                {selectedPlan.valid && !selectedPlan.stale
                  ? t('compare.selected_for_simulation', { name: selectedPlan.name })
                  : t('compare.sep_stale')}
              </div>
            )}
            {selection.isError && (
              <div role="alert" className="alert alert-error" style={{ marginTop: '10px' }}>
                {t('errors.server')}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}

function rowsOf(scenario?: ScenarioOut | null): OptimizationOut[] {
  if (!scenario) return []
  const res = scenario.results
  const arr = res?.results ?? res?.comparison
  return Array.isArray(arr) ? (arr as OptimizationOut[]) : []
}

function normalizeScenarioId(id: string | number): string {
  return String(id)
}

function formatMetric(value: number | null, multiplier = 1): string {
  return value === null || !Number.isFinite(value) ? '—' : (value * multiplier).toFixed(2)
}

function formatPercent(value: number | null): string {
  const formatted = formatMetric(value, 100)
  return formatted === '—' ? formatted : `${formatted}%`
}

function statusKey(stable: boolean, rho: number | null): string {
  if (rho === null || !Number.isFinite(rho)) return 'integrity.status.Unavailable'
  return stable ? 'compare.stable' : 'integrity.status.Unstable'
}

export function ComparisonPage() {
  const { t } = useTranslation()
  const analysisParam = useParams().analysisId
  const analysisId = analysisParam ? Number(analysisParam) : undefined
  const queryClient = useQueryClient()
  const { data, isLoading, isError } = useQuery({ queryKey: ['scenarios', analysisId], queryFn: () => listScenarios(analysisId) })
  const workflow = useQuery({
    queryKey: ['workflow', analysisId],
    queryFn: () => getWorkflow(analysisId!),
    enabled: Number.isInteger(analysisId),
  })
  const scenarios = useMemo(() => data?.scenarios ?? [], [data])

  const [scenarioId, setScenarioId] = useState('')
  const [selectedScenarioIds, setSelectedScenarioIds] = useState<string[]>([])
  const effectiveScenarioId = scenarioId
    || String(workflow.data?.scenario?.id ?? scenarios[0]?.id ?? '')

  const selected = useMemo(() => {
    return scenarios.find((s) => normalizeScenarioId(s.id) === effectiveScenarioId) ?? null
  }, [scenarios, effectiveScenarioId])

  const rows = useMemo(() => rowsOf(selected), [selected])

  const selectedScenarios = useMemo(
    () => scenarios.filter((scenario) => selectedScenarioIds.includes(normalizeScenarioId(scenario.id))),
    [scenarios, selectedScenarioIds],
  )

  const compared = useMemo(
    () => selectedScenarios.filter((scenario) => operationalComparisonComplete(rowsOf(scenario))),
    [selectedScenarios],
  )

  const incompleteSelected = useMemo(
    () => selectedScenarios.filter((scenario) => !operationalComparisonComplete(rowsOf(scenario))),
    [selectedScenarios],
  )

  const totals = comparisonTotals(rows)
  const operationallyComparable = operationalComparisonComplete(rows)
  const hasVerifiedOptimizedScenario = useMemo(
    () => scenarios.some((scenario) => scenario.provenance === 'verified_snapshot' && operationalComparisonComplete(rowsOf(scenario))),
    [scenarios],
  )
  const selection = useMutation({
    mutationFn: () => selectWorkflowScenario(analysisId!, Number(selected!.id)),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['workflow', analysisId] })
    },
  })
  const selectedForSimulation = workflow.data?.scenario?.id === Number(selected?.id)
  const analysis = useQuery({
    queryKey: ['analysis', analysisId],
    queryFn: () => getAnalysis(analysisId!),
    enabled: Number.isInteger(analysisId),
  })
  const isSeparateStaffing = analysis.data?.analysis.queue_setup.queue_structure === 'separate_queues'
  if (isSeparateStaffing && Number.isInteger(analysisId)) {
    return <SeparateComparisonView analysisId={analysisId!} />
  }
  if (isLoading) return <ApiState.Loading />
  if (isError) return <ApiState.ErrorState />

  if (scenarios.length === 0) {
    return (
      <div>
        {/* Topbar */}
        <div className="topbar">
          <div>
            <div className="topbar-eyebrow">{t('compare.eyebrow')}</div>
            <h1 className="page-title">{t('page4.title')}</h1>
            <p className="page-caption">{t('compare.description')}</p>
          </div>
        </div>
        <ApiState.Empty message={t('compare.empty')} />
      </div>
    )
  }

  return (
    <div>
      {/* Topbar */}
      <div className="topbar">
        <div>
          <div className="topbar-eyebrow">{t('compare.eyebrow')}</div>
          <h1 className="page-title">{t('page4.title')}</h1>
          <p className="page-caption">{t('compare.description')}</p>
        </div>
      </div>
      {selected && !selected.settings.calculation && <p className="alert alert-warn" style={{ marginTop: '8px' }}>{t('integrity.legacy')}</p>}
      {!hasVerifiedOptimizedScenario && (
        <div className="alert alert-warn" data-testid="compare-not-applicable" style={{ marginTop: '12px' }}>
          {t('compare.notApplicableNoOptimizedScenario')}{' '}
          <Link to={`/analyses/${analysisId}/simulate`}>{t('nav.simulate')}</Link>
          {' · '}
          <Link to={`/analyses/${analysisId}/reports`}>{t('nav.reports')}</Link>
        </div>
      )}

      {/* Scenario Selector */}
      <div className="card" style={{ marginTop: '12px', padding: '18px' }}>
        <h3 className="section-title">{t('compare.title')}</h3>
        <div className="form-row">
          <div className="form-field" style={{ flex: 1 }}>
            <label htmlFor="compare-scenario" style={{ fontSize: '14px', fontWeight: 800 }}>{t('compare.source_scenario')}</label>
            <select
              id="compare-scenario"
              aria-label={t('compare.source_scenario')}
              value={effectiveScenarioId}
              onChange={(e) => setScenarioId(e.target.value)}
              style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: '8px', fontSize: '14px' }}
            >
              {scenarios.map((s) => (
                <option key={normalizeScenarioId(s.id)} value={normalizeScenarioId(s.id)}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
          <button
            type="button"
            className="btn-primary"
            disabled={
              !selected
              || !hasVerifiedOptimizedScenario
              || selected.provenance !== 'verified_snapshot'
              || !operationallyComparable
              || selection.isPending
            }
            onClick={() => selection.mutate()}
          >
            {selection.isPending ? t('common.loading') : t('compare.select_for_simulation')}
          </button>
        </div>
        {selectedForSimulation && (
          <div className="alert alert-ok" style={{ marginTop: '10px' }}>
            {t('compare.selected_for_simulation', { name: selected?.name })}
          </div>
        )}
        {selection.isError && (
          <div role="alert" className="alert alert-error" style={{ marginTop: '10px' }}>
            {t('errors.server')}
          </div>
        )}
      </div>

      {!totals && <div role="alert" className="alert alert-warn" style={{ marginTop: '12px' }}>{t('integrity.incomplete')}</div>}

      {/* Quick Summary */}
      {totals && operationallyComparable && (
        <>
          <p role="status" className="alert alert-info">{t('compare.period_cost_note')}</p>
          <div className="card-grid" style={{ marginTop: '12px' }}>
            <MetricCard label={t('compare.current_total_cost')} value={`₱${totals.current.toLocaleString()}`} />
            <MetricCard label={t('compare.optimized_total_cost')} value={`₱${totals.optimal.toLocaleString()}`} />
            <MetricCard label={t('compare.cost_savings')} value={`₱${totals.savings.toLocaleString()}`} />
            <MetricCard label={t('compare.savings_percent')} value={totals.current === 0 ? t('common.not_available') : `${((totals.savings / totals.current) * 100).toFixed(1)}%`} />
          </div>
          {(() => {
            const avgCurrentRho = completeFiniteAverage(rows.map((row) => row.rho_current))
            const avgCurrentWq = completeFiniteAverage(rows.map((row) => row.Wq_current))
            const avgOptWq = completeFiniteAverage(rows.map((row) => row.Wq_optimal))
            const peakCurrent = rows.length > 0 ? Math.max(...rows.map((r) => r.c_current ?? 0)) : 0
            const peakOptimal = rows.length > 0 ? Math.max(...rows.map((r) => r.c_optimal!)) : 0
            const insights = generateOptimizationInsights(
              peakCurrent,
              peakOptimal,
              avgCurrentWq !== null ? avgCurrentWq * 60 : null,
              avgOptWq !== null ? avgOptWq * 60 : null,
              avgCurrentRho,
              t,
            )
            return insights.length > 0 ? <NovaQInsights insights={insights} /> : null
          })()}
        </>
      )}

      {/* Operational Table */}
      {rows.length > 0 && (
        <section className="card" style={{ marginTop: '12px', padding: '18px' }} aria-labelledby="compare-operational-title">
          <h2 id="compare-operational-title" className="section-title">{t('compare.operational')}</h2>
          <div className="table-scroll" role="region" aria-labelledby="compare-operational-title" tabIndex={0}>
            <table>
              <caption className="sr-only">{t('compare.operational_caption')}</caption>
              <thead>
                <tr>
                  <th scope="col">{t('common.time')}</th>
                  <th scope="col">{t('compare.current_cashiers')}</th>
                  <th scope="col">{t('compare.current_utilization')}</th>
                  <th scope="col">{t('compare.current_status')}</th>
                  <th scope="col">{t('compare.current_wait')}</th>
                  <th scope="col">{t('compare.optimized_cashiers')}</th>
                  <th scope="col">{t('compare.optimized_utilization')}</th>
                  <th scope="col">{t('compare.optimized_status')}</th>
                  <th scope="col">{t('compare.optimized_wait')}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, index) => (
                  <tr key={`${row.time}-${index}`}>
                    <th scope="row">{row.time}</th>
                    <td>{row.c_current ?? '—'}</td>
                    <td>{formatPercent(row.rho_current)}</td>
                    <td>{t(statusKey(row.current_stable, row.rho_current))}</td>
                    <td>{formatMetric(row.Wq_current, 60)}</td>
                    <td>{row.c_optimal ?? '—'}</td>
                    <td>{formatPercent(row.rho_optimal)}</td>
                    <td>{t(statusKey(row.optimized_stable, row.rho_optimal))}</td>
                    <td>{formatMetric(row.Wq_optimal, 60)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Charts */}
      {operationallyComparable && (
        <>
          <div className="card-grid" style={{ marginTop: '12px' }}>
            <div className="card">
              <UtilizationCompareBars rows={rows} />
            </div>
            <div className="card">
              <ServerCompareBars rows={rows} />
            </div>
          </div>
          <div className="card" style={{ marginTop: '12px' }}>
            <WaitTimeLines rows={rows} />
          </div>
        </>
      )}

      {totals && <div className="card" style={{ marginTop: '12px' }}><CostWaterfall rows={rows} /></div>}

      {/* Multi-Scenario Compare */}
      <div className="card" style={{ marginTop: '12px', padding: '18px' }}>
        <h3 className="section-title">{t('compare.scenarios')}</h3>
        <div className="form-row">
          <div className="form-field" style={{ flex: 1 }}>
            <label htmlFor="compare-multi" style={{ fontSize: '14px', fontWeight: 800 }}>{t('compare.select_scenarios')}</label>
            <div id="compare-multi" className="checkbox-list" role="group" aria-label={t('compare.select_scenarios')} style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '6px' }}>
              {scenarios.map((s) => (
                <label key={normalizeScenarioId(s.id)} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '14px' }}>
                  <input
                    type="checkbox"
                    checked={selectedScenarioIds.includes(normalizeScenarioId(s.id))}
                    onChange={(e) => {
                      const id = normalizeScenarioId(s.id)
                      if (e.target.checked) {
                        setSelectedScenarioIds((prev) => prev.includes(id) ? prev : [...prev, id])
                      } else {
                        setSelectedScenarioIds((prev) => prev.filter((selectedId) => selectedId !== id))
                      }
                    }}
                    style={{ width: '14px', height: '14px' }}
                  />
                  {s.name}
                </label>
              ))}
            </div>
          </div>
        </div>
        {selectedScenarios.length < 2 ? (
          <p className="page-caption" style={{ marginTop: '8px' }}>{t('compare.min_two')}</p>
        ) : (
          <>
            {incompleteSelected.length > 0 && (
              <div role="alert" className="alert alert-warn" style={{ marginTop: '8px' }}>
                {t('compare.incomplete_scenarios', {
                  names: incompleteSelected.map((scenario) => scenario.name).join(', '),
                })}
              </div>
            )}
            {compared.length >= 2 && (
              <div style={{ marginTop: '10px' }}>
                <ScenarioCompareBars
                  scenarios={compared.map((s) => ({ name: s.name, rows: rowsOf(s) }))}
                />
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
