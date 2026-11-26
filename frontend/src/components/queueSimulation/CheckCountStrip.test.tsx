import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import { renderWithProviders } from '../../test/test-utils'
import { CheckCountStrip } from './CheckCountStrip'

// Phase E (owner O-E1, OD-E3, OD-E4): recorded counts only; nothing is derived or filled in.

function values() {
  const strip = screen.getByTestId('check-count-strip')
  return within(strip).getAllByRole('definition').map((node) => node.textContent)
}

describe('CheckCountStrip', () => {
  it('shows the four recorded values under their labels', () => {
    renderWithProviders(<CheckCountStrip total={60} passed={50} failed={8} insufficient={2} />)
    const strip = screen.getByTestId('check-count-strip')
    expect(strip.tagName).toBe('DL')
    expect(strip).toHaveAttribute('aria-label', 'Validation outcomes')
    expect(within(strip).getAllByRole('term').map((node) => node.textContent)).toEqual(['Required checks', 'Passed', 'Did not pass', 'Not enough to tell'])
    expect(within(strip).getAllByRole('definition').map((node) => node.textContent)).toEqual(['60', '50', '8', '2'])
    // Not a live region.
    expect(strip).not.toHaveAttribute('aria-live')
    expect(strip).not.toHaveAttribute('role', 'status')
  })

  it('never derives a missing count: legacy evidence without the family shows Unavailable, the recorded total still shows', () => {
    renderWithProviders(<CheckCountStrip total={12} passed={undefined} failed={undefined} insufficient={undefined} />)
    expect(screen.getAllByRole('definition').map((node) => node.textContent)).toEqual(['12', 'Unavailable', 'Unavailable', 'Unavailable'])
  })

  it('shows a recorded zero as 0 and an unknown total as Unavailable', () => {
    renderWithProviders(<CheckCountStrip total={null} passed={0} failed={0} insufficient={3} />)
    expect(screen.getAllByRole('definition').map((node) => node.textContent)).toEqual(['Unavailable', '0', '0', '3'])
  })

  it('treats a non-integer or negative value as Unavailable', () => {
    renderWithProviders(<CheckCountStrip total={2.5} passed={-1} failed={Number.NaN} insufficient={1} />)
    expect(screen.getAllByRole('definition').map((node) => node.textContent)).toEqual(['Unavailable', 'Unavailable', 'Unavailable', '1'])
  })

  it('uses the Tagalog labels and "Hindi available"', () => {
    renderWithProviders(<CheckCountStrip total={4} passed={undefined} failed={null} insufficient={undefined} />, { lang: 'tl' })
    const strip = screen.getByTestId('check-count-strip')
    expect(strip).toHaveAttribute('aria-label', 'Mga resulta ng check')
    expect(within(strip).getAllByRole('term').map((node) => node.textContent)).toEqual(['Mga kailangang check', 'Pumasa', 'Hindi pumasa', 'Kulang para masabi'])
    expect(values()).toEqual(['4', 'Hindi available', 'Hindi available', 'Hindi available'])
  })
})
