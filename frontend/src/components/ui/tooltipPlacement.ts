export type TooltipSide = 'top' | 'right' | 'bottom' | 'left'
export interface TooltipRect { left: number; top: number; width: number; height: number }

/** Viewport coordinates only; these values never participate in analytical calculations. */
export function tooltipPlacement(anchor: TooltipRect, size: { width: number; height: number }, viewport: TooltipRect, preferred: TooltipSide, avoid?: TooltipRect) {
  const margin = 12
  const left = viewport.left + margin
  const top = viewport.top + margin
  const right = viewport.left + viewport.width - margin
  const bottom = viewport.top + viewport.height - margin
  const maxWidth = Math.max(1, right - left)
  const maxHeight = Math.max(1, bottom - top)
  const width = Math.min(size.width, maxWidth)
  const height = Math.min(size.height, maxHeight)
  const topEdge = Math.min(anchor.top, avoid?.top ?? anchor.top)
  const bottomEdge = Math.max(anchor.top + anchor.height, avoid ? avoid.top + avoid.height : 0)
  const leftEdge = Math.min(anchor.left, avoid?.left ?? anchor.left)
  const rightEdge = Math.max(anchor.left + anchor.width, avoid ? avoid.left + avoid.width : 0)
  const room = {
    top: Math.max(0, topEdge - top),
    bottom: Math.max(0, bottom - bottomEdge),
    left: Math.max(0, leftEdge - left),
    right: Math.max(0, right - rightEdge),
  }
  const orders: Record<TooltipSide, TooltipSide[]> = {
    top: ['top', 'right', 'left', 'bottom'],
    right: ['right', 'left', 'top', 'bottom'],
    bottom: ['bottom', 'right', 'left', 'top'],
    left: ['left', 'right', 'top', 'bottom'],
  }
  const side = orders[preferred].find((candidate) => room[candidate] >= (candidate === 'left' || candidate === 'right' ? width : height))
    ?? (room.top >= room.bottom ? 'top' : 'bottom')
  const limitedHeight = side === 'top' || side === 'bottom' ? Math.min(maxHeight, room[side]) : maxHeight
  const shownHeight = Math.min(height, limitedHeight)
  const clamp = (value: number, start: number, end: number) => Math.max(start, Math.min(value, Math.max(start, end)))
  // Position against the trigger/input envelope, preserving viewport margins.
  const x = side === 'right' ? rightEdge : side === 'left' ? leftEdge - width : anchor.left
  const y = side === 'top' ? topEdge - shownHeight : side === 'bottom' ? bottomEdge : anchor.top + (anchor.height - shownHeight) / 2
  return { left: clamp(x, left, right - width), top: clamp(y, top, bottom - shownHeight), maxWidth, maxHeight: limitedHeight, side }
}
