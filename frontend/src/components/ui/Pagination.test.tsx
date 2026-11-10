import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/test-utils'
import { Pagination } from './Pagination'

function Pages({ count }: { count: number }) {
  const [page, setPage] = useState(0)
  return <Pagination page={page} pageCount={count} onPageChange={setPage} />
}

describe('Pagination keyboard focus (K-SAI-4)', () => {
  it('keeps focus on the other button when the pressed one becomes disabled', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Pages count={3} />)
    const previous = screen.getByRole('button', { name: 'Previous' })
    const next = screen.getByRole('button', { name: 'Next' })
    await user.tab()
    expect(next).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(screen.getByRole('status')).toHaveTextContent('Page 2 of 3')
    expect(next).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(screen.getByRole('status')).toHaveTextContent('Page 3 of 3')
    expect(next).toBeDisabled()
    expect(previous).toHaveFocus()
    await user.keyboard(' ')
    expect(screen.getByRole('status')).toHaveTextContent('Page 2 of 3')
    expect(previous).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(screen.getByRole('status')).toHaveTextContent('Page 1 of 3')
    expect(previous).toBeDisabled()
    expect(next).toHaveFocus()
  })

  it('does not take focus when a button was not focused', async () => {
    renderWithProviders(<><button type="button">Elsewhere</button><Pages count={2} /></>)
    const elsewhere = screen.getByRole('button', { name: 'Elsewhere' })
    elsewhere.focus()
    screen.getByRole('button', { name: 'Next' }).click()
    expect(await screen.findByText('Page 2 of 2')).toBeInTheDocument()
    expect(elsewhere).toHaveFocus()
  })
})
