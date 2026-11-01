import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it, vi } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import type { ScenarioOut } from '../../api/scenarios'
import type { SeparateComparison, SeparatePlanComparison } from '../../api/types'
import type { ResultRow } from '../../lib/results'
import { renderWithProviders } from '../../test/test-utils'
import { BusyLevelCard } from './BusyLevelCard'
import type { SelectedPlan } from './useSelectedPlan'

// Busy Level by period (spec 2026-10-29 §5.3). Rows mirror /current rows; plans mirror the
// separate comparison (peak_util) and saved shared scenario rows (rho_optimal, optimized_stable).

const separateRows: ResultRow[] = [
  { time: '08:00-09:00', queue_id: 'cashier_1', c: 1, rho: 0.75, stable: true },
  { time: '08:00-09:00', queue_id: 'cashier_2', c: 1, rho: 0.0019, stable: true },
  { time: '09:00-10:00', queue_id: 'cashier_1', c: 1, rho: 0.0019, stable: true },
  { time: '09:00-10:00', queue_id: 'cashier_2', c: 1, rho: 0.001, stable: true },
]
const sharedRows: ResultRow[] = [
  { time: '08:00-09:00', c: 3, rho: 0.95, stable: true },
  { time: '09:00-10:00', c: 3, rho: 0.5, stable: true },
]

function separatePlan(peaks: number[], target = 0.85): SelectedPlan {
  const times = ['08:00-09:00', '09:00-10:00']
  const comparison = { current: { periods: times.map((time) => ({ time, active_lanes: ['cashier_1', 'cashier_2'] })) } } as unknown as SeparateComparison
  const plan = { replications: 5, target, periods: times.map((time, index) => ({ time, peak_util: peaks[index] })) } as unknown as SeparatePlanComparison
  return { kind: 'separate', plan, comparison, usable: true, target }
}

function sharedPlan(): SelectedPlan {
  const scenario = { id: 3, name: 'Plan', results: { results: [
    { time: '08:00-09:00', c_optimal: 4, rho_optimal: 0.7125, optimized_stable: true },
    { time: '09:00-10:00', c_optimal: 2, rho_optimal: 0.75, optimized_stable: true },
  ] } } as unknown as ScenarioOut
  return { kind: 'shared', scenario, scenarios: [scenario], usable: true, target: 0.8 }
}

function Harness({ rows, separate, plan, planTarget = null, onPeriod = () => {} }: { rows: ResultRow[]; separate: boolean; plan: SelectedPlan; planTarget?: number | null; onPeriod?: (time: string | null) => void }) {
  const [period, setPeriod] = useState<string | null>(null)
  return <BusyLevelCard rows={rows} separate={separate} plan={plan} planTarget={planTarget} period={period} onPeriod={(time) => { onPeriod(time); setPeriod(time) }} />
}

function ribbon() {
  return within(screen.getByRole('group', { name: 'Periods' })).getAllByRole('button')
}

