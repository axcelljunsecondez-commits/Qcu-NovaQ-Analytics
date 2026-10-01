import type {
  NamedLimits,
  NamedRunProvenance,
  NamedWorkforceInput,
} from '../api/sharedNamed'

// Pure form-to-request mapping for the Named Shared Queue form (spec section 9.2 and 16.3). Clock
// times are typed as HH:MM and sent as whole minutes since midnight; 24:00 is minute 1440. Nothing
// is defaulted: an empty field is an error, and a pay value is sent as null only when the user marks
// it "not supplied", never as 0. Semantic rules stay with the backend domain.

export interface ClockWindowForm { start: string; end: string }
export interface SegmentForm extends ClockWindowForm { segment_id: string; servers: string }
export interface PayFieldForm { value: string; not_supplied: boolean }
export interface EmployeeForm {
  employee_id: string
  availability: ClockWindowForm[]
  pay: { regular_rate_per_hour: PayFieldForm; overtime_rate_per_hour: PayFieldForm; daily_regular_paid_minutes: PayFieldForm }
}
export interface BreakRequirementForm {
  name: string
  duration_minutes: string
  paid: boolean
  earliest_start_offset_minutes: string
  latest_start_offset_minutes: string
}
export interface BreakRuleForm {
  min_shift_minutes: string
  max_shift_minutes: string
  min_gap_minutes: string
  breaks: BreakRequirementForm[]
}
export interface ShiftRulesForm {
  earliest_start: string
  latest_end: string
  min_shift_minutes: string
  max_shift_minutes: string
  boundary_granularity_minutes: string
  max_shifts_per_employee: string
  min_minutes_between_shifts: string
}
export interface RosterBreakForm { name: string; start: string }
export interface RosterShiftForm extends ClockWindowForm { employee_id: string; breaks: RosterBreakForm[] }

export interface NamedForm {
  dataset_id: string
  horizon: ClockWindowForm
  required_staffing: SegmentForm[]
  register_count: string
  shift_rules: ShiftRulesForm
  break_rules: BreakRuleForm[]
  employees: EmployeeForm[]
  roster: RosterShiftForm[]
  closing_policy: string
}

export interface FieldError {
  field: string
  code: 'required' | 'clock' | 'whole' | 'number'
}

export type BuildResult =
  | { ok: true; body: NamedWorkforceInput }
  | { ok: false; errors: FieldError[] }

const CLOCK = /^(\d{1,2}):(\d{2})$/
const WHOLE = /^-?\d+$/

export function emptyForm(): NamedForm {
  return {
    dataset_id: '',
    horizon: { start: '', end: '' },
    required_staffing: [],
    register_count: '',
    shift_rules: {
      earliest_start: '', latest_end: '', min_shift_minutes: '', max_shift_minutes: '',
      boundary_granularity_minutes: '', max_shifts_per_employee: '', min_minutes_between_shifts: '',
    },
    break_rules: [],
    employees: [],
    roster: [],
    closing_policy: '',
  }
}

export function emptyPayField(): PayFieldForm {
  return { value: '', not_supplied: true }
}

/** Minutes since midnight for `HH:MM` (00:00 to 24:00), or null when the text is not such a time. */
export function clockToMinutes(text: string): number | null {
  const match = CLOCK.exec(text.trim())
  if (!match) return null
  const hours = Number(match[1])
  const minutes = Number(match[2])
  if (minutes > 59 || hours > 24 || (hours === 24 && minutes !== 0)) return null
  return hours * 60 + minutes
}

