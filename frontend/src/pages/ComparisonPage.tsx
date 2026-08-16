import { useEffect, useMemo, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { listScenarios, type ScenarioOut } from '../api/scenarios'
import type { OptimizationOut } from '../api/types'
import { computeRadarScores } from '../lib/radar'
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

export function ComparisonPage() {
  const { t } = useTranslation()
  const { data, isLoading, isError } = useQuery({ queryKey: ['scenarios'], queryFn: listScenarios })
  const scenarios = useMemo(() => data?.scenarios ?? [], [data])

  const [scenarioId, setScenarioId] = useState('')
  const [selectedNames, setSelectedNames] = useState<string[]>([])
  const [holidays, setHolidays] = useState(12)
  const defaulted = useRef(false)

  useEffect(() => {
    if (defaulted.current || scenarios.length === 0) return
    defaulted.current = true
    setSelectedNames(scenarios.slice(0, 2).map((s) => s.name))
  }, [scenarios])

  const selected = useMemo(() => {
    const id = scenarioId || String(scenarios[0]?.id ?? '')
    return scenarios.find((s) => String(s.id) === id) ?? null
  }, [scenarios, scenarioId])

  const rows = useMemo(() => rowsOf(selected), [selected])

  const compared = useMemo(
    () => scenarios.filter((s) => selectedNames.includes(s.name)),
    [scenarios, selectedNames],
  )

  const currentTotal = rows.reduce((acc, r) => acc + (r.cost_current ?? 0), 0)
  const optimalTotal = rows.reduce((acc, r) => acc + (r.cost_optimal ?? 0), 0)
  const dailySavings = currentTotal - optimalTotal
  const thirtyDaySavings = dailySavings * 30
  const annualSavings = dailySavings * (365 - holidays)
  const fmtMoney = (n: number) =>
    '₱' + n.toLocaleString(undefined, { maximumFractionDigits: 0 })

  if (isLoading) return <ApiState.Loading />
  if (isError) return <ApiState.ErrorState />

  if (scenarios.length === 0) {
    return (
      <div>
        <h1 className="page-title">{t('page4.title')}</h1>
        <p className="page-caption">{t('page4.caption')}</p>
        <ApiState.Empty message={t('compare.empty')} />
      </div>
    )
  }

  return (
    <div>
      <h1 className="page-title">{t('page4.title')}</h1>
      <p className="page-caption">{t('page4.caption')}</p>

      <div className="card">
        <h2 className="card-title">{t('compare.title')}</h2>
        <div className="form-row">
          <div className="form-field">
            <label htmlFor="compare-scenario">{t('compare.source_scenario')}</label>
            <select
              id="compare-scenario"
              aria-label={t('compare.source_scenario')}
              value={scenarioId || String(scenarios[0]?.id ?? '')}
              onChange={(e) => setScenarioId(e.target.value)}
            >
              {scenarios.map((s) => (
                <option key={s.id} value={String(s.id)}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {rows.length > 0 && (
        <>
          <div className="card">
            <RadarChart
              current={computeRadarScores(rows, { current: true }).r}
              optimized={computeRadarScores(rows, { current: false }).r}
            />
          </div>
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
                  max={30}
                  value={holidays}
                  onChange={(e) => setHolidays(Number(e.target.value))}
                />
              </div>
            </div>
            <div className="card-grid">
              <MetricCard label={t('compare.daily_savings')} value={fmtMoney(dailySavings)} />
              <MetricCard label={t('compare.thirty_day_savings')} value={fmtMoney(thirtyDaySavings)} />
              <MetricCard label={t('compare.annual_savings')} value={fmtMoney(annualSavings)} />
            </div>
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
                <label key={s.id}>
                  <input
                    type="checkbox"
                    checked={selectedNames.includes(s.name)}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedNames((prev) => [...prev, s.name])
                      } else {
                        setSelectedNames((prev) => prev.filter((n) => n !== s.name))
                      }
                    }}
                  />
                  {s.name}
                </label>
              ))}
            </div>
          </div>
        </div>
        {compared.length >= 2 ? (
          <ScenarioCompareBars
            scenarios={compared.map((s) => ({ name: s.name, rows: rowsOf(s) }))}
          />
        ) : (
          <p className="page-caption">{t('compare.min_two')}</p>
        )}
      </div>
    </div>
  )
}
