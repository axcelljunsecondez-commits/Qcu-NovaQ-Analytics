import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { SimMcOut } from '../../api/types'
import { renderWithProviders } from '../../test/test-utils'
import { CheckMethodDetails } from './CheckMethodDetails'

// Phase E: the method and the parameters every stored Many variations row agrees on; never the form values.

const row = (overrides: Partial<SimMcOut> = {}) => ({ time: '08:00', queue_id: 'east-07', num_trials: 2000, failure_threshold: 0.85, failure_rate_cap: 0.05, ...overrides }) as SimMcOut

describe('CheckMethodDetails', () => {
  // Keyboard Enter/Space on <summary> is native browser behaviour that jsdom does not emulate; it is checked in
  // real Chrome (CDP runtime check). Here: a native, closed disclosure that the summary toggles.
  it('is a native disclosure, closed by default, toggled by its summary', async () => {
    const user = userEvent.setup()
    renderWithProviders(<CheckMethodDetails rows={[row(), row({ queue_id: 'lane-A' })]} planTarget={0.85} />)
    const details = screen.getByTestId('check-method-details')
    expect(details.tagName).toBe('DETAILS')
    expect(details).not.toHaveAttribute('open')
    const summary = screen.getByText('How checks were calculated')
    expect(summary.tagName).toBe('SUMMARY')
    expect(summary.querySelector('button')).toBeNull()
    await user.click(summary)
    expect(details).toHaveAttribute('open')
    await user.click(summary)
    expect(details).not.toHaveAttribute('open')
  })

  it('shows the stored trials and the plan-target rule when every row agrees', () => {
    renderWithProviders(<CheckMethodDetails rows={[row(), row({ queue_id: 'lane-A' })]} planTarget={0.85} />)
    expect(screen.getByText('Many variations')).toBeInTheDocument()
    expect(screen.getByTestId('check-method-trials')).toHaveTextContent('2,000')
    expect(screen.getByTestId('check-method-rule')).toHaveTextContent('A variation fails when a cashier’s Utilization Rate is above 85%, the plan’s target.')
  })

  it('does not call another threshold the plan target', () => {
    renderWithProviders(<CheckMethodDetails rows={[row({ failure_threshold: 0.8 })]} planTarget={0.85} />)
    expect(screen.getByTestId('check-method-rule')).toHaveTextContent('A variation fails when a cashier’s Utilization Rate is above 80%.')
  })

  it('shows Unavailable trials and no rule when rows disagree or there are none', () => {
    const { unmount } = renderWithProviders(<CheckMethodDetails rows={[row(), row({ num_trials: 1000, failure_threshold: 0.75 })]} planTarget={0.85} />)
    expect(screen.getByTestId('check-method-trials')).toHaveTextContent('Unavailable')
    expect(screen.queryByTestId('check-method-rule')).not.toBeInTheDocument()
    unmount()
    renderWithProviders(<CheckMethodDetails rows={[]} />)
    expect(screen.getByTestId('check-method-trials')).toHaveTextContent('Unavailable')
    expect(screen.queryByTestId('check-method-rule')).not.toBeInTheDocument()
  })

  it('uses the Tagalog labels', () => {
    renderWithProviders(<CheckMethodDetails rows={[]} />, { lang: 'tl' })
    expect(screen.getByText('Paano kinalkula ang mga check')).toBeInTheDocument()
    expect(screen.getByText('Maraming bersyon')).toBeInTheDocument()
    expect(screen.getByText('Mga trial')).toBeInTheDocument()
    expect(screen.getByTestId('check-method-trials')).toHaveTextContent('Hindi available')
  })
})
