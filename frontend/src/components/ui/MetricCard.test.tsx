import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import { MetricCard } from './MetricCard'

describe('MetricCard', () => {
  it('renders label, value and sub', () => {
    const { getByText } = render(<MetricCard label="Utilization" value="75%" sub="+5%" />)
    expect(getByText('Utilization')).toBeInTheDocument()
    expect(getByText('75%')).toBeInTheDocument()
    expect(getByText('+5%')).toBeInTheDocument()
  })
})