describe('Busy Level grid', () => {
  it('prints time, level word and fmtPctDecimal percentage for every period, and only the present levels in the legend', () => {
    renderWithProviders(<Harness rows={separateRows} separate plan={{ kind: 'none' }} />)
    expect(ribbon().map((button) => button.textContent)).toEqual(['08:00-09:00Normal75%', '09:00-10:00Lean0.19%'])
    expect(ribbon()[1]).toHaveAccessibleName('09:00-10:00: Lean, 0.19%')
    const legend = screen.getByRole('list')
    expect(within(legend).getAllByRole('listitem').map((item) => item.textContent)).toEqual(['Leanunder 60%', 'Normal60–80%'])
    expect(screen.queryByRole('group', { name: 'Chart view' })).not.toBeInTheDocument()
    expect(screen.getByText('Calculated estimate: every period is Lean or Normal; the busiest line peaks at 75% during 08:00-09:00.')).toBeInTheDocument()
  })

  it('separate Current: choosing a period syncs it and shows each cashier line', async () => {
    const user = userEvent.setup()
    const onPeriod = vi.fn()
    renderWithProviders(<Harness rows={separateRows} separate plan={{ kind: 'none' }} onPeriod={onPeriod} />)
    await user.click(ribbon()[0])
    expect(onPeriod).toHaveBeenLastCalledWith('08:00-09:00')
    expect(ribbon()[0]).toHaveAttribute('aria-pressed', 'true')
    const table = screen.getByRole('table')
    expect(within(table).getAllByRole('row').slice(1).map((row) => row.textContent)).toEqual(['cashier_175%Normal', 'cashier_20.19%Lean'])
    await user.click(ribbon()[0])
    expect(onPeriod).toHaveBeenLastCalledWith(null)
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('separate Suggested plan: uses peak_util, says per-cashier plan values are not available, and states the target', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Harness rows={separateRows} separate plan={separatePlan([0.6606, 0.5])} />)
    await user.click(screen.getByRole('button', { name: 'Suggested plan' }))
    expect(ribbon().map((button) => button.textContent)).toEqual(['08:00-09:00Normal66.06%', '09:00-10:00Lean50%'])
    expect(screen.getByText('Suggested plan, simulated: every period is Lean or Normal; the busiest cashier peaks at 66.06% during 08:00-09:00, below the plan’s 85% target.')).toBeInTheDocument()
    expect(screen.getByText('Simulated: busiest cashier’s mean over 5 runs')).toBeInTheDocument()
    await user.click(ribbon()[1])
    expect(screen.getByText('09:00-10:00: Values for each cashier are not available for the plan.')).toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('omits the "below target" takeaway when a period sits on the target, and counts periods above it', async () => {
    const user = userEvent.setup()
    const { unmount } = renderWithProviders(<Harness rows={separateRows} separate plan={separatePlan([0.85, 0.5])} />)
    await user.click(screen.getByRole('button', { name: 'Suggested plan' }))
    expect(screen.queryByText(/Suggested plan, simulated:/)).not.toBeInTheDocument()
    unmount()
    renderWithProviders(<Harness rows={separateRows} separate plan={separatePlan([0.9, 0.5])} />)
    await user.click(screen.getByRole('button', { name: 'Suggested plan' }))
    expect(screen.getByText('Suggested plan, simulated: 1 of 2 periods are above the plan’s 85% target; the busiest cashier peaks at 90% during 08:00-09:00.')).toBeInTheDocument()
  })

  it('shared: choosing a period shows the counter group, never cashier names, for Current and the plan', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Harness rows={sharedRows} separate={false} plan={sharedPlan()} planTarget={0.8} />)
    expect(screen.getByText('Calculated estimate: every period is Lean or Critical; the line peaks at 95% during 08:00-09:00.')).toBeInTheDocument()
    // Plan-target and Critical warnings stay visible.
    expect(screen.getByRole('status')).toHaveTextContent("08:00-09:00: Critical (90–100%) · above this plan's target of 80%")
    await user.click(ribbon()[0])
    let table = screen.getByRole('table')
    expect(within(table).getAllByRole('columnheader').map((cell) => cell.textContent)).toEqual(['Counters', 'Workload', 'Busy level'])
    expect(within(table).getAllByRole('row')[1].textContent).toBe('395%Critical')
    await user.click(screen.getByRole('button', { name: 'Suggested plan' }))
    expect(screen.getByText('Suggested plan, calculated: every period is Normal; the line peaks at 75% during 09:00-10:00.')).toBeInTheDocument()
    // Today's warnings are not repeated under the plan grid (review K-UC-4).
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(screen.queryByText(/above this plan's target/)).not.toBeInTheDocument()
    table = screen.getByRole('table')
    expect(within(table).getAllByRole('row')[1].textContent).toBe('471.25%Normal')
    expect(screen.queryByText(/cashier/i)).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Current' }))
    expect(screen.getByRole('status')).toHaveTextContent('08:00-09:00: Critical')
  })
})

describe('ribbon cell layout', () => {
  // Buttons are display: inline-flex app-wide; without a column direction the time, level and % sat on
  // one line and overflowed the 98 px cell at 375 px (browser check 2026-10-29).
  it('stacks time, level and percentage in each period button', () => {
    const css = readFileSync(resolve(process.cwd(), 'src/styles/charts.css'), 'utf8')
    expect(css).toMatch(/\.cv-ribbon button\s*\{[^}]*display: flex;[^}]*flex-direction: column;/)
  })
})
