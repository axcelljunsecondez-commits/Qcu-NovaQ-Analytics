import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import type { ScenarioOut } from '../../api/scenarios'
import type { AnalysisSegment, DatasetOut, SeparateComparison, SeparatePlanComparison } from '../../api/types'
import { renderWithProviders } from '../../test/test-utils'
import { PlanChanges } from './PlanChanges'
import type { SelectedPlan } from './useSelectedPlan'

// The plan section after the chart redesign (spec 2026-10-29 §5.4, §6, OD-5/W17): Switcher,
// calculated result and cost line stay; the per-period plan table moved into the chart tabs.

const dataset: DatasetOut = {
  id: 11, analysis_id: 7, name: 'n', source_filename: 'n.xlsx', source_format: 'xlsx', row_count: 3, created_at: '', normalized: null,
  validation: { ok: true, message: 'Input data is valid.', period_basis: 'representative_day', observation_days: 14 },
  data_dates: { first: '2000-01-03', last: '2000-01-16', source: 'stored_at_upload' },
}

const hourly: AnalysisSegment[] = [
  { id: 'morning', start_time: '08:00', end_time: '09:00', active_queue_ids: null },
  { id: 'noon', start_time: '12:00', end_time: '13:00', active_queue_ids: null },
]

function separatePlan(total: number): SelectedPlan {
  const plan = {
    scenario_id: 21, name: 'Lanes plan', dataset_id: 11, target: 0.85, evaluation_method: 'DES_REPLICATIONS', replications: 5, base_seed: 42, overall: null,
    wait_basis_kind: 'simulation', stale: false, valid: true, valid_reason: null,
    totals: { lane_periods: 4, wait_mean: 0.02, peak_util: 0.66, waiting_cost_mean: 5, total_cost_mean: total },
    periods: [
      { time: 'morning', current_active_lanes: ['A', 'B'], optimal_active_lanes: 2, adjustment: 0, peak_util: 0.6, wait_mean: 0.02, wait_ci: [-0.01, 0.05], waiting_cost_mean: 2, total_cost_mean: 1000.25, total_cost_ci: null, status: null },
      { time: 'noon', current_active_lanes: ['A', 'B'], optimal_active_lanes: 3, adjustment: 1, peak_util: 0.66, wait_mean: 0.02, wait_ci: [0.01, 0.05], waiting_cost_mean: 3, total_cost_mean: 500.5, total_cost_ci: null, status: null },
    ],
  } as unknown as SeparatePlanComparison
  const comparison = {
    analysis_id: 7, queue_structure: 'separate_queues', selected_scenario_id: 21, plans: [plan],
    current: { dataset_id: 11, wait_mean: 0.19, wait_basis: 'analytical', util_max: 0.8, waiting_cost: null, waiting_cost_basis: null, total_cost: null, total_cost_reason: null,
      periods: [{ time: 'morning', active_lanes: ['A', 'B'] }, { time: 'noon', active_lanes: ['A', 'B'] }] },
  } as unknown as SeparateComparison
  return { kind: 'separate', plan, comparison, usable: true, target: 0.85 }
}

function sharedPlan(): SelectedPlan {
  const row = (time: string, c: number, cost: number) => ({ time, c_current: 3, c_optimal: c, rho_current: 0.7, rho_optimal: 0.6, Wq_current: 0.05, Wq_optimal: 0.01,
    Lq_optimal: 0.1, cost_current: 500, cost_optimal: cost, current_stable: true, optimized_stable: true })
  const scenario = { id: 3, name: 'Plan A', provenance: 'verified_snapshot', evidence_status: 'CURRENT', results: { results: [row('morning', 4, 450), row('noon', 3, 400)] } } as unknown as ScenarioOut
  return { kind: 'shared', scenario, scenarios: [scenario], usable: true, target: 0.7 }
}

describe('PlanChanges after the chart redesign', () => {
  it('separate lines: no per-period plan table, both kinds named in the wait line, and the cost labelled per average day', () => {
    renderWithProviders(<PlanChanges analysisId={7} plan={separatePlan(1500.75)} dataset={dataset} periodBasis="representative_day" segments={hourly} />)
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.getByText('The calculation suggests these counter changes: noon: 2 → 3 counters.')).toBeInTheDocument()
    expect(screen.getByText('Wait (average of the periods): Calculated estimate 11.4 min → Suggested plan, simulated 1.2 min.')).toBeInTheDocument()
    expect(screen.getByTestId('plan-cost')).toHaveTextContent('Unavailable → ₱1,500.75 per average day (from 14 days of data)')
    expect(screen.getByText(/^Total cost: Unavailable → ₱1,500\.75 per average day \(from 14 days of data\)\./)).toBeInTheDocument()
  })

  it('separate lines: no label when the total is not the period sum or the basis is not a day basis', () => {
    const { unmount } = renderWithProviders(<PlanChanges analysisId={7} plan={separatePlan(1400)} dataset={dataset} periodBasis="representative_day" segments={hourly} />)
    expect(screen.getByTestId('plan-cost')).toHaveTextContent(/→ ₱1,400$/)
    unmount()
    renderWithProviders(<PlanChanges analysisId={7} plan={separatePlan(1500.75)} dataset={dataset} periodBasis={undefined} segments={hourly} />)
    expect(screen.getByTestId('plan-cost')).toHaveTextContent(/→ ₱1,500\.75$/)
  })

  it('separate lines: no label when a Setup segment is not 60 minutes (period costs are hourly rates, K-UC-1)', () => {
    const halfHour: AnalysisSegment[] = [{ ...hourly[0], end_time: '08:30' }, hourly[1]]
    renderWithProviders(<PlanChanges analysisId={7} plan={separatePlan(1500.75)} dataset={dataset} periodBasis="representative_day" segments={halfHour} />)
    expect(screen.getByTestId('plan-cost')).toHaveTextContent(/→ ₱1,500\.75$/)
    expect(document.body.textContent).not.toMatch(/per average day|total for \d+ days/)
  })

  it('shared line: keeps the calculated wait line and adds no day-basis label (shared semantics UNKNOWN)', () => {
    renderWithProviders(<PlanChanges analysisId={7} plan={sharedPlan()} dataset={dataset} periodBasis="representative_day" segments={hourly} />)
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    expect(screen.getByText('Estimated wait (average of the periods): 3 → 0.6 min.')).toBeInTheDocument()
    expect(screen.getByText('Total cost: ₱1,000 → ₱850.', { exact: false })).toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/per average day|total for \d+ days/)
  })

  it('shows the no-plan prompt unless it is already shown under the wait chart', () => {
    const { unmount } = renderWithProviders(<PlanChanges analysisId={7} plan={{ kind: 'none' }} />)
    expect(screen.getByText('No plan is selected yet. Choose one in Suggested plans to see what it changes.')).toBeInTheDocument()
    unmount()
    const { container } = renderWithProviders(<PlanChanges analysisId={7} plan={{ kind: 'none' }} promptShown />)
    expect(container).toBeEmptyDOMElement()
  })
})
