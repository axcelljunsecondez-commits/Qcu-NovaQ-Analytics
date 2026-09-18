export type Role = 'admin' | 'analyst'

export interface UserOut {
  id: number
  email: string
  role: Role
  active: boolean
  created_at: string
  email_verified?: boolean
  has_password?: boolean
  auth_methods?: string[]
}

export interface LoginResponse {
  user: UserOut
}

export interface MeResponse {
  user: UserOut | null
}

export interface SegmentInput {
  time: string
  lambda: number
  mu: number
  c: number
  variance?: number
  K?: number
  theta?: number
  server_cost?: number
  queue_structure?: string | null
  model_id?: string | null
}

/**
 * Alias for SegmentInput used in optimization and simulation pages.
 */
export type SegmentRow = SegmentInput

export interface OptimizationOut {
  feasibility_status?: string
  constraints_passed?: boolean
  violated_constraints?: string[]
  selected_model?: string
  metric_provenance?: string
  effective_constraints?: Record<string, unknown>
  effective_costs?: Record<string, unknown>
  explanation?: string
  time: string
  lambda_: number | null
  mu: number | null
  c_current: number | null
  c_optimal: number | null
  rho_current: number | null
  rho_optimal: number | null
  Wq_current: number | null
  Wq_optimal: number | null
  Lq_current: number | null
  Lq_optimal: number | null
  cost_current: number | null
  cost_optimal: number | null
  delta_cost: number | null
  delta_Wq: number | null
  delta_Lq: number | null
  delta_c: number | null
  delta_rho: number | null
  waiting_cost_current: number | null
  waiting_cost_optimal: number | null
  abandonment_cost_current: number | null
  abandonment_cost_optimal: number | null
  cost_per_server: number | null
  current_stable: boolean
  optimized_stable: boolean
  recommendation: string
  warning: string
}

export interface AnalysisOut {
  rho: number
  L: number | null
  Lq: number | null
  W: number | null
  Wq: number | null
  stable: boolean
  error: string | null
  blocking_probability?: number
  effective_lambda?: number
  K?: number
  metric_basis?: string
  approximation?: string
  rho_effective?: number
  theta?: number
  lambda_eff?: number
  abandonment_rate?: number
}

export interface DatasetValidation {
  ok: boolean
  message: string
  /** Present only for customer-event uploads (per period/queue observed means). */
  derived_statistics?: Record<string, unknown>[]
}

export interface DatasetOut {
  id: number
  analysis_id: number | null
  name: string
  source_filename: string
  source_format: string
  row_count: number
  validation: DatasetValidation
  created_at: string
  normalized: Record<string, unknown>[] | null
}

export type QueueStructure = 'shared_queue' | 'single_server' | 'separate_queues' | 'unknown'
export type CapacityMode = 'unlimited' | 'finite' | 'unknown'
export type AbandonmentMode = 'not_modeled' | 'modeled' | 'unknown'
export type SeparateQueueClosurePolicy = 'drain_existing'
export type EventPeriodBasis = 'per_date' | 'representative_day'

export interface AnalysisSegment {
  id: string | null
  start_time: string
  end_time: string
  active_queue_ids: string[] | null
}

export interface QueueBreak {
  queue_id: string
  scheduled_start_time: string
  duration_minutes: number
  break_name?: string | null
}

export interface SetupStaffRow {
  row: number
  queue_id: string
  shift_start: string
  shift_end: string
}

export interface SetupBreakRow {
  row: number
  queue_id: string
  break_name: string | null
  start: string
  minutes: number | string | null
  label: string | null
}

export interface SetupFieldChange {
  field: string
  saved: unknown
  derived: unknown
}

export type DatasetPreviewOut =
  | { mode: 'legacy' }
  | {
      mode: 'multi_sheet'
      derived_setup: QueueSetup | null
      saved_setup: QueueSetup
      diff: SetupFieldChange[]
      needs_confirmation: boolean
      staff: SetupStaffRow[]
      breaks: SetupBreakRow[]
      errors: string[]
    }

