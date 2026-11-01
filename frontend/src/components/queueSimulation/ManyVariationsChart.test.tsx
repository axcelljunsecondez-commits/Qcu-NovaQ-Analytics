import { describe, expect, it } from 'vitest'
import { act, cleanup, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { SimMcOut } from '../../api/types'
import { renderWithProviders } from '../../test/test-utils'
import en from '../../../public/locales/en/translation.json'
import { ManyVariationsChart, ManyVariationsInfo } from './ManyVariationsChart'

// Many variations on Checks (spec 2026-10-29 §8; owner decisions B7, B8, C5).

function row(time: string, queue: string | null, failure: number, extra: Partial<SimMcOut> = {}): SimMcOut {
  return { time, queue_id: queue, lambda: 2, mu: 3, c: 1, rho_mean: 0.5, rho_std: 0.05, rho_p95: 0.6, Lq_mean: 0.2, Wq_mean: 0.05,
    failure_rate: failure, failure_count: 0, status: 'PASS', error: null, ci_Wq_hw: 0.01, ci_Lq_hw: 0.01, adequate_samples: true,
    failure_rate_ci_lower: 0, failure_rate_ci_upper: 0.0019, num_trials: 2000, failure_threshold: 0.85, failure_rate_cap: 0.05, ...extra }
}

const separateRows = [
  row('09:00-10:00', 'cashier_2', 0.003, { failure_rate_ci_lower: 0.0014, failure_rate_ci_upper: 0.0065 }),
  row('09:00-10:00', 'cashier_4', 0.003, { failure_rate_ci_lower: 0.0014, failure_rate_ci_upper: 0.0065 }),
  row('09:00-10:00', 'cashier_1', 0),
  row('13:00-14:00', 'cashier_3', 0.027, { failure_rate_ci_lower: 0.0208, failure_rate_ci_upper: 0.0351 }),
  row('13:00-14:00', 'cashier_1', 0.0005, { failure_rate_ci_lower: 0.0001, failure_rate_ci_upper: 0.0028 }),
]

describe('ManyVariationsInfo', () => {
  it('fills the explanation from the stored trials, threshold and cap', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ManyVariationsInfo rows={separateRows} />)
    await user.hover(screen.getByRole('button', { name: en['charts.mc_info_name'] }))
    expect(screen.getByRole('tooltip')).toHaveTextContent(en['charts.mc_info_text'].replace('{{trials}}', '2,000').replace('{{target}}', '85%').replace('{{cap}}', '5%'))
  })

  it('is not shown when the stored rows disagree on the threshold', () => {
    renderWithProviders(<ManyVariationsInfo rows={[row('a', 'c1', 0), row('b', 'c1', 0, { failure_threshold: 0.75 })]} />)
    expect(screen.queryByRole('button', { name: en['charts.mc_info_name'] })).not.toBeInTheDocument()
  })
})

