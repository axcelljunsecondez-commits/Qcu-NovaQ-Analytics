import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
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
  const { data, isLoading, isError } = useQuery({ queryKey: ['scenarios'], queryFn: listScenarios })
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
        <h1 className="page-title">{t('page4.title')}</h1>
        <p className="page-caption">{t('page4.caption')}</p>
      {!selected?.settings.calculation && <p className="alert alert-warn">{t('integrity.legacy')}</p>}
        <ApiState.Empty message={t('compare.empty')} />
      </div>
    )
  }

  return (
    <div>
      <h1 className="page-title">{t('page4.title')}</h1>
      <p className="page-caption">{t('page4.caption')}</p>
      {!selected?.settings.calculation && <p className="alert alert-warn">{t('integrity.legacy')}</p>}

      <div className="card">
        <h2 className="card-title">{t('compare.title')}</h2>
        <div className="form-row">
          <div className="form-field">
            <label htmlFor="compare-scenario">{t('compare.source_scenario')}</label>
            <select
              id="compare-scenario"
              aria-label={t('compare.source_scenario')}
              value={scenarioId || (scenarios[0] ? normalizeScenarioId(scenarios[0].id) : '')}
              onChange={(e) => setScenarioId(e.target.value)}
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

      {!totals && <div role="alert" className="alert alert-warn">{t('integrity.incomplete')}</div>}
      {rows.length > 0 && (
        <div className="card">
          <h2 className="card-title">{t('compare.operational')}</h2>
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
      )}
      {operationallyComparable && (
        <>
          <div className="card-grid">
            <div className="card">
              <UtilizationCompareBars rows={rows} />
            </div>
            <div className="card">
              <ServerCompareBars rows={rows} />
            </div>
          </div>
          <div className="card">
            <WaitTimeLines rows={rows} />
          </div>
        </>
      )}
      {totals && roi && (
        <>
          <div className="card">
            <RadarChart
              current={computeRadarScores(radarRows, { current: true, targetRho: targetUtilization }).r}
              optimized={computeRadarScores(radarRows, { current: false, targetRho: targetUtilization }).r}
            />
          </div>
          <div className="card">
            <CostWaterfall rows={rows} />
          </div>
          <div className="card">
            <h2 className="card-title">{t('page4.roi')}</h2>
            <div className="form-row">
              <div className="form-field">
                <label htmlFor="roi-holidays">{t('compare.holidays')}</label>
                <input
                  id="roi-holidays"
                  aria-label={t('compare.holidays')}
                  type="number"
                  min={0}
                  max={365}
                  value={holidays}
                  onChange={(e) => setHolidays(clampHolidays(Number(e.target.value)))}
                />
              </div>
              <div className="form-field">
                <label htmlFor="roi-sundays">{t('compare.sundays')}</label>
                <input
                  id="roi-sundays"
                  type="checkbox"
                  checked={closedSundays}
                  onChange={(e) => setClosedSundays(e.target.checked)}
                />
              </div>
            </div>
            <p className="page-caption">{t('compare.roi_note')}</p>
            <div className="card-grid">
              <MetricCard label={t('compare.daily_savings')} value={fmtMoney(roi.dailySavings)} />
              <MetricCard label={t('compare.monthly_savings')} value={fmtMoney(roi.monthlySavings)} />
              <MetricCard label={t('compare.annual_savings')} value={fmtMoney(roi.annualSavings)} />
              <MetricCard label={t('compare.operating_days')} value={String(roi.workingDaysPerYear)} />
            </div>
            <p className="form-hint">
              {t('compare.roi_basis', {
                days: String(roi.workingDaysPerYear),
                holidays: String(holidays),
              })}
            </p>
          </div>
        </>
      )}

      <div className="card">
        <h2 className="card-title">{t('compare.scenarios')}</h2>
        <div className="form-row">
          <div className="form-field">
            <label htmlFor="compare-multi">{t('compare.select_scenarios')}</label>
            <div id="compare-multi" className="checkbox-list" role="group" aria-label={t('compare.select_scenarios')}>
              {scenarios.map((s) => (
                <label key={normalizeScenarioId(s.id)}>
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
                  />
                  {s.name}
                </label>
              ))}
            </div>
          </div>
        </div>
        {selectedScenarios.length < 2 ? (
          <p className="page-caption">{t('compare.min_two')}</p>
        ) : (
          <>
            {incompleteSelected.length > 0 && (
              <div role="alert" className="alert alert-warn">
                {t('compare.incomplete_scenarios', {
                  names: incompleteSelected.map((scenario) => scenario.name).join(', '),
                })}
              </div>
            )}
            {compared.length >= 2 && (
              <ScenarioCompareBars
                scenarios={compared.map((s) => ({ name: s.name, rows: rowsOf(s) }))}
              />
            )}
          </>
        )}
      </div>
    </div>
  )
}
