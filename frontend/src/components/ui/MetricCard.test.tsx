import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { ProgressBar, MetricCard } from './MetricCard'

describe('MetricCard', () => {
  it('renders label, value and sub', () => {
    const { getByText } = render(<MetricCard label="Utilization" value="75%" sub="+5%" />)
    expect(getByText('Utilization')).toBeInTheDocument()
    expect(getByText('75%')).toBeInTheDocument()
    expect(getByText('+5%')).toBeInTheDocument()
  })
})

describe('ProgressBar', () => {
  it('renders width proportional to value', () => {
    const { container } = render(<ProgressBar value={0.5} />)
    const fill = container.querySelector('.progress-fill')
    expect(fill).toHaveStyle({ width: '50%' })
  })
})