export interface QueueSetup {
  queue_structure: QueueStructure
  fixed_server_count: number | null
  staffing_varies_by_period: boolean
  capacity_mode: CapacityMode
  total_system_capacity: number | null
  abandonment_mode: AbandonmentMode
  patience_rate_per_hour: number | null
  segments: AnalysisSegment[]
  separate_queue_closure_policy: SeparateQueueClosurePolicy
  queue_ids: string[]
  breaks: QueueBreak[]
  event_period_basis?: EventPeriodBasis
}

export interface AnalysisProjectOut {
  id: number
  name: string
  service_type: string | null
  location_label: string | null
  queue_setup: QueueSetup
  setup_status: string
  archived_at: string | null
  created_at: string
  updated_at: string
}

export interface ModelExplanation {
  time: string
  selected_model: string
  queue_id?: string | null
  operational_facts: string[]
  measured_characteristics: string[]
  model_assumptions: string[]
  selection_reason: string
}

export interface AnalysisCurrentOut {
  analysis: AnalysisProjectOut
  dataset: DatasetOut
  selected_model: string | null
  rows: Record<string, unknown>[]
  kpis: Record<string, number | string | null>
  explanations: ModelExplanation[]
}

export interface AdminUserOut {
  id: number
  email: string
  role: Role
  active: boolean
  created_at: string
  email_verified?: boolean
  has_password?: boolean
  auth_methods?: string[]
}

export interface AuthConfig {
  google_sign_in_enabled: boolean
  google_client_id: string | null
}

export interface CreateUserRequest {
  email: string
  password: string
  role: Role
}

export interface UpdateUserRequest {
  role?: Role
  active?: boolean
}

export interface SimDesOut {
  requested_sim_hours?: number
  effective_sim_hours?: number
  measurement_hours?: number
  metric_provenance?: string
  selected_model?: string
  simulation_supported?: boolean
  time: string
  queue_id?: string | null
  lambda: number
  mu: number
  c: number
  rho_sim: number | null
  Lq_sim: number | null
  Wq_sim: number | null
  max_queue: number
  served: number
  dropped: number
  status: string
  error: string | null
  warmup_fraction?: number
  warmup_end?: number
  initial_queue_depth?: number
  final_Lq?: number
}

export type SimulationTraceEventType = 'arrival' | 'service_start' | 'service_end' | 'abandon'

export interface SimulationTraceEvent {
  t: number
  type: SimulationTraceEventType
  segment_id: string | number
  customer_id: number
  server_id: string | number | null
  queue_len_after: number
  queue_id?: string | number | null
  service_time_hours?: number
}

export interface SimulationTraceSegment {
  segment_id: string | number
  time: string
  lambda: number | null
  mu: number | null
  c: number
  selected_model: string | null
  simulation_supported: boolean
  error: string | null
  queue_structure: 'shared' | 'separate'
  initial_queue_depth: number
  final_queue_depth: number
}

export interface SimulationTrace {
  results?: SimDesOut[]
  trace: SimulationTraceEvent[]
  trace_hours: number
  total_hours: number
  event_count: number
  truncated: boolean
  abandonment_supported: boolean
  segments: SimulationTraceSegment[]
}

export interface SelectedDesLaneRow {
  time: string
  queue_id: string | null
  server_id: string | null
  lambda: number | null
  lambda_routed: number | null
  mu: number | null
  c: number
  arrivals: number | null
  served: number | null
  waiting: number | null
  in_service: number | null
  abandoned: number | null
  Wq_sim: number | null
  rho_sim: number | null
  max_queue: number | null
  active: boolean | null
  simulation_supported: boolean | null
  error: string | null
  metric_provenance: string | null
  customer_conservation: boolean | null
}

export interface SelectedDesPeriod {
  time: string
  active_queue_ids: string[]
  inactive_queue_ids: string[]
  evaluation_status: string | null
  conservation: boolean | null
  total_lambda: number | null
  total_cost: number | null
  server_cost: number | null
  waiting_cost: number | null
  results: SelectedDesLaneRow[]
  trace: SimulationTrace
}

