// Which Analysis Results chart tabs have something to show (spec 2026-10-29 §5.1). Shared by the tabs
// and the page, so the no-plan prompt is placed under the wait chart only while that tab is open (K-UC-2).
import type { ObservedWaitPeriod } from '../api/types'
import { timeOf, type ResultRow } from './results'

export type ChartTab = 'wait' | 'level'

/** The tabs with content, and the one `?chart=` opens (absent or invalid: the first; none: null). */
export function chartTabs(chart: string | null, observed: ObservedWaitPeriod[] | null, rows: ResultRow[], plan: { kind: string; usable?: boolean }): { available: ChartTab[]; active: ChartTab | null } {
  // The selected plan (useSelectedPlan's SelectedPlan): only a usable separate or shared plan has a Plan view.
  const planUsable = (plan.kind === 'separate' || plan.kind === 'shared') && plan.usable === true
  const available: ChartTab[] = []
  if (observed !== null || planUsable) available.push('wait')
  if (new Set(rows.map(timeOf)).size > 1) available.push('level')
  return { available, active: available.find((tab) => tab === chart) ?? available[0] ?? null }
}
