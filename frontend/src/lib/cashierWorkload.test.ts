import { describe, expect, it } from 'vitest'
import { summarizeCashierWorkload, type WorkloadEntry } from './cashierWorkload'

const entry = (queueId: unknown, rho: number | null, time: string, status: unknown = 'Normal'): WorkloadEntry => ({ queueId, rho, time, status })

describe('summarizeCashierWorkload', () => {
  it('averages and peaks each line over its finite ρ values, in first-appearance order', () => {
    const lines = summarizeCashierWorkload([
      entry('Q2', 0.9, '08:00-09:00', 'Peak'),
      entry('Q1', 0.5, '08:00-09:00', 'Lean'),
      entry('Q1', 0.8, '09:00-10:00', 'Peak'),
      entry('Q1', 0.2, '10:00-11:00', 'Lean'),
    ])
    expect(lines.map((line) => line.queueId)).toEqual(['Q2', 'Q1'])
    expect(lines[1].averageRho).toBeCloseTo(0.5, 12)
    expect(lines[1]).toMatchObject({ peakRho: 0.8, peakTime: '09:00-10:00', peakStatus: 'Peak', periodCount: 3 })
    expect(lines[0]).toMatchObject({ averageRho: 0.9, peakRho: 0.9, periodCount: 1 })
  })

  it('skips missing ρ and missing queue IDs instead of counting them as zero', () => {
    const lines = summarizeCashierWorkload([
      entry('Q1', 0.6, '08:00-09:00'),
      entry('Q1', null, '09:00-10:00'),
      entry('Q1', Number.NaN, '10:00-11:00'),
      entry('Q1', Number.POSITIVE_INFINITY, '11:00-12:00'),
      entry(null, 0.99, '08:00-09:00'),
      entry('  ', 0.99, '08:00-09:00'),
      entry(7, 0.99, '08:00-09:00'),
      entry('Q3', null, '08:00-09:00'),
    ])
    expect(lines).toEqual([{ queueId: 'Q1', averageRho: 0.6, peakRho: 0.6, peakTime: '08:00-09:00', peakStatus: 'Normal', periodCount: 1 }])
  })

  it('keeps the earlier row on a peak tie', () => {
    const [line] = summarizeCashierWorkload([entry('Q1', 0.7, '08:00-09:00', 'Normal'), entry('Q1', 0.7, '09:00-10:00', 'Peak')])
    expect(line).toMatchObject({ peakTime: '08:00-09:00', peakStatus: 'Normal' })
  })

  it('returns no lines when nothing is usable', () => {
    expect(summarizeCashierWorkload([])).toEqual([])
    expect(summarizeCashierWorkload([entry('Q1', null, '08:00-09:00')])).toEqual([])
  })
})
