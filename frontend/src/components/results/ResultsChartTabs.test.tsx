import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useState } from 'react'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/test-utils'
import { ResultsChartTabs, type ChartTab } from './ResultsChartTabs'

vi.mock('../../api/auth', () => ({ me: vi.fn(async () => ({ user: null })), login: vi.fn(), logout: vi.fn() }))
vi.mock('./WaitByHourCard', () => ({ WaitByHourCard: () => <p>Wait fixture</p> }))
vi.mock('./BusyLevelCard', () => ({ BusyLevelCard: () => <p>Busy fixture</p> }))
const animate = vi.fn((_frames: unknown, _options: { duration: number }) => ({ cancel: vi.fn() }))
const originalAnimate = HTMLElement.prototype.animate
const props = { chart: null, onChart: vi.fn(), observed: [], rows: [{ time: 'first' }, { time: 'second' }], selectedModel: null, separate: false, separateRows: false, plan: { kind: 'none' as const }, planTarget: null, period: null, onPeriod: vi.fn() }
function Controlled() {
  const [chart, onChart] = useState<ChartTab | null>(null)
  return <ResultsChartTabs {...props} chart={chart} onChart={onChart} />
}
beforeEach(() => { animate.mockClear(); Object.defineProperty(HTMLElement.prototype, 'animate', { configurable: true, value: animate }) })
afterEach(() => { if (originalAnimate) Object.defineProperty(HTMLElement.prototype, 'animate', { configurable: true, value: originalAnimate }); else Reflect.deleteProperty(HTMLElement.prototype, 'animate') })

describe('chart panel presentation', () => {
  it('retains keyboard selection and animates only the selected panel', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Controlled />)
    const tabs = screen.getAllByRole('tab')
    expect(animate).not.toHaveBeenCalled()
    tabs[0].focus()
    await user.keyboard('{ArrowRight}')
    expect(tabs[1]).toHaveFocus()
    expect(tabs[1]).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tabpanel')).toHaveTextContent('Busy fixture')
    expect(animate).toHaveBeenCalledTimes(1)
    expect(animate.mock.calls[0][1].duration).toBe(205)
    await user.click(tabs[1])
    expect(animate).toHaveBeenCalledTimes(1)
  })

  it('does not animate data refreshes or invalid chart queries that retain the same panel', () => {
    const { rerender } = renderWithProviders(<ResultsChartTabs {...props} />)
    rerender(<ResultsChartTabs {...props} rows={[{ time: 'third' }, { time: 'fourth' }]} />)
    rerender(<ResultsChartTabs {...props} chart="invalid" />)
    expect(screen.getByRole('tabpanel')).toHaveTextContent('Wait fixture')
    expect(animate).not.toHaveBeenCalled()
  })
})
