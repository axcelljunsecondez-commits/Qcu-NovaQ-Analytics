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
}

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
  lambda_: number
  mu: number
  c_current: number
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

export interface QueueSetup {
  queue_structure: QueueStructure
  fixed_server_count: number | null
  staffing_varies_by_period: boolean
  capacity_mode: CapacityMode
  total_system_capacity: number | null
  abandonment_mode: AbandonmentMode
  patience_rate_per_hour: number | null
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