describe('ManyVariationsChart', () => {
  it('keeps a partial period unavailable and withholds a global ranking when one cashier rate is missing', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ManyVariationsChart rows={[
      row('a', 'c1', 0.02), row('a', 'c2', Number.NaN), row('b', 'c1', 0.03),
    ]} separate run="current" planTarget={null} seed={null} />)
    const points = screen.getAllByTestId('row-chart-row')
    expect(points[0]).toHaveTextContent('Unavailable')
    expect(points[0].querySelector('.cv-m-mc')).toBeNull()
    expect(points[1]).toHaveTextContent('c1 3%')
    expect(points.every((point) => !point.classList.contains('hl'))).toBe(true)
    expect(screen.queryByTestId('mc-take')).not.toBeInTheDocument()
    await user.click(points[0])
    expect(screen.getByTestId('mc-detail')).toHaveTextContent('c12%')
    expect(screen.getByTestId('mc-detail')).toHaveTextContent('c2Unavailable')
  })

  it('draws one row per period with the highest-risk cashier (tie: queue id), the cap line and the decimal rule', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ManyVariationsChart rows={separateRows} separate run="plan" planTarget={0.85} seed={42} />)
    const rows = screen.getAllByTestId('row-chart-row')
    expect(rows).toHaveLength(2)
    expect(rows[0]).toHaveTextContent('cashier_2 0.3%')
    expect(rows[1]).toHaveTextContent('cashier_3 2.7%')
    expect(rows[1]).toHaveClass('hl')
    expect(screen.getByTestId('row-chart-reference')).toHaveTextContent('5%')
    expect(screen.getByTestId('mc-take')).toHaveTextContent('Closest to the 5% cap: 13:00-14:00, cashier_3, with 2.7% of 2,000 variations failing.')
    await user.click(rows[0])
    const detail = screen.getByTestId('mc-detail')
    expect(within(detail).getAllByRole('row').slice(1).map((item) => item.textContent)).toEqual([
      'cashier_20.3%0.14% – 0.65%', 'cashier_40.3%0.14% – 0.65%', 'cashier_10%0% – 0.19%',
    ])
    expect(screen.getByText('Trials: 2,000')).toBeInTheDocument()
    expect(screen.getByText('Failure rate cap: 5%')).toBeInTheDocument()
    expect(screen.getByText('Random seed: 42')).toBeInTheDocument()
    expect(screen.getByText(en['charts.mc_chip_fail_plan'].replace('{{threshold}}', '85%'))).toBeInTheDocument()
  })

  it('reads a row out with its range when the chart is focused, starting at the highest-risk period', () => {
    renderWithProviders(<ManyVariationsChart rows={separateRows} separate run="plan" planTarget={0.85} seed={null} />)
    act(() => screen.getByRole('group', { name: en['charts.mc_chart_name'] }).focus())
    expect(screen.getByTestId('row-chart-readout')).toHaveTextContent('13:00-14:00Queue: cashier_3Failure rate: 2.7%95% range: 2.08% – 3.51%')
  })

  it('does not call a threshold the plan target when the stored threshold differs from it', () => {
    renderWithProviders(<ManyVariationsChart rows={separateRows} separate run="plan" planTarget={0.75} seed={null} />)
    expect(screen.getByText(en['charts.mc_chip_fail_current'].replace('{{threshold}}', '85%'))).toBeInTheDocument()
    expect(screen.queryByText(en['charts.mc_chip_fail_plan'].replace('{{threshold}}', '85%'))).not.toBeInTheDocument()
  })

  it('shows a shared line as one row per period without a cashier name', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ManyVariationsChart rows={[row('08:00-09:00', null, 0), row('09:00-10:00', null, 0.0019, { failure_rate_ci_upper: 0.004 })]}
      separate={false} run="plan" planTarget={null} seed={null} />)
    const rows = screen.getAllByTestId('row-chart-row')
    expect(rows.map((item) => item.textContent)).toEqual(['08:00-09:000%', '09:00-10:000.19%'])
    await user.click(rows[0])
    expect(screen.queryByTestId('mc-detail')).not.toBeInTheDocument()
    expect(screen.getByTestId('row-chart-readout')).not.toHaveTextContent('Queue')
    expect(screen.getByText(en['charts.mc_chip_fail_shared'].replace('{{threshold}}', '85%'))).toBeInTheDocument()
    expect(screen.getByTestId('mc-take')).toHaveTextContent('Closest to the 5% cap: 09:00-10:00, with 0.19% of 2,000 variations failing.')
  })

  it('says "above the cap" instead of "closest to the cap" when the highest rate is above it, for the plan and the Current run', () => {
    const over = [row('09:00-10:00', 'cashier_1', 0.003), row('13:00-14:00', 'cashier_3', 0.081, { failure_rate_ci_lower: 0.07, failure_rate_ci_upper: 0.09 })]
    for (const run of ['plan', 'current'] as const) {
      const { unmount } = renderWithProviders(<ManyVariationsChart rows={over} separate run={run} planTarget={0.85} seed={null} />)
      expect(screen.getByTestId('mc-take')).toHaveTextContent('Highest risk, above the 5% cap: 13:00-14:00, cashier_3, with 8.1% of 2,000 variations failing.')
      expect(screen.getByTestId('mc-take')).not.toHaveTextContent('Closest')
      unmount()
      renderWithProviders(<ManyVariationsChart rows={[row('08:00-09:00', null, 0.06)]} separate={false} run={run} planTarget={null} seed={null} />)
      expect(screen.getByTestId('mc-take')).toHaveTextContent('Highest risk, above the 5% cap: 08:00-09:00, with 6% of 2,000 variations failing.')
      cleanup()
    }
  })

  it('keeps "closest to the cap" for a highest rate exactly at the cap', () => {
    renderWithProviders(<ManyVariationsChart rows={[row('08:00-09:00', null, 0.05)]} separate={false} run="current" planTarget={null} seed={null} />)
    expect(screen.getByTestId('mc-take')).toHaveTextContent('Closest to the 5% cap: 08:00-09:00, with 5% of 2,000 variations failing.')
  })

  it('draws no cap line and no takeaway when the stored cap is unknown', () => {
    renderWithProviders(<ManyVariationsChart rows={[row('a', 'c1', 0.01, { failure_rate_cap: undefined })]} separate run="current" planTarget={null} seed={null} />)
    expect(screen.queryByTestId('row-chart-reference')).not.toBeInTheDocument()
    expect(screen.queryByTestId('mc-take')).not.toBeInTheDocument()
    expect(screen.getByText(en['charts.mc_chip_fail_current'].replace('{{threshold}}', '85%'))).toBeInTheDocument()
  })

  it('labels a period without a rate as a gap and has no range there', () => {
    renderWithProviders(<ManyVariationsChart rows={[row('a', 'c1', Number.NaN, { failure_rate_ci_lower: undefined, failure_rate_ci_upper: undefined })]} separate run="current" planTarget={null} seed={null} />)
    expect(screen.getByTestId('row-chart-row')).toHaveTextContent('Unavailable')
  })
})
