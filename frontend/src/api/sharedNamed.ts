import { http } from '../lib/http'

// Named Shared Queue API, first slice (spec 2026-09-30-shared-queue-named-api-ui-first-slice.md, sections 4 and 10).
// Fields the components read are typed exactly as the backend produces them; pass-through blocks stay
// Record<string, unknown>. Times in the request are whole minutes since midnight; results are in hours.

export interface MinuteWindow {
  start_minute: number
  end_minute: number
}

export interface StaffingSegmentIn extends MinuteWindow {
  segment_id: string
  servers: number
}

export interface EmployeePayIn {
  regular_rate_per_hour: number | null
  overtime_rate_per_hour: number | null
  daily_regular_paid_minutes: number | null
}

export interface EmployeeIn {
  employee_id: string
  availability: MinuteWindow[]
  pay: EmployeePayIn
}

export interface ShiftRulesIn {
  earliest_start_minute: number
  latest_end_minute: number
  min_shift_minutes: number
  max_shift_minutes: number
  boundary_granularity_minutes: number
  max_shifts_per_employee: number
  min_minutes_between_shifts: number | null
}

export interface BreakRequirementIn {
  name: string
  duration_minutes: number
  paid: boolean
  earliest_start_offset_minutes: number
  latest_start_offset_minutes: number
}

export interface BreakRuleIn {
  min_shift_minutes: number
  max_shift_minutes: number
  min_gap_minutes: number
  breaks: BreakRequirementIn[]
}

export interface WorkforceRulesIn {
  shift_rules: ShiftRulesIn
  break_rules: BreakRuleIn[]
  register_count: number
}

export interface ScheduledBreakIn {
  name: string
  start_minute: number
}

export interface ScheduledShiftIn extends MinuteWindow {
  employee_id: string
  breaks: ScheduledBreakIn[]
}

export interface NamedWorkforceInput {
  dataset_id: number
  horizon: MinuteWindow
  required_staffing: StaffingSegmentIn[]
  employees: EmployeeIn[]
  rules: WorkforceRulesIn
  roster: ScheduledShiftIn[]
  closing_policy: string
  employee_policy: Record<string, string>
}

export interface NamedRunRequest extends NamedWorkforceInput {
  replications: number
  seed: number
}

export interface NamedLimits {
  max_replications: number
  max_required_staffing_segments: number
  max_employees: number
  max_roster_shifts: number
  max_availability_windows_per_employee: number
  max_break_rules: number
  max_breaks_per_break_rule: number
  max_breaks_per_roster_shift: number
  max_expected_customers_per_run: number
  result_max_bytes: number
  status: string
}

export interface NamedContract {
  eligible: boolean
  ineligible_reasons: string[]
  closing_policies: string[]
  employee_policy: Record<string, { approved: string; meaning: string }>
  limits: NamedLimits
  seed: { min: number; max: number }
  versions: Record<string, string>
  verdict: null
  verdict_reason: string
  model_scope: string
}

export interface DemandPeriodOut {
  period_id: string
  start_minute: number
  end_minute: number
  arrival_rate_per_hour: number
  service_rate_per_hour: number
}

export interface RosterViolation {
  code: string
  employee_id: string | null
  shift_index: number | null
  message: string
}

export interface RosterMissing {
  employee_id: string | null
  field: string
  consequence: string
}

export interface CoverageSegment {
  segment_id: string
  start_minute: number
  end_minute: number
  required_servers: number
  min_active_servers: number
  max_active_servers: number
  shortfall_server_minutes: number
  surplus_server_minutes: number
}

export interface RosterReport {
  status: string
  violations: RosterViolation[]
  missing: RosterMissing[]
  totals: { minutes: Record<string, number | null>; hours: Record<string, number | null> } | null
  totals_withheld_reason: string | null
  register_check: { register_count: number; max_active_servers: number; exceeded: boolean } | null
  coverage: {
    segments: CoverageSegment[]
    shortfall_server_minutes: number
    surplus_server_minutes: number
    fully_covered: boolean
    note: string
  } | null
  [key: string]: unknown
}

export type NamedStage = 'demand' | 'workforce' | 'engine'

export interface NamedValidateOut {
  runnable: boolean
  stage_failed: NamedStage | null
  problems: string[]
  demand: { dataset_id: number; demand_periods: DemandPeriodOut[]; expected_customers_per_replication: number } | null
  roster_report: RosterReport | null
  limits: NamedLimits
}

