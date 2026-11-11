import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, render, screen } from '@testing-library/react'
import { useContentEntrance } from './useContentEntrance'

const originalAnimate = HTMLElement.prototype.animate
const animate = vi.fn()
const cancel = vi.fn()
let matches = false
const listeners = new Set<(event: MediaQueryListEvent) => void>()

function Sample({ trigger = 'first', contentKey = trigger, initial = true, duration = 220 }: { trigger?: string; contentKey?: string; initial?: boolean; duration?: number }) {
  const ref = useContentEntrance<HTMLDivElement>(trigger, duration, { animateInitial: initial, contentKey })
  return <div data-testid="content" ref={ref}><input aria-label="State" defaultValue="kept" /></div>
}

beforeEach(() => {
  matches = false
  listeners.clear()
  cancel.mockReset()
  animate.mockReset().mockReturnValue({ cancel })
  Object.defineProperty(HTMLElement.prototype, 'animate', { configurable: true, value: animate })
  vi.stubGlobal('matchMedia', vi.fn(() => ({ get matches() { return matches }, addEventListener: (_type: string, fn: (event: MediaQueryListEvent) => void) => listeners.add(fn), removeEventListener: (_type: string, fn: (event: MediaQueryListEvent) => void) => listeners.delete(fn) })))
})
afterEach(() => {
  if (originalAnimate) Object.defineProperty(HTMLElement.prototype, 'animate', { configurable: true, value: originalAnimate })
  else Reflect.deleteProperty(HTMLElement.prototype, 'animate')
  vi.unstubAllGlobals()
})

describe('content-only entrance', () => {
  it('uses the specified duration and keeps the existing DOM identity on updates', () => {
    const { rerender, unmount } = render(<Sample />)
    const input = screen.getByRole('textbox', { name: 'State' })
    expect(animate).toHaveBeenCalledWith([{ opacity: 0, transform: 'translateY(6px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 220, easing: 'cubic-bezier(.16,1,.3,1)' })
    rerender(<Sample />)
    expect(animate).toHaveBeenCalledTimes(1)
    rerender(<Sample trigger="next" />)
    expect(cancel).toHaveBeenCalledTimes(1)
    expect(animate).toHaveBeenCalledTimes(2)
    expect(screen.getByRole('textbox', { name: 'State' })).toBe(input)
    unmount()
    expect(cancel).toHaveBeenCalledTimes(2)
  })

  it('animates a tab only when its explicit selection and visible panel both change', () => {
    const { rerender } = render(<Sample trigger="wait" contentKey="wait" initial={false} duration={205} />)
    expect(animate).not.toHaveBeenCalled()
    rerender(<Sample trigger="wait" contentKey="level" initial={false} duration={205} />)
    expect(animate).not.toHaveBeenCalled()
    rerender(<Sample trigger="invalid" contentKey="level" initial={false} duration={205} />)
    expect(animate).not.toHaveBeenCalled()
    rerender(<Sample trigger="wait" contentKey="wait" initial={false} duration={205} />)
    expect(animate).toHaveBeenCalledTimes(1)
    expect(animate.mock.calls[0][1].duration).toBe(205)
  })

  it('skips reduced motion and cancels an active entrance when the preference changes', () => {
    matches = true
    const first = render(<Sample />)
    expect(animate).not.toHaveBeenCalled()
    first.unmount()
    matches = false
    render(<Sample />)
    expect(animate).toHaveBeenCalledTimes(1)
    act(() => { matches = true; listeners.forEach((fn) => fn({ matches: true } as MediaQueryListEvent)) })
    expect(cancel).toHaveBeenCalledTimes(1)
    act(() => { matches = false; listeners.forEach((fn) => fn({ matches: false } as MediaQueryListEvent)) })
    expect(animate).toHaveBeenCalledTimes(1)
  })

  it('is immediately visible when Web Animations is unavailable', () => {
    Object.defineProperty(HTMLElement.prototype, 'animate', { configurable: true, value: undefined })
    render(<Sample />)
    expect(screen.getByTestId('content')).toBeVisible()
    expect(screen.getByTestId('content').style.opacity).toBe('')
  })
})
