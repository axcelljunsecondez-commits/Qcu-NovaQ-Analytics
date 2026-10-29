import { describe, expect, it } from 'vitest'
import type { OptimizationOut, SeparateComparison, SeparatePlanComparison } from '../api/types'
import {
  complete, currentGroupDetail, joinLevels, laneDetail, peakCell, planBand, planGroupDetail, presentLevels,
  separatePlanCells, separatePlanTakeaway, sharedPlanCells, todayCells,
} from './busyLevel'

const sepRows = [
  { time: '08:00-09:00', queue_id: 'A', c: 1, rho: 0.75, stable: true },
  { time: '08:00-09:00', queue_id: 'B', c: 1, rho: 0.0019, stable: true },
  { time: '09:00-10:00', queue_id: 'A', c: 1, rho: 0.6 - 1e-12, stable: true },
]

describe('busy level cells', () => {
  it('takes the busiest line per period for today, with the 1e-9 band tolerance', () => {
    const cells = todayCells(sepRows)
    expect(cells).toEqual([
      { time: '08:00-09:00', level: 'Normal', rho: 0.75 },
      { time: '09:00-10:00', level: 'Normal', rho: 0.6 - 1e-12 },
    ])
  })

  it('uses peak_util for a separate plan and keeps a missing period unknown', () => {
    const comparison = { current: { periods: [{ time: 'a', active_lanes: ['A'] }, { time: 'b', active_lanes: ['A'] }] } } as unknown as SeparateComparison
    const plan = { periods: [{ time: 'a', peak_util: 0.85 }] } as unknown as SeparatePlanComparison
    expect(separatePlanCells(comparison, plan)).toEqual([{ time: 'a', level: 'Peak', rho: 0.85 }, { time: 'b', level: null, rho: null }])
  })

  it('uses rho_optimal with the plan stability flag for a shared plan', () => {
    const cells = sharedPlanCells([
      { time: 'a', rho_optimal: 0.5, optimized_stable: true },
      { time: 'b', rho_optimal: 0.95, optimized_stable: false },
    ] as OptimizationOut[])
    expect(cells.map((cell) => cell.level)).toEqual(['Lean', 'Unstable'])
    expect(planBand(null, null)).toBeNull()
  })

  it('lists only the levels present, in order, and finds the peak', () => {
    const cells = [{ time: 'a', level: 'Peak' as const, rho: 0.85 }, { time: 'b', level: 'Lean' as const, rho: 0.2 }, { time: 'c', level: null, rho: null }]
    expect(presentLevels(cells)).toEqual({ levels: ['Lean', 'Peak'], unknown: true })
    expect(peakCell(cells)).toBe(0)
    expect(complete(cells)).toBe(false)
    expect(complete(cells.slice(0, 2))).toBe(true)
  })

  it('joins level words with the connector', () => {
    expect(joinLevels(['Lean'], 'or')).toBe('Lean')
    expect(joinLevels(['Lean', 'Normal', 'Peak'], 'or')).toBe('Lean, Normal or Peak')
  })

  it('says "below target" only when every period is below it, counts periods strictly above it, and says nothing on the target', () => {
    const cells = (values: number[]) => values.map((rho, index) => ({ time: String(index), level: 'Normal' as const, rho }))
    expect(separatePlanTakeaway(cells([0.6, 0.7]), 0.85)).toEqual({ kind: 'below' })
    expect(separatePlanTakeaway(cells([0.6, 0.9, 0.95]), 0.85)).toEqual({ kind: 'above', count: 2 })
    expect(separatePlanTakeaway(cells([0.6, 0.85]), 0.85)).toBeNull()
    expect(separatePlanTakeaway(cells([0.6]), null)).toBeNull()
  })

  it('gives each cashier for a separate period and the counter group for a shared one', () => {
    expect(laneDetail(sepRows, '08:00-09:00')).toEqual([
      { lane: 'A', rho: 0.75, level: 'Normal' },
      { lane: 'B', rho: 0.0019, level: 'Lean' },
    ])
    expect(currentGroupDetail([{ time: 'a', c: 3, rho: 1.2, stable: false }], 'a')).toEqual({ counters: 3, rho: 1.2, level: 'Unstable' })
    expect(currentGroupDetail([], 'a')).toBeNull()
    expect(planGroupDetail([{ time: 'a', c_optimal: 4, rho_optimal: 0.625, optimized_stable: true }] as OptimizationOut[], 'a'))
      .toEqual({ counters: 4, rho: 0.625, level: 'Normal' })
  })
})
