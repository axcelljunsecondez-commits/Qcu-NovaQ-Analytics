import { describe, expect, it } from 'vitest'
import { focusAfterCancel } from './focusAfterCancel'

function card(html: string): HTMLElement {
  const element = document.createElement('div')
  element.tabIndex = -1
  element.innerHTML = html
  document.body.replaceChildren(element)
  return element
}

describe('focusAfterCancel (D2, N1)', () => {
  it('focuses the primary action when it is enabled', () => {
    const container = card('<input type="radio" /><button type="button" class="btn-primary">Upload and process</button>')
    const primary = container.querySelector('button') as HTMLButtonElement
    focusAfterCancel(primary, container)
    expect(document.activeElement).toBe(primary)
  })

  it('focuses the first enabled control in the card when the primary action is disabled', () => {
    const container = card('<input type="radio" disabled /><a href="/simulation">Open Advanced settings</a><button type="button" class="btn-primary" disabled>Upload and process</button>')
    focusAfterCancel(container.querySelector('button'), container)
    expect(document.activeElement).toBe(container.querySelector('a'))
  })

  it('focuses the card itself when nothing in it can take focus', () => {
    const container = card('<button type="button" class="btn-primary" disabled>Upload and process</button>')
    focusAfterCancel(container.querySelector('button'), container)
    expect(document.activeElement).toBe(container)
  })

  it('also falls back when the primary action is not rendered', () => {
    const container = card('<input type="radio" />')
    focusAfterCancel(null, container)
    expect(document.activeElement).toBe(container.querySelector('input'))
  })
})
