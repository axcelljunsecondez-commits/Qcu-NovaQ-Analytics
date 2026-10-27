import { describe, expect, it } from 'vitest'
import { tooltipPlacement } from './tooltipPlacement'

const viewport = { left: 0, top: 0, width: 1000, height: 800 }
const anchor = { left: 100, top: 200, width: 32, height: 32 }
const size = { width: 260, height: 70 }

describe('tooltip viewport placement', () => {
  it('prefers above the info button, leaving the field below unobstructed', () => {
    const p = tooltipPlacement(anchor, size, viewport, 'top')
    expect(p.side).toBe('top')
    expect(p.top + size.height).toBeLessThanOrEqual(anchor.top)
    expect(p.left).toBeGreaterThanOrEqual(12)
  })
  it('uses a side when the top has no room', () => {
    const p = tooltipPlacement({ ...anchor, top: 12 }, size, viewport, 'top')
    expect(p.side).toBe('right')
    expect(p.left).toBeGreaterThanOrEqual(anchor.left + anchor.width)
  })
  it('flips a right-side name at the viewport edge', () => {
    const p = tooltipPlacement({ ...anchor, left: 950 }, size, viewport, 'right')
    expect(p.side).toBe('left')
    expect(p.left + size.width).toBeLessThanOrEqual(950)
  })
  it('keeps a narrow-screen fallback outside the editable input', () => {
    const input = { left: 16, top: 52, width: 288, height: 44 }
    const p = tooltipPlacement({ left: 24, top: 12, width: 32, height: 32 }, { width: 288, height: 80 }, { ...viewport, width: 320, height: 640 }, 'top', input)
    expect(p.side).toBe('bottom')
    expect(p.top).toBeGreaterThanOrEqual(input.top + input.height)
    expect(p.left + 288).toBeLessThanOrEqual(308)
  })
  it('clips a long explanation into available space instead of leaving the viewport', () => {
    const p = tooltipPlacement({ left: 144, top: 200, width: 32, height: 32 }, { width: 296, height: 900 }, { ...viewport, width: 320, height: 400 }, 'top')
    expect(p.maxHeight).toBeLessThanOrEqual(188)
    expect(p.top).toBeGreaterThanOrEqual(12)
    expect(p.top + p.maxHeight).toBeLessThanOrEqual(388)
  })
  it('respects the visual viewport offset when zoomed or panned', () => {
    const p = tooltipPlacement({ left: 180, top: 180, width: 32, height: 32 }, size, { left: 100, top: 100, width: 350, height: 500 }, 'top')
    expect(p.left).toBeGreaterThanOrEqual(112)
    expect(p.top).toBeGreaterThanOrEqual(112)
    expect(p.left + size.width).toBeLessThanOrEqual(438)
  })
})
