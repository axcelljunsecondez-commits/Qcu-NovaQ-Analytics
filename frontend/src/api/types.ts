export type Role = 'admin' | 'analyst'

export interface UserOut {
  id: number
  email: string
  role: Role
  active: boolean
  created_at: string
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
  time: string
  lambda_: number
  mu: number
  c_current: number
  c_optimal: number
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
  delta_c: number
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
  name: string
  source_filename: string
  source_format: string
  row_count: number
  validation: DatasetValidation
  created_at: string
  normalized: Record<string, unknown>[] | null
}

export interface ScenarioOut {
  id: number
  user_id: number
  dataset_id: number | null
  name: string
  settings: Record<string, unknown>
  results: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface AdminUserOut {
  id: number
  email: string
  role: Role
  active: boolean
  created_at: string
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
}

export interface SimValidateOut {
  time: string
  lambda: number
  mu: number
  c: number
  c_optimal: number
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
}
