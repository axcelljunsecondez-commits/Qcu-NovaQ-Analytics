import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { NumericValue } from './NumericValue'
import { MetricCard } from './MetricCard'

describe('numeric presentation preserves existing text', () => {
  it.each(['08.4200 min', '87.25%', '−1,234.5000 min', '-1\u00a0234,50\u00a0min', '+1.20e-5 hours', '—', 'Not available', ''])('retains %j including units, precision and grouping', (text) => {
    const { container } = render(<div data-testid="value"><NumericValue>{text}</NumericValue></div>)
    expect(screen.getByTestId('value').textContent).toBe(text)
    expect([...container.querySelectorAll('.numeric-value')].every((node) => !/min|hours|%/.test(node.textContent ?? ''))).toBe(true)
  })

  it('does not infer numeric intent from model names or other text', () => {
    const { container } = render(<MetricCard label="Model" value="M/M/1 at counter 2" />)
    expect(screen.getByRole('group', { name: 'Model' })).toHaveTextContent('M/M/1 at counter 2')
    expect(container.querySelector('.numeric-value')).toBeNull()
  })

  it('allows explicit numeric string opt-in and typed numbers', () => {
    const { container } = render(<><MetricCard label="Wait" value="08.42 min" numeric /><MetricCard label="Count" value={12} /></>)
    expect([...container.querySelectorAll('.numeric-value')].map((node) => node.textContent)).toEqual(['08.42', '12'])
    expect(screen.getByRole('group', { name: 'Wait' }).textContent).toBe('Wait08.42 min')
  })
})
