import { describe, expect, it } from 'vitest'
import {
  buildRequest,
  clockFromHours,
  clockToMinutes,
  emptyForm,
  emptyPayField,
  formFingerprint,
  formFromRun,
  limitProblems,
  minutesToClock,
  type NamedForm,
} from './namedWorkforce'
import type { NamedLimits, NamedRunProvenance, NamedWorkforceInput } from '../api/sharedNamed'
import fixture from '../test/fixtures/sharedNamed.json'

const POLICY = Object.fromEntries(Object.entries(fixture.contract.employee_policy).map(([key, item]) => [key, item.approved]))
const LIMITS = fixture.contract.limits as NamedLimits
const provenance = fixture.run.evidence.result.provenance as unknown as NamedRunProvenance

function filledForm(): NamedForm {
  return formFromRun(fixture.dataset_id, provenance)
}

describe('clock conversion', () => {
  it('round-trips HH:MM and minutes, including 24:00', () => {
    for (const minute of [0, 1, 59, 60, 480, 525, 1439, 1440]) {
      expect(clockToMinutes(minutesToClock(minute))).toBe(minute)
    }
    expect(minutesToClock(1440)).toBe('24:00')
    expect(clockToMinutes('24:00')).toBe(1440)
    expect(clockToMinutes('8:05')).toBe(485)
  })

  it('rejects text that is not a clock time', () => {
    for (const text of ['', '24:01', '25:00', '08:60', '8', '08:5', 'noon', '-1:00', '08:00 AM']) {
      expect(clockToMinutes(text)).toBeNull()
    }
  })

  it('shows playback hours as clock time from the horizon start, before opening too', () => {
    expect(clockFromHours(480, 0)).toBe('08:00:00')
    expect(clockFromHours(480, 1.5)).toBe('09:30:00')
    expect(clockFromHours(480, -0.25)).toBe('07:45:00')
  })
})

describe('buildRequest', () => {
  it('reproduces the recorded inputs of a stored run exactly', () => {
    const built = buildRequest(filledForm(), POLICY)
    expect(built.ok).toBe(true)
    if (!built.ok) return
    const { replications: _r, seed: _s, ...workforce } = fixture.request
    void _r
    void _s
    expect(built.body).toEqual(workforce)
  })

  it('keeps a pay value marked not supplied as null, never 0', () => {
    const form = filledForm()
    form.employees[0].pay.regular_rate_per_hour = { value: '0', not_supplied: true }
    const built = buildRequest(form, POLICY)
    expect(built.ok && built.body.employees[0].pay.regular_rate_per_hour).toBeNull()
    form.employees[0].pay.regular_rate_per_hour = { value: '0', not_supplied: false }
    const zero = buildRequest(form, POLICY)
    expect(zero.ok && zero.body.employees[0].pay.regular_rate_per_hour).toBe(0)
  })

  it('applies no defaults: an empty form lists every missing value', () => {
    const built = buildRequest(emptyForm(), POLICY)
    expect(built.ok).toBe(false)
    if (built.ok) return
    const fields = built.errors.map((item) => item.field)
    for (const field of ['dataset_id', 'horizon.start', 'horizon.end', 'register_count', 'closing_policy',
      'shift_rules.max_shifts_per_employee', 'required_staffing', 'employees']) {
      expect(fields).toContain(field)
    }
  })

  it('refuses malformed numbers and clocks instead of guessing', () => {
    const form = filledForm()
    form.required_staffing[0].servers = '1.5'
    form.horizon.start = '8 AM'
    form.employees[0].pay.overtime_rate_per_hour = { value: 'abc', not_supplied: false }
    form.employees[0].pay.daily_regular_paid_minutes = { value: '480.0', not_supplied: false }
    const built = buildRequest(form, POLICY)
    expect(built.ok).toBe(false)
    if (built.ok) return
    expect(built.errors).toEqual(expect.arrayContaining([
      { field: 'required_staffing.0.servers', code: 'whole' },
      { field: 'horizon.start', code: 'clock' },
      { field: 'employees.0.pay.overtime_rate_per_hour', code: 'number' },
      { field: 'employees.0.pay.daily_regular_paid_minutes', code: 'whole' },
    ]))
  })

  it('sends the minimum gap between shifts only when more than one shift is allowed', () => {
    const form = filledForm()
    form.shift_rules.min_minutes_between_shifts = '45'
    const single = buildRequest(form, POLICY)
    expect(single.ok && single.body.rules.shift_rules.min_minutes_between_shifts).toBeNull()
    form.shift_rules.max_shifts_per_employee = '2'
    const split = buildRequest(form, POLICY)
    expect(split.ok && split.body.rules.shift_rules.min_minutes_between_shifts).toBe(45)
  })

  it('sends the approved employee policy it is given', () => {
    const built = buildRequest(filledForm(), POLICY)
    expect(built.ok && built.body.employee_policy).toEqual(POLICY)
  })
})

describe('formFingerprint', () => {
  it('changes on any field edit', () => {
    const form = filledForm()
    const before = formFingerprint(form)
    const edits: Array<(draft: NamedForm) => void> = [
      (draft) => { draft.horizon.end = '09:59' },
      (draft) => { draft.required_staffing[0].servers = '3' },
      (draft) => { draft.employees[0].employee_id = 'E9' },
      (draft) => { draft.employees[1].pay.regular_rate_per_hour = { value: '', not_supplied: false } },
      (draft) => { draft.break_rules[1].breaks[0].paid = false },
      (draft) => { draft.roster[0].breaks[0].start = '08:50' },
      (draft) => { draft.closing_policy = 'DRAIN' },
      (draft) => { draft.dataset_id = '99' },
    ]
    for (const change of edits) {
      const draft = JSON.parse(JSON.stringify(form)) as NamedForm
      change(draft)
      expect(formFingerprint(draft)).not.toBe(before)
    }
    expect(formFingerprint(JSON.parse(JSON.stringify(form)) as NamedForm)).toBe(before)
  })
})

describe('limitProblems', () => {
  const body = (): NamedWorkforceInput => {
    const built = buildRequest(filledForm(), POLICY)
    if (!built.ok) throw new Error('fixture form must build')
    return built.body
  }

  it('accepts the limits themselves and refuses one more', () => {
    expect(limitProblems(body(), LIMITS, LIMITS.max_replications)).toEqual([])
    expect(limitProblems(body(), LIMITS, LIMITS.max_replications + 1)).toEqual([
      { limit: 'replications', value: LIMITS.max_replications + 1, max: LIMITS.max_replications },
    ])
  })

  it('checks every list bound', () => {
    const big = body()
    big.employees = Array.from({ length: LIMITS.max_employees + 1 }, (_, index) => ({ ...big.employees[0], employee_id: `E${index}` }))
    big.roster[0].breaks = Array.from({ length: LIMITS.max_breaks_per_roster_shift + 1 }, () => ({ name: 'rest', start_minute: 500 }))
    expect(limitProblems(big, LIMITS).map((item) => item.limit)).toEqual(['employees', 'roster.breaks'])
  })
})

describe('formFromRun', () => {
  it('loads a run as explicit text values and marks absent pay as not supplied', () => {
    const form = filledForm()
    expect(form.dataset_id).toBe(String(fixture.dataset_id))
    expect(form.horizon).toEqual({ start: '08:00', end: '10:00' })
    expect(form.employees[1].pay.regular_rate_per_hour).toEqual(emptyPayField())
    expect(form.employees[0].pay.regular_rate_per_hour).toEqual({ value: '100', not_supplied: false })
    expect(form.closing_policy).toBe('HARD_CUTOFF')
  })
})
