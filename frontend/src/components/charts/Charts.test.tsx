import { describe, expect, it, vi } from 'vitest'
import React from 'react'
import { renderWithProviders } from '../../test/test-utils'
import type { OptimizationOut } from '../../api/types'

// Capture the Plotly `data` prop instead of rendering charts: the audit asserts
// on the exact series values (null gap vs numeric zero), not on pixels.
vi.mock('react-plotly.js/factory', () => ({
  default: () => (props: { data: unknown }) =>
    React.createElement('div', {
      className: 'plotly-capture',
      'data-data': JSON.stringify(props.data),
    }),
}))

import { CostWaterfall, ServerCompareBars, UtilizationCompareBars } from './Charts'

const valid: OptimizationOut = {
  time: '08:00-09:00',
  lambda_: 30,
  mu: 12,
  c_current: 3,
  c_optimal: 4,
  rho_current: 0.9,
  rho_optimal: 0.7,
  Wq_current: 0.1,
  Wq_optimal: 0.05,
  Lq_current: 3.5,
  Lq_optimal: 0.5,
  cost_current: 800,
  cost_optimal: 500,
  delta_cost: 300,
  delta_Wq: 0.05,
  delta_Lq: 3,
  delta_c: 1,
  delta_rho: -0.2,
  waiting_cost_current: 300,
  waiting_cost_optimal: 150,
  abandonment_cost_current: 100,
  abandonment_cost_optimal: 50,
  cost_per_server: 87,
  current_stable: true,
  optimized_stable: true,
  recommendation: '',
  warning: '',
}

const blocked: OptimizationOut = {
  ...valid,
  lambda_: 5,
  mu: 4,
  c_current: 1,
  c_optimal: null,
  rho_current: null,
  rho_optimal: null,
  Wq_current: null,
  Wq_optimal: null,
  Lq_current: null,
  Lq_optimal: null,
  cost_current: null,
  cost_optimal: null,
  delta_cost: null,
  delta_Wq: null,
  delta_Lq: null,
  delta_c: null,
  delta_rho: null,
  waiting_cost_current: null,
  waiting_cost_optimal: null,
  abandonment_cost_current: null,
  abandonment_cost_optimal: null,
  cost_per_server: null,
  current_stable: false,
  optimized_stable: false,
  feasibility_status: 'INVALID_INPUT',
  warning: 'Optimization is not supported.',
}

function plottedData(container: HTMLElement, testId: string): Array<{ y: Array<number | null> }> {
  const frame = container.querySelector(`[data-testid="${testId}"] .plotly-capture`)
  expect(frame).not.toBeNull()
  return JSON.parse(frame!.getAttribute('data-data') as string)
}

describe('optimization chart null semantics', () => {
  it('plots null staffing as a gap, never as zero servers', () => {
    const { container } = renderWithProviders(<ServerCompareBars rows={[{ ...blocked, c_current: null }]} />)
    const data = plottedData(container, 'chart-server-compare')
    expect(data[0].y).toEqual([null])
    expect(data[1].y).toEqual([null])
  })

  it('preserves evaluated staffing values exactly', () => {
    const { container } = renderWithProviders(<ServerCompareBars rows={[valid]} />)
    const data = plottedData(container, 'chart-server-compare')
    expect(data[0].y).toEqual([3])
    expect(data[1].y).toEqual([4])
  })

  it('plots null utilization as a gap', () => {
    const { container } = renderWithProviders(<UtilizationCompareBars rows={[blocked]} />)
    const data = plottedData(container, 'chart-utilization-compare')
    expect(data[0].y).toEqual([null])
    expect(data[1].y).toEqual([null])
  })

  it('keeps waterfall totals unavailable for blocked rows but plots genuine zeroes', () => {
    const { container } = renderWithProviders(<CostWaterfall rows={[blocked]} />)
    const blockedData = plottedData(container, 'chart-cost-waterfall')
    for (const series of blockedData) {
      expect(series.y.every((value) => value === null)).toBe(true)
    }

    const zeroCost: OptimizationOut = {
      ...valid,
      abandonment_cost_current: 0,
      abandonment_cost_optimal: 0,
    }
    const { container: validContainer } = renderWithProviders(<CostWaterfall rows={[zeroCost]} />)
    const validData = plottedData(validContainer, 'chart-cost-waterfall')
    // Abandonment is index 2: a genuine zero is plotted as 0, not dropped.
    expect(validData[0].y[2]).toBe(0)
    expect(validData[1].y[2]).toBe(0)
  })
})