export interface SelectedDesResult {
  provenance: string | null
  engine_version?: string | null
  execution?: string | null
  arrival_method?: string | null
  routing_policy?: string | null
  service_sampling_method?: string | null
  scenario_id: number | null
  analysis_id: number | null
  dataset_id: number | null
  target_utilization: number | null
  seed: number | null
  duration_hours: number | null
  max_events: number | null
  periods: SelectedDesPeriod[]
  overall_conservation: boolean | null
  overall_status: string | null
}

export interface SelectedMcResult {
  provenance: string | null
  scenario_id: number | null
  analysis_id: number | null
  dataset_id: number | null
  des_job_id: number | null
  results: SimMcOut[]
}

export interface SelectedValidationQueue {
  time: string
  queue_id: string | null
  selected_model: string | null
  mc_failure_rate: number | null
  mc_failure_rate_adequate: boolean | null
  failure_rate_cap: number | null
  validation_verdict: string | null
  rho_sim: number | null
  Wq_sim: number | null
  served: number | null
}

export interface SelectedValidationPeriod {
  time: string
  active_queue_ids: string[]
  status: string | null
  des_ok: boolean | null
  des_reason: string | null
  queues: SelectedValidationQueue[]
}

export interface SelectedValidationVerdict {
  status: string | null
  failed: Array<[string, string] | { time: string; queue_id: string }>
  inadequate: Array<[string, string] | { time: string; queue_id: string }>
  total: number | null
}

export interface SelectedValidationResult {
  provenance: string | null
  scenario_id: number | null
  analysis_id: number | null
  dataset_id: number | null
  des_job_id: number | null
  mc_job_id: number | null
  failure_rate_cap: number | null
  periods: SelectedValidationPeriod[]
  verdict: SelectedValidationVerdict
}

export interface SelectedDecisionFacts {
  selected_target: number | null
  validation_checks: number | null
  failed_checks: number | null
  inadequate_checks: number | null
  failure_rate_cap: number | null
  lane_delta: number | null
  periods: number | null
}

export interface SelectedDecision {
  provenance: string | null
  status: string | null
  headline: string | null
  recommendation: string | null
  rationale: string[]
  missing_evidence: string[]
  scenario_id: number | null
  scenario_name: string | null
  dataset_id: number | null
  facts: SelectedDecisionFacts | null
  failed_periods: string[]
  inadequate_periods: string[]
  evidence_ids: Record<string, number | null> | null
}

export interface SimMcOut {
  num_trials?: number
  failure_criterion?: string
  failure_threshold?: number
  failure_rate_cap?: number
  confidence_level?: number
  method?: string
  arrival_noise_fraction?: number
  service_noise_fraction?: number
  selected_model?: string
  simulation_supported?: boolean
  time: string
  queue_id?: string | null
  lambda: number
  mu: number
  c: number
  rho_mean: number
  rho_std: number
  rho_p95: number
  Lq_mean: number
  Wq_mean: number
  failure_rate: number
  failure_count: number
  status: string
  error: string | null
  ci_Wq_hw: number
  ci_Lq_hw: number
  adequate_samples: boolean
  failure_rate_ci_lower?: number
  failure_rate_ci_upper?: number
  failure_rate_ci_half_width?: number
  failure_rate_precision?: 'high' | 'moderate' | 'low' | null
  failure_rate_adequate?: boolean
}

export interface SeparateUncertainty {
  mean: number | null
  sd: number | null
  se: number | null
  ci_lower: number | null
  ci_upper: number | null
  n: number | null
}

export interface SeparateCandidate {
  active_lane_count: number
  status: string
  reason: string | null
  candidate_utilization: number | null
  total_cost: number | null
  mean_total_cost: number | null
  server_cost: number | null
  waiting_cost: number | null
  evaluation_method?: string | null
}

export interface SeparateOptimum {
  active_lane_count: number
  recommendation: string | null
  total_cost: number | null
  candidate_utilization: number | null
  estimated_optimal?: boolean | null
  cost_uncertainty?: SeparateUncertainty | null
}

