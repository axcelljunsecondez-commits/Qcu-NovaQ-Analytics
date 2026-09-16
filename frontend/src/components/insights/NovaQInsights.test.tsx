import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '../../test/test-utils'
import { NovaQInsights } from './NovaQInsights'
import type { Insight } from '../../lib/insights'

const insights: Insight[] = [
  {
    type: 'success',
    title: 'Staffing Reduction Possible',
    message: 'NovaQ recommends reducing from 3 to 2 service points.',
  },
]

describe('NovaQInsights accessibility', () => {
  it('exposes dynamically rendered insights as a polite live region', () => {
    renderWithProviders(<NovaQInsights insights={insights} />)
    const region = screen.getByRole('status')
    expect(region).toHaveClass('novaq-insights')
    expect(region).toHaveTextContent('Staffing Reduction Possible')
  })

  it('keeps decorative icons hidden while preserving heading structure', () => {
    const { container } = renderWithProviders(<NovaQInsights insights={insights} />)
    expect(container.querySelector('.insight-icon')).toHaveAttribute('aria-hidden', 'true')
    expect(screen.getByRole('heading', { name: 'Staffing Reduction Possible' })).toBeInTheDocument()
  })

  it('renders nothing when there are no insights', () => {
    const { container } = renderWithProviders(<NovaQInsights insights={[]} />)
    expect(container).toBeEmptyDOMElement()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
