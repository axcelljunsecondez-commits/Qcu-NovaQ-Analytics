import { describe, expect, it } from 'vitest'
import type { SelectedLoadUncertainty, SimMcOut } from '../api/types'
import { showSelectedRawPassGuidance } from './selectedRawPassGuidance'

// Owner 2026-11-26: synthetic rows shaped like the stored evidence (MC job rows with status PASS/FAIL,
// the selected-load family's recorded counts); the helper reads them and computes nothing.

const row = (status: string) => ({ time: '08:00', queue_id: 'a', status }) as SimMcOut
const family = (fail: unknown, insufficient: unknown) => ({ estimand: 'mean_load', confidence_level: 0.95, family_size: 60, replications: 20, assumptions: [],
  pass_count: 0, fail_count: fail, insufficient_count: insufficient }) as unknown as SelectedLoadUncertainty
const shown = (overrides: Partial<Parameters<typeof showSelectedRawPassGuidance>[0]> = {}) => showSelectedRawPassGuidance({
  status: 'insufficient_evidence', mcRows: [row('PASS'), row('PASS')], loadUncertainty: family(0, 60), ...overrides })

describe('showSelectedRawPassGuidance', () => {
  it('shows for insufficient evidence when every cited run row passed and no check failed', () => {
    expect(shown()).toBe(true)
  })

  it.each([
    ['revise', { status: 'revise' }],
    ['conditional', { status: 'conditional' }],
    ['adopt', { status: 'adopt' }],
    ['no status', { status: null }],
    ['a failed Many variations row', { mcRows: [row('PASS'), row('FAIL')] }],
    ['an errored Many variations row', { mcRows: [row('PASS'), row('ERROR')] }],
    ['no Many variations rows', { mcRows: [] }],
    ['legacy evidence without the family', { loadUncertainty: undefined }],
    ['a recorded failed check', { loadUncertainty: family(1, 59) }],
    ['no unsettled check', { loadUncertainty: family(0, 0) }],
    ['a missing fail count', { loadUncertainty: family(undefined, 60) }],
    ['a non-integer count', { loadUncertainty: family(0, 2.5) }],
    ['a negative count', { loadUncertainty: family(-1, 60) }],
  ] as const)('hides for %s', (_name, overrides) => {
    expect(shown(overrides as Partial<Parameters<typeof showSelectedRawPassGuidance>[0]>)).toBe(false)
  })
})
