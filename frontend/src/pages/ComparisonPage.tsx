import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { listScenarios, type ScenarioOut } from '../api/scenarios'
import type { OptimizationOut } from '../api/types'
import { computeRadarScores, DEFAULT_TARGET_UTILIZATION, type RadarRow } from '../lib/radar'
import {
  comparisonTotals,
  operationalComparisonComplete,
} from '../lib/comparison'
import { computeRoi, clampHolidays } from '../lib/roi'
import {
  RadarChart,
  UtilizationCompareBars,
  ServerCompareBars,
  WaitTimeLines,
  CostWaterfall,
  ScenarioCompareBars,
} from '../components/charts/Charts'
import { NovaQInsights, generateOptimizationInsights } from '../components/insights/NovaQInsights'
import { ApiState } from '../components/ui/ApiState'
import { MetricCard } from '../components/ui/MetricCard'

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
  if (stable) return 'compare.stable'
  return rho === null ? 'integrity.status.Unavailable' : 'integrity.status.Unstable'
}

export function ComparisonPage() {
  const { t } = useTranslation()
  const analysisParam = useParams().analysisId
  const analysisId = analysisParam ? Number(analysisParam) : undefined
  const { data, isLoading, isError } = useQuery({ queryKey: ['scenarios', analysisId], queryFn: () => listScenarios(analysisId) })
  const scenarios = useMemo(() => data?.scenarios ?? [], [data])

  const [scenarioId, setScenarioId] = useState('')
  const [selectedScenarioIds, setSelectedScenarioIds] = useState<string[]>([])
  const [holidays, setHolidays] = useState(12)
  const [closedSundays, setClosedSundays] = useState(false)

  const selected = useMemo(() => {
    const id = scenarioId || (scenarios[0] ? normalizeScenarioId(scenarios[0].id) : '')
    return scenarios.find((s) => normalizeScenarioId(s.id) === id) ?? null
  }, [scenarios, scenarioId])

  const rows = useMemo(() => rowsOf(selected), [selected])

  const radarRows = useMemo<RadarRow[]>(
    () => rows.map((r) => ({ ...r, lambda: r.lambda_ })),
    [rows],
  )

  const targetUtilization = useMemo(() => {
    const raw = selected?.settings?.target_utilization
    return typeof raw === 'number' && Number.isFinite(raw) ? raw : DEFAULT_TARGET_UTILIZATION
  }, [selected])

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
  const roi = totals
    ? computeRoi({ currentTotal: totals.current, optimalTotal: totals.optimal, holidays, closedSundays })
    : null
  const fmtMoney = (n: number) =>
    '₱' + n.toLocaleString(undefined, { maximumFractionDigits: 0 })

  if (isLoading) return <ApiState.Loading />
  if (isError) return <ApiState.ErrorState />

  if (scenarios.length === 0) {
    return (
      <div>
        {/* Topbar */}
        <div className="topbar">
          <div>
            <div className="topbar-eyebrow">Comparison · Compare Scenarios Against Current Operations</div>
            <h1 className="page-title">{t('page4.title')}</h1>
            <p className="page-caption">Compare scenarios side by side to find the best staffing plan.</p>
          </div>
        </div>
        {!selected?.settings.calculation && <p className="alert alert-warn" style={{ marginTop: '8px' }}>{t('integrity.legacy')}</p>}
        <ApiState.Empty message={t('compare.empty')} />
      </div>
    )
  }

  return (
    <div>
      {/* Topbar */}
      <div className="topbar">
        <div>
          <div className="topbar-eyebrow">Comparison · Compare Scenarios Against Current Operations</div>
          <h1 className="page-title">{t('page4.title')}</h1>
          <p className="page-caption">Compare scenarios side by side to find the best staffing plan.</p>
        </div>
      </div>
      {!selected?.settings.calculation && <p className="alert alert-warn" style={{ marginTop: '8px' }}>{t('integrity.legacy')}</p>}

      {/* Scenario Selector */}
      <div className="card" style={{ marginTop: '12px', padding: '18px' }}>
        <h3 className="section-title">{t('compare.title')}</h3>
        <div className="form-row">
          <div className="form-field" style={{ flex: 1 }}>
            <label htmlFor="compare-scenario" style={{ fontSize: '11px', fontWeight: 800 }}>{t('compare.source_scenario')}</label>
            <select
              id="compare-scenario"
              aria-label={t('compare.source_scenario')}
              value={scenarioId || (scenarios[0] ? normalizeScenarioId(scenarios[0].id) : '')}
              onChange={(e) => setScenarioId(e.target.value)}
              style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: '8px', fontSize: '12px' }}
            >
              {scenarios.map((s) => (
                <option key={normalizeScenarioId(s.id)} value={normalizeScenarioId(s.id)}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {!totals && <div role="alert" className="alert alert-warn" style={{ marginTop: '12px' }}>{t('integrity.incomplete')}</div>}

      {/* Quick Summary */}
      {totals && operationallyComparable && (
        <>
          <div className="card-grid" style={{ marginTop: '12px' }}>
            <MetricCard label={t('compare.current_total_cost')} value={`₱${totals.current.toLocaleString()}`} />
            <MetricCard label={t('compare.optimized_total_cost')} value={`₱${totals.optimal.toLocaleString()}`} />
            <MetricCard label={t('compare.cost_savings')} value={`₱${totals.savings.toLocaleString()}`} />
            <MetricCard label={t('compare.savings_percent')} value={`${((totals.savings / totals.current) * 100).toFixed(1)}%`} />
          </div>
          {(() => {
            const avgCurrentRho = rows.length > 0 ? rows.reduce((s, r) => s + (r.rho_current ?? 0), 0) / rows.length : null
            const avgCurrentWq = rows.length > 0 ? rows.reduce((s, r) => s + (r.Wq_current ?? 0), 0) / rows.length : null
            const avgOptWq = rows.length > 0 ? rows.reduce((s, r) => s + (r.Wq_optimal ?? 0), 0) / rows.length : null
            const peakCurrent = rows.length > 0 ? Math.max(...rows.map((r) => r.c_current)) : 0
            const peakOptimal = rows.length > 0 ? Math.max(...rows.map((r) => r.c_optimal ?? 0)) : 0
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
        <div className="card" style={{ marginTop: '12px', padding: '18px' }}>
          <h3 className="section-title">{t('compare.operational')}</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t('common.time')}</th>
                  <th>{t('compare.current_cashiers')}</th>
                  <th>{t('compare.current_utilization')}</th>
                  <th>{t('compare.current_status')}</th>
                  <th>{t('compare.current_wait')}</th>
                  <th>{t('compare.optimized_cashiers')}</th>
                  <th>{t('compare.optimized_utilization')}</th>
                  <th>{t('compare.optimized_status')}</th>
                  <th>{t('compare.optimized_wait')}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.time}>
                    <td>{row.time}</td>
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
        </div>
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

      {/* ROI */}
      {totals && roi && (
        <>
          <div className="card" style={{ marginTop: '12px' }}>
            <RadarChart
              current={computeRadarScores(radarRows, { current: true, targetRho: targetUtilization }).r}
              optimized={computeRadarScores(radarRows, { current: false, targetRho: targetUtilization }).r}
            />
          </div>
          <div className="card" style={{ marginTop: '12px' }}>
            <CostWaterfall rows={rows} />
          </div>
          <div className="card" style={{ marginTop: '12px', padding: '18px' }}>
            <h3 className="section-title">{t('page4.roi')}</h3>
            <div className="form-row" style={{ gap: '10px' }}>
              <div className="form-field" style={{ flex: 1 }}>
                <label htmlFor="roi-holidays" style={{ fontSize: '11px', fontWeight: 800 }}>{t('compare.holidays')}</label>
                <input
                  id="roi-holidays"
                  aria-label={t('compare.holidays')}
                  type="number"
                  min={0}
                  max={365}
                  value={holidays}
                  onChange={(e) => setHolidays(clampHolidays(Number(e.target.value)))}
                  style={{ width: '100%', padding: '8px 10px', border: '1px solid var(--border)', borderRadius: '8px', fontSize: '12px' }}
                />
              </div>
              <div className="form-field" style={{ flex: 1 }}>
                <label htmlFor="roi-sundays" style={{ fontSize: '11px', fontWeight: 800 }}>{t('compare.sundays')}</label>
                <div style={{ padding: '8px 0' }}>
                  <input
                    id="roi-sundays"
                    type="checkbox"
                    checked={closedSundays}
                    onChange={(e) => setClosedSundays(e.target.checked)}
                    style={{ width: '16px', height: '16px' }}
                  />
                </div>
              </div>
            </div>
            <p className="page-caption" style={{ marginTop: '6px' }}>{t('compare.roi_note')}</p>
            <div className="card-grid" style={{ marginTop: '10px' }}>
              <MetricCard label={t('compare.daily_savings')} value={fmtMoney(roi.dailySavings)} />
              <MetricCard label={t('compare.monthly_savings')} value={fmtMoney(roi.monthlySavings)} />
              <MetricCard label={t('compare.annual_savings')} value={fmtMoney(roi.annualSavings)} />
              <MetricCard label={t('compare.operating_days')} value={String(roi.workingDaysPerYear)} />
            </div>
            <p className="form-hint" style={{ marginTop: '8px' }}>
              {t('compare.roi_basis', {
                days: String(roi.workingDaysPerYear),
                holidays: String(holidays),
              })}
            </p>
          </div>
        </>
      )}

      {/* Multi-Scenario Compare */}
      <div className="card" style={{ marginTop: '12px', padding: '18px' }}>
        <h3 className="section-title">{t('compare.scenarios')}</h3>
        <div className="form-row">
          <div className="form-field" style={{ flex: 1 }}>
            <label htmlFor="compare-multi" style={{ fontSize: '11px', fontWeight: 800 }}>{t('compare.select_scenarios')}</label>
            <div id="compare-multi" className="checkbox-list" role="group" aria-label={t('compare.select_scenarios')} style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '6px' }}>
              {scenarios.map((s) => (
                <label key={normalizeScenarioId(s.id)} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px' }}>
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
