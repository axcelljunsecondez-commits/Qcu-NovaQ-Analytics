import { describe, expect, it } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/test-utils'
import { InfoTip } from './InfoTip'

function renderTip() {
  return renderWithProviders(<><InfoTip stableInteraction name="Wait" text="Source explanation" /><button>Elsewhere</button></>)
}

describe('signed-in explanation interaction', () => {
  it('keeps the first pointer activation open after hover and focus, then closes on the second', async () => {
    const user = userEvent.setup()
    renderTip()
    const button = screen.getByRole('button', { name: 'About: Wait' })
    await user.hover(button)
    expect(screen.getByRole('tooltip')).toHaveTextContent('Source explanation')
    await user.click(button) // user-event includes the pointer focus that previously closed the tip
    expect(button).toHaveFocus()
    expect(button).toHaveAttribute('aria-expanded', 'true')
    expect(button).toHaveAccessibleDescription('Source explanation')
    await user.unhover(button)
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
    await user.click(button)
    expect(button).toHaveAttribute('aria-expanded', 'false')
  })

  it('allows moving from the trigger into its explanation and dismisses outside', async () => {
    const user = userEvent.setup()
    renderTip()
    const button = screen.getByRole('button', { name: 'About: Wait' })
    await user.hover(button)
    await user.hover(screen.getByRole('tooltip'))
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Elsewhere' }))
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
    expect(button).toHaveAttribute('aria-expanded', 'false')
  })

  it.each(['{Enter}', ' '])('pins and closes with keyboard activation %s, and Escape stays dismissed', async (key) => {
    const user = userEvent.setup()
    renderTip()
    const button = screen.getByRole('button', { name: 'About: Wait' })
    await user.tab()
    expect(button).toHaveFocus()
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
    await user.keyboard(key)
    expect(button).toHaveAttribute('aria-expanded', 'true')
    await user.keyboard(key)
    expect(button).toHaveAttribute('aria-expanded', 'false')
    await user.keyboard(key)
    await user.keyboard('{Escape}')
    expect(button).toHaveFocus()
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
    await user.tab()
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })

  it('dismisses on blur, including a pinned explanation', async () => {
    const user = userEvent.setup()
    renderTip()
    await user.tab()
    await user.keyboard('{Enter}')
    await user.tab()
    expect(screen.getByRole('button', { name: 'Elsewhere' })).toHaveFocus()
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })
})
