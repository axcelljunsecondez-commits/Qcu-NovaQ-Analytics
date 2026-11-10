import { afterAll, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { I18nextProvider } from 'react-i18next'
import { testI18n } from '../../test/test-utils'
import en from '../../../public/locales/en/translation.json'
import tl from '../../../public/locales/tl/translation.json'
import { DecisionDetailsDialog } from './DecisionDetailsDialog'

// JSDOM lacks native modal behavior. These stubs verify the native API wiring,
// not browser focus containment; the parent verifies that in the actual browser.
const descriptors = new Map<string, PropertyDescriptor | undefined>()
const showModal = vi.fn(function (this: HTMLDialogElement) { this.setAttribute('open', '') })
const close = vi.fn(function (this: HTMLDialogElement) { this.removeAttribute('open') })

beforeAll(() => {
  for (const key of ['showModal', 'close']) descriptors.set(key, Object.getOwnPropertyDescriptor(HTMLDialogElement.prototype, key))
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value: showModal })
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value: close })
})
beforeEach(() => { showModal.mockClear(); close.mockClear() })
afterAll(() => {
  for (const [key, descriptor] of descriptors) {
    if (descriptor) Object.defineProperty(HTMLDialogElement.prototype, key, descriptor)
    else Reflect.deleteProperty(HTMLDialogElement.prototype, key)
  }
})

function ui(disabled = false, lang: 'en' | 'tl' = 'en') {
  const i18n = testI18n()
  void i18n.changeLanguage(lang)
  return <I18nextProvider i18n={i18n}>
    <DecisionDetailsDialog label={(lang === 'en' ? en : tl)['decision.status.conditional']} disabled={disabled}>
      <p>Stored synthetic rationale.</p>
      <p>{(lang === 'en' ? en : tl)['decision.plain.selected_scope_details']}</p>
    </DecisionDetailsDialog>
  </I18nextProvider>
}

describe('saved Decision dialog (native APIs explicitly stubbed)', () => {
  it.each(['en', 'tl'] as const)('uses approved %s controls/body, English heading, native showModal and initial Close focus', async (lang) => {
    const user = userEvent.setup()
    const text = lang === 'en' ? en : tl
    render(ui(false, lang))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    const trigger = screen.getByRole('button', { name: text['decision.status.conditional'] })
    expect(trigger).toHaveAttribute('aria-haspopup', 'dialog')
    await user.click(trigger)
    const dialog = screen.getByRole('dialog', { name: en['decision.plain.details'] })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(showModal).toHaveBeenCalledTimes(1)
    expect(within(dialog).getByRole('heading', { name: en['decision.plain.details'] })).toHaveAttribute('lang', 'en')
    expect(within(dialog).getByRole('button', { name: text['tutorials.close'] })).toHaveFocus()
    expect(dialog).toHaveTextContent('Stored synthetic rationale.')
    expect(dialog).toHaveTextContent(text['decision.plain.selected_scope_details'])
  })

  it('closes with Close and returns focus to the saved outcome trigger', async () => {
    const user = userEvent.setup()
    render(ui())
    const trigger = screen.getByRole('button', { name: 'Conditional' })
    await user.click(trigger)
    await user.click(screen.getByRole('button', { name: 'Close' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(close).toHaveBeenCalledTimes(1)
    expect(trigger).toHaveFocus()
  })

  it('handles the native Escape cancel event and restores trigger focus', async () => {
    const user = userEvent.setup()
    render(ui())
    const trigger = screen.getByRole('button', { name: 'Conditional' })
    await user.click(trigger)
    const cancel = new Event('cancel', { cancelable: true })
    fireEvent(screen.getByRole('dialog'), cancel)
    expect(cancel.defaultPrevented).toBe(true)
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(trigger).toHaveFocus()
  })

  it('disables the outcome while running and does not reopen after the request ends', async () => {
    const user = userEvent.setup()
    const { rerender } = render(ui())
    await user.click(screen.getByRole('button', { name: 'Conditional' }))
    rerender(ui(true))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Conditional' })).toBeDisabled()
    rerender(ui(false))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(showModal).toHaveBeenCalledTimes(1)
  })

  it('removes the modal from the native top layer on unmount', async () => {
    const user = userEvent.setup()
    const { unmount } = render(ui())
    await user.click(screen.getByRole('button', { name: 'Conditional' }))
    unmount()
    expect(close).toHaveBeenCalledTimes(1)
  })
})
