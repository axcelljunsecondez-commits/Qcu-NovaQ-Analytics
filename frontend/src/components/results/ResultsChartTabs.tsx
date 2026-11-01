import { useRef, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import type { ObservedWaitPeriod } from '../../api/types'
import type { StaffingSetup } from '../../lib/longestLine'
import { headingText } from '../../lib/headingText'
import { chartTabs, type ChartTab } from '../../lib/resultsTabs'
import type { ResultRow } from '../../lib/results'
import { BusyLevelCard } from './BusyLevelCard'
import type { SelectedPlan } from './useSelectedPlan'
import { WaitByHourCard } from './WaitByHourCard'

export type { ChartTab }

const LABELS: Record<ChartTab, string> = { wait: 'results.plan_changes', level: 'results.day_by_level' }

/**
 * Analysis Results charts as tabs (spec 2026-10-29 §5.1, owner decision B1): "What the plan changes"
 * first, "Your day, by Busy Level" second. One panel shows one card. A tab with nothing to show is
 * left out; a single remaining card renders without a tablist. The chosen tab lives in `?chart=`.
 */
export function ResultsChartTabs({ chart, onChart, observed, rows, selectedModel, separate, separateRows, plan, planTarget, period, onPeriod, staffing, noPlanPrompt }: {
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
  /** Separate lines: the Setup and the file's records, for the Today view's staffed-cashier counts. */
  staffing?: { setup: StaffingSetup; records: Record<string, unknown>[] | null }
  /** The no-plan prompt shown under the wait chart (planning file, no plan selected); the page passes it only while the wait tab is open. */
  noPlanPrompt?: ReactNode
}) {
  const { t } = useTranslation()
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({})
  const { available, active } = chartTabs(chart, observed, rows, plan)
  if (active === null) return null

  const panel = active === 'wait'
    ? <WaitByHourCard observed={observed} rows={rows} selectedModel={selectedModel} separate={separate} plan={plan} staffing={staffing} footer={noPlanPrompt} />
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