export interface NamedReplicationRow {
  replication_index: number
  spawn_key: number[]
  customer_inputs_sha256: string
  customer_conservation: boolean
  customers: {
    arrivals: number
    served: number
    unserved: number
    unserved_hard_cutoff: number
    unserved_no_eligible_employee: number
    served_after_closing: number
  }
  waiting: {
    wait_sum_hours: number
    mean_wait_hours: number | null
    customer_hours_in_horizon: number
    customer_hours_after_closing: number
    customer_hours_total: number
    max_queue_in_horizon: number
  }
  closing: {
    waiting_at_close: number
    in_service_at_close: number
    drain_crew_size: number
    run_after_closing_hours: number
  }
  staffing: Record<string, unknown>
  employees: {
    shifts_with_overrun: number
    breaks_unfulfilled: number
    [key: string]: unknown
  }
}

export interface MetricSummary {
  mean: number | null
  sd: number | null
  se: number | null
  ci_lower: number | null
  ci_upper: number | null
  ci_half_width: number | null
  min: number | null
  max: number | null
  n: number
  n_undefined: number
  definition: string
}

export interface OutcomeCount {
  replications: number
  denominator_replications: number
}

export interface NamedRunSummary {
  replications: number
  customers: {
    totals: NamedReplicationRow['customers']
    conserved_in_every_replication: boolean
    [key: string]: unknown
  }
  waiting_time: {
    mean_of_replication_means_hours: MetricSummary
    customer_weighted_mean_hours: {
      value: number | null
      numerator_wait_hours: number
      denominator_served_customers: number
      definition: string
      interval: string
    }
  }
  outcome_counts: { definition: string } & Record<string, OutcomeCount | string>
  verdict: null
  verdict_reason: string
  [key: string]: unknown
}

export interface NamedRunProvenance {
  method_version: string
  named_engine_version: string
  state_machine_version: string
  arrival_engine_version: string
  replications: number
  seed: number | null
  root_entropy: number
  seed_scheme: string
  runtime: Record<string, string>
  closing_policy: string
  employee_policy: Record<string, string>
  inputs: {
    horizon: MinuteWindow
    demand_periods: DemandPeriodOut[]
    required_staffing: StaffingSegmentIn[]
    employees: EmployeeIn[]
    rules: WorkforceRulesIn
    roster: ScheduledShiftIn[]
  }
  inputs_sha256: string
  [key: string]: unknown
}

export interface NamedRunResult {
  replications: NamedReplicationRow[]
  summary: NamedRunSummary
  provenance: NamedRunProvenance
}

export interface NamedRunEvidence {
  id: number
  kind: string
  status: string
  params: Record<string, unknown> & { dataset_id: number; dataset_generation: string; setup_hash: string }
  result: NamedRunResult
  created_at: string
  finished_at: string | null
}

export interface NamedRunListItem {
  id: number
  created_at: string
  dataset_id: number
  replications: number
  seed: number
  root_entropy: number
  closing_policy: string
  inputs_sha256: string
  method_version: string
  named_engine_version: string
  runtime: Record<string, string> | null
  setup_matches_current: boolean
}

export type PlaybackPeriod = 'before_opening' | 'operating_horizon' | 'closing' | 'after_closing'

export interface NamedPlaybackEvent {
  seq: number
  source: 'customer_trace' | 'employee_transition'
  source_index: number
  t: number
  period: PlaybackPeriod
  type: string
  stage: string | null
  customer_id: number | null
  employee_id: string | null
  register_id: number | null
  employee_state_before: string | null
  employee_state_after: string | null
  register_before: number | null
  register_after: number | null
  queue_len_before: number
  queue_len_after: number
  accepting_capacity_after: number
  busy_employees_after: number
  register_occupancy_after: number
  waiting_for_register_after: number
  unserved_reason: string | null
  closing_policy: string | null
  drain_crew: string[] | null
  break: Record<string, unknown> | null
}

export interface EmployeeInterval {
  start: number
  end: number
  state: string
  register_id: number | null
}

export interface NamedPlayback {
  events: NamedPlaybackEvent[]
  instants: Array<Record<string, unknown>>
  customers: Array<Record<string, unknown>>
  employees: Record<string, EmployeeInterval[]>
  shifts: Array<Record<string, unknown>>
  breaks: Array<Record<string, unknown>>
  not_represented_by_events: {
    definition: string
    unfulfilled_breaks: Array<Record<string, unknown>>
    shifts_not_activated: Array<Record<string, unknown>>
  }
  closing: { policy: string; closing_hours: number; [key: string]: unknown }
  outside_horizon: Record<string, unknown>
  summary: Record<string, unknown>
  validation: { valid: boolean; [key: string]: unknown }
  reconciliation: Array<Record<string, unknown>>
  event_vocabulary: {
    customer_trace: Record<string, string>
    employee_transitions: Array<{ stage: string; event: string; from_state: string; to_state: string; meaning: string }>
    [key: string]: unknown
  }
  unsupported: Record<string, string>
  provenance: Record<string, unknown>
  replication: Record<string, unknown>
}

