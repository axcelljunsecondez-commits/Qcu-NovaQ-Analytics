import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { listScenarios, type ScenarioOut } from '../api/scenarios'
import type { OptimizationOut } from '../api/types'
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
import { getWorkflow, selectWorkflowScenario } from '../api/workflow'

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
  const selection = useMutation({
    mutationFn: () => selectWorkflowScenario(analysisId!, Number(selected!.id)),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['workflow', analysisId] })
    },
  })
  const selectedForSimulation = workflow.data?.scenario?.id === Number(selected?.id)
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
          <p className="alert alert-info">{t('compare.period_cost_note')}</p>
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
            const peakCurrent = rows.length > 0 ? Math.max(...rows.map((r) => r.c_current)) : 0
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
                {rows.map((row) => (
                  <tr key={row.time}>
                    <th scope="row">{row.time}</th>
                    <td>{row.c_current}</td>
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
