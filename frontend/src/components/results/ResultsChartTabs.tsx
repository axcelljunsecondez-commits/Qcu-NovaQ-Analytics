import { useRef, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import type { ObservedWaitPeriod } from '../../api/types'
import { headingText } from '../../lib/headingText'
import { timeOf, type ResultRow } from '../../lib/results'
import { BusyLevelCard } from './BusyLevelCard'
import type { SelectedPlan } from './useSelectedPlan'
import { WaitByHourCard } from './WaitByHourCard'

export type ChartTab = 'wait' | 'level'

const LABELS: Record<ChartTab, string> = { wait: 'results.plan_changes', level: 'results.day_by_level' }

/**
 * Analysis Results charts as tabs (spec 2026-10-29 §5.1, owner decision B1): "What the plan changes"
 * first, "Your day, by Busy Level" second. One panel shows one card. A tab with nothing to show is
 * left out; a single remaining card renders without a tablist. The chosen tab lives in `?chart=`.
 */
export function ResultsChartTabs({ chart, onChart, observed, rows, selectedModel, separate, separateRows, plan, planTarget, period, onPeriod, noPlanPrompt }: {
  /** `?chart=` from the address; absent or invalid opens the first available tab. */
  chart: string | null
  onChart: (tab: ChartTab) => void
  observed: ObservedWaitPeriod[] | null
  rows: ResultRow[]
  selectedModel: string | null
  /** The analysis uses separate cashier lines. */
  separate: boolean
  /** Today's rows are per cashier line. */
  separateRows: boolean
  plan: SelectedPlan
  planTarget: number | null
  period: string | null
  onPeriod: (time: string | null) => void
  /** The no-plan prompt shown under the wait chart (planning file, no plan selected). */
  noPlanPrompt?: ReactNode
}) {
  const { t } = useTranslation()
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({})
  const planUsable = (plan.kind === 'separate' || plan.kind === 'shared') && plan.usable
  const available: ChartTab[] = []
  if (observed !== null || planUsable) available.push('wait')
  if (new Set(rows.map(timeOf)).size > 1) available.push('level')
  if (available.length === 0) return null
  const active: ChartTab = available.find((tab) => tab === chart) ?? available[0]

  const panel = active === 'wait'
    ? <WaitByHourCard observed={observed} rows={rows} selectedModel={selectedModel} separate={separate} plan={plan} footer={noPlanPrompt} />
    : <BusyLevelCard rows={rows} separate={separateRows} plan={plan} planTarget={planTarget} period={period} onPeriod={onPeriod} />
  if (available.length === 1) return panel

  const choose = (tab: ChartTab, focus: boolean) => {
    onChart(tab)
    if (focus) tabRefs.current[tab]?.focus()
  }
  return (
    <div className="results-chart-tabs">
      <div className="tabs cv-tabs" role="tablist" aria-label={t('charts.tabs_label')}>
        {available.map((tab, index) => (
          <button key={tab} type="button" role="tab" lang="en" id={`results-chart-tab-${tab}`} aria-controls="results-chart-panel"
            aria-selected={tab === active} tabIndex={tab === active ? 0 : -1} className={`tab${tab === active ? ' active' : ''}`}
            ref={(element) => { tabRefs.current[tab] = element }} onClick={() => choose(tab, false)}
            onKeyDown={(event) => {
              const last = available.length - 1
              const next = event.key === 'ArrowRight' ? (index + 1) % available.length
                : event.key === 'ArrowLeft' ? (index + last) % available.length
                  : event.key === 'Home' ? 0 : event.key === 'End' ? last : null
              if (next !== null) { event.preventDefault(); choose(available[next], true) }
            }}>
            {headingText(t, LABELS[tab])}
          </button>
        ))}
      </div>
      <div className="cv-tab-panel" id="results-chart-panel" role="tabpanel" aria-labelledby={`results-chart-tab-${active}`} tabIndex={0}>
        {panel}
      </div>
    </div>
  )
}
