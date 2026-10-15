import { describe, expect, it } from 'vitest'
import { buildAggregateCsv, makePeriods, manualRowError } from './periods'

describe('makePeriods (spec §7.6, §8)', () => {
  it('makes back-to-back periods of one length', () => {
    expect(makePeriods('08:00', 3, 30)).toEqual([
      { start: '08:00', end: '08:30' },
      { start: '08:30', end: '09:00' },
      { start: '09:00', end: '09:30' },
    ])
  })

  it('accepts saved HH:MM:SS start times', () => {
    expect(makePeriods('07:45:00', 1, 15)).toEqual([{ start: '07:45', end: '08:00' }])
  })

  it('allows up to 24 periods within the day', () => {
    const periods = makePeriods('00:00', 23, 60)
    expect(Array.isArray(periods) && periods.length).toBe(23)
    expect(Array.isArray(periods) && periods[22]).toEqual({ start: '22:00', end: '23:00' })
    expect(makePeriods('06:00', 24, 15)).toHaveLength(24)
  })

  it.each([
    ['24 hours from midnight would end at 24:00', '00:00', 24, 60],
    ['an evening run past midnight', '22:00', 3, 60],
    ['one period ending at 24:00', '23:00', 1, 60],
  ])('refuses %s', (_label, start, count, length) => {
    expect(makePeriods(start, count, length)).toBe('crosses_midnight')
  })

  it.each([
    ['', 1, 60, 'bad_start'],
    ['25:00', 1, 60, 'bad_start'],
    ['08:00', 0, 60, 'bad_count'],
    ['08:00', 25, 15, 'bad_count'],
    ['08:00', 1.5, 60, 'bad_count'],
    ['08:00', 2, 45, 'bad_length'],
  ] as const)('rejects start %s, count %s, length %s with %s', (start, count, length, error) => {
    expect(makePeriods(start, count, length)).toBe(error)
  })
})

describe('manual entry rows (B9)', () => {
  const row = { start: '08:00', arrivalsPerHour: '40', servedPerHourPerCounter: '15', counters: '3' }

  it('accepts what the server accepts', () => {
    expect(manualRowError(row)).toBeNull()
    expect(manualRowError({ ...row, arrivalsPerHour: '0' })).toBeNull()
    expect(manualRowError({ ...row, servedPerHourPerCounter: '7.5' })).toBeNull()
  })

  it.each([
    [{ arrivalsPerHour: '' }, 'arrivals'],
    [{ arrivalsPerHour: '-1' }, 'arrivals'],
    [{ arrivalsPerHour: 'abc' }, 'arrivals'],
    [{ servedPerHourPerCounter: '0' }, 'served'],
    [{ servedPerHourPerCounter: '' }, 'served'],
    [{ counters: '0' }, 'counters'],
    [{ counters: '2.5' }, 'counters'],
    [{ counters: '100001' }, 'counters'],
  ])('rejects %o as %s', (change, error) => {
    expect(manualRowError({ ...row, ...change })).toBe(error)
  })

  it('builds the shared aggregate template CSV with one-hour period labels', () => {
    expect(buildAggregateCsv([row, { start: '09:00', arrivalsPerHour: ' 55 ', servedPerHourPerCounter: '15', counters: '4' }]))
      .toBe('time,lambda,mu,c\n08:00-09:00,40,15,3\n09:00-10:00,55,15,4\n')
  })
})
