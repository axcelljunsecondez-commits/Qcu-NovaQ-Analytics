import { describe, expect, it } from 'vitest'
import { plainDecision } from './decisionPlain'

describe('plainDecision (spec §7.9, U10 F5)', () => {
  it('maps each stored status to its plain sentence', () => {
    expect(plainDecision({ status: 'adopt', separate: false })).toEqual({ key: 'decision.plain.adopt' })
    expect(plainDecision({ status: 'conditional', separate: false })).toEqual({ key: 'decision.plain.conditional_shared' })
    expect(plainDecision({ status: 'conditional', separate: true })).toEqual({ key: 'decision.plain.conditional_separate' })
    expect(plainDecision({ status: 'something_new', separate: false })).toBeNull()
    expect(plainDecision({ status: null, separate: false })).toBeNull()
  })

  it('names the failed periods when the Decision lists them, else counts them', () => {
    expect(plainDecision({ status: 'revise', separate: true, failedPeriods: ['09:00', '10:00'] }))
      .toEqual({ key: 'decision.plain.revise_periods', params: { periods: '09:00, 10:00' } })
    expect(plainDecision({ status: 'revise', separate: false, failedPeriods: [], failedCount: 1, totalCount: 4 }))
      .toEqual({ key: 'decision.plain.revise_count', params: { failed: 1, total: 4 } })
    expect(plainDecision({ status: 'revise', separate: false, failedCount: 0, totalCount: 4 }))
      .toEqual({ key: 'decision.plain.revise_count', params: { failed: 0, total: 4 } })
    expect(plainDecision({ status: 'revise', separate: false, failedCount: 1 })).toEqual({ key: 'decision.plain.revise' })
  })

  it('names the missing evidence, else the periods without enough data', () => {
    expect(plainDecision({ status: 'insufficient_evidence', separate: false, missing: ['completed Setup', 'a Results check'] }))
      .toEqual({ key: 'decision.plain.insufficient', params: { missing: 'completed Setup; a Results check' } })
    expect(plainDecision({ status: 'insufficient_evidence', separate: true, missing: [], inadequatePeriods: ['08:00'] }))
      .toEqual({ key: 'decision.plain.insufficient_periods', params: { periods: '08:00' } })
    expect(plainDecision({ status: 'insufficient_evidence', separate: true })).toEqual({ key: 'decision.plain.insufficient_none' })
  })

  it('says a stale Decision is out of date whatever it said', () => {
    expect(plainDecision({ status: 'adopt', stale: true, separate: false })).toEqual({ key: 'decision.plain.stale' })
  })
})