export interface AttributionClosing {
  after_closing_hours: number
  past_scheduled_end_hours: number
  after_closing_and_past_scheduled_end_hours: number
  after_closing_only_hours: number
  past_scheduled_end_only_hours: number
  neither_hours: number
  after_closing_or_past_scheduled_end_hours: number
}

export interface AttributionShift {
  employee_id: string
  shift_index: number
  activated: boolean
  not_activated_reason: string | null
  scheduled_start_hours: number
  scheduled_end_hours: number
  scheduled_duration_hours: number
  actual_start_hours: number | null
  release_hours: number | null
  activation_delay_hours: number | null
  overrun_hours: number | null
  on_duty_hours: number
  hours_by_state: Record<string, number>
  register_wait_hours: number
  closing_attribution: AttributionClosing
  [key: string]: unknown
}

export interface AttributionEmployee {
  employee_id: string
  shift_count: number
  activated_shift_count: number
  on_duty_hours: number
  overrun_hours: number
  register_wait_hours: number
  activation_delay_hours: number
  hours_by_state: Record<string, number>
  closing_attribution: AttributionClosing
  [key: string]: unknown
}

export interface NamedAttribution {
  shifts: AttributionShift[]
  employees: AttributionEmployee[]
  reconciliation: Array<Record<string, unknown>>
  definitions: Record<string, string>
  checks: Record<string, string>
  undetermined: string[]
  provenance: Record<string, unknown>
}

export interface NamedReplicationOut {
  replication_index: number
  playback: NamedPlayback
  attribution: NamedAttribution
  regeneration: {
    runtime_matches_recorded: boolean
    runtime_recorded: Record<string, string>
    runtime_current: Record<string, string> | null
    basis: string
  }
}

const base = (analysisId: number) => `/analyses/${analysisId}/shared-named`

export async function getNamedContract(analysisId: number): Promise<NamedContract> {
  const { data } = await http.get<NamedContract>(`${base(analysisId)}/contract`)
  return data
}

export async function validateNamedInputs(analysisId: number, body: NamedWorkforceInput): Promise<NamedValidateOut> {
  const { data } = await http.post<NamedValidateOut>(`${base(analysisId)}/validate`, body)
  return data
}

export async function createNamedRun(analysisId: number, body: NamedRunRequest): Promise<{ evidence: NamedRunEvidence }> {
  const { data } = await http.post<{ evidence: NamedRunEvidence }>(`${base(analysisId)}/runs`, body)
  return data
}

export async function listNamedRuns(analysisId: number): Promise<{ runs: NamedRunListItem[] }> {
  const { data } = await http.get<{ runs: NamedRunListItem[] }>(`${base(analysisId)}/runs`)
  return data
}

export async function getNamedRun(
  analysisId: number,
  runId: number,
): Promise<{ evidence: NamedRunEvidence; setup_matches_current: boolean }> {
  const { data } = await http.get<{ evidence: NamedRunEvidence; setup_matches_current: boolean }>(
    `${base(analysisId)}/runs/${runId}`,
  )
  return data
}

export async function getNamedReplication(
  analysisId: number,
  runId: number,
  replicationIndex: number,
): Promise<NamedReplicationOut> {
  const { data } = await http.get<NamedReplicationOut>(
    `${base(analysisId)}/runs/${runId}/replications/${replicationIndex}`,
  )
  return data
}

export interface NamedApiError {
  status: number | null
  code: string | null
  detail: unknown
}

/** The status and structured `detail.code` of a failed named-API request; never invents a code. */
export function namedApiError(error: unknown): NamedApiError {
  const response = (error as { response?: { status?: number; data?: { detail?: unknown } } }).response
  const detail = response?.data?.detail
  const code = detail && typeof detail === 'object' && !Array.isArray(detail)
    && typeof (detail as { code?: unknown }).code === 'string'
    ? (detail as { code: string }).code
    : null
  return { status: typeof response?.status === 'number' ? response.status : null, code, detail }
}