/** `HH:MM` for whole minutes since midnight; 1440 is written 24:00. */
export function minutesToClock(minute: number): string {
  const hours = Math.floor(minute / 60)
  const minutes = minute - hours * 60
  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}`
}

/** Clock text for a time in hours from the horizon start (playback times); fractional seconds kept to whole seconds. */
export function clockFromHours(horizonStartMinute: number, hours: number): string {
  const totalSeconds = Math.round((horizonStartMinute + hours * 60) * 60)
  const sign = totalSeconds < 0 ? '-' : ''
  const absolute = Math.abs(totalSeconds)
  const h = Math.floor(absolute / 3600)
  const m = Math.floor((absolute % 3600) / 60)
  const s = absolute % 60
  return `${sign}${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function whole(text: string): number | null {
  const trimmed = text.trim()
  return WHOLE.test(trimmed) ? Number(trimmed) : null
}

function finite(text: string): number | null {
  const trimmed = text.trim()
  if (trimmed === '') return null
  const value = Number(trimmed)
  return Number.isFinite(value) ? value : null
}

export function buildRequest(form: NamedForm, employeePolicy: Record<string, string>): BuildResult {
  const errors: FieldError[] = []
  const clock = (field: string, text: string): number => {
    const value = clockToMinutes(text)
    if (value === null) errors.push({ field, code: text.trim() === '' ? 'required' : 'clock' })
    return value ?? 0
  }
  const count = (field: string, text: string): number => {
    const value = whole(text)
    if (value === null) errors.push({ field, code: text.trim() === '' ? 'required' : 'whole' })
    return value ?? 0
  }
  const text = (field: string, value: string): string => {
    if (value.trim() === '') errors.push({ field, code: 'required' })
    return value.trim()
  }
  const pay = (field: string, item: PayFieldForm, isWhole: boolean): number | null => {
    if (item.not_supplied) return null
    const value = isWhole ? whole(item.value) : finite(item.value)
    if (value === null) errors.push({ field, code: item.value.trim() === '' ? 'required' : (isWhole ? 'whole' : 'number') })
    return value
  }

  const datasetId = count('dataset_id', form.dataset_id)
  const maxShifts = count('shift_rules.max_shifts_per_employee', form.shift_rules.max_shifts_per_employee)
  const body: NamedWorkforceInput = {
    dataset_id: datasetId,
    horizon: { start_minute: clock('horizon.start', form.horizon.start), end_minute: clock('horizon.end', form.horizon.end) },
    required_staffing: form.required_staffing.map((segment, index) => ({
      segment_id: text(`required_staffing.${index}.segment_id`, segment.segment_id),
      start_minute: clock(`required_staffing.${index}.start`, segment.start),
      end_minute: clock(`required_staffing.${index}.end`, segment.end),
      servers: count(`required_staffing.${index}.servers`, segment.servers),
    })),
    employees: form.employees.map((employee, index) => ({
      employee_id: text(`employees.${index}.employee_id`, employee.employee_id),
      availability: employee.availability.map((window, position) => ({
        start_minute: clock(`employees.${index}.availability.${position}.start`, window.start),
        end_minute: clock(`employees.${index}.availability.${position}.end`, window.end),
      })),
      pay: {
        regular_rate_per_hour: pay(`employees.${index}.pay.regular_rate_per_hour`, employee.pay.regular_rate_per_hour, false),
        overtime_rate_per_hour: pay(`employees.${index}.pay.overtime_rate_per_hour`, employee.pay.overtime_rate_per_hour, false),
        daily_regular_paid_minutes: pay(`employees.${index}.pay.daily_regular_paid_minutes`, employee.pay.daily_regular_paid_minutes, true),
      },
    })),
    rules: {
      shift_rules: {
        earliest_start_minute: clock('shift_rules.earliest_start', form.shift_rules.earliest_start),
        latest_end_minute: clock('shift_rules.latest_end', form.shift_rules.latest_end),
        min_shift_minutes: count('shift_rules.min_shift_minutes', form.shift_rules.min_shift_minutes),
        max_shift_minutes: count('shift_rules.max_shift_minutes', form.shift_rules.max_shift_minutes),
        boundary_granularity_minutes: count('shift_rules.boundary_granularity_minutes', form.shift_rules.boundary_granularity_minutes),
        max_shifts_per_employee: maxShifts,
        // The domain rule: a gap between shifts is required only when more than one shift is allowed.
        min_minutes_between_shifts: maxShifts > 1
          ? count('shift_rules.min_minutes_between_shifts', form.shift_rules.min_minutes_between_shifts)
          : null,
      },
      break_rules: form.break_rules.map((rule, index) => ({
        min_shift_minutes: count(`break_rules.${index}.min_shift_minutes`, rule.min_shift_minutes),
        max_shift_minutes: count(`break_rules.${index}.max_shift_minutes`, rule.max_shift_minutes),
        min_gap_minutes: count(`break_rules.${index}.min_gap_minutes`, rule.min_gap_minutes),
        breaks: rule.breaks.map((item, position) => ({
          name: text(`break_rules.${index}.breaks.${position}.name`, item.name),
          duration_minutes: count(`break_rules.${index}.breaks.${position}.duration_minutes`, item.duration_minutes),
          paid: item.paid,
          earliest_start_offset_minutes: count(`break_rules.${index}.breaks.${position}.earliest_start_offset_minutes`, item.earliest_start_offset_minutes),
          latest_start_offset_minutes: count(`break_rules.${index}.breaks.${position}.latest_start_offset_minutes`, item.latest_start_offset_minutes),
        })),
      })),
      register_count: count('register_count', form.register_count),
    },
    roster: form.roster.map((shift, index) => ({
      employee_id: text(`roster.${index}.employee_id`, shift.employee_id),
      start_minute: clock(`roster.${index}.start`, shift.start),
      end_minute: clock(`roster.${index}.end`, shift.end),
      breaks: shift.breaks.map((item, position) => ({
        name: text(`roster.${index}.breaks.${position}.name`, item.name),
        start_minute: clock(`roster.${index}.breaks.${position}.start`, item.start),
      })),
    })),
    closing_policy: text('closing_policy', form.closing_policy),
    employee_policy: { ...employeePolicy },
  }
  if (form.required_staffing.length === 0) errors.push({ field: 'required_staffing', code: 'required' })
  if (form.employees.length === 0) errors.push({ field: 'employees', code: 'required' })
  form.employees.forEach((employee, index) => {
    if (employee.availability.length === 0) errors.push({ field: `employees.${index}.availability`, code: 'required' })
  })
  return errors.length > 0 ? { ok: false, errors } : { ok: true, body }
}

/** Identity of the exact form content; any edit changes it. Run needs a runnable validation of this value. */
export function formFingerprint(form: NamedForm): string {
  return JSON.stringify(form)
}

export interface LimitProblem { limit: string; value: number; max: number }

/** The provisional limits from the contract, checked in the server's order before a request is sent. */
export function limitProblems(body: NamedWorkforceInput, limits: NamedLimits, replications?: number): LimitProblem[] {
  const counts: Array<[string, number, number]> = []
  if (replications !== undefined) counts.push(['replications', replications, limits.max_replications])
  counts.push(
    ['required_staffing', body.required_staffing.length, limits.max_required_staffing_segments],
    ['employees', body.employees.length, limits.max_employees],
    ['roster', body.roster.length, limits.max_roster_shifts],
    ['break_rules', body.rules.break_rules.length, limits.max_break_rules],
  )
  body.employees.forEach((item) => counts.push(['availability', item.availability.length, limits.max_availability_windows_per_employee]))
  body.rules.break_rules.forEach((rule) => counts.push(['break_rules.breaks', rule.breaks.length, limits.max_breaks_per_break_rule]))
  body.roster.forEach((shift) => counts.push(['roster.breaks', shift.breaks.length, limits.max_breaks_per_roster_shift]))
  return counts.filter(([, value, max]) => value > max).map(([limit, value, max]) => ({ limit, value, max }))
}

function payField(value: number | null): PayFieldForm {
  return value === null ? { value: '', not_supplied: true } : { value: String(value), not_supplied: false }
}

/** The form for a stored run's recorded inputs (OD-6: an explicit "load inputs from this run" only). */
export function formFromRun(datasetId: number, provenance: NamedRunProvenance): NamedForm {
  const inputs = provenance.inputs
  const shiftRules = inputs.rules.shift_rules
  return {
    dataset_id: String(datasetId),
    horizon: { start: minutesToClock(inputs.horizon.start_minute), end: minutesToClock(inputs.horizon.end_minute) },
    required_staffing: inputs.required_staffing.map((segment) => ({
      segment_id: segment.segment_id,
      start: minutesToClock(segment.start_minute),
      end: minutesToClock(segment.end_minute),
      servers: String(segment.servers),
    })),
    register_count: String(inputs.rules.register_count),
    shift_rules: {
      earliest_start: minutesToClock(shiftRules.earliest_start_minute),
      latest_end: minutesToClock(shiftRules.latest_end_minute),
      min_shift_minutes: String(shiftRules.min_shift_minutes),
      max_shift_minutes: String(shiftRules.max_shift_minutes),
      boundary_granularity_minutes: String(shiftRules.boundary_granularity_minutes),
      max_shifts_per_employee: String(shiftRules.max_shifts_per_employee),
      min_minutes_between_shifts: shiftRules.min_minutes_between_shifts === null ? '' : String(shiftRules.min_minutes_between_shifts),
    },
    break_rules: inputs.rules.break_rules.map((rule) => ({
      min_shift_minutes: String(rule.min_shift_minutes),
      max_shift_minutes: String(rule.max_shift_minutes),
      min_gap_minutes: String(rule.min_gap_minutes),
      breaks: rule.breaks.map((item) => ({
        name: item.name,
        duration_minutes: String(item.duration_minutes),
        paid: item.paid,
        earliest_start_offset_minutes: String(item.earliest_start_offset_minutes),
        latest_start_offset_minutes: String(item.latest_start_offset_minutes),
      })),
    })),
    employees: inputs.employees.map((employee) => ({
      employee_id: employee.employee_id,
      availability: employee.availability.map((window) => ({
        start: minutesToClock(window.start_minute),
        end: minutesToClock(window.end_minute),
      })),
      pay: {
        regular_rate_per_hour: payField(employee.pay.regular_rate_per_hour),
        overtime_rate_per_hour: payField(employee.pay.overtime_rate_per_hour),
        daily_regular_paid_minutes: payField(employee.pay.daily_regular_paid_minutes),
      },
    })),
    roster: inputs.roster.map((shift) => ({
      employee_id: shift.employee_id,
      start: minutesToClock(shift.start_minute),
      end: minutesToClock(shift.end_minute),
      breaks: shift.breaks.map((item) => ({ name: item.name, start: minutesToClock(item.start_minute) })),
    })),
    closing_policy: provenance.closing_policy,
  }
}
