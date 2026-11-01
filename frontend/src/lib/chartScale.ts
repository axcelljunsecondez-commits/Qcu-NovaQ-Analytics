/**
 * Axis helpers for the hand-built SVG charts (spec 2026-10-29 §2.1, §5.2, §8.2).
 * Display only: they choose where gridlines go, never a value that is plotted.
 */

const STEPS = [1, 2, 2.5, 5, 10]

/** Smallest "round" number (1, 2, 2.5 or 5 times a power of ten) at or above `value`; 1 when there is nothing to show. */
export function niceMax(value: number): number {
  if (!Number.isFinite(value) || value <= 0) return 1
  const power = 10 ** Math.floor(Math.log10(value))
  for (const step of STEPS) {
    if (step * power >= value - value * 1e-12) return step * power
  }
  return 10 * power
}

/** Evenly spaced ticks from 0 to `max` inclusive; the axis always starts at 0. */
export function axisTicks(max: number, count: number): number[] {
  if (!Number.isFinite(max) || max <= 0 || count < 1) return [0]
  const step = max / count
  return Array.from({ length: count + 1 }, (_, index) => (index === count ? max : step * index))
}

/** Integer ticks from 0 to `max` for counts of people (at most `limit` + 1 labels). */
export function countTicks(max: number, limit = 5): number[] {
  const top = Number.isFinite(max) && max > 0 ? Math.ceil(max) : 1
  const step = Math.max(1, Math.ceil(top / limit))
  const ticks: number[] = []
  for (let value = 0; value < top; value += step) ticks.push(value)
  ticks.push(top)
  return ticks
}