export interface SeparatePeriod {
  time: string
  overall: string
  reason: string | null
  current_active_lanes: string[] | null
  optimal_active_lanes: number | null
  adjustment: number | null
  optimum: SeparateOptimum | null
  candidates: SeparateCandidate[]
  evaluation_method: string | null
  replication_seeds?: number[] | null
}

export interface SeparateDesConfig {
  replications: number
  base_seed: number
  duration_hours: number
  max_events: number
}

export interface SeparateSchedule {
  overall: string
  reason: string | null
  target_utilization: number
  evaluation_method: string | null
  periods: SeparatePeriod[]
  des: SeparateDesConfig
}

export interface SeparateCurrentPeriod {
  time: string
  active_lanes: string[] | null
  lambda_total: number | null
  wait_mean: number | null
  /** Observed (event-upload) wait in hours; null or absent when not recorded. */
  observed_wait?: number | null
  observed_flag?: boolean
  util_max: number | null
}

export interface SeparateCurrentComparison {
  dataset_id: number | null
  periods: SeparateCurrentPeriod[]
  wait_mean: number | null
  wait_basis: string | null
  wait_basis_kind?: 'analytical'
  observed_wait_available?: boolean
  observed_wait_flagged_any?: boolean
  observed_wait_ratio?: number
  observed_wait_min_gap_minutes?: number
  util_max: number | null
  waiting_cost: number | null
  waiting_cost_basis: string | null
  total_cost: number | null
  total_cost_reason: string | null
}

export interface SeparatePlanPeriod {
  time: string
  current_active_lanes: string[] | null
  optimal_active_lanes: number | null
  adjustment: number | null
  peak_util: number | null
  wait_mean: number | null
  wait_ci: [number | null, number | null] | null
  waiting_cost_mean: number | null
  total_cost_mean: number | null
  total_cost_ci: [number | null, number | null] | null
  status: string | null
}

export interface SeparatePlanTotals {
  lane_periods: number | null
  wait_mean: number | null
  peak_util: number | null
  waiting_cost_mean: number | null
  total_cost_mean: number | null
}

export interface SeparatePlanComparison {
  scenario_id: number
  name: string
  dataset_id: number | null
  target: number | null
  evaluation_method: string | null
  replications: number | null
  base_seed: number | null
  overall: string | null
  wait_basis_kind?: 'simulation' | null
  stale: boolean
  valid: boolean
  valid_reason: string | null
  periods: SeparatePlanPeriod[]
  totals: SeparatePlanTotals | null
}

export interface ObservedWaitPeriod {
  time: string
  /** Hours; the lambda-weighted analytical wait the pages display. */
  modeled_wait: number | null
  /** Hours; arrival-weighted mean of recorded waits, or null when unknown. */
  observed_wait: number | null
  flagged: boolean
}

export interface ObservedWaitSummary {
  analysis_id: number
  dataset_id: number
  available: boolean
  periods: ObservedWaitPeriod[]
  flagged_any: boolean
  day_modeled_wait: number | null
  day_observed_wait: number | null
  ratio: number
  min_gap_minutes: number
}

export interface SeparateComparison {
  analysis_id: number
  queue_structure: string
  current: SeparateCurrentComparison
  plans: SeparatePlanComparison[]
  selected_scenario_id: number | null
}

export interface SimValidateOut {
  selected_model?: string
  simulation_supported?: boolean
  validation_reason?: string | null
  time: string
  lambda: number
  mu: number
  c: number
  c_optimal: number | null
  rho_current: number
  rho_optimal: number
  Lq_current: number
  Lq_optimal: number
  Wq_current: number
  Wq_optimal: number
  sim_rho: number
  sim_Wq: number
  sim_max_queue: number
  sim_status: string
  mc_failure_rate: number
  mc_adequate: boolean
  mc_rho_mean: number
  mc_rho_p95: number
  mc_Wq_ci: string
  mc_failure_rate_ci_lower?: number
  mc_failure_rate_ci_upper?: number
  mc_failure_rate_ci_half_width?: number
  mc_failure_rate_precision?: 'high' | 'moderate' | 'low' | null
  mc_failure_rate_adequate?: boolean
}
